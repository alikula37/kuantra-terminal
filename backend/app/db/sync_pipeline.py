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
        causation_id: Optional[str] = None,
        local_tracking_plan: Optional[Dict[str, Any]] = None,
        local_tracking_reset: bool = False,
        local_tracking_expected_revision: Optional[int] = None,
        occurred_at: Optional[str] = None,
        expected_revision: Optional[int] = None,
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

        occurred_at = occurred_at or payload.get("exit_time") or payload.get("entry_time")
        saved = sqlite_driver.record_trade_with_evidence(
            payload,
            event_type=event_type,
            idempotency_key=idempotency_key,
            occurred_at=occurred_at,
            causation_id=causation_id,
            provenance=provenance,
            local_tracking_plan=local_tracking_plan,
            local_tracking_reset=local_tracking_reset,
            local_tracking_expected_revision=local_tracking_expected_revision,
            expected_revision=expected_revision,
        )
        if getattr(duckdb_driver, "is_available", False):
            duckdb_driver.sync_trade(saved)
        return saved

    @staticmethod
    def full_sync_report() -> Dict[str, Any]:
        """Run the full SQLite -> DuckDB sync and report the honest outcome.

        The report distinguishes "DuckDB is not available in this build" from
        "the evidence projection coverage is incomplete", so the UI can never
        claim a successful sync that did not happen.
        """
        if not getattr(duckdb_driver, "is_available", False):
            return {
                "available": False,
                "coverage_ready": False,
                "synced": 0,
                "reason": "DUCKDB_UNAVAILABLE",
            }
        # Bulk OLAP writes must use the same evidence coverage gate as the
        # hydrator.  Construct the adapter from the module's current driver so
        # tests and explicit per-database maintenance jobs remain injectable.
        from app.services.trade_read_adapter import TradeReadAdapter

        reader = TradeReadAdapter(legacy_driver=sqlite_driver)
        coverage = reader.coverage()
        if not coverage["ready"]:
            return {
                "available": True,
                "coverage_ready": False,
                "synced": 0,
                "reason": "COVERAGE_INCOMPLETE",
            }
        all_trades = reader.list_trades(limit=100000)
        synced_count = duckdb_driver.sync_all_trades(all_trades)
        return {
            "available": True,
            "coverage_ready": True,
            "synced": int(synced_count),
            "reason": None,
        }

    @staticmethod
    def full_sync() -> int:
        """Run full synchronization of all historical SQLite trades into DuckDB."""
        report = SyncPipeline.full_sync_report()
        if report["reason"] == "DUCKDB_UNAVAILABLE":
            logger.info("DuckDB not available; skipping full sync in Lite mode.")
        elif report["reason"] == "COVERAGE_INCOMPLETE":
            logger.warning(
                "DuckDB full sync blocked: evidence projection coverage is incomplete."
            )
        else:
            logger.info(f"Full OLTP -> OLAP sync completed: {report['synced']} trades synchronized.")
        return report["synced"]

sync_pipeline = SyncPipeline()
