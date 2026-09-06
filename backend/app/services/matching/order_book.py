"""In-memory L2/L3 limit-order-book model used for explicit local/test inputs.

It is not connected to a venue and does not provide a market-data or latency SLA.
"""

import time
import uuid
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger("order_book")

@dataclass
class Order:
    order_id: str
    side: str # "BUY" or "SELL"
    price: float
    size: float
    remaining_size: float
    order_type: str = "LIMIT" # "LIMIT", "MARKET", "IOC", "FOK", "POST_ONLY"
    timestamp: float = field(default_factory=time.time)

@dataclass
class PriceLevel:
    price: float
    total_volume: float = 0.0
    orders: List[Order] = field(default_factory=list)

    def add_order(self, order: Order):
        self.orders.append(order)
        self.total_volume += order.remaining_size

    def remove_order(self, order_id: str) -> Optional[Order]:
        for i, o in enumerate(self.orders):
            if o.order_id == order_id:
                removed = self.orders.pop(i)
                self.total_volume -= removed.remaining_size
                return removed
        return None

class LimitOrderBook:
    """Price-time-priority in-memory book; callers must supply every order explicitly."""

    def __init__(self, symbol: str = "BTCUSDT", tick_size: float = 0.10):
        self.symbol = symbol
        self.tick_size = tick_size
        self.bids: Dict[float, PriceLevel] = {} # price -> PriceLevel (Descending)
        self.asks: Dict[float, PriceLevel] = {} # price -> PriceLevel (Ascending)
        self.orders_map: Dict[str, Order] = {}

    def get_bbo(self) -> Tuple[Optional[float], Optional[float]]:
        """Returns Best Bid and Best Offer prices."""
        best_bid = max(self.bids.keys()) if self.bids else None
        best_ask = min(self.asks.keys()) if self.asks else None
        return best_bid, best_ask

    def add_order(
        self,
        order_id: str,
        side: str,
        price: float,
        size: float,
        order_type: str = "LIMIT"
    ) -> Dict[str, Any]:
        """
        Inserts and matches orders with Price-Time Priority and specialized execution modes (IOC, FOK, POST_ONLY).
        """
        side = side.upper().strip()
        order_type = order_type.upper().strip()
        price = round(price, 2)
        size = float(size)

        best_bid, best_ask = self.get_bbo()
        fills: List[Dict[str, Any]] = []

        # 1. Post-Only Guard
        if order_type == "POST_ONLY":
            if (side == "BUY" and best_ask is not None and price >= best_ask) or \
               (side == "SELL" and best_bid is not None and price <= best_bid):
                return {
                    "order_id": order_id,
                    "status": "REJECTED_POST_ONLY_RESTRICTED",
                    "filled_size": 0.0,
                    "remaining_size": size,
                    "fills": []
                }

        # 2. Fill-Or-Kill (FOK) Check
        if order_type == "FOK":
            can_fill = self._can_fill_completely(side, price, size)
            if not can_fill:
                return {
                    "order_id": order_id,
                    "status": "CANCELLED_FOK_INSUFFICIENT_LIQUIDITY",
                    "filled_size": 0.0,
                    "remaining_size": size,
                    "fills": []
                }

        # 3. Matching Execution Loop
        remaining = size
        if side == "BUY":
            # Match against lowest asks <= price
            while remaining > 0 and self.asks:
                best_ask_price = min(self.asks.keys())
                if best_ask_price > price and order_type != "MARKET":
                    break

                level = self.asks[best_ask_price]
                while remaining > 0 and level.orders:
                    resting_order = level.orders[0]
                    fill_qty = min(remaining, resting_order.remaining_size)
                    remaining -= fill_qty
                    resting_order.remaining_size -= fill_qty
                    level.total_volume -= fill_qty

                    fills.append({
                        "trade_id": f"TRD-{uuid.uuid4().hex[:8].upper()}",
                        "matched_order_id": resting_order.order_id,
                        "price": best_ask_price,
                        "size": fill_qty,
                        "side": "BUY"
                    })

                    if resting_order.remaining_size <= 0:
                        level.orders.pop(0)
                        self.orders_map.pop(resting_order.order_id, None)

                if level.total_volume <= 0 or len(level.orders) == 0:
                    self.asks.pop(best_ask_price, None)

        else: # SELL
            # Match against highest bids >= price
            while remaining > 0 and self.bids:
                best_bid_price = max(self.bids.keys())
                if best_bid_price < price and order_type != "MARKET":
                    break

                level = self.bids[best_bid_price]
                while remaining > 0 and level.orders:
                    resting_order = level.orders[0]
                    fill_qty = min(remaining, resting_order.remaining_size)
                    remaining -= fill_qty
                    resting_order.remaining_size -= fill_qty
                    level.total_volume -= fill_qty

                    fills.append({
                        "trade_id": f"TRD-{uuid.uuid4().hex[:8].upper()}",
                        "matched_order_id": resting_order.order_id,
                        "price": best_bid_price,
                        "size": fill_qty,
                        "side": "SELL"
                    })

                    if resting_order.remaining_size <= 0:
                        level.orders.pop(0)
                        self.orders_map.pop(resting_order.order_id, None)

                if level.total_volume <= 0 or len(level.orders) == 0:
                    self.bids.pop(best_bid_price, None)

        filled_size = size - remaining

        # 4. Handle IOC / Market remainder cancellation or Resting Insertion
        if order_type in ("IOC", "MARKET") or remaining <= 0:
            status = "FILLED" if remaining <= 0 else "PARTIALLY_FILLED_IOC_CANCELLED"
            return {
                "order_id": order_id,
                "status": status,
                "filled_size": filled_size,
                "remaining_size": remaining,
                "fills": fills
            }

        # 5. Insert resting order into book
        new_order = Order(
            order_id=order_id,
            side=side,
            price=price,
            size=size,
            remaining_size=remaining,
            order_type=order_type
        )
        self.orders_map[order_id] = new_order

        if side == "BUY":
            if price not in self.bids:
                self.bids[price] = PriceLevel(price=price)
            self.bids[price].add_order(new_order)
        else:
            if price not in self.asks:
                self.asks[price] = PriceLevel(price=price)
            self.asks[price].add_order(new_order)

        status = "NEW" if filled_size == 0 else "PARTIALLY_FILLED"
        return {
            "order_id": order_id,
            "status": status,
            "filled_size": filled_size,
            "remaining_size": remaining,
            "fills": fills
        }

    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """Cancels resting order with O(1) hash map lookup and doubly-linked queue removal."""
        order = self.orders_map.get(order_id)
        if not order:
            return {"order_id": order_id, "status": "ORDER_NOT_FOUND"}

        side = order.side
        price = order.price

        if side == "BUY" and price in self.bids:
            self.bids[price].remove_order(order_id)
            if self.bids[price].total_volume <= 0 or len(self.bids[price].orders) == 0:
                self.bids.pop(price, None)
        elif side == "SELL" and price in self.asks:
            self.asks[price].remove_order(order_id)
            if self.asks[price].total_volume <= 0 or len(self.asks[price].orders) == 0:
                self.asks.pop(price, None)

        self.orders_map.pop(order_id, None)
        return {
            "order_id": order_id,
            "status": "CANCELLED_SUCCESS",
            "cancelled_size": order.remaining_size,
            "price": price
        }

    def _can_fill_completely(self, side: str, price: float, size: float) -> bool:
        """Helper to verify if FOK order can be filled in its entirety."""
        accum = 0.0
        if side == "BUY":
            for p in sorted(self.asks.keys()):
                if p > price:
                    break
                accum += self.asks[p].total_volume
                if accum >= size:
                    return True
        else:
            for p in sorted(self.bids.keys(), reverse=True):
                if p < price:
                    break
                accum += self.bids[p].total_volume
                if accum >= size:
                    return True
        return False

    def simulate_sweep(self, side: str, size: float) -> Dict[str, Any]:
        """Calculate a hypothetical sweep against this explicitly populated in-memory book."""
        side = side.upper()
        remaining = size
        total_cost = 0.0
        depth_levels = []

        target_dict = self.asks if side == "BUY" else self.bids
        sorted_prices = sorted(target_dict.keys()) if side == "BUY" else sorted(target_dict.keys(), reverse=True)

        for p in sorted_prices:
            if remaining <= 0:
                break
            level_vol = target_dict[p].total_volume
            fill_vol = min(remaining, level_vol)
            total_cost += fill_vol * p
            remaining -= fill_vol
            depth_levels.append({"price": p, "filled_volume": fill_vol})

        filled_size = size - remaining
        if filled_size <= 0:
            return {
                "symbol": self.symbol,
                "status": "NO_DATA",
                "provenance": "IN_MEMORY_EXPLICIT_ORDERS",
                "caveat": "This in-memory book contains no executable liquidity; no venue fill was attempted.",
                "sweep_side": side,
                "requested_size": size,
                "filled_size": 0.0,
                "unfilled_size": remaining,
                "execution_vwap": None,
                "reference_bbo": None,
                "slippage_bps": None,
                "price_impact_usd": None,
                "depth_levels_swept": 0,
            }

        vwap = round(total_cost / filled_size, 2)
        best_bid, best_ask = self.get_bbo()
        reference_price = best_ask if side == "BUY" else best_bid
        slippage_bps = round((abs(vwap - (reference_price or vwap)) / max(0.0001, reference_price or 1.0)) * 10000.0, 2)

        return {
            "symbol": self.symbol,
            "status": "IN_MEMORY_NON_VENUE",
            "provenance": "IN_MEMORY_EXPLICIT_ORDERS",
            "caveat": "This is a local in-memory calculation, not a venue execution or market-data record.",
            "sweep_side": side,
            "requested_size": size,
            "filled_size": filled_size,
            "unfilled_size": remaining,
            "execution_vwap": vwap,
            "reference_bbo": reference_price,
            "slippage_bps": slippage_bps,
            "price_impact_usd": round(abs(total_cost - (filled_size * (reference_price or vwap))), 2),
            "depth_levels_swept": len(depth_levels)
        }

    def get_l2_snapshot(self, depth: int = 20) -> Dict[str, Any]:
        """Return an explicit local-book snapshot without inventing market levels."""
        sorted_bids = sorted(self.bids.keys(), reverse=True)[:depth]
        sorted_asks = sorted(self.asks.keys())[:depth]

        bid_levels = [{"price": p, "volume": round(self.bids[p].total_volume, 4), "orders_count": len(self.bids[p].orders)} for p in sorted_bids]
        ask_levels = [{"price": p, "volume": round(self.asks[p].total_volume, 4), "orders_count": len(self.asks[p].orders)} for p in sorted_asks]

        best_bid = sorted_bids[0] if sorted_bids else None
        best_ask = sorted_asks[0] if sorted_asks else None
        spread_abs = round(best_ask - best_bid, 2) if best_ask and best_bid else 0.0
        mid_price = round((best_bid + best_ask) / 2.0, 2) if best_bid and best_ask else (best_bid or best_ask)

        total_bid_vol = sum(b["volume"] for b in bid_levels)
        total_ask_vol = sum(a["volume"] for a in ask_levels)

        # Micro-Price (Volume-Weighted Mid Price)
        if (total_bid_vol + total_ask_vol) > 0 and best_bid and best_ask:
            micro_price = round(((best_ask * total_bid_vol) + (best_bid * total_ask_vol)) / (total_bid_vol + total_ask_vol), 2)
        else:
            micro_price = mid_price

        # Book Imbalance Ratio: (BidVol - AskVol) / (BidVol + AskVol) in [-1.0, +1.0]
        imbalance = (
            round((total_bid_vol - total_ask_vol) / (total_bid_vol + total_ask_vol), 4)
            if (total_bid_vol + total_ask_vol) > 0
            else None
        )

        has_levels = bool(bid_levels or ask_levels)

        return {
            "symbol": self.symbol,
            "status": "IN_MEMORY_NON_VENUE" if has_levels else "NO_DATA",
            "provenance": "IN_MEMORY_EXPLICIT_ORDERS",
            "caveat": (
                "This snapshot is derived from explicitly supplied local orders, not a venue feed."
                if has_levels
                else "No local orders have been supplied; no L2 market-data feed is connected."
            ),
            "best_bid": best_bid,
            "best_ask": best_ask,
            "spread_absolute": spread_abs,
            "spread_bps": round((spread_abs / max(0.01, mid_price)) * 10000.0, 2) if mid_price else 0.0,
            "mid_price": mid_price,
            "micro_price": micro_price,
            "book_imbalance_ratio": imbalance,
            "total_bid_depth_volume": round(total_bid_vol, 4),
            "total_ask_depth_volume": round(total_ask_vol, 4),
            "bids": bid_levels,
            "asks": ask_levels,
            "timestamp": time.time()
        }

# Global book intentionally starts empty. It is not a venue-connected L2 source.
global_order_book = LimitOrderBook(symbol="BTCUSDT")
