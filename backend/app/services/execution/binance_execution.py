"""
Binance Live & Paper Execution Client Bridge.
Powered by authentic CCXT Execution Engine.
"""

from typing import Dict, Any, Optional
from app.services.execution.ccxt_engine import ccxt_execution_engine


class BinanceExecutionClient:
    """Dispatches orders to Binance Spot or Futures via CCXT."""

    def __init__(self, default_subaccount: str = "binance_futures"):
        self.default_subaccount = default_subaccount

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
        """Places order on Binance via CCXT or paper simulated sandbox."""
        return ccxt_execution_engine.create_order(
            symbol=symbol,
            side=side,
            order_type=order_type,
            qty=qty,
            price=price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            exchange_id=self.default_subaccount,
            mode=mode
        )


binance_execution = BinanceExecutionClient()