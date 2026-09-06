"""
TwelveData Multi-Asset Adapter for Forex, Metals & Commodities (XAUUSD, EURUSD).
Normalizes tick and candle streams for Kuantra Terminal.
"""

import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("twelvedata_adapter")

class TwelveDataAdapter:
    """Connects to TwelveData WebSocket/REST streams."""

    SUPPORTED_PAIRS = ["EUR/USD", "GBP/USD", "USD/JPY", "XAU/USD", "XAG/USD", "WTI/USD"]

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.active_subscriptions: List[str] = []
        self.is_connected: bool = False

    def normalize_symbol(self, raw_symbol: str) -> str:
        """Converts EUR/USD or EURUSD into unified EURUSD identifier."""
        return raw_symbol.replace("/", "").replace("_", "").upper()

    def parse_tick(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalizes TwelveData tick packet into Kuantra standard schema."""
        raw_symbol = data.get("symbol")
        raw_price = data.get("price") if data.get("price") is not None else data.get("close")
        if not raw_symbol or raw_price is None:
            raise ValueError("TwelveData tick payload is missing symbol or price.")
        sym = self.normalize_symbol(raw_symbol)
        price = float(raw_price)
        ts_value = data.get("timestamp")
        ts = float(ts_value) if ts_value is not None else None

        return {
            "symbol": sym,
            "price": price,
            "bid": float(data["bid"]) if data.get("bid") is not None else None,
            "ask": float(data["ask"]) if data.get("ask") is not None else None,
            "source": "UNVERIFIED_ADAPTER",
            "asset_class": "FOREX_COMMODITIES",
            "timestamp": ts,
            "provenance": "RAW_PAYLOAD_NORMALIZER",
        }

    def subscribe(self, symbols: List[str]) -> Dict[str, Any]:
        self.is_connected = False
        return {
            "status": "EXPERIMENTAL_DISABLED",
            "capability": "twelvedata_connector",
            "provenance": "UNVERIFIED_ADAPTER",
            "reason": "REAL_TRANSPORT_NOT_CONFIGURED",
            "symbols": [],
            "transport_connected": False,
        }

twelvedata_adapter = TwelveDataAdapter()
