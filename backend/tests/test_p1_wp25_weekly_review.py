"""P1-WP25 deterministic weekly review and as-of contracts."""

import pytest
from fastapi.testclient import TestClient

from app.api import endpoints
from app.db.repositories.evidence_ledger_repo import EvidenceLedgerRepository
from app.services.weekly_review import WeeklyReviewError, WeeklyReviewService
from main import create_app


def _append_event(ledger, *, event_id, occurred_at, received_at=None, payload=None, provenance=None):
    return ledger.append_event(
        event_type="LegacyTradeImported",
        account_id="local-journal",
        venue="local-journal",
        idempotency_key=event_id,
        normalized_payload=payload or {
            "trade": {
                "id": event_id,
                "symbol": "BTCUSDT",
                "status": "CLOSED",
                "pnl": 1.0,
            }
        },
        occurred_at=occurred_at,
        received_at=received_at or occurred_at,
        adapter_version="wp25-test",
        correlation_id=event_id,
        provenance=provenance or {},
    )


def test_weekly_review_is_deterministic_across_dst_and_as_of(tmp_path):
    ledger = EvidenceLedgerRepository(str(tmp_path / "weekly.sqlite"))
    _append_event(
        ledger,
        event_id="DST-1",
        occurred_at="2026-11-01T04:30:00Z",
        provenance={
            "import_review": {
                "coverage": {
                    "status": "PARTIAL",
                    "commission": "UNKNOWN",
                    "funding_transfer": "NOT_AVAILABLE",
                    "market_context": "NOT_AVAILABLE",
                }
            }
        },
    )
    service = WeeklyReviewService(ledger_repo=ledger)

    first = service.build_review(
        period_start="2026-11-01",
        period_end="2026-11-02",
        timezone_name="America/New_York",
        as_of_utc="2026-11-02T04:00:00Z",
    )
    second = service.build_review(
        period_start="2026-11-01",
        period_end="2026-11-02",
        timezone_name="America/New_York",
        as_of_utc="2026-11-02T04:00:00Z",
    )

    assert first == second
    assert first["period"]["start_utc"] == "2026-11-01T04:00:00Z"
    assert first["period"]["end_utc"] == "2026-11-02T05:00:00Z"
    assert first["review_status"] == "LIMITED"
    assert first["coverage"]["fees"] == "UNKNOWN"
    assert first["coverage"]["funding_transfer"] == "NOT_AVAILABLE"
    assert first["snapshot_sha256"]
    assert first["review_id"] == second["review_id"]


def test_empty_period_is_not_ready_and_cannot_be_completed(tmp_path):
    ledger = EvidenceLedgerRepository(str(tmp_path / "empty.sqlite"))
    service = WeeklyReviewService(ledger_repo=ledger)
    review = service.build_review(
        period_start="2026-09-01",
        period_end="2026-09-08",
        timezone_name="Europe/Istanbul",
        as_of_utc="2026-09-08T12:00:00Z",
    )

    assert review["review_status"] == "NOT_READY"
    assert review["completion_allowed"] is False
    assert review["coverage"]["overall"] == "NOT_AVAILABLE"
    assert review["is_pass"] is False
    with pytest.raises(WeeklyReviewError, match="not ready"):
        service.record_decision(
            review,
            decision="COMPLETE",
            note="must not turn no-data into success",
        )


def test_late_event_marks_review_stale_and_future_rule_is_excluded(tmp_path):
    ledger = EvidenceLedgerRepository(str(tmp_path / "stale.sqlite"))
    _append_event(
        ledger,
        event_id="IN-CUTOFF",
        occurred_at="2026-09-08T10:00:00Z",
        payload={
            "trade": {"id": "TRADE-1", "symbol": "BTCUSDT", "status": "CLOSED", "pnl": 1.0},
            "risk_policy": {
                "policy_id": "future-policy",
                "policy_version": 2,
                "snapshot_sha256": "a" * 64,
                "effective_at_utc": "2026-09-08T12:00:00Z",
            },
        },
    )
    _append_event(
        ledger,
        event_id="AFTER-CUTOFF",
        occurred_at="2026-09-08T11:30:00Z",
        payload={"trade": {"id": "TRADE-1", "symbol": "BTCUSDT", "status": "CLOSED", "pnl": 2.0}},
    )
    _append_event(
        ledger,
        event_id="LATE-CORRECTION",
        occurred_at="2026-09-08T10:30:00Z",
        received_at="2026-09-08T12:30:00Z",
        payload={"trade": {"id": "TRADE-1", "symbol": "BTCUSDT", "status": "CLOSED", "pnl": 3.0}},
    )
    service = WeeklyReviewService(ledger_repo=ledger)
    review = service.build_review(
        period_start="2026-09-08",
        period_end="2026-09-09",
        timezone_name="UTC",
        as_of_utc="2026-09-08T11:00:00Z",
    )

    assert review["review_status"] == "STALE_REVIEW"
    assert review["late_event_count"] == 2
    assert review["excluded_future_rule_count"] == 1
    assert review["applicable_rules"] == []
    assert review["completion_allowed"] is False


def test_review_completion_reuses_journal_review_event_idempotently(tmp_path):
    ledger = EvidenceLedgerRepository(str(tmp_path / "decision.sqlite"))
    _append_event(ledger, event_id="REVIEW-SOURCE", occurred_at="2026-09-08T10:00:00Z")
    service = WeeklyReviewService(ledger_repo=ledger)
    review = service.build_review(
        period_start="2026-09-08",
        period_end="2026-09-09",
        timezone_name="UTC",
        as_of_utc="2026-09-08T12:00:00Z",
    )
    first = service.record_decision(review, decision="COMPLETE", note="Reviewed evidence")
    replay = service.record_decision(review, decision="COMPLETE", note="Reviewed evidence")

    assert first["decision"] == "COMPLETED"
    assert replay["created"] is False
    events = list(ledger.export_events(account_id="local-journal"))
    review_events = [event for event in events if event["event_type"] == "JournalReviewAdded"]
    assert len(review_events) == 1
    assert review_events[0]["normalized_payload"]["review_kind"] == "WEEKLY_REVIEW"
    assert events[0]["event_id"] != review_events[0]["event_id"]


def test_weekly_review_api_keeps_period_and_as_of_explicit(tmp_path, monkeypatch):
    ledger = EvidenceLedgerRepository(str(tmp_path / "api.sqlite"))
    service = WeeklyReviewService(ledger_repo=ledger)
    monkeypatch.setattr(endpoints, "weekly_review_service", service)
    client = TestClient(create_app())
    response = client.get(
        "/api/v1/reviews/weekly",
        params={
            "period_start": "2026-09-01",
            "period_end": "2026-09-08",
            "timezone": "UTC",
            "as_of_utc": "2026-09-08T12:00:00Z",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["period"]["timezone"] == "UTC"
    assert payload["as_of_utc"] == "2026-09-08T12:00:00Z"
    assert payload["review_status"] == "NOT_READY"
