"""P2-WP17 Ed25519 operator attestation and sidecar store contracts."""

import asyncio
import base64
import copy
import json
from dataclasses import replace

import pytest

from app.services.market_data.binance_depth_attestation import (
    BinanceDepthAttestationStore,
    DepthSoakAttestationError,
    attest_archive_record,
    generate_operator_key_bundle,
    private_key_from_bundle,
    verify_attestation,
)
from app.services.market_data.binance_depth_report_archive import BinanceDepthReportArchive
from scripts.archive_binance_depth_soak_report import main as archive_main
from scripts.attest_binance_depth_soak_report import main as attest_main
from scripts.generate_binance_depth_attestation_key import main as key_main
from scripts.run_binance_depth_soak import run_fixture_probe


def _archive_with_fixture(tmp_path):
    report = asyncio.run(
        run_fixture_probe(symbol="BTCUSDT", storage_root=tmp_path / "soak", max_reconnects=1)
    )
    archive = BinanceDepthReportArchive(tmp_path / "archive")
    record = archive.archive(report)
    return archive, record


def test_attestation_signs_archived_hash_and_reopens_store(tmp_path):
    archive, record = _archive_with_fixture(tmp_path)
    private_key = private_key_from_bundle(generate_operator_key_bundle())
    attestation = attest_archive_record(
        record,
        private_key,
        operator_label="operator-a",
        attested_at="2026-09-07T12:00:00Z",
    )

    assert verify_attestation(record, attestation) is True
    store = BinanceDepthAttestationStore(archive)
    assert store.append(attestation) == attestation
    assert store.append(copy.deepcopy(attestation)) == attestation
    reopened = BinanceDepthAttestationStore(BinanceDepthReportArchive(tmp_path / "archive"))
    assert len(reopened.attestations) == 1
    assert reopened.recovery_report()["valid"] is True


def test_signature_or_truth_tamper_is_rejected(tmp_path):
    archive, record = _archive_with_fixture(tmp_path)
    private_key = private_key_from_bundle(generate_operator_key_bundle())
    attestation = attest_archive_record(record, private_key, operator_label="operator-a")
    tampered_signature = replace(
        attestation,
        signature_b64=base64.b64encode(b"x" * 64).decode("ascii"),
    )
    assert verify_attestation(record, tampered_signature) is False
    with pytest.raises(DepthSoakAttestationError, match="does not verify"):
        BinanceDepthAttestationStore(archive).append(tampered_signature)

    tampered_truth = replace(attestation, execution_authority=True)
    assert verify_attestation(record, tampered_truth) is False


def test_attestation_file_tamper_fails_strict_recovery(tmp_path):
    archive, record = _archive_with_fixture(tmp_path)
    private_key = private_key_from_bundle(generate_operator_key_bundle())
    attestation = attest_archive_record(record, private_key, operator_label="operator-a")
    store = BinanceDepthAttestationStore(archive)
    store.append(attestation)
    file_path = tmp_path / "archive" / "attestations" / f"attestation-{attestation.attestation_id}.json"
    payload = json.loads(file_path.read_text(encoding="utf-8"))
    payload["operator_label"] = "tampered"
    file_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    with pytest.raises(DepthSoakAttestationError):
        BinanceDepthAttestationStore(BinanceDepthReportArchive(tmp_path / "archive"))


def test_multiple_operator_attestations_are_distinct_and_valid(tmp_path):
    archive, record = _archive_with_fixture(tmp_path)
    store = BinanceDepthAttestationStore(archive)
    first = attest_archive_record(
        record,
        private_key_from_bundle(generate_operator_key_bundle()),
        operator_label="operator-a",
        attested_at="2026-09-07T12:00:00Z",
    )
    second = attest_archive_record(
        record,
        private_key_from_bundle(generate_operator_key_bundle()),
        operator_label="operator-b",
        attested_at="2026-09-07T12:01:00Z",
    )
    store.append(first)
    store.append(second)
    assert first.attestation_id != second.attestation_id
    assert len(store.attestations) == 2
    assert store.recovery_report()["valid"] is True


def test_key_and_attestation_clis_are_explicit_and_reproducible(tmp_path):
    key_path = tmp_path / "operator-key.json"
    assert key_main(["--output", str(key_path)]) == 0
    assert key_main(["--output", str(key_path)]) == 1

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
                "--attested-at",
                "2026-09-07T12:00:00Z",
            ]
        )
        == 0
    )
    assert (archive_root / "attestations.jsonl").is_file()
