"""P2-WP07 rotated segment manifest and global-chain contracts."""

import json

import pytest

from app.services.market_data.binance_depth_payload import normalize_snapshot
from app.services.market_data.market_event_envelope import MarketEventChain
from app.services.market_data.market_event_segments import (
    MarketEventSegmentSet,
    MarketEventSegmentSetRecoveryError,
)


def _snapshot(last_id: int, quantity: str = "2"):
    return normalize_snapshot(
        {"lastUpdateId": last_id, "bids": [["65000", quantity]], "asks": []},
        "BTCUSDT",
    )


def test_segments_rotate_and_reopen_as_one_global_chain(tmp_path):
    root = tmp_path / "market-events"
    chain = MarketEventChain()
    segment_set = MarketEventSegmentSet(root, max_events_per_segment=2)
    events = [chain.append_snapshot(_snapshot(index)) for index in (100, 101, 102)]

    for event in events:
        segment_set.append(event)
    reopened = MarketEventSegmentSet(root, max_events_per_segment=2)

    assert segment_set.segment_count == 2
    assert segment_set.event_count == 3
    assert segment_set.last_sequence == 3
    assert reopened.recovery_report()["valid"] is True
    assert reopened.segment_count == 2
    assert reopened.head_hash == events[-1].event_hash
    assert [event.chain_sequence for event in reopened.events] == [1, 2, 3]


def test_append_continues_from_manifest_head_after_restart(tmp_path):
    root = tmp_path / "market-events"
    chain = MarketEventChain()
    segment_set = MarketEventSegmentSet(root, max_events_per_segment=2)
    first = chain.append_snapshot(_snapshot(100))
    segment_set.append(first)
    reopened = MarketEventSegmentSet(root, max_events_per_segment=2)
    second = chain.append_snapshot(_snapshot(101))

    appended = reopened.append(second)

    assert appended.chain_sequence == 2
    assert reopened.head_hash == second.event_hash
    assert reopened.recovery_report()["valid"] is True


def test_manifest_tamper_fails_closed(tmp_path):
    root = tmp_path / "market-events"
    chain = MarketEventChain()
    segment_set = MarketEventSegmentSet(root, max_events_per_segment=2)
    segment_set.append(chain.append_snapshot(_snapshot(100)))
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["event_count"] = 999
    manifest_path.write_text(json.dumps(manifest) + "\n", encoding="utf-8")

    with pytest.raises(MarketEventSegmentSetRecoveryError, match="manifest_sha256"):
        MarketEventSegmentSet(root, max_events_per_segment=2)


def test_missing_segment_is_not_reconstructed_from_directory_listing(tmp_path):
    root = tmp_path / "market-events"
    chain = MarketEventChain()
    segment_set = MarketEventSegmentSet(root, max_events_per_segment=1)
    segment_set.append(chain.append_snapshot(_snapshot(100)))
    segment_set.append(chain.append_snapshot(_snapshot(101)))
    (root / "segment-000001.jsonl").unlink()

    with pytest.raises(MarketEventSegmentSetRecoveryError):
        MarketEventSegmentSet(root, max_events_per_segment=1)


def test_duplicate_identity_is_idempotent_across_segments(tmp_path):
    root = tmp_path / "market-events"
    chain = MarketEventChain()
    original = chain.append_snapshot(_snapshot(100))
    segment_set = MarketEventSegmentSet(root, max_events_per_segment=1)
    segment_set.append(original)
    reopened = MarketEventSegmentSet(root, max_events_per_segment=1)

    duplicate = reopened.append(original)

    assert duplicate.event_hash == original.event_hash
    assert reopened.event_count == 1
    assert reopened.segment_count == 1
