"""Shared TradingView-extension WebSocket handler.

Lives outside main.py so that both the dev HTTP server and the desktop integrations gateway
mount the exact same handler.
"""
from fastapi import WebSocket, WebSocketDisconnect
from app.websocket.tv_sync import tv_sync_manager


async def tv_sync_websocket(websocket: WebSocket):
    await tv_sync_manager.connect_extension(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            await tv_sync_manager.handle_extension_message(data)
    except WebSocketDisconnect:
        tv_sync_manager.disconnect_extension(websocket)
    except Exception:
        tv_sync_manager.disconnect_extension(websocket)
