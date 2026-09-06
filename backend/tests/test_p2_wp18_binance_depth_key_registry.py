"""P2-WP18 attestation key registry/revocation contracts."""

import asyncio
import json

import pytest

from app.services.market_data.binance_depth_attestation import (
    BinanceDepthAttestationStore,
    attest_archive_record,
    generate_operator_key_bundle,
    private_key_from_bundle,
)
from app.services.market_data.binance_depth_key_registry import (
    BinanceDepthAttestationKeyRegistry,
    DepthKeyRegistryError,
    key_id_for_public_key,
)
from app.services.market_data.binance_depth_report_archive import BinanceDepthReportArchive
from scripts.archive_binance_depth_soak_report import main as archive_main
from scripts.attest_binance_depth_soak_report import main as attest_main
from scripts.generate_binance_depth_attestation_key import main as key_main
from scripts.manage_binance_depth_keys import main as manage_main
from scripts.run_binance_depth_soak import run_fixture_probe


def _archive_and_attestation(tmp_path):
    report = asyncio.run(
        run_fixture_probe(symbol="BTCUSDT", storage_root=tmp_path / "soak", max_reconnects=1)
    )
    archive = BinanceDepthReportArchive(tmp_path / "archive")
    record = archive.archive(report)
    bundle = generate_operator_key_bundle()
    private_key = private_key_from_bundle(bundle)
    attestation = attest_archive_record(record, private_key, operator_label="operator-a")
    BinanceDepthAttestationStore(archive).append(attestation)
    return archive, record, attestation, bundle


def test_register_audit_revoke_preserves_historical_signature(tmp_path):
    archive, record, attestation, bundle = _archive_and_attestation(tmp_path)
    registry_path = tmp_path / "keys.jsonl"
    registry = BinanceDepthAttestationKeyRegistry(registry_path)
    key_record = registry.register(bundle["public_key_b64"], operator_label="operator-a")

    active = registry.audit(record, attestation)
    assert active.status == "ACTIVE_KEY"
    assert active.signature_valid is True
    assert active.key_id == key_record.key_id

    revoked = registry.revoke(key_record.key_id, reason="operator offboarding")
    assert revoked.status == "REVOKED"
    after_revoke = registry.audit(record, attestation)
    assert after_revoke.status == "REVOKED_KEY"
    assert after_revoke.signature_valid is True
    assert registry.recovery_report()["valid"] is True

    reopened = BinanceDepthAttestationKeyRegistry(registry_path)
    assert reopened.get(key_record.key_id).status == "REVOKED"
    assert reopened.register(bundle["public_key_b64"], operator_label="operator-a").status == "REVOKED"


def test_registry_rejects_metadata_conflict_and_tamper(tmp_path):
    bundle = generate_operator_key_bundle()
    registry_path = tmp_path / "keys.jsonl"
    registry = BinanceDepthAttestationKeyRegistry(registry_path)
    registry.register(bundle["public_key_b64"], operator_label="operator-a")
    with pytest.raises(DepthKeyRegistryError, match="different key metadata"):
        registry.register(bundle["public_key_b64"], operator_label="operator-b")

    event = json.loads(registry_path.read_text(encoding="utf-8"))
    event["operator_label"] = "tampered"
    registry_path.write_text(json.dumps(event) + "\n", encoding="utf-8")
    with pytest.raises(DepthKeyRegistryError):
        BinanceDepthAttestationKeyRegistry(registry_path)


def test_unregistered_key_is_auditable_but_not_registered(tmp_path):
    archive, record, attestation, _ = _archive_and_attestation(tmp_path)
    registry = BinanceDepthAttestationKeyRegistry(tmp_path / "keys.jsonl")

    audit = registry.audit(record, attestation)

    assert audit.status == "UNREGISTERED_KEY"
    assert audit.signature_valid is True
    assert key_id_for_public_key(attestation.public_key_b64) == audit.key_id


def test_registry_cli_roundtrip_and_require_registered_gate(tmp_path):
    key_path = tmp_path / "key.json"
    assert key_main(["--output", str(key_path)]) == 0
    report = asyncio.run(
        run_fixture_probe(symbol="BTCUSDT", storage_root=tmp_path / "soak", max_reconnects=1)
    )
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    archive_root = tmp_path / "archive"
    assert archive_main([str(report_path), "--archive-root", str(archive_root)]) == 0
    report_id = BinanceDepthReportArchive(archive_root).records[0].report_id
    assert (
        attest_main(
            [
                "--archive-root",
                str(archive_root),
                "--report-id",
                report_id,
                "--key-bundle",
                str(key_path),
                "--operator-label",
                "operator-cli",
            ]
        )
        == 0
    )
    registry_path = tmp_path / "keys.jsonl"
    assert (
        manage_main(
            [
                "register",
                "--registry",
                str(registry_path),
                "--key-bundle",
                str(key_path),
                "--operator-label",
                "operator-cli",
            ]
        )
        == 0
    )
    assert manage_main(["audit", "--registry", str(registry_path), "--archive-root", str(archive_root)]) == 0
    key_payload = json.loads(key_path.read_text(encoding="utf-8"))
    key_id = key_id_for_public_key(key_payload["public_key_b64"])
    assert (
        manage_main(
            [
                "revoke",
                "--registry",
                str(registry_path),
                "--key-id",
                key_id,
                "--reason",
                "rotation",
            ]
        )
        == 0
    )
    assert manage_main(
        [
            "audit",
            "--registry",
            str(registry_path),
            "--archive-root",
            str(archive_root),
            "--require-registered",
        ]
    ) == 0
    assert manage_main(
        [
            "audit",
            "--registry",
            str(registry_path),
            "--archive-root",
            str(archive_root),
            "--fail-on-revoked",
        ]
    ) == 1


def test_key_registry_rejects_invalid_reason_and_unknown_key(tmp_path):
    bundle = generate_operator_key_bundle()
    registry = BinanceDepthAttestationKeyRegistry(tmp_path / "keys.jsonl")
    registry.register(bundle["public_key_b64"], operator_label="operator-a")
    with pytest.raises(DepthKeyRegistryError, match="not found"):
        registry.revoke("deadbeefdeadbeef", reason="rotation")
    with pytest.raises(DepthKeyRegistryError, match="revocation_reason"):
        registry.revoke(key_id_for_public_key(bundle["public_key_b64"]), reason="\n")
