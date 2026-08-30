"""
Institutional Multi-Venue Smart Order Router.
Enforces Risk Guardrails (Tilt / Prop Shield) and routes orders to designated exchange.
"""

import time
import logging
from typing import Dict, Any, Optional
from app.services.execution.risk_interceptor import risk_interceptor
from app.services.execution.binance_execution import binance_execution
from app.services.execution.okx_execution import okx_execution
from app.db.sqlite_driver import sqlite_driver

logger = logging.getLogger("order_router")

class OrderRouter:
    """Routes execution signals with pre-trade risk interception."""

    def route_order(self, order_payload: Dict[str, Any]) -> Dict[str, Any]:
        venue = str(order_payload.get("exchange", "BINANCE")).upper()
        symbol = str(order_payload.get("symbol", "BTCUSDT")).upper()
        side = str(order_payload.get("side", "BUY")).upper()
        qty = float(order_payload.get("qty", 1.0))
        price = float(order_payload.get("price", 0.0))

        # 1. Pre-Trade Risk Guardrail Interception
        is_approved, reason, meta = risk_interceptor.evaluate_order(order_payload)
        if not is_approved:
            logger.warning(f"[ROUTER] Execution blocked by guardrail: {reason}")
            return {
                "status": "REJECTED_RISK_GUARDRAIL",
                "reason": reason,
                "metadata": meta,
                "timestamp": time.time()
            }

        # 2. Route to Target Exchange Execution Client
        if "OKX" in venue:
            exec_res = okx_execution.place_order(symbol, side, qty, price)
        else:
            exec_res = binance_execution.place_order(symbol, side, qty, price)

        # 3. Persist Order Execution in SQLite OLTP
        trade_entry = {
            "id": exec_res["order_id"],
            "symbol": symbol,
            "side": side,
            "entry_price": price,
            "exit_price": None,
            "qty": qty,
            "stop_loss": order_payload.get("stop_loss"),
            "take_profit": order_payload.get("take_profit"),
            "entry_time": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "status": "OPEN",
            "pnl": 0.0,
            "notes": f"Executed via {venue} Router ({exec_res['mode']})"
        }
        sqlite_driver.insert_trade(trade_entry)

        return {
            "status": "EXECUTED",
            "order": exec_res,
            "risk_metadata": meta
        }

order_router = OrderRouter()