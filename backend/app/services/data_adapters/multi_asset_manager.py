"""
Multi-Asset Market Data Ingestion Manager.
Directs quotes from TwelveData, Polygon, MT5, and Binance into DuckDB OLAP market_candles.
"""

import time
import logging
from typing import Dict, Any, List
from app.db.duckdb_driver import duckdb_driver
from app.services.data_adapters.twelvedata_adapter import twelvedata_adapter
from app.services.data_adapters.polygon_adapter import polygon_adapter
from app.services.data_adapters.mt5_adapter import mt5_adapter

logger = logging.getLogger("multi_asset_manager")

class MultiAssetManager:
    """Coordinates multi-asset streaming feeds and hydrates DuckDB OLAP."""

    def __init__(self):
        self.adapters = {
            "twelvedata": twelvedata_adapter,
            "polygon": polygon_adapter,
            "mt5": mt5_adapter
        }
        # Initialize MT5
        mt5_adapter.initialize()

    def get_all_statuses(self) -> Dict[str, Any]:
        return {
            "twelvedata": {
                "active_subscriptions": twelvedata_adapter.active_subscriptions,
                "supported": twelvedata_adapter.SUPPORTED_PAIRS
            },
            "polygon": {
                "active_subscriptions": polygon_adapter.active_subscriptions,
                "supported": polygon_adapter.SUPPORTED_TICKERS
            },
            "mt5": mt5_adapter.get_account_summary(),
            "total_supported_assets": len(twelvedata_adapter.SUPPORTED_PAIRS) + len(polygon_adapter.SUPPORTED_TICKERS)
        }

    def ingest_candle_to_duckdb(
        self,
        symbol: str,
        open_p: float,
        high_p: float,
        low_p: float,
        close_p: float,
        volume: float,
        timeframe: str = "1m",
        timestamp: float = 0.0
    ):
        """Streams normalized candle into DuckDB OLAP table."""
        ts_str = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(timestamp or time.time()))
        duckdb_driver.insert_market_candle(
            symbol=symbol.upper(),
            timeframe=timeframe,
            timestamp=ts_str,
            open_p=open_p,
            high_p=high_p,
            low_p=low_p,
            close_p=close_p,
            volume=volume
        )

multi_asset_manager = MultiAssetManager()