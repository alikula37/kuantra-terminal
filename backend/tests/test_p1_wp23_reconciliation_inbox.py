"""P1-WP23 red/green contracts for the reconciliation inbox boundary."""

import hashlib

import pytest
from fastapi.testclient import TestClient

from app.api import endpoints
from app.db.repositories.evidence_ledger_repo import EvidenceLedgerRepository
from app.db.repositories.evidence_projection_repo import EvidenceTradeProjectionRepository
from app.db.sqlite_driver import SQLiteDriver
from app.services.broker_import_service import BrokerImportService
from app.services.reconciliation_inbox import (
    ReconciliationDecisionConflict,
    ReconciliationInboxService,
)
from app.services.trade_read_adapter import TradeReadAdapter
from main import create_app


def _source_review(*, status="PARTIAL", decision="USER_REVIEW_REQUIRED"):
    return {
        "status": status,
        "decision": decision,
        "source_type": "CSV_JOURNAL_SNAPSHOT",
        "source_file_sha256": "a" * 64,
        "reconciliation": {
            "status": "NOT_PERFORMED",
            "scope": "CSV_JOURNAL_SNAPSHOT",
            "discrepancy_count": 1,
        },
        "coverage": {
            "status": "PARTIAL",
            "trade_snapshot": "PARTIAL",
            "realized_pnl": "COMPLETE",
            "commission": "COMPLETE",
            "account_scope": "NOT_AVAILABLE",
            "funding_transfer": "NOT_AVAILABLE",
            "market_context": "NOT_AVAILABLE",
        },
        "discrepancies": [{"type": "CSV_ROW_REJECTED", "source_row_number": 3}],
    }


def _seed_trade_review(tmp_path, *, review=None):
    driver = SQLiteDriver(str(tmp_path / "inbox.sqlite"))
    trade = {
        "id": "TRD-INBOX-1",
        "symbol": "BTCUSDT",
        "side": "BUY",
        "entry_price": 100.0,
        "exit_price": 101.0,
        "qty": 1.0,
        "entry_time": "2026-09-08T10:00:00Z",
        "exit_time": "2026-09-08T10:05:00Z",
        "status": "CLOSED",
        "pnl": 1.0,
        "commission": 0.1,
    }
    driver.record_trade_with_evidence(
        trade,
        event_type="LegacyTradeImported",
        idempotency_key="wp23-source-1",
        occurred_at="2026-09-08T10:05:00Z",
        provenance={
            "source": "csv",
            "source_file_sha256": "a" * 64,
            "source_row_number": 2,
            "source_row_sha256": "b" * 64,
            "import_review": review or _source_review(),
        },
    )
    ledger = EvidenceLedgerRepository(driver.db_path)
    event = ledger.get_event_by_identity(
        "local-journal", "local-journal", "LegacyTradeImported", "wp23-source-1"
    )
    assert event is not None
    service = ReconciliationInboxService(ledger_repo=ledger, legacy_driver=driver)
    return driver, ledger, service, event


def test_inbox_is_deterministic_and_keeps_source_lineage(tmp_path):
    _driver, _ledger, service, source_event = _seed_trade_review(tmp_path)

    first = service.list_items()
    second = service.list_items()

    assert first == second
    assert len(first) == 1
    item = first[0]
    assert item["status"] == "UNRESOLVED"
    assert item["decision"] == "UNRESOLVED"
    assert item["trade_id"] == "TRD-INBOX-1"
    assert item["source"]["event_id"] == source_event["event_id"]
    assert item["source"]["event_hash"] == source_event["event_hash"]
    assert item["source"]["source_file_sha256"] == "a" * 64
    assert item["source"]["source_row_number"] == 2
    assert item["discrepancy"] == {"type": "CSV_ROW_REJECTED", "source_row_number": 3}
    assert item["coverage"]["realized_pnl"] == "COMPLETE"
    assert item["coverage"]["account_scope"] == "NOT_AVAILABLE"


