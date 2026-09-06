"""P2-WP10 injected async depth transport contracts."""

import asyncio

import pytest

from app.services.market_data.binance_depth_ingestor import BinanceDepthIngestor
from app.services.market_data.binance_depth_transport import (
    BinanceDepthTransport,
    BinanceDepthTransportConfig,
    DepthTransportDecision,
)


def _snapshot(last_id: int = 101):
    return {"lastUpdateId": last_id, "bids": [["65000", "2"]], "asks": [["65010", "3"]]}


def _event(first: int = 101, final: int = 102):
    return {"e": "depthUpdate", "s": "BTCUSDT", "U": first, "u": final, "b": [["65000", "1"]], "a": []}


@pytest.mark.asyncio
async def test_transport_buffers_source_before_delayed_snapshot_and_completes():
    ingestor = BinanceDepthIngestor("BTCUSDT")
    transport = BinanceDepthTransport(ingestor, BinanceDepthTransportConfig("BTCUSDT", queue_size=2))

    async def source():
        yield _event(101, 102)
        yield _event(103, 104)

    async def fetch_snapshot():
        await asyncio.sleep(0.01)
        return _snapshot(101)

    result = await transport.run_once(event_source=source(), snapshot_fetcher=fetch_snapshot)

    assert result.decision is DepthTransportDecision.COMPLETED
    assert result.snapshot is not None
    assert result.snapshot.applied_updates == 2
    assert result.processed_event_count >= 2
    assert ingestor.book.as_dict()["bids"] == [["65000", "1"]]


@pytest.mark.asyncio
async def test_snapshot_fetch_failure_is_explicit_and_does_not_claim_success():
    ingestor = BinanceDepthIngestor("BTCUSDT")
    transport = BinanceDepthTransport(ingestor, BinanceDepthTransportConfig("BTCUSDT"))

    async def source():
        yield _event()

    async def failing_fetch():
        raise OSError("snapshot unavailable")

    result = await transport.run_once(event_source=source(), snapshot_fetcher=failing_fetch)

    assert result.decision is DepthTransportDecision.SOURCE_FAILED
    assert result.reason_code == "SNAPSHOT_FETCH_FAILED"
    assert result.source_verified is False
    assert ingestor.book.as_dict()["status"] == "NO_DATA"


@pytest.mark.asyncio
async def test_event_source_failure_is_not_reported_as_completed():
    ingestor = BinanceDepthIngestor("BTCUSDT")
    transport = BinanceDepthTransport(ingestor, BinanceDepthTransportConfig("BTCUSDT"))

    async def source():
        yield _event(101, 102)
        raise ConnectionError("socket closed")

    result = await transport.run_once(event_source=source(), snapshot_fetcher=lambda: _snapshot(101))

    assert result.decision is DepthTransportDecision.SOURCE_FAILED
    assert result.reason_code == "EVENT_SOURCE_FAILED"
    assert "socket closed" in (result.source_error or "")


@pytest.mark.asyncio
async def test_stop_event_returns_stopped_without_fake_source_verification():
    ingestor = BinanceDepthIngestor("BTCUSDT")
    transport = BinanceDepthTransport(ingestor, BinanceDepthTransportConfig("BTCUSDT", queue_size=1))
    stop_event = asyncio.Event()

    async def source():
        yield _event(101, 102)
        stop_event.set()

    result = await transport.run_once(
        event_source=source(),
        snapshot_fetcher=lambda: _snapshot(101),
        stop_event=stop_event,
    )

    assert result.decision is DepthTransportDecision.STOPPED
    assert result.source_verified is False


def test_transport_config_builds_explicit_safe_binance_urls():
    config = BinanceDepthTransportConfig("btcusdt")

    assert config.symbol == "BTCUSDT"
    assert config.snapshot_url == "https://api.binance.com/api/v3/depth?symbol=BTCUSDT&limit=5000"
    assert config.stream_url == "wss://stream.binance.com:9443/ws/btcusdt@depth@100ms"
    with pytest.raises(ValueError, match="https"):
        BinanceDepthTransportConfig("BTCUSDT", rest_base_url="http://localhost")
