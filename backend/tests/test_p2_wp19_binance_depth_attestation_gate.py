"""P2-WP19 review eligibility gate contracts."""

import asyncio

from app.services.market_data.binance_depth_attestation import (
    BinanceDepthAttestationStore,
    attest_archive_record,
    generate_operator_key_bundle,
    private_key_from_bundle,
)
from app.services.market_data.binance_depth_attestation_gate import (
    evaluate_binance_depth_attestation_gate,
)
from app.services.market_data.binance_depth_key_registry import (
    BinanceDepthAttestationKeyRegistry,
    key_id_for_public_key,
)
from app.services.market_data.binance_depth_report_archive import BinanceDepthReportArchive
from scripts.evaluate_binance_depth_attestation_gate import main as gate_main
from scripts.run_binance_depth_soak import run_fixture_probe


def _case(tmp_path, *, mode: str = "testnet", attested_at: str | None = None):
    report = asyncio.run(
        run_fixture_probe(symbol="BTCUSDT", storage_root=tmp_path / "soak", max_reconnects=1)
    )
    if mode == "testnet":
        report = {**report, "mode": "testnet", "environment": "testnet"}
    archive = BinanceDepthReportArchive(tmp_path / "archive")
    record = archive.archive(report)
    bundle = generate_operator_key_bundle()
    attestation = attest_archive_record(
        record,
        private_key_from_bundle(bundle),
        operator_label="operator-a",
        attested_at=attested_at,
    )
    store = BinanceDepthAttestationStore(archive)
    store.append(attestation)
    registry = BinanceDepthAttestationKeyRegistry(tmp_path / "keys.jsonl")
    registry.register(bundle["public_key_b64"], operator_label="operator-a")
    return archive, store, registry, record, attestation


def test_active_testnet_attestation_is_only_review_eligible(tmp_path):
    archive, store, registry, record, attestation = _case(tmp_path)

    result = evaluate_binance_depth_attestation_gate(
        archive,
        store,
        registry,
        record.report_id,
        now="2026-09-07T12:00:00Z",
    )

    assert result.decision == "ELIGIBLE_FOR_REVIEW"
    assert result.signature_valid is True
    assert result.freshness_valid is True
    assert result.source_verified is False
    assert result.execution_authority is False
    assert result.attestation_id == attestation.attestation_id
    assert gate_main(
        [
            "--archive-root",
            str(archive.root),
            "--registry",
            str(registry.path),
            "--report-id",
            record.report_id,
            "--now",
            "2026-09-07T12:00:00Z",
            "--json",
        ]
    ) == 0


def test_offline_fixture_is_rejected_even_with_active_signature(tmp_path):
    archive, store, registry, record, _ = _case(tmp_path, mode="fixture")

    result = evaluate_binance_depth_attestation_gate(
        archive,
        store,
        registry,
        record.report_id,
        now="2026-09-07T12:00:00Z",
    )

    assert result.decision == "REJECTED"
    assert any("not a valid testnet observation" in error for error in result.errors)


def test_revoked_key_rejects_gate_but_signature_remains_valid(tmp_path):
    archive, store, registry, record, attestation = _case(tmp_path)
    registry.revoke(
        key_id_for_public_key(attestation.public_key_b64),
        reason="rotation",
        revoked_at="2026-09-07T11:30:00Z",
    )

    result = evaluate_binance_depth_attestation_gate(
        archive,
        store,
        registry,
        record.report_id,
        now="2026-09-07T12:00:00Z",
    )

    assert result.decision == "REJECTED"
    assert result.signature_valid is True
    assert result.key_status == "REVOKED_KEY"
    assert any("key status is REVOKED_KEY" in error for error in result.errors)


def test_stale_and_future_attestations_fail_freshness(tmp_path):
    archive, store, registry, record, _ = _case(
        tmp_path,
        attested_at="2026-09-05T12:00:00Z",
    )
    stale = evaluate_binance_depth_attestation_gate(
        archive,
        store,
        registry,
        record.report_id,
        now="2026-09-07T12:00:00Z",
        max_age_seconds=3600,
    )
    assert stale.decision == "REJECTED"
    assert stale.freshness_valid is False
    assert any("older than the configured freshness window" in error for error in stale.errors)

    archive2, store2, registry2, record2, _ = _case(
        tmp_path / "future",
        attested_at="2026-09-07T14:00:00Z",
    )
    future = evaluate_binance_depth_attestation_gate(
        archive2,
        store2,
        registry2,
        record2.report_id,
        now="2026-09-07T12:00:00Z",
    )
    assert future.decision == "REJECTED"
    assert future.freshness_valid is False
    assert any("too far in the future" in error for error in future.errors)


def test_multiple_operator_attestations_require_explicit_selection(tmp_path):
    archive, store, registry, record, first = _case(tmp_path)
    second_bundle = generate_operator_key_bundle()
    second = attest_archive_record(
        record,
        private_key_from_bundle(second_bundle),
        operator_label="operator-b",
        attested_at=first.attested_at,
    )
    store.append(second)
    registry.register(second_bundle["public_key_b64"], operator_label="operator-b")

    ambiguous = evaluate_binance_depth_attestation_gate(
        archive,
        store,
        registry,
        record.report_id,
        now="2026-09-07T12:00:00Z",
    )
    assert ambiguous.decision == "REJECTED"
    assert any("multiple attestations match" in error for error in ambiguous.errors)

    selected = evaluate_binance_depth_attestation_gate(
        archive,
        store,
        registry,
        record.report_id,
        attestation_id=second.attestation_id,
        now="2026-09-07T12:00:00Z",
    )
    assert selected.decision == "ELIGIBLE_FOR_REVIEW"
    assert selected.operator_label == "operator-b"
