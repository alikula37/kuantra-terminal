"""P2-WP15 fail-closed soak report verification contracts."""

import asyncio
import copy
import json

from scripts.run_binance_depth_soak import run_fixture_probe
from scripts.verify_binance_depth_soak_report import main
from app.services.market_data.binance_depth_report import (
    LEGACY_REPORT_SCHEMA_VERSION,
    DepthSoakReportVerdict,
    verify_depth_soak_report,
)


def _fixture_report(tmp_path):
    return asyncio.run(
        run_fixture_probe(
            symbol="BTCUSDT",
            storage_root=tmp_path / "storage",
            max_reconnects=1,
        )
    )


def test_fixture_report_is_valid_but_not_production_verified(tmp_path):
    report = _fixture_report(tmp_path)

    verification = verify_depth_soak_report(report, expected_mode="fixture")

    assert verification.ok is True
    assert verification.verdict is DepthSoakReportVerdict.VALID_OFFLINE_FIXTURE
    assert verification.errors == ()
    assert any("source_verified" in warning for warning in verification.warnings)


def test_truth_flag_tampering_is_rejected(tmp_path):
    report = _fixture_report(tmp_path)
    tampered = copy.deepcopy(report)
    tampered["source_verified"] = True

    verification = verify_depth_soak_report(tampered)

    assert verification.ok is False
    assert verification.verdict is DepthSoakReportVerdict.INVALID
    assert any("source_verified" in error for error in verification.errors)


def test_chain_and_durable_mismatch_is_rejected(tmp_path):
    report = _fixture_report(tmp_path)
    tampered = copy.deepcopy(report)
    tampered["chain"]["valid"] = False
    tampered["persistence"]["event_count"] += 1

    verification = verify_depth_soak_report(tampered)

    assert verification.ok is False
    assert any("chain.valid" in error for error in verification.errors)
    assert any("event_count" in error for error in verification.errors)


def test_minimum_duration_and_mode_are_enforced(tmp_path):
    report = _fixture_report(tmp_path)
    too_long = verify_depth_soak_report(report, minimum_elapsed_ms=10_000_000)
    wrong_mode = verify_depth_soak_report(report, expected_mode="testnet")

    assert too_long.ok is False
    assert any("elapsed_ms" in error for error in too_long.errors)
    assert wrong_mode.ok is False
    assert any("expected mode" in error for error in wrong_mode.errors)


def test_stop_during_recovery_backoff_is_not_a_valid_observation(tmp_path):
    report = _fixture_report(tmp_path)
    report["session"] = {
        "decision": "STOPPED",
        "reason_code": "STOP_EVENT_SET_DURING_BACKOFF",
        "attempts": 1,
        "reconnects": 1,
        "processed_event_count": 2,
        "source_verified": False,
        "cycles": [
            {
                "decision": "RECOVERY_REQUIRED",
                "reason_code": "INGESTOR_REQUIRES_RECOVERY",
                "source_verified": False,
            }
        ],
    }

    verification = verify_depth_soak_report(report, expected_mode="fixture")

    assert verification.ok is False
    assert verification.verdict is DepthSoakReportVerdict.INVALID
    assert any("successful terminal cycle" in error for error in verification.errors)


def test_processed_event_count_must_match_cycle_totals(tmp_path):
    report = _fixture_report(tmp_path)
    report["session"]["processed_event_count"] += 1

    verification = verify_depth_soak_report(report, expected_mode="fixture")

    assert verification.ok is False
    assert verification.verdict is DepthSoakReportVerdict.INVALID
    assert any("cycle event totals" in error for error in verification.errors)


def test_continuity_metric_tamper_is_rejected(tmp_path):
    report = _fixture_report(tmp_path)
    report["session"]["continuity"]["gap_event_count"] = 99

    verification = verify_depth_soak_report(report, expected_mode="fixture")

    assert verification.ok is False
    assert verification.verdict is DepthSoakReportVerdict.INVALID
    assert any("gap_event_count" in error for error in verification.errors)


def test_legacy_v1_report_remains_readable_without_new_metrics(tmp_path):
    report = _fixture_report(tmp_path)
    report["schema_version"] = LEGACY_REPORT_SCHEMA_VERSION
    report["session"].pop("continuity")
    for cycle in report["session"]["cycles"]:
        cycle.pop("gap_events")

    verification = verify_depth_soak_report(report, expected_mode="fixture")

    assert verification.ok is True
    assert verification.verdict is DepthSoakReportVerdict.VALID_OFFLINE_FIXTURE
    assert any("legacy V1" in warning for warning in verification.warnings)


def test_verifier_cli_serializes_and_returns_nonzero_for_tamper(tmp_path):
    report = _fixture_report(tmp_path)
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")

    assert main([str(report_path), "--mode", "fixture", "--json"]) == 0
    report["execution_authority"] = True
    report_path.write_text(json.dumps(report), encoding="utf-8")
    assert main([str(report_path), "--mode", "fixture"]) == 1
