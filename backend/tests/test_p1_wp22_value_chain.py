"""P1-WP22 import review -> evidence pack -> export contracts."""

import hashlib
from types import SimpleNamespace

from app.db.repositories.evidence_ledger_repo import EvidenceLedgerRepository
from app.db.repositories.evidence_projection_repo import EvidenceTradeProjectionRepository
from app.db.sqlite_driver import SQLiteDriver
from app.services import csv_importer as csv_importer_module
from app.services.broker_import_service import BrokerImportService
from app.services.csv_importer import csv_trade_importer
from app.services.evidence_pack_export import EvidencePackExportService
from app.services.trade_read_adapter import TradeReadAdapter
from app.db import sync_pipeline as sync_pipeline_module


def _complete_csv(symbol: str = "WP22USDT") -> bytes:
    return (
        "symbol,side,entry_price,exit_price,qty,entry_time,exit_time,status,pnl,commission,notes\n"
        f"{symbol},BUY,100.0,102.0,1.0,2026-09-08T10:00:00Z,2026-09-08T10:05:00Z,CLOSED,2.0,0.1,fixture\n"
    ).encode("utf-8")


def test_csv_preview_is_read_only_and_exposes_bounded_review_contract(tmp_path):
    driver = SQLiteDriver(str(tmp_path / "preview.sqlite"))
    before = driver.list_trades(limit=100)

    preview = csv_trade_importer.parse_and_preview_csv(_complete_csv(), "wp22.csv")

    assert driver.list_trades(limit=100) == before == []
    assert preview["import_review"]["status"] == "READY"
    assert preview["import_review"]["decision"] == "IMPORT_ALLOWED"
    assert preview["import_review"]["reconciliation"]["status"] == "NOT_PERFORMED"
    assert preview["import_review"]["coverage"] == {
        "status": "PARTIAL",
        "source_rows": 1,
        "normalized_rows": 1,
        "rejected_rows": 0,
        "trade_snapshot": "COMPLETE",
        "realized_pnl": "COMPLETE",
        "commission": "COMPLETE",
        "account_scope": "NOT_AVAILABLE",
        "funding_transfer": "NOT_AVAILABLE",
        "market_context": "NOT_AVAILABLE",
    }
    assert "raw_payload" not in preview


def test_mixed_csv_rows_require_user_review_without_claiming_reconciliation():
    content = (
        b"symbol,side,entry_price,exit_price,qty,entry_time,exit_time,status,pnl,commission\n"
        b"GOODUSDT,BUY,100,101,1,2026-09-08T10:00:00Z,2026-09-08T10:05:00Z,CLOSED,1,0.1\n"
        b"BADUSDT,BUY,not-a-number,101,1,2026-09-08T10:01:00Z,2026-09-08T10:06:00Z,CLOSED,0,0\n"
    )

    preview = csv_trade_importer.parse_and_preview_csv(content, "mixed.csv")
    review = preview["import_review"]

    assert review["status"] == "PARTIAL"
    assert review["decision"] == "USER_REVIEW_REQUIRED"
    assert review["reconciliation"]["status"] == "NOT_PERFORMED"
    assert review["reconciliation"]["discrepancy_count"] == 1
    assert review["coverage"]["normalized_rows"] == 1
    assert review["coverage"]["rejected_rows"] == 1
    assert review["discrepancies"] == [{"type": "CSV_ROW_REJECTED", "source_row_number": 3}]


def test_missing_accounting_fields_remain_unknown_and_require_review():
    content = (
        b"symbol,side,entry_price,qty,entry_time,status\n"
        b"UNKNOWNUSDT,BUY,100,1,2026-09-08T10:00:00Z,OPEN\n"
    )

    review = csv_trade_importer.parse_and_preview_csv(content, "unknown-accounting.csv")["import_review"]

    assert review["status"] == "REJECTED"
    assert review["decision"] == "IMPORT_BLOCKED"
    assert review["coverage"]["realized_pnl"] == "UNKNOWN"
    assert review["coverage"]["commission"] == "UNKNOWN"
    assert review["coverage"]["realized_pnl"] != "COMPLETE"
    assert review["discrepancies"] == [{
        "type": "ACCOUNTING_COVERAGE_UNKNOWN",
        "fields": ["realized_pnl", "commission"],
        "source_row_number": 2,
    }]


