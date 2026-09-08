"""P1-WP19 account-event, coverage and immutable-correction contracts."""

from decimal import Decimal

from app.db.repositories.evidence_ledger_repo import EvidenceLedgerRepository
from app.services.account_reconciliation import (
    AccountReconciliationService,
)


def _row(event_type: str, event_id: str, amount: str = "1.25", **extra):
    return {
        "event_type": event_type,
        "id": event_id,
        "amount": amount,
        "currency": "USDT",
        "timestamp": "2026-09-08T10:00:00Z",
        **extra,
    }


def test_account_event_kinds_are_distinct_and_decimal_safe(tmp_path):
    service = AccountReconciliationService(EvidenceLedgerRepository(str(tmp_path / "ledger.sqlite")))
    records, rejected = service.normalize_events(
        "BINANCE",
        [
            _row("funding", "FUND-1"),
            _row("transfer", "TRANSFER-1", "-10"),
            _row("trade_fee", "FEE-1", "0.01"),
            _row("rebate", "REBATE-1", "-0.02"),
        ],
        account_id="acct-1",
        source_exchange_id="binance_futures",
        market_type="swap",
    )

    assert rejected == []
    assert [record.event_kind for record in records] == [
        "FUNDING",
        "TRANSFER",
        "TRADE_FEE",
        "REBATE",
    ]
    assert records[1].amount == Decimal("-10")
    assert records[1].payload()["amount"] == "-10"
    assert records[1].payload()["numeric_encoding"] == "DECIMAL_STRING_V1"
    assert records[1].payload()["numeric_units"]["amount"] == "CURRENCY:USDT"
    assert records[2].ledger_event_type == "FeeAdjusted"
    assert records[3].ledger_event_type == "FeeAdjusted"


def test_missing_opening_coverage_never_becomes_zero_or_flat_pnl(tmp_path):
    service = AccountReconciliationService(EvidenceLedgerRepository(str(tmp_path / "ledger.sqlite")))
    records, rejected = service.normalize_events(
        "BINANCE",
        [_row("funding", "FUND-1"), _row("transfer", "TRANSFER-1", "-10")],
        account_id="acct-1",
    )
    assert rejected == []

    report = service.reconcile(records, coverage={"events_complete": True})

    assert report["status"] == "NOT_AVAILABLE"
    assert report["realized_pnl"] is None
    assert report["unrealized_pnl"] is None
    assert report["cash_movement_by_kind"]["FUNDING"]["USDT"] == "1.25"
    assert report["cash_movement_by_kind"]["TRANSFER"]["USDT"] == "-10"
    assert "OPENING_BALANCE_MISSING" in report["coverage"]["reasons"]
    assert "OPENING_POSITION_MISSING" in report["coverage"]["reasons"]


def test_cash_movement_does_not_merge_into_realized_or_unrealized_pnl(tmp_path):
    service = AccountReconciliationService(EvidenceLedgerRepository(str(tmp_path / "ledger.sqlite")))
    records, _ = service.normalize_events(
        "BINANCE",
        [_row("funding", "FUND-1"), _row("trade_fee", "FEE-1", "0.05")],
        account_id="acct-1",
    )

    report = service.reconcile(
        records,
        opening_balance={"USDT": "1000"},
        opening_positions=[],
        coverage={"events_complete": True},
    )

    assert report["status"] == "PARTIAL"
    assert report["realized_pnl"] is None
    assert report["unrealized_pnl"] is None
    assert report["cash_movement_by_kind"]["FUNDING"]["USDT"] == "1.25"
    assert report["cash_movement_by_kind"]["TRADE_FEE"]["USDT"] == "0.05"
    assert "REALIZED_PNL_COVERAGE_MISSING" in report["coverage"]["reasons"]
    assert "UNREALIZED_PNL_COVERAGE_MISSING" in report["coverage"]["reasons"]


def test_liquidation_and_adl_are_explicitly_unsupported(tmp_path):
    service = AccountReconciliationService(EvidenceLedgerRepository(str(tmp_path / "ledger.sqlite")))
    records, rejected = service.normalize_events(
        "OKX",
        [_row("liquidation", "LIQ-1"), _row("adl", "ADL-1")],
        account_id="acct-1",
    )
    assert rejected == []
    assert {record.event_kind for record in records} == {"LIQUIDATION", "ADL"}
    assert all(record.account_event_status == "UNSUPPORTED" for record in records)

    report = service.reconcile(records, coverage={"events_complete": True})

    assert report["status"] == "NOT_AVAILABLE"
    assert {item["type"] for item in report["discrepancies"]} == {"UNSUPPORTED_ACCOUNT_EVENT"}
    assert {item["event_kind"] for item in report["discrepancies"]} == {"LIQUIDATION", "ADL"}
    assert report["realized_pnl"] is None

    missing_amount, rejected_missing_amount = service.normalize_events(
        "OKX",
        [{"event_type": "liquidation", "id": "LIQ-NO-AMOUNT", "timestamp": "2026-09-08T10:00:00Z"}],
        account_id="acct-1",
    )
    assert rejected_missing_amount == []
    assert missing_amount[0].amount is None
    assert missing_amount[0].account_event_status == "UNSUPPORTED"


