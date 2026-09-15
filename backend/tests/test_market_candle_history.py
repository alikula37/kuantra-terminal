"""Bounded market-chart history: provider pagination, freshness and deep ranges."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db.repositories.candles_repo import CandlesRepository
from app.services.market_data.public_fetcher import PublicMarketDataFetcher


def _response(*, status_code: int, payload=None, headers=None):
    response = MagicMock(status_code=status_code)
    response.json.return_value = payload
    response.headers = headers or {}
    response.text = ""
    return response


def _klines(timestamps):
    return [
        [ts, "100", "101", "99", "100.5", "10", ts + 59_999, "0", 0, "0", "0", "0"]
        for ts in timestamps
    ]


def _yahoo_payload(timestamps):
    return {
        "chart": {
            "result": [{
                "timestamp": timestamps,
                "indicators": {"quote": [{
                    "open": [100.0 for _ in timestamps],
                    "high": [101.0 for _ in timestamps],
                    "low": [99.0 for _ in timestamps],
                    "close": [100.5 for _ in timestamps],
                    "volume": [1000.0 for _ in timestamps],
                }]},
            }],
        },
    }


@pytest.mark.asyncio
async def test_crypto_history_walks_backwards_in_bounded_pages():
    fetcher = PublicMarketDataFetcher()
    calls = []

    async def fake_get(_url, *args, **kwargs):
        params = kwargs.get("params", {})
        calls.append(dict(params))
        end_time = params.get("endTime")
        if end_time is None:
            return _response(status_code=200, payload=_klines([2_000_000, 2_060_000]))
        return _response(status_code=200, payload=_klines([1_880_000]))

    with patch("httpx.AsyncClient.get", new=AsyncMock(side_effect=fake_get)):
        candles = await fetcher.fetch_crypto_candles(
            "BTCUSDT", interval="1m", limit=2, start_time=1_000_000
        )

    assert [c["timestamp"] for c in candles] == [1_880_000, 2_000_000, 2_060_000]
    assert len(calls) == 2
    assert calls[0]["startTime"] == 1_000_000
    assert calls[1]["endTime"] == 2_000_000 - 1
    assert calls[1]["limit"] == 2


@pytest.mark.asyncio
async def test_crypto_history_stops_at_a_short_page():
    fetcher = PublicMarketDataFetcher()
    calls = []

    async def fake_get(_url, *args, **kwargs):
        calls.append(dict(kwargs.get("params", {})))
        if len(calls) == 1:
            return _response(status_code=200, payload=_klines([5_000_000, 5_060_000, 5_120_000]))
        return _response(status_code=200, payload=_klines([4_880_000]))

    with patch("httpx.AsyncClient.get", new=AsyncMock(side_effect=fake_get)):
        candles = await fetcher.fetch_crypto_candles(
            "BTCUSDT", interval="1m", limit=3, start_time=1_000_000
        )

    assert len(calls) == 2
    assert [c["timestamp"] for c in candles] == [4_880_000, 5_000_000, 5_060_000, 5_120_000]


@pytest.mark.asyncio
async def test_yahoo_history_uses_period_range_and_clamps_intraday():
    fetcher = PublicMarketDataFetcher()
    captured = {}

    async def fake_get(_url, *args, **kwargs):
        captured.update(kwargs.get("params", {}))
        return _response(status_code=200, payload=_yahoo_payload([1_700_000_000, 1_700_086_400]))

    now_ms = int(time.time() * 1000)
    requested_start = now_ms - 400 * 86_400_000  # older than Yahoo's 5m window
    with patch("httpx.AsyncClient.get", new=AsyncMock(side_effect=fake_get)):
        candles = await fetcher.fetch_macro_candles(
            "SPY", interval="5m", start_time=requested_start, end_time=now_ms
        )

    assert candles
    assert "period1" in captured and "period2" in captured
    assert "range" not in captured
    clamped_start_ms = captured["period1"] * 1000
    assert clamped_start_ms >= now_ms - 60 * 86_400_000 - 60_000
    assert clamped_start_ms > requested_start


@pytest.mark.asyncio
async def test_yahoo_daily_history_keeps_the_requested_lookback():
    fetcher = PublicMarketDataFetcher()
    captured = {}

    async def fake_get(_url, *args, **kwargs):
        captured.update(kwargs.get("params", {}))
        return _response(status_code=200, payload=_yahoo_payload([1_400_000_000, 1_700_000_000]))

    now_ms = int(time.time() * 1000)
    requested_start = now_ms - 20 * 365 * 86_400_000
    with patch("httpx.AsyncClient.get", new=AsyncMock(side_effect=fake_get)):
        await fetcher.fetch_macro_candles("SPY", interval="1d", start_time=requested_start, end_time=now_ms)

    assert captured["period1"] == requested_start // 1000


@pytest.mark.asyncio
async def test_stale_cache_triggers_fetch_and_fresh_cache_does_not(tmp_path):
    repo = CandlesRepository(str(tmp_path / "candles.sqlite"))
    now_ms = int(time.time() * 1000)
    hour = 3_600_000

    stale = [
        {"timestamp": now_ms - 10 * hour + index * hour, "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}
        for index in range(3)
    ]
    repo.save_candles_batch(stale, symbol="BTCUSDT", timeframe="1h")

    refreshed = [
        {"timestamp": now_ms - 2 * hour + index * hour, "open": 2, "high": 2, "low": 2, "close": 2, "volume": 2}
        for index in range(3)
    ]
    provider = AsyncMock(return_value=refreshed)
    with patch.object(repo, "_get_connection", wraps=repo._get_connection):
        with patch(
            "app.services.market_data.public_fetcher.public_market_fetcher.fetch_crypto_candles",
            new=provider,
        ):
            candles = await repo.get_or_fetch_candles("BTCUSDT", "1h", limit=3)
    assert provider.await_count == 1
    assert candles[-1]["close"] == 2

    # The window we just stored is current; a second read stays cache-only.
    provider.reset_mock()
    with patch(
        "app.services.market_data.public_fetcher.public_market_fetcher.fetch_crypto_candles",
        new=provider,
    ):
        candles = await repo.get_or_fetch_candles("BTCUSDT", "1h", limit=3)
    assert provider.await_count == 0
    assert candles[-1]["close"] == 2


@pytest.mark.asyncio
async def test_history_query_fetches_missing_older_bars(tmp_path):
    repo = CandlesRepository(str(tmp_path / "candles.sqlite"))
    now_ms = int(time.time() * 1000)
    hour = 3_600_000

    repo.save_candles_batch(
        [{"timestamp": now_ms - index * hour, "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}
         for index in range(3)],
        symbol="BTCUSDT",
        timeframe="1h",
    )
    older = [
        {"timestamp": now_ms - 20 * hour + index * hour, "open": 5, "high": 5, "low": 5, "close": 5, "volume": 5}
        for index in range(3)
    ]
    provider = AsyncMock(return_value=older)
    with patch(
        "app.services.market_data.public_fetcher.public_market_fetcher.fetch_crypto_candles",
        new=provider,
    ):
        candles = await repo.get_or_fetch_candles(
            "BTCUSDT", "1h", limit=3, start_ts=now_ms - 20 * hour, end_ts=now_ms - 19 * hour
        )
    assert provider.await_count == 1
    expected = [c["timestamp"] for c in older if c["timestamp"] <= now_ms - 19 * hour]
    assert [c["timestamp"] for c in candles] == expected
