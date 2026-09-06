"""
Cumulative Volume Delta (CVD) & Limit Order Book Liquidity Heatmap for Kuantra Terminal.
Tracks continuous delta accumulation, institutional absorption divergences, and resting limit depth.
"""

import time
import logging
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger("delta_heatmap")

class DeltaHeatmapEngine:
    """Computes real-time CVD time series and aggregates order book depth into a liquidity matrix."""

    def __init__(self, depth_history_limit: int = 100):
        self.depth_history_limit = depth_history_limit
        self.cvd_state: Dict[str, float] = {}
        self.cvd_series: Dict[str, List[Dict[str, Any]]] = {}
        self.depth_snapshots: Dict[str, List[Dict[str, Any]]] = {}

    def update_cvd_tick(
        self,
        symbol: str,
        delta: float,
        price: float,
        timestamp: Optional[float] = None
    ) -> Dict[str, Any]:
        """Accumulates delta and tracks CVD series."""
        sym = symbol.upper()
        ts = timestamp or time.time()

        if sym not in self.cvd_state:
            self.cvd_state[sym] = 0.0
            self.cvd_series[sym] = []

        self.cvd_state[sym] += delta
        current_cvd = round(self.cvd_state[sym], 2)

        point = {
            "timestamp": ts,
            "price": round(price, 2),
            "delta": round(delta, 2),
            "cvd": current_cvd
        }
        self.cvd_series[sym].append(point)

        # Keep buffer bounded
        if len(self.cvd_series[sym]) > 500:
            self.cvd_series[sym] = self.cvd_series[sym][-500:]

        return point

    def detect_delta_divergence(self, symbol: str) -> Dict[str, Any]:
        """
        Detects Institutional Absorption vs Exhaustion:
        - Bullish Absorption: Price makes lower low, but CVD forms higher low.
        - Bearish Exhaustion: Price makes higher high, but CVD forms lower high.
        """
        sym = symbol.upper()
        points = self.cvd_series.get(sym, [])

        if len(points) < 10:
            return {
                "has_divergence": False,
                "type": "UNAVAILABLE",
                "confidence": None,
                "detail": "At least ten explicitly ingested ticks are required for divergence analysis.",
            }

        p1, p2 = points[-10], points[-1]
        price_change = p2["price"] - p1["price"]
        cvd_change = p2["cvd"] - p1["cvd"]

        if price_change < 0 and cvd_change > 0:
            return {
                "has_divergence": True,
                "type": "BULLISH_ABSORPTION",
                "confidence": 0.88,
                "detail": f"Price dropped by {abs(price_change):.2f}, but aggressive buying (+{cvd_change:.1f} CVD) signals passive absorption."
            }
        elif price_change > 0 and cvd_change < 0:
            return {
                "has_divergence": True,
                "type": "BEARISH_EXHAUSTION",
                "confidence": 0.85,
                "detail": f"Price rallied by {price_change:.2f}, but aggressive selling ({cvd_change:.1f} CVD) signals institutional distribution."
            }

        return {
            "has_divergence": False,
            "type": "NEUTRAL_TREND_ALIGNED",
            "confidence": 0.90,
            "detail": "Price and CVD trajectory are aligned."
        }

    def update_book_depth(
        self,
        symbol: str,
        bids: List[List[float]], # [[price, size], ...]
        asks: List[List[float]],
        timestamp: Optional[float] = None
    ):
        """Records limit order book depth slice."""
        sym = symbol.upper()
        ts = timestamp or time.time()

        if sym not in self.depth_snapshots:
            self.depth_snapshots[sym] = []

        snapshot = {
            "timestamp": ts,
            "bids": bids[:15],
            "asks": asks[:15]
        }
        self.depth_snapshots[sym].append(snapshot)

        if len(self.depth_snapshots[sym]) > self.depth_history_limit:
            self.depth_snapshots[sym] = self.depth_snapshots[sym][-self.depth_history_limit:]

    def get_cvd_series(self, symbol: str, limit: int = 100) -> Dict[str, Any]:
        """Return only explicitly ingested CVD observations, never seed data."""
        sym = symbol.upper()
        if sym not in self.cvd_series or len(self.cvd_series[sym]) == 0:
            return {
                "symbol": sym,
                "status": "NO_DATA",
                "provenance": "RUNTIME_INGEST_ONLY",
                "caveat": "No recorded trade-tick feed is connected; CVD and divergence are unavailable.",
                "current_cvd": None,
                "series": [],
                "divergence": {
                    "has_divergence": False,
                    "type": "UNAVAILABLE",
                    "confidence": None,
                    "detail": "No CVD observations are available.",
                },
            }

        divergence = self.detect_delta_divergence(sym)
        return {
            "symbol": sym,
            "status": "IN_MEMORY_UNVERIFIED",
            "provenance": "RUNTIME_INGEST_ONLY",
            "caveat": "CVD is derived from the current in-memory tick buffer and is not a canonical market-data record.",
            "current_cvd": self.cvd_state.get(sym, 0.0),
            "series": self.cvd_series[sym][-max(0, limit):],
            "divergence": divergence
        }

    def get_liquidity_heatmap(self, symbol: str) -> Dict[str, Any]:
        """Return only explicitly ingested depth snapshots, never seed liquidity."""
        sym = symbol.upper()
        if sym not in self.depth_snapshots or len(self.depth_snapshots[sym]) == 0:
            return {
                "symbol": sym,
                "status": "NO_DATA",
                "provenance": "RUNTIME_INGEST_ONLY",
                "caveat": "No recorded order-book feed is connected; liquidity history is unavailable.",
                "snapshots_count": 0,
                "history": [],
            }

        return {
            "symbol": sym,
            "status": "IN_MEMORY_UNVERIFIED",
            "provenance": "RUNTIME_INGEST_ONLY",
            "caveat": "Snapshots are held only in the current process and are not a canonical market-data record.",
            "snapshots_count": len(self.depth_snapshots[sym]),
            "history": self.depth_snapshots[sym]
        }

delta_heatmap_engine = DeltaHeatmapEngine()
