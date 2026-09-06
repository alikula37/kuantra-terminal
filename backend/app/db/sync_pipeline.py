import logging
import hashlib
from datetime import datetime
from typing import Dict, Any, List, Optional
from app.db.sqlite_driver import sqlite_driver
from app.db.duckdb_driver import duckdb_driver
from app.db.repositories.evidence_ledger_repo import canonical_json

logger = logging.getLogger(__name__)

class SyncPipeline:
    """Sync bridge that replicates OLTP SQLite mutations into DuckDB OLAP columnar tables."""

    @staticmethod
    def record_and_sync_trade(
        trade_data: Dict[str, Any],
        *,
        source: str = "journal",
        source_ref: str = "",
        provenance_extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Persist a journal mutation and evidence event before OLAP projection."""
        payload = dict(trade_data)
        existing = sqlite_driver.get_trade(payload["id"]) if payload.get("id") else None
        if existing is None and not payload.get("id"):
            payload["id"] = f"TRD-{int(datetime.utcnow().timestamp() * 1000)}"

        requested_status = str(payload.get("status", existing["status"] if existing else "OPEN")).upper()
        if existing is None:
            event_type = "LegacyTradeImported" if source == "csv" else "IntentRecorded"
        elif existing.get("status") != "CLOSED" and requested_status == "CLOSED":
            event_type = "FillRecorded"
        else:
            event_type = "TradeCorrected"

        identity_body = {
            key: value for key, value in payload.items()
            if key not in {"created_at", "updated_at"}
        }
        digest = hashlib.sha256(canonical_json(identity_body).encode("utf-8")).hexdigest()[:24]
        idempotency_key = f"journal:{payload['id']}:{event_type}:{digest}"
        provenance = {"source": source}
        if source_ref:
            provenance["source_ref"] = source_ref
        if provenance_extra:
            for key, value in provenance_extra.items():
                if value is not None:
                    provenance[str(key)] = value

        occurred_at = payload.get("exit_time") or payload.get("entry_time")
        saved = sqlite_driver.record_trade_with_evidence(
            payload,
            event_type=event_type,
            idempotency_key=idempotency_key,
            occurred_at=occurred_at,
            provenance=provenance,
        )
        if getattr(duckdb_driver, "is_available", False):
            duckdb_driver.sync_trade(saved)
        return saved

    @staticmethod
    def full_sync() -> int:
        """Run full synchronization of all historical SQLite trades into DuckDB."""
        if not getattr(duckdb_driver, "is_available", False):
            logger.info("DuckDB not available; skipping full sync in Lite mode.")
            return 0
        # Bulk OLAP writes must use the same evidence coverage gate as the
        # hydrator.  Construct the adapter from the module's current driver so
        # tests and explicit per-database maintenance jobs remain injectable.
        from app.services.trade_read_adapter import TradeReadAdapter

        reader = TradeReadAdapter(legacy_driver=sqlite_driver)
        coverage = reader.coverage()
        if not coverage["ready"]:
            logger.warning(
                "DuckDB full sync blocked: evidence projection coverage is incomplete: %s",
                coverage,
            )
            return 0
        all_trades = reader.list_trades(limit=100000)
        synced_count = duckdb_driver.sync_all_trades(all_trades)
        logger.info(f"Full OLTP -> OLAP sync completed: {synced_count} trades synchronized.")
        return synced_count

sync_pipeline = SyncPipeline()
