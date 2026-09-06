"""Rebuildable typed trade projection sourced from canonical evidence events."""

from __future__ import annotations

import json
import math
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

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

    def rebuild(
        self,
        *,
        account_id: Optional[str] = None,
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        """Verify the ledger and rebuild projections deterministically.

        A malformed projectable event fails closed before the projection table is
        changed.  Non-trade lifecycle events are counted as ignored until their
        own projection semantics are introduced.
        """

        ledger = EvidenceLedgerRepository(self.db_path)
        integrity = ledger.verify_chain(account_id=account_id)
        if not integrity["valid"]:
            raise EvidenceProjectionError(
                "Cannot rebuild projection from invalid evidence ledger: "
                + "; ".join(integrity["errors"][:5])
            )

        events = list(ledger.export_events(account_id=account_id))
        events.sort(key=self._sort_key)
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
            return report

        conn = self._connect(write=True)
        try:
            conn.execute("BEGIN IMMEDIATE")
            if account_id is None:
                conn.execute("DELETE FROM evidence_trade_projections")
            else:
                conn.execute(
                    "DELETE FROM evidence_trade_projections WHERE account_id = ?",
                    (account_id,),
                )
            columns = (
                "account_id", "venue", "trade_id", "symbol", "side", "entry_price",
                "exit_price", "qty", "stop_loss", "take_profit", "entry_time", "exit_time",
                "status", "pnl", "r_multiple", "commission", "notes", "source_event_id",
                "source_event_type", "source_event_hash", "occurred_at_utc", "received_at_utc",
                "is_tombstone", "snapshot_json", "projected_at_utc",
            )
            placeholders = ", ".join("?" for _ in columns)
            for record in latest.values():
                conn.execute(
                    f"INSERT INTO evidence_trade_projections ({', '.join(columns)}) VALUES ({placeholders})",
                    tuple(record[column] for column in columns),
                )
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
