"""P2-WP16 local-first hash archive and manifest recovery contracts."""

import asyncio
import copy
import json

import pytest

from app.services.market_data.binance_depth_report_archive import (
    BinanceDepthReportArchive,
    DepthSoakArchiveError,
)
from scripts.archive_binance_depth_soak_report import main as archive_main
from scripts.run_binance_depth_soak import run_fixture_probe


def _fixture_report(tmp_path):
    return asyncio.run(
        run_fixture_probe(
            symbol="BTCUSDT",
            storage_root=tmp_path / "soak",
            max_reconnects=1,
        )
    )


def test_verified_report_is_hash_archived_and_reopenable(tmp_path):
    report = _fixture_report(tmp_path)
    archive_root = tmp_path / "archive"

    archive = BinanceDepthReportArchive(archive_root)
    first = archive.archive(report)
    second = archive.archive(copy.deepcopy(report))

    assert first == second
    assert archive.record_count == 1
    assert archive.recovery_report()["valid"] is True
    assert (archive_root / first.report_path).is_file()

    reopened = BinanceDepthReportArchive(archive_root)
    assert reopened.record_count == 1
    assert reopened.records[0].report_sha256 == first.report_sha256
    assert reopened.recovery_report()["valid"] is True


def test_unverified_or_tampered_report_is_rejected(tmp_path):
    report = _fixture_report(tmp_path)
    tampered = copy.deepcopy(report)
    tampered["source_verified"] = True
    archive = BinanceDepthReportArchive(tmp_path / "archive")

    with pytest.raises(DepthSoakArchiveError, match="verification failed"):
        archive.archive(tampered)
    assert archive.record_count == 0

    record = archive.archive(report)
    report_path = tmp_path / "archive" / record.report_path
    report_path.write_text("tampered\n", encoding="utf-8")
    with pytest.raises(DepthSoakArchiveError):
        BinanceDepthReportArchive(tmp_path / "archive")


def test_manifest_truth_flag_tamper_fails_recovery(tmp_path):
    archive = BinanceDepthReportArchive(tmp_path / "archive")
    record = archive.archive(_fixture_report(tmp_path))
    manifest = tmp_path / "archive" / "manifest.jsonl"
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["source_verified"] = True
    manifest.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    with pytest.raises(DepthSoakArchiveError, match="truth flags"):
        BinanceDepthReportArchive(tmp_path / "archive")
    assert record.source_verified is False


def test_archive_cli_accepts_valid_fixture_and_rejects_tamper(tmp_path):
    report = _fixture_report(tmp_path)
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    archive_root = tmp_path / "archive"

    assert archive_main([str(report_path), "--archive-root", str(archive_root), "--json"]) == 0
    assert (archive_root / "manifest.jsonl").is_file()

    report["execution_authority"] = True
    report_path.write_text(json.dumps(report), encoding="utf-8")
    assert archive_main([str(report_path), "--archive-root", str(archive_root)]) == 1


def test_archive_manifest_is_append_only_record_count(tmp_path):
    archive = BinanceDepthReportArchive(tmp_path / "archive")
    first = _fixture_report(tmp_path / "first")
    second = _fixture_report(tmp_path / "second")
    archive.archive(first)
    archive.archive(second)

    assert archive.record_count == 2
    assert len((tmp_path / "archive" / "manifest.jsonl").read_text(encoding="utf-8").splitlines()) == 2
