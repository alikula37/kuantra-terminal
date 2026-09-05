"""Regression coverage for the P0-WP02 market-data truth contract."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from main import create_app
from app.api import endpoints
from app.services.execution.ccxt_engine import CCXTExecutionEngine
from app.websocket.binance_client import BinanceStreamClient
from desktop.bridge import DesktopBridge
from desktop.push import PushChannel


def test_binance_client_starts_without_fabricated_market_data():
    client = BinanceStreamClient()

    assert client.last_price is None
    assert client.last_tick_time is None
    assert client.event_age_ms is None


def test_combined_stream_url_and_envelope_parsing_uses_measured_event_age(monkeypatch):
    client = BinanceStreamClient("BTCUSDT")
    broadcast = AsyncMock()
    monkeypatch.setattr("app.websocket.binance_client.ws_manager.broadcast", broadcast)
    monkeypatch.setattr("app.websocket.binance_client.compliance_engine.evaluate_compliance", lambda positions: {"overall_status": "COMPLIANT"})
    monkeypatch.setattr("app.websocket.binance_client.sqlite_driver.get_open_trades", lambda: [])
    monkeypatch.setattr("app.websocket.binance_client.time.time", lambda: 1_700_000_000.01)

    asyncio.run(client._handle_message({
        "stream": "btcusdt@trade",
        "data": {"e": "trade", "p": "65001.25", "q": "0.42", "E": 1_700_000_000_000, "m": False},
    }))

    assert client._stream_url() == "wss://stream.binance.com:9443/stream?streams=btcusdt@trade/btcusdt@kline_1m"
    assert client.last_price == 65001.25
    assert client.last_tick_time == 1_700_000_000.0
    assert client.event_age_ms == 10.0
    tick_payload = broadcast.await_args_list[0].args[0]
    assert tick_payload["event_age_ms"] == 10.0
    assert tick_payload["side"] == "BUY"
    assert "latency_ms" not in tick_payload


@pytest.mark.parametrize(
    ("buyer_is_market_maker", "expected_taker_side"),
    [(False, "BUY"), (True, "SELL"), (None, "UNKNOWN"), ("false", "UNKNOWN")],
)
def test_binance_trade_flag_maps_only_boolean_values_to_aggressor_side(buyer_is_market_maker, expected_taker_side):
    assert BinanceStreamClient._taker_side(buyer_is_market_maker) == expected_taker_side


def test_reconnect_wait_emits_no_market_events(monkeypatch):
    client = BinanceStreamClient()
    broadcast = AsyncMock()
    sleep = AsyncMock()
    monkeypatch.setattr("app.websocket.binance_client.ws_manager.broadcast", broadcast)
    monkeypatch.setattr("app.websocket.binance_client.asyncio.sleep", sleep)

    asyncio.run(client._wait_to_reconnect(duration_seconds=10))

    sleep.assert_awaited_once_with(10)
    broadcast.assert_not_awaited()


def test_no_data_snapshot_preserves_positions_and_marks_price_derived_fields_null(monkeypatch):
    client = BinanceStreamClient()
    monkeypatch.setattr("app.websocket.binance_client.sqlite_driver.get_open_trades", lambda: [{
        "id": "OPEN-1", "symbol": "BTCUSDT", "side": "BUY", "entry_price": 64000.0,
        "qty": 0.1, "stop_loss": 63000.0, "take_profit": 66000.0, "entry_time": "2026-09-05T00:00:00Z",
    }])

    positions = client._recalculate_open_positions(None)

    assert len(positions) == 1
    assert positions[0]["current_price"] is None
    assert positions[0]["unrealized_pnl"] is None
    assert positions[0]["r_multiple"] is None


def test_market_ticker_and_websocket_snapshot_report_no_data(monkeypatch):
    monkeypatch.setattr(endpoints.binance_client, "last_price", None)
    monkeypatch.setattr(endpoints.binance_client, "last_tick_time", None)
    monkeypatch.setattr(endpoints.binance_client, "event_age_ms", None)
    monkeypatch.setattr(endpoints.binance_client, "_recalculate_open_positions", lambda price: [{"id": "OPEN-1", "current_price": None, "unrealized_pnl": None}])
    client = TestClient(create_app())

    ticker = client.get("/api/v1/market/ticker")
    assert ticker.status_code == 200
    assert ticker.json() == {
        "symbol": "BTCUSDT", "price": None, "event_age_ms": None, "timestamp": None, "status": "NO_DATA",
    }

    with client.websocket_connect("/api/v1/ws/stream") as websocket:
        snapshot = websocket.receive_json()
    assert snapshot["status"] == "NO_DATA"
    assert snapshot["last_price"] is None
    assert snapshot["open_positions"] == [{"id": "OPEN-1", "current_price": None, "unrealized_pnl": None}]

    monkeypatch.setattr(endpoints.binance_client, "last_price", 65001.25)
    monkeypatch.setattr(endpoints.binance_client, "last_tick_time", 1_700_000_000.0)
    monkeypatch.setattr(endpoints.binance_client, "event_age_ms", 10.0)
    live_ticker = client.get("/api/v1/market/ticker")

    assert live_ticker.json() == {
        "symbol": "BTCUSDT", "price": 65001.25, "event_age_ms": 10.0,
        "timestamp": 1_700_000_000_000, "status": "LIVE",
    }


def test_desktop_snapshot_carries_no_data_without_dropping_positions(monkeypatch):
    class InlineRuntime:
        def run(self, coroutine):
            return asyncio.run(coroutine)

    push = PushChannel()
    bridge = DesktopBridge(InlineRuntime(), push)
    monkeypatch.setattr(endpoints.binance_client, "last_price", None)
    monkeypatch.setattr(endpoints.binance_client, "last_tick_time", None)
    monkeypatch.setattr(endpoints.binance_client, "event_age_ms", None)
    monkeypatch.setattr(
        endpoints.binance_client,
        "_recalculate_open_positions",
        lambda price: [{"id": "OPEN-1", "current_price": None, "unrealized_pnl": None}],
    )

    try:
        snapshot = bridge.stream_open()
    finally:
        from app.websocket.connection_manager import ws_manager
        ws_manager.detach(push)

    assert snapshot["status"] == "NO_DATA"
    assert snapshot["last_price"] is None
    assert snapshot["open_positions"] == [{"id": "OPEN-1", "current_price": None, "unrealized_pnl": None}]


@pytest.mark.parametrize("price", [None, 0, float("nan"), float("inf")])
def test_paper_order_without_finite_positive_price_is_rejected_without_persistence(monkeypatch, price):
    persist_trade = MagicMock()
    monkeypatch.setattr("app.services.execution.ccxt_engine.sync_pipeline.record_and_sync_trade", persist_trade)

    result = CCXTExecutionEngine().create_order(symbol="BTCUSDT", side="BUY", qty=0.1, price=price, mode="PAPER")

    assert result["success"] is False
    assert result["status"] == "REJECTED"
    assert result["reason"].startswith("ORDER_REJECTED_PRICE_UNAVAILABLE")
    persist_trade.assert_not_called()
