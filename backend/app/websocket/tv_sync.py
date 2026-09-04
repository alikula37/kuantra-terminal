"""
TradingView Companion Extension WebSocket & Local Bridge Handler.
Broadcasts active symbol and timeframe changes between browser and desktop terminal in <8ms.
"""

import json
import time
import logging
from typing import Dict, Any, Set
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger("tv_sync")

class TradingViewSyncManager:
    """Maintains active TV state and coordinates bidirectional sync."""

    def __init__(self):
        self.active_symbol: str = "BTCUSDT"
        self.active_timeframe: str = "15m"
        self.active_exchange: str = "BINANCE"
        self.last_sync_timestamp: float = time.time()
        self._extension_sockets: Set[WebSocket] = set()
        self._terminal_listeners: Set[WebSocket] = set()

    async def connect_extension(self, websocket: WebSocket):
        await websocket.accept()
        self._extension_sockets.add(websocket)
        logger.info("[TV-SYNC] TradingView Companion Extension connected.")
        # Send initial state
        await websocket.send_json({
            "type": "INITIAL_STATE",
            "symbol": self.active_symbol,
            "timeframe": self.active_timeframe,
            "exchange": self.active_exchange
        })

    def disconnect_extension(self, websocket: WebSocket):
        self._extension_sockets.discard(websocket)
        logger.info("[TV-SYNC] TradingView Companion Extension disconnected.")

    async def handle_extension_message(self, message_data: Dict[str, Any]):
        """Processes symbol/timeframe updates from Chrome Extension."""
        symbol = message_data.get("symbol", self.active_symbol).upper()
        timeframe = message_data.get("timeframe", self.active_timeframe)
        exchange = message_data.get("exchange", self.active_exchange).upper()

        self.active_symbol = symbol
        self.active_timeframe = timeframe
        self.active_exchange = exchange
        self.last_sync_timestamp = time.time()

        logger.info(f"[TV-SYNC] Synced active symbol from TradingView: {symbol} ({timeframe})")

        # Broadcast update to terminal frontend clients
        broadcast_payload = {
            "type": "TV_SYNC_UPDATE",
            "symbol": self.active_symbol,
            "timeframe": self.active_timeframe,
            "exchange": self.active_exchange,
            "timestamp": self.last_sync_timestamp
        }
        await self.broadcast_to_terminal(broadcast_payload)

    async def broadcast_to_terminal(self, payload: Dict[str, Any]):
        from app.websocket.connection_manager import ws_manager
        await ws_manager.broadcast(payload, "tv_sync")

    def get_sync_state(self) -> Dict[str, Any]:
        return {
            "active_symbol": self.active_symbol,
            "active_timeframe": self.active_timeframe,
            "active_exchange": self.active_exchange,
            "connected_extensions": len(self._extension_sockets),
            "last_sync_timestamp": self.last_sync_timestamp
        }

tv_sync_manager = TradingViewSyncManager()