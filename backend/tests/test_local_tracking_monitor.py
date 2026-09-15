import pytest
from app.services.local_tracking_monitor import TrackingMonitor
from backend.tests.test_local_tracking import setup, plan, quote


@pytest.mark.asyncio
async def test_shared_poll_and_disable(setup):
    driver, service, _ = setup
    service.edit("t1", plan(), expected_revision=0)
    driver.record_trade_with_evidence(
        {"id": "t2", "symbol": "BTCUSDT", "side": "BUY", "entry_price": 100, "qty": 2,
         "qty_unit": "BASE"},
        event_type="IntentRecorded", idempotency_key="create2", local_tracking_plan=plan())
    calls = []
    async def fetch(source, symbol):
        calls.append((source, symbol))
        return quote(110)
    monitor = TrackingMonitor(service, fetch)
    await monitor.poll(enabled=False)
    assert calls == []
    await monitor.poll(enabled=True)
    assert len(calls) == 1
    assert service.get("t1")["remaining_qty"] == "1"
    assert service.get("t2")["remaining_qty"] == "1"


@pytest.mark.asyncio
async def test_failure_backoff_preserves_position(setup):
    _, service, _ = setup
    service.edit("t1", plan(), expected_revision=0)
    calls = []
    async def fail(*args):
        calls.append(args)
        raise OSError("network denied")
    monitor = TrackingMonitor(service, fail)
    await monitor.poll(enabled=True)
    await monitor.poll(enabled=True)
    assert len(calls) == 1
    assert service.get("t1")["remaining_qty"] == "2"
    assert monitor.view(service.get("t1"))["tracking_status"] == "WAITING_QUOTE"


@pytest.mark.asyncio
async def test_provider_trade_time_not_download_time(monkeypatch):
    import httpx
    from app.services.market_data.public_fetcher import public_market_fetcher
    async def get(self, url, **kwargs):
        assert kwargs["params"] == {"symbol": "BTCUSDT", "limit": 1}
        return httpx.Response(200, request=httpx.Request("GET", url), json=[
            {"id": 12, "price": "123.45", "time": 1700000000000}])
    monkeypatch.setattr(httpx.AsyncClient, "get", get)
    result = await public_market_fetcher.fetch_tracking_quote("binance_public", "BTCUSDT")
    assert result["observed_at"] == "2023-11-14T22:13:20+00:00"
    assert result["timestamp_basis"] == "PROVIDER_EVENT"
    assert result["provider_event_id"] == "12"
    result = await public_market_fetcher.fetch_tracking_quote("biquote_public", "XAUUSD")
    assert result["status"] == "UNAVAILABLE"


def test_binance_tick_does_not_price_another_instrument(monkeypatch):
    from app.websocket.binance_client import BinanceStreamClient
    from app.websocket import binance_client as module
    trades = [{"id": "x", "symbol": "XAUUSD", "entry_price": 100, "qty": 1,
               "side": "BUY", "entry_time": "2026-01-01", "price_source": "biquote_public", "price_source_symbol": "XAUUSD"},
              {"id": "b", "symbol": "BTCUSDT", "entry_price": 100, "qty": 1,
               "side": "BUY", "entry_time": "2026-01-01", "price_source": "binance_public", "price_source_symbol": "BTCUSDT"}]
    monkeypatch.setattr(module.sqlite_driver, "get_open_trades", lambda: trades)
    values = BinanceStreamClient("BTCUSDT")._recalculate_open_positions(110)
    assert values[0]["current_price"] is None
    assert values[0]["unrealized_pnl"] is None
    assert values[1]["unrealized_pnl"] == 10
