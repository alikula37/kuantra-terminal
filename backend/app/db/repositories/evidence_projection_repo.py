"""Rebuildable typed trade projection sourced from canonical evidence events."""

from __future__ import annotations

import json
import math
import sqlite3
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from app.core.paths import get_sqlite_path
from app.db.projection_schema import initialize_trade_projection_schema
from app.db.repositories.evidence_ledger_repo import (
    EvidenceLedgerRepository,
    canonical_json,
)


PROJECTABLE_EVENT_TYPES = frozenset(
    {"LegacyTradeImported", "IntentRecorded", "FillRecorded", "TradeCorrected"}
)
_SIDES = frozenset({"BUY", "SELL", "LONG", "SHORT"})
_STATUSES = frozenset({"OPEN", "CLOSED", "CANCELED"})


class EvidenceProjectionError(Exception):
    """Raised when the canonical ledger cannot produce a safe projection."""


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _required_text(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise EvidenceProjectionError(f"projection field {field} is required")
    return text


def _finite_number(value: Any, field: str, *, default: Optional[float] = None) -> Optional[float]:
    if value is None and default is not None:
        return default
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise EvidenceProjectionError(f"projection field {field} must be numeric") from exc
    if not math.isfinite(number):
        raise EvidenceProjectionError(f"projection field {field} must be finite")
    return number


class EvidenceTradeProjectionRepository:
    """Build and query a disposable projection without mutating the ledger."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = str(db_path or get_sqlite_path())
        self._ensure_schema()
        # Reuse the append-only verifier so repeated rebuilds and read adapters
        # share one ledger-only integrity cache. Projection commits do not
        # invalidate that cache, and the verifier retains no SQLite connection.
        self._ledger_repo = EvidenceLedgerRepository(self.db_path)

    @property
    def ledger_repo(self) -> EvidenceLedgerRepository:
        """Expose the shared canonical verifier to read-side adapters."""

        return self._ledger_repo

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
            initialize_trade_projection_schema(conn)
        finally:
            conn.close()

    @staticmethod
    def _projection_from_event(event: Dict[str, Any], projected_at: str) -> Dict[str, Any]:
        try:
            payload = json.loads(event["normalized_payload_json"])
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise EvidenceProjectionError(
                f"event {event.get('event_id', '<unknown>')} has invalid normalized payload"
            ) from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("trade"), dict):
            raise EvidenceProjectionError(
                f"event {event.get('event_id', '<unknown>')} has no trade snapshot"
            )

        raw_trade = dict(payload["trade"])
        trade_id = _required_text(raw_trade.get("id") or payload.get("source_id"), "trade.id")
        symbol = _required_text(raw_trade.get("symbol"), "trade.symbol").upper()
        side = _required_text(raw_trade.get("side"), "trade.side").upper()
        if side not in _SIDES:
            raise EvidenceProjectionError(f"trade {trade_id} has unsupported side {side!r}")
        status = _required_text(raw_trade.get("status"), "trade.status").upper()
        if status not in _STATUSES:
            raise EvidenceProjectionError(f"trade {trade_id} has unsupported status {status!r}")

        entry_price = _finite_number(raw_trade.get("entry_price"), "trade.entry_price")
        qty = _finite_number(raw_trade.get("qty"), "trade.qty")
        if entry_price is None or entry_price <= 0:
            raise EvidenceProjectionError(f"trade {trade_id} entry_price must be positive")
        if qty is None or qty <= 0:
            raise EvidenceProjectionError(f"trade {trade_id} qty must be positive")
        entry_time = _required_text(raw_trade.get("entry_time"), "trade.entry_time")

        normalized_trade = dict(raw_trade)
        normalized_trade.update(
            {
                "id": trade_id,
                "symbol": symbol,
                "side": side,
                "entry_price": entry_price,
                "exit_price": _finite_number(raw_trade.get("exit_price"), "trade.exit_price")
                if raw_trade.get("exit_price") is not None else None,
                "qty": qty,
                "stop_loss": _finite_number(raw_trade.get("stop_loss"), "trade.stop_loss")
                if raw_trade.get("stop_loss") is not None else None,
                "take_profit": _finite_number(raw_trade.get("take_profit"), "trade.take_profit")
                if raw_trade.get("take_profit") is not None else None,
                "entry_time": entry_time,
                "exit_time": raw_trade.get("exit_time"),
                "status": status,
                "pnl": _finite_number(raw_trade.get("pnl"), "trade.pnl", default=0.0),
                "r_multiple": _finite_number(raw_trade.get("r_multiple"), "trade.r_multiple")
                if raw_trade.get("r_multiple") is not None else None,
                "commission": _finite_number(raw_trade.get("commission"), "trade.commission", default=0.0),
                "notes": str(raw_trade.get("notes") or ""),
            }
        )
        snapshot_json = canonical_json(normalized_trade)
        return {
            "account_id": _required_text(event.get("account_id"), "event.account_id"),
            "venue": _required_text(event.get("venue"), "event.venue"),
            "trade_id": trade_id,
            "symbol": symbol,
            "side": side,
            "entry_price": entry_price,
            "exit_price": normalized_trade["exit_price"],
            "qty": qty,
            "stop_loss": normalized_trade["stop_loss"],
            "take_profit": normalized_trade["take_profit"],
            "entry_time": entry_time,
            "exit_time": normalized_trade["exit_time"],
            "status": status,
            "pnl": normalized_trade["pnl"],
            "r_multiple": normalized_trade["r_multiple"],
            "commission": normalized_trade["commission"],
            "notes": normalized_trade["notes"],
            "source_event_id": _required_text(event.get("event_id"), "event.event_id"),
            "source_event_type": _required_text(event.get("event_type"), "event.event_type"),
            "source_event_hash": _required_text(event.get("event_hash"), "event.event_hash"),
            "occurred_at_utc": _required_text(event.get("occurred_at_utc"), "event.occurred_at_utc"),
            "received_at_utc": _required_text(event.get("received_at_utc"), "event.received_at_utc"),
            "is_tombstone": int(status == "CANCELED"),
            "snapshot_json": snapshot_json,
            "projected_at_utc": projected_at,
        }

    @staticmethod
    def _sort_key(event: Dict[str, Any]) -> Tuple[str, str]:
        return (str(event.get("received_at_utc") or ""), str(event.get("event_id") or ""))

    @staticmethod
    def _venue_scope(
        venue: str,
        venues: Optional[Sequence[str]],
    ) -> Tuple[str, List[str]]:
        values = list(venues) if venues is not None else [venue]
        values = list(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))
        if not values:
            raise ValueError("At least one projection venue is required")
        placeholders = ", ".join("?" for _ in values)
        return f"venue IN ({placeholders})", values

    _PROJECTION_COLUMNS = (
        "account_id", "venue", "trade_id", "symbol", "side", "entry_price",
        "exit_price", "qty", "stop_loss", "take_profit", "entry_time", "exit_time",
        "status", "pnl", "r_multiple", "commission", "notes", "source_event_id",
        "source_event_type", "source_event_hash", "occurred_at_utc", "received_at_utc",
        "is_tombstone", "snapshot_json", "projected_at_utc",
    )
    _REBUILD_WRITE_BATCH_SIZE = 1_000

    @classmethod
    def _projection_upsert_sql(cls) -> str:
        columns = cls._PROJECTION_COLUMNS
        placeholders = ", ".join("?" for _ in columns)
        update_columns = tuple(
            column for column in columns if column not in {"account_id", "venue", "trade_id"}
        )
        update_clause = ", ".join(
            f"{column} = excluded.{column}" for column in update_columns
        )
        return f"""INSERT INTO evidence_trade_projections ({', '.join(columns)})
            VALUES ({placeholders})
            ON CONFLICT(account_id, venue, trade_id) DO UPDATE SET
            {update_clause}"""

    @classmethod
    def _insert_projection_record(
        cls,
        conn: sqlite3.Connection,
        record: Dict[str, Any],
    ) -> None:
        columns = cls._PROJECTION_COLUMNS
        conn.execute(
            cls._projection_upsert_sql(),
            tuple(record[column] for column in columns),
        )

    @classmethod
    def _insert_projection_records(
        cls,
        conn: sqlite3.Connection,
        records: Iterable[Dict[str, Any]],
    ) -> None:
        """Insert a rebuild batch without changing the transaction boundary."""

        columns = cls._PROJECTION_COLUMNS
        conn.executemany(
            cls._projection_upsert_sql(),
            (
                tuple(record[column] for column in columns)
                for record in records
            ),
        )

    def upsert_event_in_transaction(
        self,
        conn: sqlite3.Connection,
        event: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Materialize one accepted ledger event without owning the transaction.

        Journal writes use this boundary immediately after appending the canonical
        event.  The caller owns commit/rollback, so a projection validation or
        SQLite failure rolls back the compatibility row and ledger event together.
        Non-trade lifecycle events are deliberately ignored until their own typed
        projection semantics exist.
        """

        if not conn.in_transaction:
            raise EvidenceProjectionError(
                "upsert_event_in_transaction requires an active transaction"
            )
        if event.get("event_type") not in PROJECTABLE_EVENT_TYPES:
            return None
        projected_at = _now_utc()
        record = self._projection_from_event(event, projected_at)
        self._insert_projection_record(conn, record)
        return record

    def rebuild(
        self,
        *,
        account_id: Optional[str] = None,
        dry_run: bool = True,
        resource_check: Optional[Callable[[str], None]] = None,
    ) -> Dict[str, Any]:
        """Verify the ledger and rebuild projections deterministically.

        A malformed projectable event fails closed before the projection table is
        changed.  Non-trade lifecycle events are counted as ignored until their
        own projection semantics are introduced.
        """

        if resource_check is not None and not callable(resource_check):
            raise TypeError("resource_check must be callable")

        def check_resources(phase: str) -> None:
            if resource_check is not None:
                resource_check(phase)

        ledger = self._ledger_repo
        integrity = ledger.verify_chain(
            account_id=account_id,
            resource_check=resource_check,
        )
        if not integrity["valid"]:
            raise EvidenceProjectionError(
                "Cannot rebuild projection from invalid evidence ledger: "
                + "; ".join(integrity["errors"][:5])
            )
        check_resources("after_ledger_integrity")

        events = list(
            ledger.export_events(
                account_id=account_id,
                resource_check=resource_check,
            )
        )
        events.sort(key=self._sort_key)
        check_resources("after_event_snapshot")
        projected_at = _now_utc()
        latest: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
        ignored = 0
        projectable = 0
        for event in events:
            if event["event_type"] not in PROJECTABLE_EVENT_TYPES:
                ignored += 1
                continue
            record = self._projection_from_event(event, projected_at)
            latest[(record["account_id"], record["venue"], record["trade_id"])] = record
            projectable += 1
            check_resources("after_projection_candidate")

        report = {
            "dry_run": dry_run,
            "account_id": account_id,
            "events_seen": len(events),
            "projectable_events": projectable,
            "ignored_events": ignored,
            "projections_written": len(latest),
            "tombstones": sum(1 for row in latest.values() if row["is_tombstone"]),
            "ledger_valid": True,
        }
        if dry_run:
            check_resources("before_projection_return")
            return report

        conn = self._connect(write=True)
        try:
            conn.execute("BEGIN IMMEDIATE")
            check_resources("before_projection_delete")
            if account_id is None:
                conn.execute("DELETE FROM evidence_trade_projections")
            else:
                conn.execute(
                    "DELETE FROM evidence_trade_projections WHERE account_id = ?",
                    (account_id,),
                )
            check_resources("after_projection_delete")
            records = list(latest.values())
            for start in range(0, len(records), self._REBUILD_WRITE_BATCH_SIZE):
                batch = records[start:start + self._REBUILD_WRITE_BATCH_SIZE]
                check_resources("before_projection_batch")
                self._insert_projection_records(conn, batch)
                check_resources("after_projection_batch")
            check_resources("before_projection_commit")
            conn.commit()
        except Exception:
            if conn.in_transaction:
                conn.rollback()
            raise
        finally:
            conn.close()
        return report

    def get_projection(
        self,
        trade_id: str,
        *,
        account_id: str = "local-journal",
        venue: str = "local-journal",
    ) -> Optional[Dict[str, Any]]:
        conn = self._connect(write=False)
        try:
            row = conn.execute(
                """SELECT * FROM evidence_trade_projections
                   WHERE account_id = ? AND venue = ? AND trade_id = ?""",
                (account_id, venue, trade_id),
            ).fetchone()
            if row is None:
                return None
            result = dict(row)
            result["snapshot"] = json.loads(result.pop("snapshot_json"))
            return result
        finally:
            conn.close()

    def coverage(
        self,
        *,
        account_id: str = "local-journal",
        venue: str = "local-journal",
        venues: Optional[Sequence[str]] = None,
    ) -> Dict[str, Any]:
        """Return whether the typed projection covers every compatibility trade.

        A read adapter must not mix a partial projection with legacy rows.  Exact
        ID coverage is therefore the gate for switching a read path to this model.
        """

        venue_clause, venue_params = self._venue_scope(venue, venues)
        conn = self._connect(write=False)
        try:
            trade_count = int(conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0])
            projected_count = int(conn.execute(
                f"""SELECT COUNT(*) FROM evidence_trade_projections
                   WHERE account_id = ? AND {venue_clause}""",
                [account_id, *venue_params],
            ).fetchone()[0])
            missing_count = int(conn.execute(
                f"""SELECT COUNT(*)
                   FROM trades AS t
                   LEFT JOIN evidence_trade_projections AS p
                     ON p.account_id = ? AND p.{venue_clause} AND p.trade_id = t.id
                   WHERE p.trade_id IS NULL""",
                [account_id, *venue_params],
            ).fetchone()[0])
            extra_count = int(conn.execute(
                f"""SELECT COUNT(*)
                   FROM evidence_trade_projections AS p
                   LEFT JOIN trades AS t ON t.id = p.trade_id
                   WHERE p.account_id = ? AND p.{venue_clause} AND t.id IS NULL""",
                [account_id, *venue_params],
            ).fetchone()[0])
            duplicate_count = int(conn.execute(
                f"""SELECT COUNT(*) - COUNT(DISTINCT trade_id)
                   FROM evidence_trade_projections
                   WHERE account_id = ? AND {venue_clause}""",
                [account_id, *venue_params],
            ).fetchone()[0])
            return {
                "account_id": account_id,
                "venue": venue,
                "venues": list(venues) if venues is not None else [venue],
                "trade_count": trade_count,
                "projected_count": projected_count,
                "missing_count": missing_count,
                "extra_count": extra_count,
                "duplicate_count": duplicate_count,
                "ready": (
                    missing_count == 0
                    and extra_count == 0
                    and duplicate_count == 0
                    and projected_count == trade_count
                ),
            }
        finally:
            conn.close()

    @staticmethod
    def _row_to_snapshot(row: sqlite3.Row) -> Dict[str, Any]:
        return json.loads(row["snapshot_json"])

    def get_trade_snapshot(
        self,
        trade_id: str,
        *,
        account_id: str = "local-journal",
        venue: str = "local-journal",
        venues: Optional[Sequence[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        venue_clause, venue_params = self._venue_scope(venue, venues)
        conn = self._connect(write=False)
        try:
            row = conn.execute(
                f"""SELECT snapshot_json FROM evidence_trade_projections
                   WHERE account_id = ? AND {venue_clause} AND trade_id = ?""",
                [account_id, *venue_params, trade_id],
            ).fetchone()
            return self._row_to_snapshot(row) if row is not None else None
        finally:
            conn.close()

    def list_trade_snapshots(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        symbol: Optional[str] = None,
        status: Optional[str] = None,
        order_by_utc: bool = False,
        account_id: str = "local-journal",
        venue: str = "local-journal",
        venues: Optional[Sequence[str]] = None,
        include_tombstones: bool = True,
        resource_check: Optional[Callable[[str], None]] = None,
    ) -> List[Dict[str, Any]]:
        if resource_check is not None and not callable(resource_check):
            raise TypeError("resource_check must be callable")

        def check_resources(phase: str) -> None:
            if resource_check is not None:
                resource_check(phase)

        venue_clause, venue_params = self._venue_scope(venue, venues)
        query = f"""SELECT snapshot_json FROM evidence_trade_projections
                   WHERE account_id = ? AND {venue_clause}"""
        params: List[Any] = [account_id, *venue_params]
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol.upper())
        if status:
            query += " AND status = ?"
            params.append(status.upper())
        if not include_tombstones:
            query += " AND is_tombstone = 0"
        if order_by_utc:
            query += " ORDER BY julianday(entry_time) DESC, trade_id DESC"
        else:
            query += " ORDER BY entry_time DESC, trade_id DESC"
        query += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        conn = self._connect(write=False)
        try:
            check_resources("before_trade_query")
            result = []
            for row in conn.execute(query, params):
                check_resources("before_trade_row")
                result.append(self._row_to_snapshot(row))
            check_resources("after_trade_query")
            return result
        finally:
            conn.close()

    def list_projections(
        self,
        *,
        account_id: Optional[str] = None,
        include_tombstones: bool = True,
    ) -> List[Dict[str, Any]]:
        conn = self._connect(write=False)
        try:
            query = "SELECT * FROM evidence_trade_projections WHERE 1 = 1"
            params: List[Any] = []
            if account_id is not None:
                query += " AND account_id = ?"
                params.append(account_id)
            if not include_tombstones:
                query += " AND is_tombstone = 0"
            query += " ORDER BY account_id ASC, venue ASC, entry_time ASC, trade_id ASC"
            result = []
            for row in conn.execute(query, params):
                item = dict(row)
                item["snapshot"] = json.loads(item.pop("snapshot_json"))
                result.append(item)
            return result
        finally:
            conn.close()
