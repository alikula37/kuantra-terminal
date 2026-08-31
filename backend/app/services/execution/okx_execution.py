"""
OKX V5 Live & Paper Execution Client Bridge.
Powered by authentic CCXT Execution Engine.
"""

from typing import Dict, Any, Optional
from app.services.execution.ccxt_engine import ccxt_execution_engine


class OkxExecutionClient:
    """Dispatches orders to OKX V5 Unified via CCXT."""

    def place_order(
        self,
        symbol: str,
        side: str,
        qty: float,
        price: float,
        order_type: str = "LIMIT",
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        mode: str = "PAPER"
    ) -> Dict[str, Any]:
        """Places order on OKX via CCXT or paper simulated sandbox."""
        return ccxt_execution_engine.create_order(
            symbol=symbol,
            side=side,
            order_type=order_type,
            qty=qty,
            price=price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            exchange_id="okx",
            mode=mode
        )


okx_execution = OkxExecutionClient()