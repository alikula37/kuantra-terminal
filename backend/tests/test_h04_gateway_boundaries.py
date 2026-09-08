"""H04 misuse tests for the local TradingView WebSocket boundary."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.api.tv_sync_ws import is_allowed_gateway_origin
from app.websocket.tv_sync import tv_sync_manager
from desktop.gateway import build_gateway_app


def test_gateway_origin_allowlist_rejects_missing_and_external_origins():
    assert is_allowed_gateway_origin(None) is False
    assert is_allowed_gateway_origin("https://attacker.example") is False
    assert is_allowed_gateway_origin("http://127.0.0.1:5173") is True
    assert is_allowed_gateway_origin("chrome-extension://synthetic-extension") is True


def test_gateway_websocket_denies_external_origin_before_accept():
    client = TestClient(build_gateway_app())

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(
            "/ws/tv-sync",
            headers={"origin": "https://attacker.example"},
        ):
            pass


def test_gateway_websocket_closes_on_invalid_message_without_state_mutation():
    client = TestClient(build_gateway_app())
    before = (tv_sync_manager.active_symbol, tv_sync_manager.active_timeframe, tv_sync_manager.active_exchange)

    with client.websocket_connect(
        "/ws/tv-sync",
        headers={"origin": "http://127.0.0.1:5173"},
    ) as websocket:
        assert websocket.receive_json()["type"] == "INITIAL_STATE"
        websocket.send_json({"symbol": [], "timeframe": "1h", "exchange": "BINANCE"})
        with pytest.raises(WebSocketDisconnect):
            websocket.receive_json()

    assert (tv_sync_manager.active_symbol, tv_sync_manager.active_timeframe, tv_sync_manager.active_exchange) == before
