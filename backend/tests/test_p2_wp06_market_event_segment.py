"""P2-WP06 durable single-writer market-event segment contracts."""

import pytest

from app.services.market_data.binance_depth_payload import normalize_snapshot
from app.services.market_data.market_event_envelope import MarketEventChain
from app.services.market_data.market_event_segment import (
    MarketEventSegmentRecoveryError,
    MarketEventSegmentWriter,
)
from app.services.market_data.market_event_envelope import MarketEventIdentityConflict


def _snapshot(quantity: str = "2"):
    return normalize_snapshot(
        {"lastUpdateId": 100, "bids": [["65000", quantity]], "asks": []},
        "BTCUSDT",
    )


def test_segment_appends_fsync_lines_and_recovers_after_restart(tmp_path):
    path = tmp_path / "segments" / "2026-09-06.jsonl"
    chain = MarketEventChain()
    first = chain.append_snapshot(_snapshot())
    writer = MarketEventSegmentWriter(path)

    writer.append(first)
    reopened = MarketEventSegmentWriter(path)
    report = reopened.recovery_report()

    assert report["valid"] is True
    assert report["event_count"] == 1
    assert reopened.head_hash == first.event_hash
    assert path.read_bytes().endswith(b"\n")


def test_duplicate_append_is_idempotent_but_different_content_conflicts(tmp_path):
    path = tmp_path / "events.jsonl"
    chain = MarketEventChain()
    first = chain.append_snapshot(_snapshot())
    writer = MarketEventSegmentWriter(path)
    writer.append(first)

    assert writer.append(first) is first
    conflicting = MarketEventChain().append_snapshot(_snapshot("9"))
    with pytest.raises(MarketEventIdentityConflict, match="reused with different content"):
        writer.append(conflicting)


def test_writer_rejects_wrong_chain_position_without_writing(tmp_path):
    path = tmp_path / "events.jsonl"
    chain = MarketEventChain()
    first = chain.append_snapshot(_snapshot())
    second = MarketEventChain().append_snapshot(
        normalize_snapshot({"lastUpdateId": 101, "bids": [["65000", "2"]], "asks": []}, "BTCUSDT")
    )
    writer = MarketEventSegmentWriter(path)
    writer.append(first)

    with pytest.raises(MarketEventSegmentRecoveryError, match="chain_sequence"):
        writer.append(second)
    assert len(writer.events) == 1
    assert len(path.read_bytes().splitlines()) == 1


def test_corrupt_hash_fails_recovery_and_disables_append(tmp_path):
    path = tmp_path / "events.jsonl"
    chain = MarketEventChain()
    first = chain.append_snapshot(_snapshot())
    path.write_text(__import__("json").dumps({**first.as_dict(), "event_hash": "f" * 64}) + "\n", encoding="utf-8")

    with pytest.raises(MarketEventSegmentRecoveryError, match="event_hash"):
        MarketEventSegmentWriter(path)
    non_strict = MarketEventSegmentWriter(path, strict=False)
    assert non_strict.recovery_report()["valid"] is False
    with pytest.raises(MarketEventSegmentRecoveryError):
        non_strict.append(first)


def test_incomplete_final_line_is_not_silently_truncated(tmp_path):
    path = tmp_path / "events.jsonl"
    chain = MarketEventChain()
    first = chain.append_snapshot(_snapshot())
    writer = MarketEventSegmentWriter(path)
    writer.append(first)
    with path.open("ab") as handle:
        handle.write(b"{\"partial\":true")

    with pytest.raises(MarketEventSegmentRecoveryError, match="incomplete"):
        MarketEventSegmentWriter(path)