def test_correction_is_new_immutable_evidence_with_lineage_and_idempotency(tmp_path):
    ledger = EvidenceLedgerRepository(str(tmp_path / "ledger.sqlite"))
    original = ledger.append_event(
        event_type="FeeAdjusted",
        account_id="acct-1",
        venue="BINANCE",
        idempotency_key="original-fee-1",
        normalized_payload={"account_event": {"event_kind": "TRADE_FEE", "amount": "0.10"}},
        occurred_at="2026-09-08T10:00:00Z",
        adapter_version="fixture-v1",
        correlation_id="FEE-ORIGINAL",
        provenance={"source": "fixture"},
    )
    service = AccountReconciliationService(ledger)
    records, rejected = service.normalize_events(
        "BINANCE",
        [_row(
            "manual_correction",
            "CORR-1",
            "0.08",
            corrects_event_id=original["event_id"],
            effective_at="2026-09-08T12:00:00Z",
        )],
        account_id="acct-1",
    )
    assert rejected == []

    first = service.persist_records(records, source_bytes=b"correction-fixture-v1")
    second = service.persist_records(
        records,
        source_bytes=b"correction-fixture-v1",
        source_name="renamed-correction-fixture",
    )

    assert first["created_count"] == 1
    assert second["created_count"] == 0
    events = list(ledger.export_events(account_id="acct-1"))
    assert len(events) == 2
    correction = next(event for event in events if event["event_type"] == "TradeCorrected")
    assert correction["causation_id"] == original["event_id"]
    assert correction["provenance"]["corrects_event_id"] == original["event_id"]
    assert correction["normalized_payload"]["account_event"]["amount"] == "0.08"
    assert ledger.get_event(original["event_id"])["normalized_payload"]["account_event"]["amount"] == "0.10"


def test_correction_requires_existing_target_and_source_identity_is_strict(tmp_path):
    service = AccountReconciliationService(EvidenceLedgerRepository(str(tmp_path / "ledger.sqlite")))
    missing_target, rejected_target = service.normalize_events(
        "BINANCE",
        [_row("manual_correction", "CORR-MISSING")],
        account_id="acct-1",
    )
    assert missing_target == []
    assert "corrects_event_id" in rejected_target[0]["reason"]

    mismatched_identity, rejected_identity = service.normalize_events(
        "BINANCE",
        [_row("funding", "FUND-1")],
        account_id="acct-1",
        source_exchange_id="binance_futures",
        market_type="spot",
    )
    assert mismatched_identity == []
    assert "market type" in rejected_identity[0]["reason"]


def test_same_external_id_is_separate_across_accounts_but_collision_within_identity(tmp_path):
    service = AccountReconciliationService(EvidenceLedgerRepository(str(tmp_path / "ledger.sqlite")))
    first, _ = service.normalize_events("BINANCE", [_row("funding", "SAME-ID")], account_id="acct-a")
    second, _ = service.normalize_events("BINANCE", [_row("funding", "SAME-ID")], account_id="acct-b")
    conflicting, _ = service.normalize_events(
        "BINANCE", [_row("funding", "SAME-ID", "2.50")], account_id="acct-a"
    )

    assert service.reconcile([*first, *second])["status"] == "NOT_AVAILABLE"
    report = service.reconcile([*first, *conflicting])
    assert report["status"] == "NOT_AVAILABLE"
    assert any(item["type"] == "ACCOUNT_EVENT_ID_COLLISION" for item in report["discrepancies"])


def test_funding_and_transfer_do_not_claim_unapproved_ledger_event_support(tmp_path):
    ledger = EvidenceLedgerRepository(str(tmp_path / "ledger.sqlite"))
    service = AccountReconciliationService(ledger)
    records, rejected = service.normalize_events(
        "BINANCE",
        [_row("funding", "FUND-1"), _row("transfer", "TRANSFER-1", "-10"), _row("trade_fee", "FEE-1", "0.01")],
        account_id="acct-1",
    )
    assert rejected == []

    report = service.persist_records(records, source_bytes=b"account-fixture-v1")

    assert report["status"] == "PARTIAL"
    assert report["created_count"] == 1
    assert report["skipped_count"] == 2
    assert {item["reason"] for item in report["skipped"]} == {"SCHEMA_EVENT_TYPE_PENDING"}
    stored = list(ledger.export_events(account_id="acct-1"))
    assert [event["event_type"] for event in stored] == ["FeeAdjusted"]
