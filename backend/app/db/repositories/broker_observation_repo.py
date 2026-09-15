"""Persistent broker observation projection, rebuild and internal read service.

The projection is rebuilt deterministically from validated ledger evidence.
Rebuild captures its ledger boundary as a single evidence set, records the
processed-through event and an evidence digest, and never mixes events appended
while a rebuild is running.  A failed rebuild keeps the previous successful
snapshot and records the failure without losing it to the rollback.

Rows carry an explicit ``account_scope_state``.  While the source account scope
is unverified, each observation is stored individually and no economic merge,
repeat or content conflict is declared.  This is an internal read service: no
user-facing API, no journal conversion and no portfolio PnL participation.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

from app.core.paths import get_sqlite_path
from app.db.broker_observation_schema import initialize_broker_observation_schema
from app.db.repositories.evidence_ledger_repo import EvidenceLedgerRepository
from app.services.broker_observations import (
    ACCOUNT_METADATA_BASIS,
    ACCOUNT_SCOPE_BASIS,
    PROJECTION_ID,
    BrokerObservationError,
    build_broker_observation_snapshot,
)


class BrokerObservationProjectionError(Exception):
    """Raised when the broker observation projection cannot be rebuilt safely."""


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


_COLUMNS = (
    "account_id", "account_scope_state", "account_scope_reason",
    "account_environment", "account_context", "venue", "source_exchange_id",
    "market_type", "record_type", "external_identity", "related_order_id",
    "symbol", "side", "status", "occurred_at_utc", "semantics_json",
    "semantics_sha256", "source_event_id", "source_event_hash",
    "received_at_utc", "lineage_json", "projected_at_utc",
)
_BUSINESS_COLUMNS = tuple(column for column in _COLUMNS if column != "projected_at_utc")
_JSON_COLUMNS = ("semantics_json", "lineage_json")


class BrokerObservationProjectionRepository:
    """Build, rebuild and read the broker observation projection."""

    _WRITE_BATCH_SIZE = 500

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = str(db_path or get_sqlite_path())
        self._ensure_schema()
        self._ledger_repo = EvidenceLedgerRepository(self.db_path)

    def _connect(self, *, write: bool = False) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA synchronous=FULL" if write else "PRAGMA synchronous=NORMAL")
        return conn

    def _ensure_schema(self) -> None:
        conn = self._connect(write=False)
        try:
            initialize_broker_observation_schema(conn)
        finally:
            conn.close()

    def _scan_events(
        self,
        resource_check: Optional[Callable[[str], None]],
    ) -> List[Dict[str, Any]]:
        """Materialize one consistent ledger read snapshot in chain order."""

        return list(self._ledger_repo.export_events(resource_check=resource_check))

    @staticmethod
    def _evidence_digest(events: Sequence[Dict[str, Any]]) -> str:
        hasher = hashlib.sha256()
        for event in events:
            hasher.update(
                f"{event.get('event_id', '')}\n{event.get('event_hash', '')}\n".encode("utf-8")
            )
        return hasher.hexdigest()

    @staticmethod
    def _boundary(events: Sequence[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not events:
            return None
        last = events[-1]
        return {
            "event_id": str(last.get("event_id") or ""),
            "event_hash": str(last.get("event_hash") or ""),
            "received_at_utc": str(last.get("received_at_utc") or ""),
            "account_id": str(last.get("account_id") or ""),
            "chain_date_utc": str(last.get("chain_date_utc") or ""),
            "chain_sequence": int(last.get("chain_sequence") or 0),
        }

    def rebuild(
        self,
        *,
        dry_run: bool = True,
        resource_check: Optional[Callable[[str], None]] = None,
    ) -> Dict[str, Any]:
        """Verify the ledger and rebuild the broker observation snapshot.

        A malformed broker lifecycle event fails closed before the projection
        table is touched.  The report includes the captured boundary, the
        evidence digest, the counters and the deterministic snapshot hash.
        """

        if resource_check is not None and not callable(resource_check):
            raise TypeError("resource_check must be callable")

        def check(phase: str) -> None:
            if resource_check is not None:
                resource_check(phase)

        attempted_at = _now_utc()
        try:
            events = self._scan_events(resource_check)
            integrity = self._ledger_repo.verify_chain(account_id=None)
            if not integrity["valid"]:
                raise BrokerObservationProjectionError(
                    "Cannot rebuild broker observations from invalid evidence ledger: "
                    + "; ".join(integrity["errors"][:5])
                )
            check("after_event_snapshot")
            try:
                snapshot = build_broker_observation_snapshot(events)
            except BrokerObservationError as exc:
                raise BrokerObservationProjectionError(str(exc)) from exc
            evidence_sha256 = self._evidence_digest(events)
            boundary = self._boundary(events)
            report = {
                "projection_id": PROJECTION_ID,
                "dry_run": dry_run,
                "records_written": len(snapshot["records"]),
                "counters": snapshot["counters"],
                "unresolved": snapshot["unresolved"],
                "snapshot_sha256": snapshot["snapshot_sha256"],
                "evidence_sha256": evidence_sha256,
                "scanned_event_count": len(events),
                "processed_through": boundary,
            }
            if dry_run:
                return report

            self._write_snapshot(
                records=snapshot["records"],
                counters=snapshot["counters"],
                snapshot_sha256=snapshot["snapshot_sha256"],
                evidence_sha256=evidence_sha256,
                scanned_event_count=len(events),
                boundary=boundary,
                resource_check=check,
            )
            return report
        except Exception as exc:
            if not dry_run:
                self._record_failure(str(exc), attempted_at)
            raise

    def _write_snapshot(
        self,
        *,
        records: Iterable[Dict[str, Any]],
        counters: Dict[str, Any],
        snapshot_sha256: str,
        evidence_sha256: str,
        scanned_event_count: int,
        boundary: Optional[Dict[str, Any]],
        resource_check: Callable[[str], None],
    ) -> None:
        conn = self._connect(write=True)
        try:
            conn.execute("BEGIN IMMEDIATE")
            resource_check("before_projection_delete")
            conn.execute("DELETE FROM broker_observation_log")
            resource_check("after_projection_delete")
            projected_at = _now_utc()
            batch: List[Dict[str, Any]] = []

            def flush() -> None:
                if not batch:
                    return
                resource_check("before_projection_batch")
                conn.executemany(
                    f"""INSERT INTO broker_observation_log ({', '.join(_COLUMNS)})
                        VALUES ({', '.join('?' for _ in _COLUMNS)})""",
                    [tuple(record[column] for column in _COLUMNS) for record in batch],
                )
                batch.clear()
                resource_check("after_projection_batch")

            for record in records:
                batch.append(_record_to_row(record, projected_at))
                if len(batch) >= self._WRITE_BATCH_SIZE:
                    flush()
            flush()
            resource_check("before_projection_commit")
            now = _now_utc()
            conn.execute(
                """
                INSERT INTO broker_projection_state (
                    projection_id, snapshot_sha256, evidence_sha256, scanned_event_count,
                    processed_through_event_id, processed_through_event_hash,
                    processed_through_received_at_utc, counters_json,
                    last_success_at_utc, last_attempt_at_utc, last_attempt_status,
                    last_failure_reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'SUCCESS', NULL)
                ON CONFLICT(projection_id) DO UPDATE SET
                    snapshot_sha256 = excluded.snapshot_sha256,
                    evidence_sha256 = excluded.evidence_sha256,
                    scanned_event_count = excluded.scanned_event_count,
                    processed_through_event_id = excluded.processed_through_event_id,
                    processed_through_event_hash = excluded.processed_through_event_hash,
                    processed_through_received_at_utc = excluded.processed_through_received_at_utc,
                    counters_json = excluded.counters_json,
                    last_success_at_utc = excluded.last_success_at_utc,
                    last_attempt_at_utc = excluded.last_attempt_at_utc,
                    last_attempt_status = 'SUCCESS',
                    last_failure_reason = NULL
                """,
                (
                    PROJECTION_ID,
                    snapshot_sha256,
                    evidence_sha256,
                    scanned_event_count,
                    boundary["event_id"] if boundary else None,
                    boundary["event_hash"] if boundary else None,
                    boundary["received_at_utc"] if boundary else None,
                    json.dumps(counters, sort_keys=True, separators=(",", ":")),
                    now,
                    now,
                ),
            )
            conn.commit()
        except Exception:
            if conn.in_transaction:
                conn.rollback()
            raise
        finally:
            conn.close()

    def _record_failure(self, reason: str, attempted_at: str) -> None:
        """Record the failed attempt in a separate transaction.

        The failure must survive the snapshot rollback, so it is written after
        the previous transaction has been rolled back and the previous
        successful snapshot metadata is left untouched.
        """

        try:
            conn = self._connect(write=True)
            try:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute(
                    """
                    INSERT INTO broker_projection_state (
                        projection_id, last_attempt_at_utc, last_attempt_status,
                        last_failure_reason
                    ) VALUES (?, ?, 'FAILED', ?)
                    ON CONFLICT(projection_id) DO UPDATE SET
                        last_attempt_at_utc = excluded.last_attempt_at_utc,
                        last_attempt_status = 'FAILED',
                        last_failure_reason = excluded.last_failure_reason
                    """,
                    (PROJECTION_ID, attempted_at, reason[:500]),
                )
                conn.commit()
            except Exception:
                if conn.in_transaction:
                    conn.rollback()
                raise
            finally:
                conn.close()
        except Exception:
            # Recording the failure must never mask the original rebuild error.
            pass

    def coverage(self) -> Dict[str, Any]:
        """Report local ledger coverage and freshness of the last snapshot.

        Freshness describes the local evidence scope, not the broker's live
        account state.  A stale or never-built snapshot is never presented as
        current.
        """

        events = self._scan_events(None)
        current_evidence_sha256 = self._evidence_digest(events)
        conn = self._connect(write=False)
        try:
            row = conn.execute(
                "SELECT * FROM broker_projection_state WHERE projection_id = ?",
                (PROJECTION_ID,),
            ).fetchone()
            projected_records = int(conn.execute(
                "SELECT COUNT(*) FROM broker_observation_log"
            ).fetchone()[0])
        finally:
            conn.close()

        if row is None:
            return {
                "projection_id": PROJECTION_ID,
                "state": "NEVER_BUILT",
                "account_scope_basis": ACCOUNT_SCOPE_BASIS,
                "account_metadata_basis": ACCOUNT_METADATA_BASIS,
                "newer_events_pending": False,
                "last_attempt_status": None,
                "last_failure_reason": None,
                "last_attempt_at_utc": None,
                "last_success_at_utc": None,
                "last_success_snapshot_sha256": None,
                "last_success_evidence_sha256": None,
                "processed_through": None,
                "counters": None,
                "scanned_event_count": None,
                "projected_records": projected_records,
                "current_evidence_sha256": current_evidence_sha256,
                "current_scanned_event_count": len(events),
            }

        if row["last_success_at_utc"] is None:
            state = "NEVER_BUILT"
        elif (
            row["evidence_sha256"] == current_evidence_sha256
            and int(row["scanned_event_count"] or 0) == len(events)
        ):
            state = "CURRENT"
        else:
            state = "STALE"
        processed_through = None
        if row["processed_through_event_id"] is not None:
            processed_through = {
                "event_id": row["processed_through_event_id"],
                "event_hash": row["processed_through_event_hash"],
                "received_at_utc": row["processed_through_received_at_utc"],
            }
        return {
            "projection_id": PROJECTION_ID,
            "state": state,
            "account_scope_basis": ACCOUNT_SCOPE_BASIS,
            "account_metadata_basis": ACCOUNT_METADATA_BASIS,
            "newer_events_pending": state == "STALE",
            "last_attempt_status": row["last_attempt_status"],
            "last_failure_reason": row["last_failure_reason"],
            "last_attempt_at_utc": row["last_attempt_at_utc"],
            "last_success_at_utc": row["last_success_at_utc"],
            "last_success_snapshot_sha256": row["snapshot_sha256"],
            "last_success_evidence_sha256": row["evidence_sha256"],
            "processed_through": processed_through,
            "counters": json.loads(row["counters_json"]) if row["counters_json"] else None,
            "scanned_event_count": row["scanned_event_count"],
            "projected_records": projected_records,
            "current_evidence_sha256": current_evidence_sha256,
            "current_scanned_event_count": len(events),
        }

    def list_projections(self) -> List[Dict[str, Any]]:
        """Return the stored business rows without operational metadata."""

        conn = self._connect(write=False)
        try:
            rows = conn.execute(
                f"SELECT {', '.join(_BUSINESS_COLUMNS)} FROM broker_observation_log "
                "ORDER BY account_id, venue, record_type, external_identity, source_event_id"
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def list_observations(
        self,
        *,
        account_id: Optional[str] = None,
        venue: Optional[str] = None,
        source_exchange_id: Optional[str] = None,
        market_type: Optional[str] = None,
        record_type: Optional[str] = None,
        external_identity: Optional[str] = None,
        account_scope_state: Optional[str] = None,
        symbol: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List projected observations with parsed payload columns."""

        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1 or limit > 1000:
            raise ValueError("limit must be an integer between 1 and 1000")
        if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
            raise ValueError("offset must be a non-negative integer")
        query = "SELECT * FROM broker_observation_log WHERE 1 = 1"
        params: List[Any] = []
        for column, value in (
            ("account_id", account_id),
            ("venue", venue),
            ("source_exchange_id", source_exchange_id),
            ("market_type", market_type),
            ("record_type", record_type),
            ("external_identity", external_identity),
            ("account_scope_state", account_scope_state),
        ):
            if value is not None:
                query += f" AND {column} = ?"
                params.append(str(value))
        if symbol is not None:
            query += " AND symbol = ?"
            params.append(str(symbol).upper())
        query += (
            " ORDER BY occurred_at_utc, account_id, venue, record_type,"
            " external_identity, source_event_id LIMIT ? OFFSET ?"
        )
        params.extend([limit, offset])

        conn = self._connect(write=False)
        try:
            return [self._row_to_observation(row) for row in conn.execute(query, params)]
        finally:
            conn.close()

    def get_observation(self, *, source_event_id: str) -> Optional[Dict[str, Any]]:
        """Read one observation by its source ledger event."""

        conn = self._connect(write=False)
        try:
            row = conn.execute(
                "SELECT * FROM broker_observation_log WHERE source_event_id = ?",
                (source_event_id,),
            ).fetchone()
            return self._row_to_observation(row) if row is not None else None
        finally:
            conn.close()

    @staticmethod
    def _row_to_observation(row: sqlite3.Row) -> Dict[str, Any]:
        result = dict(row)
        for column in _JSON_COLUMNS:
            result[column[: -len("_json")]] = json.loads(result.pop(column))
        return result


def _record_to_row(record: Dict[str, Any], projected_at: str) -> Dict[str, Any]:
    row = {
        column: record.get(column)
        for column in _COLUMNS
        if column not in {*_JSON_COLUMNS, "projected_at_utc"}
    }
    row["semantics_json"] = json.dumps(
        record["semantics"], sort_keys=True, separators=(",", ":")
    )
    row["lineage_json"] = json.dumps(
        record["lineage"], sort_keys=True, separators=(",", ":")
    )
    row["projected_at_utc"] = projected_at
    return row