def test_broker_reconciliation_exposes_lifecycle_and_accounting_boundaries(tmp_path):
    source = (tmp_path / "broker.json")
    source.write_text(
        '{"orders":[{"orderId":"O-1","symbol":"BTCUSDT","side":"BUY",'
        '"status":"FILLED","origQty":"1","executedQty":"1","avgPrice":"100",'
        '"fee":"0.1","commissionAsset":"USDT","updateTime":1788256800000}],'
        '"fills":[{"id":"F-1","orderId":"O-1","symbol":"BTCUSDT","side":"BUY",'
        '"qty":"1","price":"100","commission":"0.1",'
        '"commissionAsset":"USDT","time":1788256800000}]}',
        encoding="utf-8",
    )
    service = BrokerImportService(EvidenceLedgerRepository(str(tmp_path / "ledger.sqlite")))
    report = service.import_json_document("BINANCE", source.read_bytes(), source_name="broker.json")

    assert report["status"] == "RECONCILED"
    assert report["coverage"] == {
        "status": "PARTIAL",
        "lifecycle": "COMPLETE",
        "fees": "RECONCILED",
        "account_events": "NOT_AVAILABLE",
        "funding_transfer": "NOT_AVAILABLE",
        "market_context": "NOT_AVAILABLE",
    }
    assert report["review"]["status"] == "READY_FOR_USER_REVIEW"
    assert report["review"]["next_action"] == "USER_DECISION_REQUIRED_TO_CREATE_TRADE_SNAPSHOT"


def test_imported_trade_keeps_review_lineage_through_correction_and_export(tmp_path, monkeypatch):
    driver = SQLiteDriver(str(tmp_path / "value-chain.sqlite"))
    monkeypatch.setattr(csv_importer_module, "sqlite_driver", driver)
    monkeypatch.setattr(sync_pipeline_module, "sqlite_driver", driver)
    monkeypatch.setattr(sync_pipeline_module, "duckdb_driver", SimpleNamespace(is_available=False))

    result = csv_trade_importer.parse_and_import_csv(_complete_csv("CHAINUSDT"), "chain.csv")
    assert result["success"] is True
    assert result["import_review"]["status"] == "READY"
    trade_id = result["trades"][0]["id"]

    adapter = TradeReadAdapter(
        legacy_driver=driver,
        projection_repo=EvidenceTradeProjectionRepository(str(tmp_path / "value-chain.sqlite")),
    )
    pack_before = adapter.get_evidence_pack(trade_id)
    assert pack_before["import_review"]["status"] == "READY"
    assert pack_before["import_review"]["source_file_sha256"] == hashlib.sha256(_complete_csv("CHAINUSDT")).hexdigest()

    existing = driver.get_trade(trade_id)
    assert existing is not None
    driver.record_trade_with_evidence(
        {"id": trade_id, "status": "CLOSED", "exit_price": 103.0, "exit_time": "2026-09-08T10:06:00Z", "pnl": 3.0},
        event_type="TradeCorrected",
        idempotency_key="wp22-manual-correction-1",
        occurred_at="2026-09-08T10:06:00Z",
        provenance={"source": "manual_correction", "decision": "USER_REVIEWED"},
    )

    pack_after = adapter.get_evidence_pack(trade_id)
    assert pack_after["event_count"] == 2
    assert pack_after["trade"]["pnl"] == 3.0
    assert len(pack_after["import_review_history"]) == 1
    assert pack_after["import_review_history"][0]["event_id"] == pack_before["events"][0]["event_id"]

    exporter = EvidencePackExportService(adapter)
    first = exporter.export(trade_id, "json")
    second = exporter.export(trade_id, "json")
    assert first.content == second.content
    assert len(first.payload_sha256) == 64
    assert len(first.artifact_sha256) == 64
    assert b"manual_correction" in first.content
    assert b"source_file_sha256" in first.content
