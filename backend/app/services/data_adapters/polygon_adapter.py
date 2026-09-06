"""
Polygon.io US Equities & Indices Adapter (NVDA, AAPL, NAS100, SPY).
Streams high-frequency Level 1 trades and aggregate bars into DuckDB.
"""

import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("polygon_adapter")

class PolygonAdapter:
    """Connects to Polygon.io Stocks & Equities streams."""

    SUPPORTED_TICKERS = ["NVDA", "AAPL", "MSFT", "TSLA", "SPY", "QQQ", "NAS100"]

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.active_subscriptions: List[str] = []
        self.is_connected: bool = False

    def normalize_symbol(self, raw_symbol: str) -> str:
        return raw_symbol.upper().strip()

    def parse_trade(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalizes Polygon.io equity trade payload."""
        raw_symbol = data.get("sym") or data.get("symbol")
        raw_price = data.get("p") if data.get("p") is not None else data.get("price")
        raw_size = data.get("s") if data.get("s") is not None else data.get("size")
        if not raw_symbol or raw_price is None:
            raise ValueError("Polygon trade payload is missing symbol or price.")
        sym = self.normalize_symbol(raw_symbol)
        price = float(raw_price)
        size = float(raw_size) if raw_size is not None else None
        ts_value = data.get("t", data.get("timestamp"))
        ts = float(ts_value) / 1000.0 if ts_value is not None else None

        return {
            "symbol": sym,
            "price": price,
            "size": size,
            "source": "UNVERIFIED_ADAPTER",
            "asset_class": "US_EQUITIES",
            "timestamp": ts,
            "provenance": "RAW_PAYLOAD_NORMALIZER",
        }

    def subscribe(self, symbols: List[str]) -> Dict[str, Any]:
        self.is_connected = False
        return {
            "status": "EXPERIMENTAL_DISABLED",
            "capability": "polygon_connector",
            "provenance": "UNVERIFIED_ADAPTER",
            "reason": "REAL_TRANSPORT_NOT_CONFIGURED",
            "symbols": [],
            "transport_connected": False,
        }

polygon_adapter = PolygonAdapter()
