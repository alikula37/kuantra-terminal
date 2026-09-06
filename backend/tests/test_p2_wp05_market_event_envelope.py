"""P2-WP05 canonical market event envelope and hash-chain contracts."""

import pytest

from app.services.market_data.binance_depth_payload import normalize_snapshot, normalize_update
from app.services.market_data.binance_depth_sequence import BinanceDepthSequenceValidator
from app.services.market_data.binance_depth_sequence import DepthSequenceDecision
from app.services.market_data.market_event_envelope import (
    GENESIS_HASH,
    MarketEventChain,
    MarketEventEnvelopeError,
    MarketEventIdentityConflict,
)


def _snapshot(bid_qty: str = "2"):
    return normalize_snapshot(
        {"lastUpdateId": 100, "bids": [["65000", bid_qty]], "asks": [["65010", "3"]]},
        "BTCUSDT",
    )


def _update():
    raw = {"e": "depthUpdate", "s": "BTCUSDT", "U": 101, "u": 102, "b": [["65000", "1.5"]], "a": []}
    update = normalize_update(raw, "BTCUSDT")
    validator = BinanceDepthSequenceValidator("BTCUSDT")
    validator.load_snapshot({"lastUpdateId": 100})
    return update, validator.accept_delta(raw)


def test_snapshot_and_sequence_approved_update_form_a_verified_chain_shape():
    chain = MarketEventChain()
    snapshot = chain.append_snapshot(_snapshot())
    update, decision = _update()
    delta = chain.append_update(update, decision)

    report = chain.verify()
    assert snapshot.chain_sequence == 1
    assert snapshot.prev_hash == GENESIS_HASH
    assert delta.chain_sequence == 2
    assert delta.prev_hash == snapshot.event_hash
    assert snapshot.provenance["source_verified"] is False
    assert delta.provenance["sequence_decision"] == "APPLIED"
    assert report["valid"] is True
    assert report["event_count"] == 2


def test_duplicate_source_identity_is_idempotent_and_different_content_conflicts():
    chain = MarketEventChain()
    first = chain.append_snapshot(_snapshot())
    duplicate = chain.append_snapshot(_snapshot())

    assert duplicate is first
    assert len(chain.events) == 1
    with pytest.raises(MarketEventIdentityConflict):
        chain.append_snapshot(_snapshot("9"))


def test_unapproved_sequence_decision_cannot_enter_canonical_chain():
    chain = MarketEventChain()
    update, decision = _update()
    gap = decision.__class__(
        decision=DepthSequenceDecision.GAP_DETECTED,
        state=decision.state,
        reason_code="UPDATE_ID_GAP",
        last_update_id=100,
        event_first_update_id=105,
        event_final_update_id=106,
        requires_snapshot=True,
    )

    with pytest.raises(MarketEventEnvelopeError, match="only APPLIED"):
        chain.append_update(update, gap)
    assert chain.events == ()


def test_same_payload_on_two_chains_has_same_fingerprint_and_hashes():
    first_chain = MarketEventChain()
    second_chain = MarketEventChain()
    first = first_chain.append_snapshot(_snapshot())
    second = second_chain.append_snapshot(_snapshot())
    update, decision = _update()
    first_delta = first_chain.append_update(update, decision)
    second_delta = second_chain.append_update(update, decision)

    assert first.payload_sha256 == second.payload_sha256
    assert first.event_hash == second.event_hash
    assert first_delta.payload_sha256 == second_delta.payload_sha256
    assert first_delta.event_hash == second_delta.event_hash


def test_chain_verifier_detects_payload_mutation_without_repairing_it():
    chain = MarketEventChain()
    envelope = chain.append_snapshot(_snapshot())
    envelope.normalized_payload["bids"][0][1] = "999"

    report = chain.verify()

    assert report["valid"] is False
    assert any("payload_sha256 mismatch" in error for error in report["errors"])


def test_update_identity_requires_matching_sequence_final_id():
    chain = MarketEventChain()
    update, decision = _update()
    bad = decision.__class__(
        decision=DepthSequenceDecision.APPLIED,
        state=decision.state,
        reason_code="CONTIGUOUS_UPDATE",
        last_update_id=103,
        event_first_update_id=101,
        event_final_update_id=103,
    )

    with pytest.raises(MarketEventEnvelopeError, match="does not match"):
        chain.append_update(update, bad)


def test_chain_can_rehydrate_from_valid_durable_events():
    original = MarketEventChain()
    snapshot = original.append_snapshot(_snapshot())
    update, decision = _update()
    delta = original.append_update(update, decision)

    restored = MarketEventChain.from_events((snapshot, delta))

    assert restored.events == (snapshot, delta)
    assert restored.verify()["valid"] is True
