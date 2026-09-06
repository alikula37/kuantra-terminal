"""
Order Flow Footprint Engine for Kuantra Terminal.
Constructs Bid/Ask volume profile clusters per candlestick with Diagonal & Stacked Imbalance detection.
"""

import time
import logging
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger("footprint_engine")

class FootprintEngine:
    """Aggregates trades into discrete price ladder footprint bars with diagonal imbalances."""

    def __init__(self, tick_size: float = 10.0, imbalance_ratio: float = 3.0):
        self.tick_size: float = tick_size
        self.imbalance_ratio: float = imbalance_ratio
        self.bars: Dict[str, List[Dict[str, Any]]] = {}

    def bucket_price(self, price: float) -> float:
        """Rounds price to nearest tick resolution."""
        return round(round(price / self.tick_size) * self.tick_size, 2)

    def process_trade_tick(
        self,
        symbol: str,
        price: float,
        qty: float,
        is_buyer_maker: bool, # If True -> Seller aggressor (Bid execution); If False -> Buyer aggressor (Ask execution)
        timestamp: Optional[float] = None
    ) -> Dict[str, Any]:
        """Ingests a live trade and updates current active footprint bar."""
        sym = symbol.upper()
        ts = timestamp or time.time()
        bucket = self.bucket_price(price)

        if sym not in self.bars or len(self.bars[sym]) == 0:
            self._init_new_bar(sym, price, ts)

        current_bar = self.bars[sym][-1]

        # Check if bar duration exceeded (e.g. 60s per bar)
        if ts - current_bar["start_time"] >= 60.0:
            self._finalize_bar(current_bar)
            self._init_new_bar(sym, price, ts)
            current_bar = self.bars[sym][-1]

        # Update OHLC
        current_bar["high"] = max(current_bar["high"], price)
        current_bar["low"] = min(current_bar["low"], price)
        current_bar["close"] = price
        current_bar["total_volume"] += qty

        # Update Price Ladder Bid/Ask Clusters
        if bucket not in current_bar["profile"]:
            current_bar["profile"][bucket] = {"bid_vol": 0.0, "ask_vol": 0.0, "total_vol": 0.0}

        if is_buyer_maker:
            # Aggressive Sell (filled on Bid)
            current_bar["profile"][bucket]["bid_vol"] += qty
            current_bar["bid_volume"] += qty
            current_bar["delta"] -= qty
        else:
            # Aggressive Buy (filled on Ask)
            current_bar["profile"][bucket]["ask_vol"] += qty
            current_bar["ask_volume"] += qty
            current_bar["delta"] += qty

        current_bar["profile"][bucket]["total_vol"] += qty
        return current_bar

    def _init_new_bar(self, symbol: str, price: float, timestamp: float):
        if symbol not in self.bars:
            self.bars[symbol] = []

        bar = {
            "symbol": symbol,
            "start_time": timestamp,
            "open": price,
            "high": price,
            "low": price,
            "close": price,
            "total_volume": 0.0,
            "bid_volume": 0.0,
            "ask_volume": 0.0,
            "delta": 0.0,
            "poc_price": price,
            "poc_volume": 0.0,
            "buy_imbalances": [],
            "sell_imbalances": [],
            "stacked_buy_imbalances": False,
            "stacked_sell_imbalances": False,
            "profile": {} # price -> {bid_vol, ask_vol, total_vol}
        }
        self.bars[symbol].append(bar)

    def _finalize_bar(self, bar: Dict[str, Any]):
        """Calculates POC, Value Area, and Diagonal/Stacked Imbalances."""
        profile = bar["profile"]
        if not profile:
            return

        sorted_prices = sorted(profile.keys())

        # 1. Point of Control (POC)
        poc_price = sorted_prices[0]
        max_vol = 0.0
        for p, data in profile.items():
            if data["total_vol"] > max_vol:
                max_vol = data["total_vol"]
                poc_price = p

        bar["poc_price"] = poc_price
        bar["poc_volume"] = max_vol

        # 2. Diagonal Imbalance Calculation
        # Ask at price P is compared against Bid at price (P - tick_size)
        buy_imb = []
        sell_imb = []

        for i in range(len(sorted_prices) - 1):
            p_lower = sorted_prices[i]
            p_higher = sorted_prices[i + 1]

            bid_lower = profile[p_lower]["bid_vol"]
            ask_higher = profile[p_higher]["ask_vol"]

            # Diagonal Buy Imbalance: Ask[P+1] vs Bid[P]
            if bid_lower > 0 and (ask_higher / bid_lower) >= self.imbalance_ratio:
                buy_imb.append(p_higher)
            elif bid_lower == 0 and ask_higher >= 5.0: # Zero-bid dominance
                buy_imb.append(p_higher)

            # Diagonal Sell Imbalance: Bid[P] vs Ask[P+1]
            if ask_higher > 0 and (bid_lower / ask_higher) >= self.imbalance_ratio:
                sell_imb.append(p_lower)
            elif ask_higher == 0 and bid_lower >= 5.0: # Zero-ask dominance
                sell_imb.append(p_lower)

        bar["buy_imbalances"] = buy_imb
        bar["sell_imbalances"] = sell_imb

        # 3. Stacked Imbalances (3 or more consecutive imbalance levels)
        bar["stacked_buy_imbalances"] = self._detect_stacked(buy_imb)
        bar["stacked_sell_imbalances"] = self._detect_stacked(sell_imb)

    def _detect_stacked(self, imbalance_prices: List[float]) -> bool:
        if len(imbalance_prices) < 3:
            return False
        sorted_p = sorted(imbalance_prices)
        consecutive = 1
        for i in range(1, len(sorted_p)):
            if abs(sorted_p[i] - sorted_p[i-1] - self.tick_size) < 1e-4:
                consecutive += 1
                if consecutive >= 3:
                    return True
            else:
                consecutive = 1
        return False

    def get_footprint_candles(self, symbol: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Return only explicitly ingested footprint bars, never generated market data."""
        sym = symbol.upper()
        if sym not in self.bars or len(self.bars[sym]) == 0:
            return []

        # Finalize current active bar for inspection
        if len(self.bars[sym]) > 0:
            self._finalize_bar(self.bars[sym][-1])

        return self.bars[sym][-max(0, limit):]

    def get_footprint_response(self, symbol: str, limit: int = 50) -> Dict[str, Any]:
        """Expose the truth-state contract used by API consumers."""
        sym = symbol.upper()
        bars = self.get_footprint_candles(sym, limit)
        if not bars:
            return {
                "symbol": sym,
                "status": "NO_DATA",
                "provenance": "RUNTIME_INGEST_ONLY",
                "caveat": "No recorded trade-tick feed is connected; footprint bars are unavailable.",
                "bars": [],
            }
        return {
            "symbol": sym,
            "status": "IN_MEMORY_UNVERIFIED",
            "provenance": "RUNTIME_INGEST_ONLY",
            "caveat": "Bars are derived from the current in-memory tick buffer and are not a canonical market-data record.",
            "bars": bars,
        }

footprint_engine = FootprintEngine()
