"""Experimental FIX routing boundary with no live or simulated execution authority."""

import time
import uuid
import logging
from typing import Dict, Any, List, Optional
from app.services.fix.fix_gateway import fix_session, FIXSessionStateMachine

logger = logging.getLogger("dma_router")

class DirectMarketAccessRouter:
    """Rejects dispatch until a certified transport and reconciliation path exist."""

    def __init__(self):
        self.fix_session = fix_session
        self.active_routes: List[str] = []

    def submit_order(
        self,
        symbol: str,
        side: str,
        price: float,
        qty: float,
        order_type: str = "LIMIT",
        tif: str = "0",
        destination: str = "INTERNAL_MATCHING_ENGINE"
    ) -> Dict[str, Any]:
        """Return a structured fail-closed result; no order is encoded or matched."""
        cl_ord_id = f"CLORD-{uuid.uuid4().hex[:8].upper()}"
        side = side.upper().strip()
        dest = destination.upper().strip()

        return {
            "status": "EXPERIMENTAL_DISABLED",
            "cl_ord_id": cl_ord_id,
            "destination": dest,
            "execution_status": "NOT_SUBMITTED",
            "transport_connected": False,
            "provenance": "FIX_SERIALIZATION_ONLY",
            "caveat": "No certified FIX transport or venue reconciliation is configured; no order was sent or matched.",
            "requested_order": {
                "symbol": symbol.upper(),
                "side": side,
                "price": price,
                "qty": qty,
                "order_type": order_type.upper(),
                "tif": tif,
            },
            "fix_raw_message": None,
            "matching_status": "NOT_ATTEMPTED",
            "filled_size": 0.0,
            "remaining_size": qty,
            "fills": [],
            "timestamp": time.time()
        }

    def cancel_order(self, cl_ord_id: str, symbol: str = "BTCUSDT", side: str = "BUY") -> Dict[str, Any]:
        """Return a structured fail-closed result; no cancel request is dispatched."""
        cancel_cl_ord_id = f"CANC-{uuid.uuid4().hex[:6].upper()}"
        return {
            "status": "EXPERIMENTAL_DISABLED",
            "orig_cl_ord_id": cl_ord_id,
            "cancel_cl_ord_id": cancel_cl_ord_id,
            "execution_status": "NOT_SUBMITTED",
            "transport_connected": False,
            "provenance": "FIX_SERIALIZATION_ONLY",
            "caveat": "No certified FIX transport or venue reconciliation is configured; no cancel request was sent.",
            "fix_cancel_message": None,
            "book_cancel_status": "NOT_ATTEMPTED",
            "timestamp": time.time()
        }

dma_router = DirectMarketAccessRouter()
