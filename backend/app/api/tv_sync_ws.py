"""Shared TradingView-extension WebSocket handler.

Lives outside main.py so that both the dev HTTP server and the desktop integrations gateway
mount the exact same handler.
"""
import json

from fastapi import WebSocket, WebSocketDisconnect
from app.websocket.tv_sync import tv_sync_manager
from app.core.config import settings
from urllib.parse import urlsplit


def is_allowed_gateway_origin(origin: str | None) -> bool:
    """Allow only explicitly configured local pages or the companion extension scheme."""

    if not isinstance(origin, str) or not origin or len(origin) > 256 or any(ord(c) < 32 for c in origin):
        return False
    if origin in settings.gateway_origins:
        return True
    for allowed in settings.gateway_origins:
        if not allowed.endswith("://*"):
            continue
        try:
            parsed = urlsplit(origin)
        except ValueError:
            return False
        if (
            parsed.scheme == allowed[:-4]
            and parsed.netloc
            and not parsed.username
            and not parsed.password
            and not parsed.path
            and not parsed.query
            and not parsed.fragment
        ):
            return True
    return False


async def tv_sync_websocket(websocket: WebSocket):
    if not is_allowed_gateway_origin(websocket.headers.get("origin")):
        await websocket.close(code=1008, reason="origin not allowed")
        return
    await tv_sync_manager.connect_extension(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            await tv_sync_manager.handle_extension_message(data)
    except WebSocketDisconnect:
        tv_sync_manager.disconnect_extension(websocket)
    except (TypeError, ValueError, json.JSONDecodeError):
        await websocket.close(code=1003, reason="invalid sync message")
        tv_sync_manager.disconnect_extension(websocket)
    except Exception:
        tv_sync_manager.disconnect_extension(websocket)
