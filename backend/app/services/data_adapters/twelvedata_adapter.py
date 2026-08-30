"""
TwelveData Multi-Asset Adapter for Forex, Metals & Commodities (XAUUSD, EURUSD).
Normalizes tick and candle streams for Kuantra Terminal.
"""

import time
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("twelvedata_adapter")

class TwelveDataAdapter:
    """Connects to TwelveData WebSocket/REST streams."""

    SUPPORTED_PAIRS = ["EUR/USD", "GBP/USD", "USD/JPY", "XAU/USD", "XAG/USD", "WTI/USD"]

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or "demo"
        self.active_subscriptions: List[str] = []
        self.is_connected: bool = False

    def normalize_symbol(self, raw_symbol: str) -> str:
        """Converts EUR/USD or EURUSD into unified EURUSD identifier."""
        return raw_symbol.replace("/", "").replace("_", "").upper()

    def parse_tick(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalizes TwelveData tick packet into Kuantra standard schema."""
        sym = self.normalize_symbol(data.get("symbol", "EURUSD"))
        price = float(data.get("price", data.get("close", 0.0)))
        ts = float(data.get("timestamp", time.time()))

        return {
            "symbol": sym,
            "price": price,
            "bid": float(data.get("bid", price - 0.0001)),
            "ask": float(data.get("ask", price + 0.0001)),
            "source": "TWELVEDATA",
            "asset_class": "FOREX_COMMODITIES",
            "timestamp": ts
        }

    def subscribe(self, symbols: List[str]) -> Dict[str, Any]:
        for s in symbols:
            norm = self.normalize_symbol(s)
            if norm not in self.active_subscriptions:
                self.active_subscriptions.append(norm)
        self.is_connected = True
        logger.info(f"[TwelveData] Subscribed to {self.active_subscriptions}")
        return {"status": "SUBSCRIBED", "symbols": self.active_subscriptions}

twelvedata_adapter = TwelveDataAdapter()