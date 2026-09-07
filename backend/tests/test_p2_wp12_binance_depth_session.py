"""P2-WP12 reconnect budget and backoff contracts with no network."""

import asyncio

import pytest

from app.services.market_data.binance_depth_session import (
    BinanceDepthReconnectPolicy,
    BinanceDepthSession,
    DepthSessionDecision,
)
from app.services.market_data.binance_depth_transport import (
    DepthTransportDecision,
    DepthTransportResult,
)


def _cycle(decision: DepthTransportDecision, reason: str = "fixture"):
    return DepthTransportResult(
        decision=decision,
        reason_code=reason,
        snapshot=None,
        events=(),
    )


class _Runner:
    def __init__(self, results, *, stop_after_first=False):
        self.results = list(results)
        self.calls = []
        self.stop_after_first = stop_after_first

    async def run_once(self, *, stop_event=None, max_source_events=None):
        self.calls.append((stop_event, max_source_events))
        result = self.results.pop(0)
        if self.stop_after_first and stop_event is not None:
            stop_event.set()
        return result


@pytest.mark.asyncio
async def test_session_reconnects_once_then_completes_with_explicit_budget():
    runner = _Runner(
        [
            _cycle(DepthTransportDecision.SOURCE_FAILED, "EVENT_SOURCE_FAILED"),
            _cycle(DepthTransportDecision.COMPLETED, "SOURCE_CYCLE_COMPLETED"),
        ]
    )
    session = BinanceDepthSession(
        runner,
        BinanceDepthReconnectPolicy(max_reconnects=1, backoff_initial_seconds=0, max_source_events_per_cycle=3),
    )

    result = await session.run()

    assert result.decision is DepthSessionDecision.COMPLETED
    assert result.attempts == 2
    assert result.reconnects == 1
    assert len(runner.calls) == 2
    assert all(call[1] == 3 for call in runner.calls)
    assert result.source_verified is False


@pytest.mark.asyncio
async def test_session_stops_after_reconnect_budget_without_fake_success():
    runner = _Runner(
        [
            _cycle(DepthTransportDecision.SOURCE_FAILED),
            _cycle(DepthTransportDecision.SNAPSHOT_RETRY_REQUIRED),
        ]
    )
    session = BinanceDepthSession(
        runner,
        BinanceDepthReconnectPolicy(max_reconnects=1, backoff_initial_seconds=0, backoff_max_seconds=0),
    )

    result = await session.run()

    assert result.decision is DepthSessionDecision.EXHAUSTED
    assert result.reason_code == "RECONNECT_BUDGET_EXHAUSTED"
    assert result.attempts == 2
    assert result.reconnects == 1


@pytest.mark.asyncio
async def test_persistence_or_recovery_failure_is_terminal_and_not_retried():
    runner = _Runner([_cycle(DepthTransportDecision.PERSISTENCE_FAILED, "PERSISTENCE_ERROR_BLOCKS_TRANSPORT")])
    session = BinanceDepthSession(runner, BinanceDepthReconnectPolicy(max_reconnects=5, backoff_initial_seconds=0))

    result = await session.run()

    assert result.decision is DepthSessionDecision.PERSISTENCE_FAILED
    assert result.attempts == 1
    assert result.reconnects == 0
    assert len(runner.calls) == 1


@pytest.mark.asyncio
async def test_recovery_retry_is_explicit_and_bounded():
    runner = _Runner(
        [
            _cycle(DepthTransportDecision.RECOVERY_REQUIRED, "INGESTOR_REQUIRES_RECOVERY"),
            _cycle(DepthTransportDecision.COMPLETED, "SOURCE_CYCLE_COMPLETED"),
        ]
    )
    session = BinanceDepthSession(
        runner,
        BinanceDepthReconnectPolicy(
            max_reconnects=1,
            backoff_initial_seconds=0,
            retry_recovery=True,
        ),
    )

    result = await session.run()

    assert result.decision is DepthSessionDecision.COMPLETED
    assert result.attempts == 2
    assert result.reconnects == 1
    assert result.cycles[0].decision is DepthTransportDecision.RECOVERY_REQUIRED


@pytest.mark.asyncio
async def test_stop_event_interrupts_before_cycle_and_during_backoff():
    stop_before = asyncio.Event()
    stop_before.set()
    runner = _Runner([_cycle(DepthTransportDecision.COMPLETED)])
    result = await BinanceDepthSession(runner).run(stop_event=stop_before)
    assert result.decision is DepthSessionDecision.STOPPED
    assert result.reason_code == "STOP_EVENT_SET"
    assert not runner.calls

    stop_during = asyncio.Event()
    runner_with_stop = _Runner([_cycle(DepthTransportDecision.SOURCE_FAILED)], stop_after_first=True)
    result = await BinanceDepthSession(
        runner_with_stop,
        BinanceDepthReconnectPolicy(max_reconnects=2, backoff_initial_seconds=1, backoff_max_seconds=1),
    ).run(stop_event=stop_during)
    assert result.decision is DepthSessionDecision.STOPPED
    assert result.reason_code == "STOP_EVENT_SET_DURING_BACKOFF"
    assert result.reconnects == 1


def test_reconnect_policy_rejects_unbounded_or_inverted_values():
    with pytest.raises(ValueError, match="max_reconnects"):
        BinanceDepthReconnectPolicy(max_reconnects=-1)
    with pytest.raises(ValueError, match="backoff_max_seconds"):
        BinanceDepthReconnectPolicy(backoff_initial_seconds=2, backoff_max_seconds=1)
    with pytest.raises(ValueError, match="max_source_events_per_cycle"):
        BinanceDepthReconnectPolicy(max_source_events_per_cycle=0)
