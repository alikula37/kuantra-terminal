"""Red tests for H03's explicit disabled/degraded market-data boundary."""

import asyncio
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app.api import endpoints
from app.core.config import AppSettings
from app.websocket.binance_client import BinanceStreamClient
from desktop.bridge import DesktopBridge
from desktop.push import PushChannel
from main import create_app


def test_market_data_environment_switch_defaults_on_and_supports_explicit_disable(monkeypatch):
    monkeypatch.delenv("KUANTRA_MARKET_DATA_ENABLED", raising=False)
    assert AppSettings().market_data_enabled is True

    monkeypatch.setenv("KUANTRA_MARKET_DATA_ENABLED", "false")
    assert AppSettings().market_data_enabled is False


def test_disabled_market_data_does_not_schedule_or_connect(monkeypatch):
    connect = AsyncMock(side_effect=AssertionError("disabled market data must not connect"))
    monkeypatch.setattr("app.websocket.binance_client.websockets.connect", connect)
    client = BinanceStreamClient(market_data_enabled=False)

    asyncio.run(client.start())

    assert client.market_data_status == "UNAVAILABLE"
    assert client.is_running is False
    assert client._task is None
    connect.assert_not_awaited()


def test_network_degradation_preserves_last_real_value_without_fabricating_events(monkeypatch):
    client = BinanceStreamClient(market_data_enabled=True)
    client.last_price = 65001.25
    client.last_tick_time = 1_700_000_000.0
    client.event_age_ms = 10.0
    client._set_live()
    sleep = AsyncMock()
    broadcast = AsyncMock()
    monkeypatch.setattr("app.websocket.binance_client.asyncio.sleep", sleep)
    monkeypatch.setattr("app.websocket.binance_client.ws_manager.broadcast", broadcast)

    asyncio.run(client._wait_to_reconnect(duration_seconds=0))

    assert client.market_data_status == "DEGRADED"
    assert client.last_price == 65001.25
    assert client.last_tick_time == 1_700_000_000.0
    assert client.event_age_ms == 10.0
    broadcast.assert_not_awaited()


def test_degraded_transition_publishes_status_only(monkeypatch):
    client = BinanceStreamClient(market_data_enabled=True)
    client._set_degraded()
    broadcast = AsyncMock()
    monkeypatch.setattr("app.websocket.binance_client.ws_manager.broadcast", broadcast)

    asyncio.run(client._broadcast_status())

    broadcast.assert_awaited_once_with(
        {
            "type": "MARKET_DATA_STATUS",
            "symbol": "BTCUSDT",
            "status": "DEGRADED",
            "market_data_enabled": True,
        },
        channel="market_ticks",
    )


def test_disabled_health_ticker_and_websocket_snapshot_are_explicitly_unavailable(monkeypatch):
    monkeypatch.setattr(endpoints.binance_client, "market_data_enabled", False)
    monkeypatch.setattr(endpoints.binance_client, "market_data_status", "UNAVAILABLE")
    monkeypatch.setattr(endpoints.binance_client, "is_running", False)
    monkeypatch.setattr(endpoints.binance_client, "last_price", None)
    monkeypatch.setattr(endpoints.binance_client, "last_tick_time", None)
    monkeypatch.setattr(endpoints.binance_client, "event_age_ms", None)
    monkeypatch.setattr(endpoints.binance_client, "_recalculate_open_positions", lambda price: [])
    client = TestClient(create_app())

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["market_data_status"] == "UNAVAILABLE"
    assert health.json()["market_data"]["enabled"] is False

    ticker = client.get("/api/v1/market/ticker")
    assert ticker.status_code == 200
    assert ticker.json()["status"] == "UNAVAILABLE"
    assert ticker.json()["price"] is None

    cache_status = client.get("/api/v1/market-data/status")
    assert cache_status.status_code == 200
    assert cache_status.json()["live_stream_status"] == "UNAVAILABLE"
    assert cache_status.json()["live_stream_enabled"] is False

    with client.websocket_connect("/api/v1/ws/stream") as websocket:
        snapshot = websocket.receive_json()
    assert snapshot["status"] == "UNAVAILABLE"
    assert snapshot["last_price"] is None


def test_desktop_snapshot_exposes_degraded_status_without_blocking_local_bridge(monkeypatch):
    class InlineRuntime:
        def run(self, coroutine):
            return asyncio.run(coroutine)

    monkeypatch.setattr(endpoints.binance_client, "market_data_enabled", True)
    monkeypatch.setattr(endpoints.binance_client, "market_data_status", "DEGRADED")
    monkeypatch.setattr(endpoints.binance_client, "last_price", None)
    monkeypatch.setattr(endpoints.binance_client, "last_tick_time", None)
    monkeypatch.setattr(endpoints.binance_client, "event_age_ms", None)
    monkeypatch.setattr(endpoints.binance_client, "_recalculate_open_positions", lambda price: [])

    bridge = DesktopBridge(InlineRuntime(), PushChannel())
    snapshot = bridge.stream_open()

    assert snapshot["status"] == "DEGRADED"
    assert snapshot["last_price"] is None


def test_local_csv_preview_remains_available_when_market_data_is_disabled(monkeypatch):
    monkeypatch.setattr(endpoints.binance_client, "market_data_enabled", False)
    monkeypatch.setattr(endpoints.binance_client, "market_data_status", "UNAVAILABLE")
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/journal/preview-csv",
        files={"file": ("trades.csv", b"symbol,side,qty,price,entry_time,pnl,commission\nBTCUSDT,BUY,1,100,2026-09-01T00:00:00Z,0,0\n", "text/csv")},
    )

    assert response.status_code == 200
    assert response.json()["total_rows_parsed"] == 1
