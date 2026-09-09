"""P1-WP27 G0-G2 packaged value-chain audit contracts."""

from __future__ import annotations

import hashlib
import json

import pytest

from desktop.g0_g2_worker import run_audit
from scripts.run_g0_g2_packaged_audit import (
    SYNTHETIC_CSV,
    validate_worker_report,
)


def test_g0_g2_worker_proves_bounded_value_chain_without_user_data(tmp_path):
    fixture = tmp_path / "audit.csv"
    fixture.write_bytes(SYNTHETIC_CSV)

    report = run_audit(fixture)

    assert report["status"] == "PASS"
    assert report["execution"]["artifact_executed"] is False
    assert report["contract"] == {
        "real_data": False,
        "credentials": False,
        "network": False,
        "live_execution": False,
        "production_claim": False,
    }
    assert report["stages"]["clean_preview"]["db_trade_count_before"] == 0
    assert report["stages"]["clean_preview"]["db_trade_count_after"] == 0
    assert report["stages"]["malformed_preview"]["db_trade_count_after"] == 0
    assert report["stages"]["malformed_preview"]["decision"] in {
        "USER_REVIEW_REQUIRED",
        "IMPORT_BLOCKED",
    }
    assert report["stages"]["import"]["imported"] == 1
    assert report["stages"]["evidence_pack"]["read_source"] == "typed_projection"
    assert report["stages"]["exports"]["replay_equal"] is True
    assert report["stages"]["weekly_review"]["initial"]["review_status"] == "LIMITED"
    assert report["stages"]["weekly_review"]["complete"]["review_status"] == "COMPLETED"
    assert report["stages"]["weekly_review"]["reopen"]["review_status"] == "LIMITED"
    assert report["stages"]["weekly_review"]["reopen"]["is_pass"] is False
    assert report["stages"]["weekly_review"]["identity_preserved"] is True
    assert report["scope_guard"]["funding_transfer_schema_added"] is False
    assert report["scope_guard"]["forbidden_modules_loaded"] == []


def test_independent_oracle_rejects_mutated_accounting_or_coverage(tmp_path):
    fixture = tmp_path / "audit.csv"
    fixture.write_bytes(SYNTHETIC_CSV)
    report = run_audit(fixture)
    fixture_sha256 = hashlib.sha256(SYNTHETIC_CSV).hexdigest()

    validate_worker_report(report, fixture_sha256=fixture_sha256, packaged=False)

    mutated = json.loads(json.dumps(report))
    mutated["stages"]["import"]["trade"]["pnl"] = 0.0
    with pytest.raises(ValueError, match="oracle mismatch"):
        validate_worker_report(mutated, fixture_sha256=fixture_sha256, packaged=False)

    mutated = json.loads(json.dumps(report))
    mutated["stages"]["evidence_pack"]["coverage_summary"]["funding_transfer"] = "COMPLETE"
    with pytest.raises(ValueError, match="oracle mismatch"):
        validate_worker_report(mutated, fixture_sha256=fixture_sha256, packaged=False)


def test_independent_oracle_requires_packaged_execution_for_release_audit(tmp_path):
    fixture = tmp_path / "audit.csv"
    fixture.write_bytes(SYNTHETIC_CSV)
    report = run_audit(fixture)

    with pytest.raises(ValueError, match="packaged executable"):
        validate_worker_report(
            report,
            fixture_sha256=hashlib.sha256(SYNTHETIC_CSV).hexdigest(),
            packaged=True,
        )


def test_weekly_reopen_wins_when_decisions_share_a_timestamp(tmp_path, monkeypatch):
    """Ledger sequence, not UUID ordering, defines the latest same-second decision."""

    from app.db.repositories.evidence_ledger_repo import EvidenceLedgerRepository
    from app.services import weekly_review as weekly_review_module
    from app.services.weekly_review import WeeklyReviewService
    from datetime import datetime as real_datetime

    class FixedDateTime(real_datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 9, 9, 12, 0, 0, tzinfo=tz)

    ledger = EvidenceLedgerRepository(str(tmp_path / "same-second.sqlite"))
    ledger.append_event(
        event_type="LegacyTradeImported",
        account_id="local-journal",
        venue="local-journal",
        idempotency_key="wp27-source",
        normalized_payload={
            "trade": {
                "id": "WP27-SAME-SECOND",
                "symbol": "AUDITUSDT",
                "side": "BUY",
                "entry_price": 100.0,
                "exit_price": 102.0,
                "qty": 1.0,
                "entry_time": "2026-09-08T10:00:00Z",
                "exit_time": "2026-09-08T10:05:00Z",
                "status": "CLOSED",
                "pnl": 2.0,
                "commission": 0.1,
            }
        },
        occurred_at="2026-09-08T10:05:00Z",
        received_at="2026-09-08T10:05:00Z",
        adapter_version="wp27-test",
        correlation_id="WP27-SAME-SECOND",
        provenance={
            "import_review": {
                "coverage": {
                    "realized_pnl": "COMPLETE",
                    "commission": "COMPLETE",
                    "funding_transfer": "NOT_AVAILABLE",
                    "market_context": "NOT_AVAILABLE",
                }
            }
        },
    )
    service = WeeklyReviewService(ledger_repo=ledger)
    kwargs = {
        "period_start": "2026-09-08",
        "period_end": "2026-09-09",
        "timezone_name": "UTC",
        "as_of_utc": "2099-01-01T00:00:00Z",
    }
    monkeypatch.setattr(weekly_review_module, "datetime", FixedDateTime)
    initial = service.build_review(**kwargs)
    service.record_decision(initial, decision="COMPLETE")
    service.record_decision(service.build_review(**kwargs), decision="REOPEN")

    assert service.build_review(**kwargs)["review_status"] == "LIMITED"
    assert service.build_review(**kwargs)["completion"]["decision"] == "REOPENED"
