"""P2-WP20 operator review record and key policy contracts."""

import asyncio
import json

import pytest

from app.services.market_data.binance_depth_attestation import (
    BinanceDepthAttestationStore,
    attest_archive_record,
    generate_operator_key_bundle,
    private_key_from_bundle,
)
from app.services.market_data.binance_depth_attestation_gate import (
    evaluate_binance_depth_attestation_gate,
)
from app.services.market_data.binance_depth_key_policy import (
    evaluate_key_rotation_policy,
)
from app.services.market_data.binance_depth_key_registry import (
    BinanceDepthAttestationKeyRegistry,
    key_id_for_public_key,
)
from app.services.market_data.binance_depth_report_archive import BinanceDepthReportArchive
from app.services.market_data.binance_depth_review_record import (
    BinanceDepthOperatorReviewStore,
    DepthReviewRecordError,
    create_operator_review_record,
    verify_operator_review_record,
)
from scripts.record_binance_depth_review import main as review_main
from scripts.run_binance_depth_soak import run_fixture_probe


NOW = "2026-09-07T12:00:00Z"
ATTESTED_AT = "2026-09-07T11:59:00Z"
RETENTION_UNTIL = "2027-09-07T12:00:00Z"


def _case(tmp_path, *, mode: str = "testnet"):
    report = asyncio.run(
        run_fixture_probe(symbol="BTCUSDT", storage_root=tmp_path / "soak", max_reconnects=1)
    )
    if mode == "testnet":
        report = {**report, "mode": "testnet", "environment": "testnet"}
    archive = BinanceDepthReportArchive(tmp_path / "archive")
    record = archive.archive(report)
    bundle = generate_operator_key_bundle()
    key_path = tmp_path / "operator-key.json"
    key_path.write_text(json.dumps(bundle), encoding="utf-8")
    private_key = private_key_from_bundle(bundle)
    attestation = attest_archive_record(
        record,
        private_key,
        operator_label="operator-a",
        attested_at=ATTESTED_AT,
    )
    attestations = BinanceDepthAttestationStore(archive)
    attestations.append(attestation)
    registry = BinanceDepthAttestationKeyRegistry(tmp_path / "keys.jsonl")
    registry.register(
        bundle["public_key_b64"],
        operator_label="operator-a",
        recorded_at="2026-09-01T12:00:00Z",
    )
    gate = evaluate_binance_depth_attestation_gate(
        archive,
        attestations,
        registry,
        record.report_id,
        now=NOW,
    )
    policy = evaluate_key_rotation_policy(registry, now=NOW)
    return archive, record, bundle, key_path, attestations, registry, gate, policy


def test_key_policy_requires_one_fresh_active_key(tmp_path):
    _, _, bundle, _, _, registry, _, _ = _case(tmp_path)

    valid = evaluate_key_rotation_policy(registry, now=NOW)
    assert valid.valid is True
    assert len(valid.active_key_ids) == 1

    stale = evaluate_key_rotation_policy(
        registry,
        now=NOW,
        max_active_age_seconds=3600,
    )
    assert stale.valid is False
    assert any("exceeds maximum age" in error for error in stale.errors)

    second = generate_operator_key_bundle()
    registry.register(
        second["public_key_b64"],
        operator_label="operator-b",
        recorded_at="2026-09-07T11:00:00Z",
    )
    overlap = evaluate_key_rotation_policy(registry, now=NOW)
    assert overlap.valid is False
    assert any("exceeds policy maximum" in error for error in overlap.errors)


def test_review_record_roundtrip_and_strict_tamper_recovery(tmp_path):
    archive, record, bundle, _, _, _, gate, policy = _case(tmp_path)
    assert gate.decision == "ELIGIBLE_FOR_REVIEW"
    review = create_operator_review_record(
        gate,
        private_key_from_bundle(bundle),
        policy_result=policy,
        reviewer_label="reviewer-a",
        reviewed_at=NOW,
        retention_until=RETENTION_UNTIL,
    )
    assert verify_operator_review_record(review) is True
    store = BinanceDepthOperatorReviewStore(archive)
    assert store.append(review).review_id == review.review_id
    reopened = BinanceDepthOperatorReviewStore(archive)
    assert reopened.reviews[0].review_id == review.review_id
    assert reopened.recovery_report()["valid"] is True

    review_path = archive.root / "reviews" / f"review-{review.review_id}.json"
    payload = json.loads(review_path.read_text(encoding="utf-8"))
    payload["reviewer_label"] = "tampered"
    review_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    with pytest.raises(DepthReviewRecordError):
        BinanceDepthOperatorReviewStore(archive)


def test_review_record_rejects_ineligible_gate_and_short_retention(tmp_path):
    _, _, bundle, _, _, _, gate, policy = _case(tmp_path, mode="fixture")
    assert gate.decision == "REJECTED"
    with pytest.raises(DepthReviewRecordError, match="only ELIGIBLE_FOR_REVIEW"):
        create_operator_review_record(
            gate,
            private_key_from_bundle(bundle),
            policy_result=policy,
            reviewer_label="reviewer-a",
            reviewed_at=NOW,
            retention_until=RETENTION_UNTIL,
        )

    _, _, bundle2, _, _, _, eligible_gate, policy2 = _case(tmp_path / "short")
    with pytest.raises(DepthReviewRecordError, match="retention_until"):
        create_operator_review_record(
            eligible_gate,
            private_key_from_bundle(bundle2),
            policy_result=policy2,
            reviewer_label="reviewer-a",
            reviewed_at=NOW,
            retention_until=NOW,
        )


def test_review_cli_requires_registered_active_matching_key(tmp_path):
    archive, record, _, key_path, _, registry, _, _ = _case(tmp_path)
    registry_path = registry.path
    assert (
        review_main(
            [
                "--archive-root",
                str(archive.root),
                "--registry",
                str(registry_path),
                "--report-id",
                record.report_id,
                "--key-bundle",
                str(key_path),
                "--reviewer-label",
                "operator-a",
                "--reviewed-at",
                NOW,
                "--retention-until",
                RETENTION_UNTIL,
                "--json",
            ]
        )
        == 0
    )
    assert len(BinanceDepthOperatorReviewStore(archive).reviews) == 1

    payload = json.loads(key_path.read_text(encoding="utf-8"))
    registry.revoke(
        key_id_for_public_key(payload["public_key_b64"]),
        reason="rotation",
        revoked_at=NOW,
    )
    assert (
        review_main(
            [
                "--archive-root",
                str(archive.root),
                "--registry",
                str(registry_path),
                "--report-id",
                record.report_id,
                "--key-bundle",
                str(key_path),
                "--reviewer-label",
                "operator-a",
                "--reviewed-at",
                NOW,
                "--retention-until",
                RETENTION_UNTIL,
            ]
        )
        == 1
    )


def test_review_store_rejects_report_mismatch(tmp_path):
    archive, _, bundle, _, _, _, gate, policy = _case(tmp_path)
    review = create_operator_review_record(
        gate,
        private_key_from_bundle(bundle),
        policy_result=policy,
        reviewer_label="reviewer-a",
        reviewed_at=NOW,
        retention_until=RETENTION_UNTIL,
    )
    changed = review.__class__(**{**review.__dict__, "report_id": "deadbeefdeadbeef"})
    with pytest.raises(DepthReviewRecordError):
        BinanceDepthOperatorReviewStore(archive).append(changed)
