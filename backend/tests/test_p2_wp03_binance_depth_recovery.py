"""P2-WP03 bounded snapshot/event-buffer recovery contracts."""

from app.services.market_data.binance_depth_recovery import (
    BinanceDepthRecoveryCoordinator,
    DepthRecoveryDecision,
    DepthRecoveryState,
)


def _event(first: int, final: int, *, previous: int | None = None):
    payload = {"e": "depthUpdate", "s": "BTCUSDT", "U": first, "u": final, "b": [], "a": []}
    if previous is not None:
        payload["pu"] = previous
    return payload


def test_buffered_events_replay_after_snapshot_and_live_events_continue():
    coordinator = BinanceDepthRecoveryCoordinator("BTCUSDT", max_buffer_events=4)

    assert coordinator.ingest_event(_event(101, 102)).decision is DepthRecoveryDecision.BUFFERED
    assert coordinator.ingest_event(_event(103, 104)).buffered_events == 2

    applied = coordinator.apply_snapshot({"lastUpdateId": 101})
    live = coordinator.ingest_event(_event(105, 106))

    assert applied.decision is DepthRecoveryDecision.SNAPSHOT_APPLIED
    assert applied.replayed_events == 2
    assert applied.dropped_stale_events == 0
    assert applied.last_update_id == 104
    assert coordinator.state is DepthRecoveryState.LIVE
    assert live.decision is DepthRecoveryDecision.LIVE_APPLIED
    assert live.last_update_id == 106


def test_snapshot_behind_first_event_is_retryable_without_dropping_buffer():
    coordinator = BinanceDepthRecoveryCoordinator("BTCUSDT")
    coordinator.ingest_event(_event(101, 102))

    retry = coordinator.apply_snapshot({"lastUpdateId": 99})

    assert retry.decision is DepthRecoveryDecision.SNAPSHOT_RETRY_REQUIRED
    assert retry.buffered_events == 1
    assert coordinator.state is DepthRecoveryState.AWAITING_SNAPSHOT
    assert coordinator.apply_snapshot({"lastUpdateId": 101}).replayed_events == 1


def test_stale_buffered_events_are_discarded_before_bridge_replay():
    coordinator = BinanceDepthRecoveryCoordinator("BTCUSDT")
    coordinator.ingest_event(_event(90, 100))
    coordinator.ingest_event(_event(101, 102))

    result = coordinator.apply_snapshot({"lastUpdateId": 100})

    assert result.decision is DepthRecoveryDecision.SNAPSHOT_APPLIED
    assert result.dropped_stale_events == 1
    assert result.replayed_events == 1
    assert result.last_update_id == 102


def test_live_gap_requires_explicit_new_buffer_cycle_and_snapshot():
    coordinator = BinanceDepthRecoveryCoordinator("BTCUSDT")
    coordinator.apply_snapshot({"lastUpdateId": 100})
    coordinator.ingest_event(_event(101, 102))

    gap = coordinator.ingest_event(_event(105, 106))
    blocked = coordinator.ingest_event(_event(107, 108))
    coordinator.start_buffering()
    coordinator.ingest_event(_event(201, 202))
    recovered = coordinator.apply_snapshot({"lastUpdateId": 201})

    assert gap.decision is DepthRecoveryDecision.GAP_DETECTED
    assert blocked.decision is DepthRecoveryDecision.RECOVERY_REQUIRED
    assert recovered.decision is DepthRecoveryDecision.SNAPSHOT_APPLIED
    assert recovered.last_update_id == 202
    assert coordinator.state is DepthRecoveryState.LIVE


def test_buffer_overflow_clears_buffer_and_never_drops_silently():
    coordinator = BinanceDepthRecoveryCoordinator("BTCUSDT", max_buffer_events=2)
    coordinator.ingest_event(_event(101, 101))
    coordinator.ingest_event(_event(102, 102))

    overflow = coordinator.ingest_event(_event(103, 103))

    assert overflow.decision is DepthRecoveryDecision.BUFFER_OVERFLOW
    assert overflow.reason_code == "EVENT_BUFFER_LIMIT_EXCEEDED"
    assert overflow.buffered_events == 0
    assert overflow.requires_snapshot is True
    assert coordinator.state is DepthRecoveryState.RECOVERY_REQUIRED


def test_invalid_buffered_event_is_rejected_before_snapshot():
    coordinator = BinanceDepthRecoveryCoordinator("BTCUSDT")

    rejected = coordinator.ingest_event({"s": "ETHUSDT", "U": 101, "u": 102})

    assert rejected.decision is DepthRecoveryDecision.REJECTED
    assert rejected.requires_snapshot is True
    assert coordinator.state is DepthRecoveryState.RECOVERY_REQUIRED
