"""P2-WP04 Binance depth payload and venue-book projection contracts."""

import pytest

from app.services.market_data.binance_depth_payload import (
    BinanceDepthBook,
    DepthBookDecision,
    DepthPayloadError,
    normalize_snapshot,
    normalize_update,
)
from app.services.market_data.binance_depth_sequence import BinanceDepthSequenceValidator


def _update(first: int, final: int, *, previous: int | None = None, bids=None, asks=None):
    payload = {
        "e": "depthUpdate",
        "s": "BTCUSDT",
        "U": first,
        "u": final,
        "b": bids if bids is not None else [],
        "a": asks if asks is not None else [],
    }
    if previous is not None:
        payload["pu"] = previous
    return payload


def test_decimal_normalization_preserves_exact_payload_and_optional_times():
    update = normalize_update(
        _update(101, 102, bids=[["65000.1000", "1.2300"]], asks=[["65001", "0"]])
        | {"E": 1700000000000, "T": 1699999999999},
        "BTCUSDT",
    )

    assert update.as_dict()["b"] == [["65000.1", "1.23"]]
    assert update.as_dict()["a"] == [["65001", "0"]]
    assert update.event_time_ms == 1700000000000
    assert update.transaction_time_ms == 1699999999999
    assert update.as_dict()["source_verified"] is False


def test_book_snapshot_and_sequence_checked_update_are_atomic():
    snapshot = normalize_snapshot(
        {"lastUpdateId": 100, "bids": [["65000", "2"]], "asks": [["65010", "3"]]},
        "BTCUSDT",
    )
    update = normalize_update(
        _update(101, 102, bids=[["65000", "0"], ["64990", "1.5"]], asks=[["65010", "4"]]),
        "BTCUSDT",
    )
    sequence = BinanceDepthSequenceValidator("BTCUSDT")
    sequence.load_snapshot({"lastUpdateId": 100})
    decision = sequence.accept_delta(_update(101, 102))
    book = BinanceDepthBook("BTCUSDT")

    book.load_snapshot(snapshot)
    applied = book.apply_update(update, decision)
    view = book.as_dict()

    assert applied.decision is DepthBookDecision.UPDATE_APPLIED
    assert applied.changed_levels == 2
    assert applied.removed_levels == 1
    assert view["bids"] == [["64990", "1.5"]]
    assert view["asks"] == [["65010", "4"]]
    assert view["best_bid"] == "64990"
    assert view["best_ask"] == "65010"
    assert view["source_verified"] is False


def test_sequence_rejection_never_mutates_venue_book():
    book = BinanceDepthBook("BTCUSDT")
    book.load_snapshot(normalize_snapshot({"lastUpdateId": 100, "bids": [["65000", "2"]], "asks": []}, "BTCUSDT"))
    update = normalize_update(_update(105, 106, bids=[["65000", "0"]]), "BTCUSDT")
    sequence = BinanceDepthSequenceValidator("BTCUSDT")
    sequence.load_snapshot({"lastUpdateId": 100})
    gap = sequence.accept_delta(_update(105, 106))

    rejected = book.apply_update(update, gap)

    assert rejected.decision is DepthBookDecision.REJECTED
    assert rejected.reason_code == "SEQUENCE_NOT_APPLIED"
    assert book.as_dict()["bids"] == [["65000", "2"]]
    assert book.last_update_id == 100


def test_payload_validation_rejects_duplicates_wrong_symbol_and_non_finite_values():
    with pytest.raises(DepthPayloadError, match="duplicate"):
        normalize_snapshot({"lastUpdateId": 1, "bids": [["1", "1"], ["1.0", "2"]], "asks": []}, "BTCUSDT")
    with pytest.raises(DepthPayloadError, match="symbol"):
        normalize_update(_update(1, 1) | {"s": "ETHUSDT"}, "BTCUSDT")
    with pytest.raises(DepthPayloadError, match="finite"):
        normalize_update(_update(1, 1, bids=[["NaN", "1"]]), "BTCUSDT")


def test_book_requires_snapshot_and_rejects_mismatched_sequence_event():
    book = BinanceDepthBook("BTCUSDT")
    update = normalize_update(_update(101, 102), "BTCUSDT")
    validator = BinanceDepthSequenceValidator("BTCUSDT")
    validator.load_snapshot({"lastUpdateId": 100})
    sequence = validator.accept_delta(_update(101, 102))

    before_snapshot = book.apply_update(update, sequence)
    book.load_snapshot(normalize_snapshot({"lastUpdateId": 100, "bids": [], "asks": []}, "BTCUSDT"))
    mismatch = book.apply_update(normalize_update(_update(101, 103), "BTCUSDT"), sequence)

    assert before_snapshot.reason_code == "SNAPSHOT_REQUIRED"
    assert mismatch.reason_code == "SEQUENCE_EVENT_ID_MISMATCH"


def test_zero_quantity_snapshot_levels_are_not_present_and_output_is_deterministic():
    book = BinanceDepthBook("BTCUSDT")
    book.load_snapshot(
        normalize_snapshot(
            {"lastUpdateId": 10, "bids": [["2", "0"], ["1.0", "3.00"]], "asks": [["3", "4"]]},
            "BTCUSDT",
        )
    )

    assert book.as_dict(depth=None)["bids"] == [["1", "3"]]
    assert book.as_dict(depth=1)["asks"] == [["3", "4"]]
