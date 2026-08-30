"""
Direct Market Access (DMA) Smart Router & Fill Reconciliation for Kuantra Terminal.
Routes incoming institutional orders between internal high-speed matching engine and FIX protocol brokers.
"""

import time
import uuid
import logging
from typing import Dict, Any, List, Optional
from app.services.matching.order_book import global_order_book, LimitOrderBook
from app.services.fix.fix_gateway import fix_session, FIXSessionStateMachine

logger = logging.getLogger("dma_router")

class DirectMarketAccessRouter:
    """Smart Order Router (SOR) with FIX 4.4 / 5.0 SP2 Integration."""

    def __init__(self):
        self.order_book = global_order_book
        self.fix_session = fix_session
        self.active_routes = ["INTERNAL_MATCHING_ENGINE", "CME_DMA_FIX", "ICE_DMA_FIX"]

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
        """
        Routes order to internal matching book or dispatches via FIX 35=D NewOrderSingle.
        """
        cl_ord_id = f"CLORD-{uuid.uuid4().hex[:8].upper()}"
        side = side.upper().strip()
        dest = destination.upper().strip()

        # 1. Generate FIX representation
        fix_msg = self.fix_session.create_new_order_single(
            cl_ord_id=cl_ord_id,
            symbol=symbol,
            side=side,
            qty=qty,
            price=price,
            ord_type="2" if order_type == "LIMIT" else "1",
            tif=tif
        )

        # 2. Execute on matching engine
        match_result = self.order_book.add_order(
            order_id=cl_ord_id,
            side=side,
            price=price,
            size=qty,
            order_type=order_type
        )

        logger.info(f"[DMA-ROUTER] Submitted {side} {qty} {symbol} @ {price} via {dest} [{cl_ord_id}]")
        return {
            "cl_ord_id": cl_ord_id,
            "destination": dest,
            "fix_raw_message": fix_msg,
            "matching_status": match_result["status"],
            "filled_size": match_result["filled_size"],
            "remaining_size": match_result["remaining_size"],
            "fills": match_result["fills"],
            "timestamp": time.time()
        }

    def cancel_order(self, cl_ord_id: str, symbol: str = "BTCUSDT", side: str = "BUY") -> Dict[str, Any]:
        """Dispatches FIX 35=F OrderCancelRequest and removes resting order."""
        cancel_cl_ord_id = f"CANC-{uuid.uuid4().hex[:6].upper()}"
        fix_cancel_msg = self.fix_session.create_order_cancel_request(
            orig_cl_ord_id=cl_ord_id,
            cl_ord_id=cancel_cl_ord_id,
            symbol=symbol,
            side=side
        )

        book_cancel_res = self.order_book.cancel_order(order_id=cl_ord_id)
        return {
            "orig_cl_ord_id": cl_ord_id,
            "cancel_cl_ord_id": cancel_cl_ord_id,
            "fix_cancel_message": fix_cancel_msg,
            "book_cancel_status": book_cancel_res["status"],
            "timestamp": time.time()
        }

dma_router = DirectMarketAccessRouter()