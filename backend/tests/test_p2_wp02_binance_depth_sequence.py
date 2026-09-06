"""P2-WP02 Binance snapshot/diff sequence truth contracts."""

from app.services.market_data.binance_depth_sequence import (
    BinanceDepthSequenceValidator,
    DepthSequenceDecision,
    DepthSequenceState,
)


def _event(first: int, final: int, *, previous: int | None = None, symbol: str = "BTCUSDT"):
    payload = {"e": "depthUpdate", "s": symbol, "U": first, "u": final, "b": [], "a": []}
    if previous is not None:
        payload["pu"] = previous
    return payload


def test_snapshot_bridge_and_contiguous_spot_events_are_applied():
    validator = BinanceDepthSequenceValidator("BTCUSDT")

    snapshot = validator.load_snapshot({"lastUpdateId": 100, "bids": [], "asks": []})
    assert snapshot.decision is DepthSequenceDecision.SNAPSHOT_ACCEPTED
    assert snapshot.state is DepthSequenceState.READY

    first = validator.accept_delta(_event(99, 101))
    second = validator.accept_delta(_event(102, 104))

    assert first.decision is DepthSequenceDecision.APPLIED
    assert second.decision is DepthSequenceDecision.APPLIED
    assert second.last_update_id == 104
    assert validator.state is DepthSequenceState.LIVE


def test_futures_previous_update_id_is_checked_after_initial_bridge():
    validator = BinanceDepthSequenceValidator("BTCUSDT")
    validator.load_snapshot({"lastUpdateId": 200})

    assert validator.accept_delta(_event(201, 202, previous=199)).accepted
    applied = validator.accept_delta(_event(203, 205, previous=202))

    assert applied.decision is DepthSequenceDecision.APPLIED
    assert applied.last_update_id == 205


def test_stale_events_are_ignored_without_changing_sequence():
    validator = BinanceDepthSequenceValidator("BTCUSDT")
    validator.load_snapshot({"lastUpdateId": 100})
    validator.accept_delta(_event(101, 102))

    stale = validator.accept_delta(_event(100, 102))

    assert stale.decision is DepthSequenceDecision.STALE_IGNORED
    assert stale.last_update_id == 102
    assert validator.state is DepthSequenceState.LIVE


def test_gap_is_fail_closed_and_requires_a_fresh_snapshot():
    validator = BinanceDepthSequenceValidator("BTCUSDT")
    validator.load_snapshot({"lastUpdateId": 100})
    validator.accept_delta(_event(101, 102))

    gap = validator.accept_delta(_event(105, 106))
    after_gap = validator.accept_delta(_event(107, 108))

    assert gap.decision is DepthSequenceDecision.GAP_DETECTED
    assert gap.reason_code == "UPDATE_ID_GAP"
    assert gap.requires_snapshot is True
    assert gap.last_update_id == 102
    assert validator.state is DepthSequenceState.GAP
    assert after_gap.decision is DepthSequenceDecision.RECOVERY_REQUIRED
    assert after_gap.last_update_id == 102


def test_previous_update_mismatch_is_a_gap_even_when_ranges_overlap():
    validator = BinanceDepthSequenceValidator("BTCUSDT")
    validator.load_snapshot({"lastUpdateId": 100})
    validator.accept_delta(_event(101, 102, previous=100))

    mismatch = validator.accept_delta(_event(102, 103, previous=99))

    assert mismatch.decision is DepthSequenceDecision.GAP_DETECTED
    assert mismatch.reason_code == "PREVIOUS_UPDATE_ID_MISMATCH"
    assert mismatch.last_update_id == 102


def test_malformed_or_wrong_symbol_event_is_rejected_and_never_applied():
    validator = BinanceDepthSequenceValidator("BTCUSDT")
    validator.load_snapshot({"lastUpdateId": 100})

    wrong_symbol = validator.accept_delta(_event(101, 102, symbol="ETHUSDT"))
    malformed = BinanceDepthSequenceValidator("BTCUSDT")
    malformed.load_snapshot({"lastUpdateId": 100})
    bad_ids = malformed.accept_delta({"s": "BTCUSDT", "U": 102, "u": 101})

    assert wrong_symbol.decision is DepthSequenceDecision.REJECTED
    assert wrong_symbol.reason_code.startswith("INVALID_EVENT:")
    assert wrong_symbol.requires_snapshot is True
    assert validator.state is DepthSequenceState.GAP
    assert bad_ids.decision is DepthSequenceDecision.REJECTED
    assert "final update ID precedes" in bad_ids.reason_code


def test_invalid_snapshot_does_not_replace_last_valid_snapshot():
    validator = BinanceDepthSequenceValidator("BTCUSDT")
    validator.load_snapshot({"lastUpdateId": 100})

    invalid = validator.load_snapshot({"lastUpdateId": -1})

    assert invalid.decision is DepthSequenceDecision.REJECTED
    assert validator.last_update_id == 100
    assert validator.state is DepthSequenceState.READY
