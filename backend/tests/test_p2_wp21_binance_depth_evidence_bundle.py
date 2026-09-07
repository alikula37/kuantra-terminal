"""P2-WP21 deterministic evidence bundle and restore contracts."""

import asyncio
import json
import zipfile

from app.services.market_data.binance_depth_attestation import (
    BinanceDepthAttestationStore,
    attest_archive_record,
    generate_operator_key_bundle,
    private_key_from_bundle,
)
from app.services.market_data.binance_depth_attestation_gate import (
    evaluate_binance_depth_attestation_gate,
)
from app.services.market_data.binance_depth_evidence_bundle import (
    create_evidence_bundle,
    restore_evidence_bundle,
    verify_evidence_bundle,
)
from app.services.market_data.binance_depth_key_policy import evaluate_key_rotation_policy
from app.services.market_data.binance_depth_key_registry import BinanceDepthAttestationKeyRegistry
from app.services.market_data.binance_depth_report_archive import BinanceDepthReportArchive
from app.services.market_data.binance_depth_review_record import (
    BinanceDepthOperatorReviewStore,
    create_operator_review_record,
)
from scripts.bundle_binance_depth_evidence import main as bundle_main
from scripts.run_binance_depth_soak import run_fixture_probe


NOW = "2026-09-07T12:00:00Z"
ATTESTED_AT = "2026-09-07T11:59:00Z"
RETENTION_UNTIL = "2027-09-07T12:00:00Z"


def _evidence_case(tmp_path):
    report = asyncio.run(
        run_fixture_probe(symbol="BTCUSDT", storage_root=tmp_path / "soak", max_reconnects=1)
    )
    report = {**report, "mode": "testnet", "environment": "testnet"}
    archive = BinanceDepthReportArchive(tmp_path / "archive")
    record = archive.archive(report)
    bundle = generate_operator_key_bundle()
    key_path = tmp_path / "operator-key.json"
    key_path.write_text(json.dumps(bundle), encoding="utf-8")
    attestation = attest_archive_record(
        record,
        private_key_from_bundle(bundle),
        operator_label="operator-a",
        attested_at=ATTESTED_AT,
    )
    attestations = BinanceDepthAttestationStore(archive)
    attestations.append(attestation)
    registry_path = archive.root / "registry" / "keys.jsonl"
    registry = BinanceDepthAttestationKeyRegistry(registry_path)
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
    review = create_operator_review_record(
        gate,
        private_key_from_bundle(bundle),
        policy_result=policy,
        reviewer_label="operator-a",
        reviewed_at=NOW,
        retention_until=RETENTION_UNTIL,
    )
    BinanceDepthOperatorReviewStore(archive).append(review)
    return archive, registry_path, key_path


def test_bundle_is_deterministic_and_excludes_private_key(tmp_path):
    archive, registry_path, key_path = _evidence_case(tmp_path)
    output = tmp_path / "evidence.zip"
    manifest = create_evidence_bundle(
        archive.root,
        output,
        registry_path=registry_path,
        created_at=NOW,
    )
    first_bytes = output.read_bytes()
    second = create_evidence_bundle(
        archive.root,
        output,
        registry_path=registry_path,
        created_at=NOW,
    )
    assert manifest.bundle_id == second.bundle_id
    assert output.read_bytes() == first_bytes
    assert manifest.file_count >= 7
    with zipfile.ZipFile(output) as bundle:
        names = bundle.namelist()
        assert "registry/keys.jsonl" in names
        assert "operator-key.json" not in names
        assert b"private_key_b64" not in b"".join(bundle.read(name) for name in names)
    assert key_path.exists()


def test_bundle_verification_detects_payload_tamper(tmp_path):
    archive, registry_path, _ = _evidence_case(tmp_path)
    output = tmp_path / "evidence.zip"
    create_evidence_bundle(archive.root, output, registry_path=registry_path, created_at=NOW)
    tampered = tmp_path / "tampered.zip"
    with zipfile.ZipFile(output, "r") as source, zipfile.ZipFile(tampered, "w") as target:
        for name in source.namelist():
            payload = source.read(name)
            if name.endswith("manifest.jsonl"):
                payload += b"tampered"
            target.writestr(name, payload)
    result = verify_evidence_bundle(tampered)
    assert result.valid is False
    assert result.errors


def test_restore_reopens_archive_attestation_review_and_registry(tmp_path):
    archive, registry_path, _ = _evidence_case(tmp_path)
    output = tmp_path / "evidence.zip"
    create_evidence_bundle(archive.root, output, registry_path=registry_path, created_at=NOW)
    restored = tmp_path / "restored"
    result = restore_evidence_bundle(output, restored)
    assert result.valid is True
    restored_archive = BinanceDepthReportArchive(restored)
    assert len(restored_archive.records) == 1
    assert len(BinanceDepthAttestationStore(restored_archive).attestations) == 1
    assert len(BinanceDepthOperatorReviewStore(restored_archive).reviews) == 1
    assert BinanceDepthAttestationKeyRegistry(restored / "registry" / "keys.jsonl").recovery_report()["valid"] is True
    assert not list(restored.rglob("*private*"))


def test_bundle_rejects_private_marker_and_unsafe_path(tmp_path):
    archive, registry_path, _ = _evidence_case(tmp_path)
    output = tmp_path / "evidence.zip"
    create_evidence_bundle(archive.root, output, registry_path=registry_path, created_at=NOW)
    malicious = tmp_path / "malicious.zip"
    with zipfile.ZipFile(output, "r") as source, zipfile.ZipFile(malicious, "w") as target:
        for name in source.namelist():
            target.writestr(name, source.read(name))
        target.writestr("../private.json", b'{"private_key_b64":"secret"}')
    result = verify_evidence_bundle(malicious)
    assert result.valid is False
    assert result.errors


def test_bundle_cli_create_verify_restore(tmp_path):
    archive, registry_path, _ = _evidence_case(tmp_path)
    output = tmp_path / "cli-evidence.zip"
    assert (
        bundle_main(
            [
                "create",
                "--archive-root",
                str(archive.root),
                "--registry",
                str(registry_path),
                "--output",
                str(output),
                "--created-at",
                NOW,
                "--json",
            ]
        )
        == 0
    )
    assert bundle_main(["verify", "--bundle", str(output), "--json"]) == 0
    assert bundle_main(
        [
            "restore",
            "--bundle",
            str(output),
            "--target-root",
            str(tmp_path / "cli-restored"),
            "--json",
        ]
    ) == 0
