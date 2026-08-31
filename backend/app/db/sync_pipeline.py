import logging
from typing import Dict, Any, List
from app.db.sqlite_driver import sqlite_driver
from app.db.duckdb_driver import duckdb_driver

logger = logging.getLogger(__name__)

class SyncPipeline:
    """Sync bridge that replicates OLTP SQLite mutations into DuckDB OLAP columnar tables."""

    @staticmethod
    def record_and_sync_trade(trade_data: Dict[str, Any]) -> Dict[str, Any]:
        """Insert or update trade in SQLite and instantly synchronize to DuckDB."""
        if trade_data.get("id") and sqlite_driver.get_trade(trade_data["id"]):
            updated = sqlite_driver.update_trade(trade_data["id"], trade_data)
            if updated:
                if getattr(duckdb_driver, "is_available", False):
                    duckdb_driver.sync_trade(updated)
                return updated
        
        saved = sqlite_driver.insert_trade(trade_data)
        if getattr(duckdb_driver, "is_available", False):
            duckdb_driver.sync_trade(saved)
        return saved

    @staticmethod
    def full_sync() -> int:
        """Run full synchronization of all historical SQLite trades into DuckDB."""
        if not getattr(duckdb_driver, "is_available", False):
            logger.info("DuckDB not available; skipping full sync in Lite mode.")
            return 0
        all_trades = sqlite_driver.list_trades(limit=100000)
        synced_count = duckdb_driver.sync_all_trades(all_trades)
        logger.info(f"Full OLTP -> OLAP sync completed: {synced_count} trades synchronized.")
        return synced_count

sync_pipeline = SyncPipeline()
