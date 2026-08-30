import asyncio
import json
import logging
import time
from typing import Dict, Set, Any, Optional
from fastapi import WebSocket

logger = logging.getLogger(__name__)

class ConnectionManager:
    """AsyncIO WebSocket Connection & Channel Broadcast Manager with sub-100ms dispatch."""

    def __init__(self):
        # Set of active client websockets
        self.active_connections: Set[WebSocket] = set()
        # Optional topic/channel subscriptions per client
        self.subscriptions: Dict[WebSocket, Set[str]] = {}
        self._lock = asyncio.Lock()
        self.total_messages_sent: int = 0
        self.last_broadcast_time: float = time.time()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        async with self._lock:
            self.active_connections.add(websocket)
            self.subscriptions[websocket] = {"market_ticks", "kline_updates", "open_positions", "system_metrics"}
        logger.info(f"WebSocket client connected. Total clients: {len(self.active_connections)}")

    async def disconnect(self, websocket: WebSocket):
        async with self._lock:
            self.active_connections.discard(websocket)
            self.subscriptions.pop(websocket, None)
        logger.info(f"WebSocket client disconnected. Total clients: {len(self.active_connections)}")

    async def broadcast(self, message: Dict[str, Any], channel: Optional[str] = None):
        """Broadcast JSON payload to connected clients with channel filtering."""
        if not self.active_connections:
            return

        payload_str = json.dumps(message)
        dead_connections = []

        async with self._lock:
            clients = list(self.active_connections)

        for connection in clients:
            try:
                if channel and channel not in self.subscriptions.get(connection, set()):
                    continue
                await connection.send_text(payload_str)
                self.total_messages_sent += 1
            except Exception as e:
                logger.warning(f"Error broadcasting to client: {e}")
                dead_connections.append(connection)

        if dead_connections:
            async with self._lock:
                for dead in dead_connections:
                    self.active_connections.discard(dead)
                    self.subscriptions.pop(dead, None)
        self.last_broadcast_time = time.time()

    def get_stats(self) -> Dict[str, Any]:
        return {
            "active_clients": len(self.active_connections),
            "total_messages_sent": self.total_messages_sent,
            "last_broadcast_time": self.last_broadcast_time
        }

ws_manager = ConnectionManager()
