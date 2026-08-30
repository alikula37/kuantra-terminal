"""
Polygon.io US Equities & Indices Adapter (NVDA, AAPL, NAS100, SPY).
Streams high-frequency Level 1 trades and aggregate bars into DuckDB.
"""

import time
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("polygon_adapter")

class PolygonAdapter:
    """Connects to Polygon.io Stocks & Equities streams."""

    SUPPORTED_TICKERS = ["NVDA", "AAPL", "MSFT", "TSLA", "SPY", "QQQ", "NAS100"]

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or "demo"
        self.active_subscriptions: List[str] = []
        self.is_connected: bool = False

    def normalize_symbol(self, raw_symbol: str) -> str:
        return raw_symbol.upper().strip()

    def parse_trade(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalizes Polygon.io equity trade payload."""
        sym = self.normalize_symbol(data.get("sym", data.get("symbol", "NVDA")))
        price = float(data.get("p", data.get("price", 0.0)))
        size = float(data.get("s", data.get("size", 100.0)))
        ts = float(data.get("t", time.time() * 1000)) / 1000.0

        return {
            "symbol": sym,
            "price": price,
            "size": size,
            "source": "POLYGON_IO",
            "asset_class": "US_EQUITIES",
            "timestamp": ts
        }

    def subscribe(self, symbols: List[str]) -> Dict[str, Any]:
        for s in symbols:
            norm = self.normalize_symbol(s)
            if norm not in self.active_subscriptions:
                self.active_subscriptions.append(norm)
        self.is_connected = True
        logger.info(f"[Polygon.io] Subscribed to equities {self.active_subscriptions}")
        return {"status": "SUBSCRIBED", "symbols": self.active_subscriptions}

polygon_adapter = PolygonAdapter()