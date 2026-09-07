"""P2-WP13 deterministic disconnect/continuity proof without live network."""

import pytest

from app.services.market_data.binance_depth_ingestor import BinanceDepthIngestor
from app.services.market_data.binance_depth_session import (
    BinanceDepthReconnectPolicy,
    DepthSessionDecision,
)
from app.services.market_data.binance_depth_soak import (
    BinanceDepthSoakHarness,
    DepthFixtureCycle,
)
from app.services.market_data.binance_depth_transport import BinanceDepthTransportConfig
from app.services.market_data.market_event_segments import MarketEventSegmentSet


def _snapshot(last_id: int):
    return {"lastUpdateId": last_id, "bids": [["65000", "2"]], "asks": [["65010", "3"]]}


def _event(first: int, final: int):
    return {"e": "depthUpdate", "s": "BTCUSDT", "U": first, "u": final, "b": [["65000", "1"]], "a": []}


@pytest.mark.asyncio
async def test_disconnect_reconnect_preserves_chain_and_rotated_sink(tmp_path):
    sink = MarketEventSegmentSet(tmp_path / "segments", max_events_per_segment=2)
    ingestor = BinanceDepthIngestor("BTCUSDT", event_sink=sink)
    harness = BinanceDepthSoakHarness(
        ingestor,
        BinanceDepthTransportConfig("BTCUSDT", queue_size=2),
        [
            DepthFixtureCycle(_snapshot(101), (_event(101, 102),), failure_reason="fixture disconnect"),
            DepthFixtureCycle(_snapshot(102), (_event(103, 104),)),
        ],
        policy=BinanceDepthReconnectPolicy(max_reconnects=1, backoff_initial_seconds=0),
    )

    report = await harness.run()

    assert report.decision is DepthSessionDecision.COMPLETED
    assert report.session.reconnects == 1
    assert report.chain_report["valid"] is True
    assert report.persistence_report["valid"] is True
    assert report.persistence_report["event_count"] == 4
    assert report.persistence_report["segment_count"] == 2
    assert report.remaining_fixture_cycles == 0
    assert report.source_verified is False

    reopened = MarketEventSegmentSet(tmp_path / "segments", max_events_per_segment=2)
    assert reopened.recovery_report()["valid"] is True
    assert reopened.event_count == 4
    assert reopened.head_hash == sink.head_hash


@pytest.mark.asyncio
async def test_gap_after_reconnect_is_terminal_and_not_filled(tmp_path):
    sink = MarketEventSegmentSet(tmp_path / "segments", max_events_per_segment=10)
    ingestor = BinanceDepthIngestor("BTCUSDT", event_sink=sink)
    harness = BinanceDepthSoakHarness(
        ingestor,
        BinanceDepthTransportConfig("BTCUSDT"),
        [
            DepthFixtureCycle(_snapshot(101), (_event(101, 102),), failure_reason="fixture disconnect"),
            DepthFixtureCycle(_snapshot(102), (_event(105, 106),)),
        ],
        policy=BinanceDepthReconnectPolicy(max_reconnects=1, backoff_initial_seconds=0),
    )

    report = await harness.run()

    assert report.decision is DepthSessionDecision.RECOVERY_REQUIRED
    assert report.session.attempts == 2
    assert report.persistence_report["event_count"] == 3
    assert report.chain_report["valid"] is True
    assert report.session.gap_event_count == 1
    assert report.source_verified is False


@pytest.mark.asyncio
async def test_fixture_cycle_exhaustion_is_explicit(tmp_path):
    ingestor = BinanceDepthIngestor("BTCUSDT")
    harness = BinanceDepthSoakHarness(
        ingestor,
        BinanceDepthTransportConfig("BTCUSDT"),
        [DepthFixtureCycle(_snapshot(101), failure_reason="disconnect")],
        policy=BinanceDepthReconnectPolicy(max_reconnects=1, backoff_initial_seconds=0),
    )

    report = await harness.run()

    assert report.decision is DepthSessionDecision.EXHAUSTED
    assert report.reason_code == "RECONNECT_BUDGET_EXHAUSTED"
    assert report.remaining_fixture_cycles == 0
