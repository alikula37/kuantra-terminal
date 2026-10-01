"""Quote-display truth must not weaken the automatic-close evidence gate."""
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.services.market_data.public_fetcher import PublicMarketDataFetcher
from app.services.quote_refresh import QuoteRefreshService
from app.services.local_tracking_monitor import TrackingMonitor
from backend.tests.test_local_tracking import setup, plan

NOW = datetime(2026, 10, 2, 12, tzinfo=timezone.utc)
TRADE = {"id": "t", "status": "OPEN", "price_source": "binance_public", "price_source_symbol": "BTCUSDT"}


@pytest.mark.asyncio
async def test_gold_candle_is_not_a_live_last_trade():
    fetcher = PublicMarketDataFetcher()
    with patch.object(fetcher, "_fetch_biquote_candles", new=AsyncMock(return_value=[
        {"close": 4200, "timestamp": int(NOW.timestamp() * 1000)}
    ])):
        result = (await fetcher.fetch_quote("XAUUSD", "biquote_public")).as_dict()
    assert result["status"] == "DELAYED"
    assert result["price_kind"] == "CLOSE"
    assert result["timestamp_basis"] == "CANDLE_OPEN"
    assert result["candle_interval"] == "1h"


@pytest.mark.asyncio
async def test_crypto_display_uses_provider_event_time_not_download_time():
    fetcher = PublicMarketDataFetcher()
    event = {"price": "100", "observed_at": (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat(),
             "status": "LIVE", "timestamp_basis": "PROVIDER_EVENT", "provider_event_id": "42",
             "source_id": "binance_public", "source_symbol": "BTCUSDT"}
    with patch.object(fetcher, "fetch_tracking_quote", new=AsyncMock(return_value=event)) as get, \
            patch("httpx.AsyncClient.get", new=AsyncMock(side_effect=AssertionError("real network forbidden"))):
        result = (await fetcher.fetch_quote("BTCUSDT", "binance_public")).as_dict()
    get.assert_awaited_once_with("binance_public", "BTCUSDT")
    assert result["observed_at"] == event["observed_at"]
    assert result["timestamp_basis"] == "PROVIDER_EVENT"
    assert result["status"] == "DELAYED"


@pytest.mark.parametrize("basis,offset,expected", [
    ("PROVIDER_EVENT", 60, "LIVE"), ("PROVIDER_EVENT", 61, "DELAYED"),
    ("PROVIDER_EVENT", -6, "DELAYED"), ("CANDLE_OPEN", 0, "DELAYED"),
    ("REQUEST_TIME", 0, "DELAYED"), ("UNKNOWN", 0, "DELAYED"),
])
def test_live_requires_fresh_provider_event(basis, offset, expected):
    view = QuoteRefreshService._quote_view({"price": 100, "status": "LIVE",
        "timestamp_basis": basis, "observed_at": (NOW - timedelta(seconds=offset)).isoformat()}, NOW)
    assert view["quote_status"] == expected
    assert view["timestamp_basis"] == basis


def test_invalid_time_is_unknown_not_fresh():
    view = QuoteRefreshService._quote_view({"price": 100, "status": "LIVE",
        "timestamp_basis": "PROVIDER_EVENT", "observed_at": "2026-10-02T12:00:00"}, NOW)
    assert view["quote_status"] == "DELAYED"
    assert view["freshness"] == "UNKNOWN"


@pytest.mark.asyncio
async def test_cached_live_price_expires_without_refetch():
    clock = [NOW]
    quote = {"price": 100, "status": "LIVE", "timestamp_basis": "PROVIDER_EVENT",
             "observed_at": (NOW - timedelta(seconds=59)).isoformat()}
    fetcher = type("Fetcher", (), {"fetch_quote": AsyncMock(return_value=quote)})()
    service = QuoteRefreshService(fetcher, clock=lambda: clock[0])
    assert (await service.refresh([TRADE]))["quotes"]["t"]["quote_status"] == "LIVE"
    clock[0] += timedelta(seconds=3)
    assert (await service.refresh([TRADE]))["quotes"]["t"]["quote_status"] == "DELAYED"
    assert fetcher.fetch_quote.await_count == 1
    cached = service.cached_quote(TRADE)
    assert cached["price"] == 100 and cached["stale"] is True


@pytest.mark.asyncio
async def test_display_only_tracking_wait_is_explained_and_bounded(setup):
    _, service, _ = setup
    service.edit("t1", plan(), expected_revision=0)
    fetch = AsyncMock(return_value={"status": "UNAVAILABLE", "reason": "PROVIDER_EVENT_TIME_UNAVAILABLE"})
    monitor = TrackingMonitor(service, fetch)
    await monitor.poll(enabled=True)
    await monitor.poll(enabled=True)
    state = service.get("t1")
    view = monitor.view(state)
    assert view["monitor"]["wait_reason"] == "PROVIDER_EVENT_TIME_UNAVAILABLE"
    assert view["monitor"]["next_poll_in_seconds"] > 45
    assert state["remaining_qty"] == "2" and state["closures"] == []
    assert fetch.await_count == 1


@pytest.mark.asyncio
async def test_refresh_checks_age_after_fetch_not_before_it():
    clock = [NOW]
    async def fetch(*args):
        clock[0] += timedelta(seconds=10)
        return {"status": "LIVE", "price": 100, "timestamp_basis": "PROVIDER_EVENT",
                "observed_at": (clock[0] - timedelta(seconds=1)).isoformat()}
    fetcher = type("Fetcher", (), {"fetch_quote": staticmethod(fetch)})()
    service = QuoteRefreshService(fetcher, clock=lambda: clock[0])
    result = (await service.refresh([TRADE]))["quotes"]["t"]
    assert result["quote_status"] == "LIVE" and result["age_seconds"] == 1


@pytest.mark.asyncio
async def test_rate_limit_on_direct_quote_is_structured_unavailable(monkeypatch):
    from app.api import endpoints
    from app.services.market_data.public_fetcher import TrackingQuoteRateLimit
    monkeypatch.setattr(endpoints.binance_client, "market_data_enabled", True)
    monkeypatch.setattr(endpoints.public_market_fetcher, "fetch_quote", AsyncMock(side_effect=TrackingQuoteRateLimit(60)))
    result = await endpoints.get_market_quote("BTCUSDT", "binance_public")
    assert result["status"] == "UNAVAILABLE" and result["price"] is None
    assert result["reason"] == "PROVIDER_RATE_LIMIT"


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["binance_public", "bybit_public"])
async def test_crypto_event_adapters_keep_provider_time_and_exact_symbol(provider, monkeypatch):
    import httpx
    stamp = int((datetime.now(timezone.utc) - timedelta(seconds=2)).timestamp() * 1000)
    async def get(self, url, **kwargs):
        assert kwargs["params"]["symbol"] == "BTCUSDT"
        payload = ([{"id": 7, "price": "120", "time": stamp}] if provider == "binance_public"
                   else {"retCode": 0, "result": {"list": [{"symbol": "BTCUSDT", "execId": "7", "price": "120", "time": stamp}]}})
        return httpx.Response(200, request=httpx.Request("GET", url), json=payload)
    monkeypatch.setattr(httpx.AsyncClient, "get", get)
    result = (await PublicMarketDataFetcher().fetch_quote("BTCUSDT", provider)).as_dict()
    assert result["status"] == "LIVE" and result["timestamp_basis"] == "PROVIDER_EVENT"
    assert result["source_id"] == provider and result["source_symbol"] == "BTCUSDT"
    assert datetime.fromisoformat(result["observed_at"]).timestamp() * 1000 == stamp