def test_acknowledge_is_append_only_idempotent_and_conflict_safe(tmp_path):
    driver, ledger, service, source_event = _seed_trade_review(tmp_path)
    item = service.list_items()[0]

    first = service.record_decision(item["review_id"], "ACKNOWLEDGE", note="Reviewed source row")
    replay = service.record_decision(item["review_id"], "ACKNOWLEDGE", note="Reviewed source row")

    assert first["decision"] == "ACKNOWLEDGED"
    assert replay["event_id"] == first["event_id"]
    assert service.list_items()[0]["status"] == "ACKNOWLEDGED"
    assert ledger.get_event(source_event["event_id"])["event_hash"] == source_event["event_hash"]
    with pytest.raises(ReconciliationDecisionConflict):
        service.record_decision(item["review_id"], "REJECT")

    events = list(ledger.export_events())
    decision_events = [event for event in events if event["event_type"] == "JournalReviewAdded"]
    assert len(decision_events) == 1
    assert decision_events[0]["normalized_payload"]["review_kind"] == "RECONCILIATION_DECISION"
    assert decision_events[0]["provenance"]["source_event_hash"] == source_event["event_hash"]
    assert driver.get_trade("TRD-INBOX-1")["pnl"] == 1.0


def test_correction_updates_trade_with_causation_and_preserves_old_event(tmp_path):
    driver, ledger, service, source_event = _seed_trade_review(tmp_path)
    item = service.list_items()[0]

    result = service.record_decision(
        item["review_id"],
        "CORRECT",
        note="Corrected exit and accounting from the reviewed source.",
        correction={"exit_price": 104.0, "pnl": 4.0, "commission": 0.2, "status": "CLOSED"},
    )

    assert result["decision"] == "CORRECTED"
    assert service.list_items()[0]["status"] == "CORRECTED"
    assert driver.get_trade("TRD-INBOX-1")["pnl"] == 4.0
    events = list(ledger.export_events(account_id="local-journal"))
    assert len(events) == 2
    correction = events[-1]
    assert correction["event_type"] == "TradeCorrected"
    assert correction["causation_id"] == source_event["event_id"]
    assert correction["provenance"]["reconciliation_decision"]["review_id"] == item["review_id"]
    assert ledger.get_event(source_event["event_id"])["event_hash"] == source_event["event_hash"]

    adapter = TradeReadAdapter(
        legacy_driver=driver,
        projection_repo=EvidenceTradeProjectionRepository(driver.db_path),
    )
    pack = adapter.get_evidence_pack("TRD-INBOX-1")
    assert pack["event_count"] == 2
    assert pack["trade"]["pnl"] == 4.0
    assert pack["events"][0]["event_id"] == source_event["event_id"]
    assert pack["events"][1]["causation_id"] == source_event["event_id"]

    with pytest.raises(ValueError, match="unsupported correction field"):
        service.record_decision(
            item["review_id"],
            "CORRECT",
            correction={"api_key": "must-not-enter-ledger"},
        )


def test_broker_review_has_bounded_discrepancy_reference_without_trade_claim(tmp_path):
    ledger = EvidenceLedgerRepository(str(tmp_path / "broker.sqlite"))
    broker = BrokerImportService(ledger)
    report = broker.import_records(
        "BINANCE",
        orders=[{
            "orderId": "ORDER-1", "symbol": "BTCUSDT", "side": "BUY", "status": "FILLED",
            "origQty": "2", "executedQty": "2", "avgPrice": "100", "fee": "0.2",
            "commissionAsset": "USDT", "updateTime": 1788256800000,
        }],
        fills=[{
            "id": "FILL-1", "orderId": "ORDER-1", "symbol": "BTCUSDT", "side": "BUY",
            "qty": "1", "price": "100", "commission": "0.1", "commissionAsset": "USDT",
            "time": 1788256800000,
        }],
        source_bytes=b"broker-fixture",
    )
    service = ReconciliationInboxService(ledger_repo=ledger)

    items = service.list_items()
    assert report["review"]["discrepancies"]
    assert any(item["trade_id"] is None for item in items)
    mismatch = next(item for item in items if item["discrepancy"]["type"] == "QUANTITY_MISMATCH")
    assert mismatch["discrepancy"]["external_order_id"] == "ORDER-1"
    assert mismatch["source"]["source_file_sha256"] == hashlib.sha256(b"broker-fixture").hexdigest()


def test_reconciliation_inbox_api_exposes_items_and_decision(tmp_path, monkeypatch):
    driver, ledger, service, _source_event = _seed_trade_review(tmp_path)
    monkeypatch.setattr(endpoints, "reconciliation_inbox_service", service)
    client = TestClient(create_app())

    response = client.get("/api/v1/reconciliation/inbox")
    assert response.status_code == 200
    item = response.json()["items"][0]

    decision = client.post(
        f"/api/v1/reconciliation/inbox/{item['review_id']}/decision",
        json={"decision": "ACKNOWLEDGE", "note": "Reviewed"},
    )
    assert decision.status_code == 200
    assert decision.json()["decision"] == "ACKNOWLEDGED"
    assert driver.get_trade("TRD-INBOX-1") is not None
