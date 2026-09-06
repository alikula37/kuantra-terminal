"""P2-WP08 deterministic columnar row batch contracts."""

import pytest

from app.services.market_data.binance_depth_payload import normalize_snapshot
from app.services.market_data.market_event_batch import (
    MarketEventBatchError,
    MarketEventBatchProjector,
)
from app.services.market_data.market_event_envelope import MarketEventChain


def _event(last_update_id: int, bids=None, asks=None):
    snapshot = normalize_snapshot(
        {
            "lastUpdateId": last_update_id,
            "bids": bids if bids is not None else [["65000", "2"]],
            "asks": asks if asks is not None else [["65010", "3"]],
        },
        "BTCUSDT",
    )
    return MarketEventChain().append_snapshot(snapshot)


def test_projector_emits_deterministic_event_and_level_rows():
    envelope = _event(100, bids=[["65000", "2"], ["64990", "1"]])
    batch = MarketEventBatchProjector().project([envelope])

    assert len(batch.event_rows) == 1
    assert len(batch.level_rows) == 3
    assert batch.event_rows[0]["normalized_payload_json"]
    assert batch.level_rows[0]["price_text"] == "65000"
    assert batch.level_rows[0]["side"] == "BID"
    assert batch.source_verified is False
    assert batch.batch_sha256 == MarketEventBatchProjector().project([envelope]).batch_sha256


def test_empty_batch_is_explicit_and_deterministic():
    batch = MarketEventBatchProjector().project([])

    assert batch.event_rows == ()
    assert batch.level_rows == ()
    assert batch.first_chain_sequence is None
    assert batch.last_chain_sequence is None
    assert len(batch.batch_sha256) == 64
    assert batch.to_jsonl() == ""


def test_non_contiguous_envelopes_are_rejected_before_columnar_write():
    first = MarketEventChain().append_snapshot(
        normalize_snapshot({"lastUpdateId": 100, "bids": [], "asks": []}, "BTCUSDT")
    )
    later = MarketEventChain().append_snapshot(normalize_snapshot({"lastUpdateId": 200, "bids": [], "asks": []}, "BTCUSDT"))

    with pytest.raises(MarketEventBatchError, match="contiguous"):
        MarketEventBatchProjector().project([first, later])


def test_event_and_level_bounds_fail_closed_without_truncation():
    envelope = _event(100, bids=[["65000", "2"], ["64990", "1"]])

    with pytest.raises(ValueError, match="max_events"):
        MarketEventBatchProjector(max_events=0)
    with pytest.raises(MarketEventBatchError, match="max_events"):
        MarketEventBatchProjector(max_events=1).project([envelope, envelope])
    with pytest.raises(MarketEventBatchError, match="max_levels"):
        MarketEventBatchProjector(max_levels=2).project([envelope])


def test_malformed_level_shape_is_rejected_even_if_envelope_hash_is_valid():
    envelope = _event(100)
    envelope.normalized_payload["bids"] = [[65000, "2"]]

    with pytest.raises(MarketEventBatchError, match="payload_sha256"):
        MarketEventBatchProjector().project([envelope])
