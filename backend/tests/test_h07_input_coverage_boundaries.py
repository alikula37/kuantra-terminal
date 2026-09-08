"""H07 fail-closed fixtures for bounded CSV input and coverage propagation."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.db import sync_pipeline as sync_pipeline_module
from app.db.repositories.evidence_projection_repo import EvidenceTradeProjectionRepository
from app.db.sqlite_driver import SQLiteDriver
from app.services import csv_importer as csv_importer_module
from app.services.csv_importer import csv_trade_importer
from app.services.trade_read_adapter import TradeReadAdapter


def _valid_csv(symbol: str = "H07USDT", *, notes: str = "fixture") -> bytes:
    return (
        "symbol,side,entry_price,exit_price,qty,entry_time,exit_time,status,pnl,commission,notes\n"
        f"{symbol},BUY,100.0,102.0,1.0,2026-09-08T10:00:00Z,"
        f"2026-09-08T10:05:00Z,CLOSED,2.0,0.1,{notes}\n"
    ).encode("utf-8")


def _isolated_importer(tmp_path, monkeypatch):
    driver = SQLiteDriver(str(tmp_path / "h07-input.sqlite"))
    monkeypatch.setattr(csv_importer_module, "sqlite_driver", driver)
    monkeypatch.setattr(sync_pipeline_module, "sqlite_driver", driver)
    monkeypatch.setattr(sync_pipeline_module, "duckdb_driver", SimpleNamespace(is_available=False))
    return driver


def test_oversized_csv_is_rejected_before_import_writes(tmp_path, monkeypatch):
    driver = _isolated_importer(tmp_path, monkeypatch)
    content = _valid_csv()
    monkeypatch.setattr(csv_importer_module, "MAX_CSV_BYTES", len(content) - 1)

    with pytest.raises(ValueError, match="size limit"):
        csv_trade_importer.parse_and_import_csv(content, "oversized.csv")

    assert driver.list_trades(limit=100) == []


def test_csv_row_limit_is_rejected_before_import_writes(tmp_path, monkeypatch):
    driver = _isolated_importer(tmp_path, monkeypatch)
    header = _valid_csv().splitlines()[0] + b"\n"
    rows = b"".join(
        _valid_csv(f"H07-{index}USDT").split(b"\n", 1)[1]
        for index in range(3)
    )
    monkeypatch.setattr(csv_importer_module, "MAX_CSV_ROWS", 2)

    with pytest.raises(ValueError, match="row count"):
        csv_trade_importer.parse_and_import_csv(header + rows, "too-many-rows.csv")

    assert driver.list_trades(limit=100) == []


def test_csv_field_limit_is_rejected_before_import_writes(tmp_path, monkeypatch):
    driver = _isolated_importer(tmp_path, monkeypatch)
    content = _valid_csv(notes="x" * 64)
    monkeypatch.setattr(csv_importer_module, "MAX_CSV_FIELD_BYTES", 32)

    with pytest.raises(ValueError, match="field or record"):
        csv_trade_importer.parse_and_import_csv(content, "wide-field.csv")

    assert driver.list_trades(limit=100) == []


def test_malformed_quote_is_rejected_before_import_writes(tmp_path, monkeypatch):
    driver = _isolated_importer(tmp_path, monkeypatch)
    malformed = (
        b"symbol,side,entry_price,exit_price,qty,entry_time,exit_time,status,pnl,commission,notes\n"
        b'H07USDT,BUY,100,102,1,2026-09-08T10:00:00Z,2026-09-08T10:05:00Z,CLOSED,2,0.1,"unterminated\n'
    )

    with pytest.raises(ValueError, match="CSV parsing failed"):
        csv_trade_importer.parse_and_import_csv(malformed, "malformed.csv")

    assert driver.list_trades(limit=100) == []


def test_extra_csv_columns_are_reported_in_preview_instead_of_dropped():
    content = _valid_csv().rstrip(b"\n") + b",unexpected\n"

    preview = csv_trade_importer.parse_and_preview_csv(content, "extra-column.csv")

    assert preview["preview_trades"] == []
    assert preview["errors_count"] == 1
    assert "CSV_EXTRA_COLUMNS" in preview["errors"][0]
    assert preview["import_review"]["status"] == "REJECTED"
    assert preview["import_review"]["decision"] == "IMPORT_BLOCKED"
    assert preview["import_review"]["discrepancies"] == [{
        "type": "CSV_MALFORMED_ROW",
        "source_row_number": 2,
    }]


def test_partial_csv_is_review_only_and_does_not_partially_write(tmp_path, monkeypatch):
    driver = _isolated_importer(tmp_path, monkeypatch)
    content = (
        _valid_csv("GOOD-H07USDT")
        + b"BAD-H07USDT,BUY,not-a-number,102,1,2026-09-08T10:01:00Z,"
        b"2026-09-08T10:06:00Z,CLOSED,0,0,bad\n"
    )

    result = csv_trade_importer.parse_and_import_csv(content, "partial.csv")

    assert result["success"] is False
    assert result["imported"] == 0
    assert result["import_review"]["status"] == "PARTIAL"
    assert result["import_review"]["decision"] == "USER_REVIEW_REQUIRED"
    assert driver.list_trades(limit=100) == []


def test_empty_csv_is_rejected_and_never_reports_success(tmp_path, monkeypatch):
    driver = _isolated_importer(tmp_path, monkeypatch)

    result = csv_trade_importer.parse_and_import_csv(
        b"symbol,side,entry_price,qty,entry_time,pnl,commission\n",
        "empty.csv",
    )

    assert result["success"] is False
    assert result["imported"] == 0
    assert result["import_review"]["status"] == "REJECTED"
    assert result["import_review"]["decision"] == "IMPORT_BLOCKED"
    assert result["import_review"]["coverage"]["status"] == "UNKNOWN"
    assert driver.list_trades(limit=100) == []


@pytest.mark.parametrize("trade_snapshot", ["PARTIAL", "UNKNOWN", "NOT_AVAILABLE"])
def test_evidence_pack_preserves_source_trade_coverage(tmp_path, trade_snapshot):
    driver = SQLiteDriver(str(tmp_path / f"coverage-{trade_snapshot.lower()}.sqlite"))
    driver.record_trade_with_evidence(
        {
            "id": "H07-COVERAGE",
            "symbol": "BTCUSDT",
            "side": "BUY",
            "entry_price": 100.0,
            "exit_price": 101.0,
            "qty": 1.0,
            "entry_time": "2026-09-08T10:00:00Z",
            "exit_time": "2026-09-08T10:05:00Z",
            "status": "CLOSED",
            "pnl": 0.0,
            "commission": 0.0,
        },
        event_type="LegacyTradeImported",
        idempotency_key=f"h07-coverage-{trade_snapshot}",
        occurred_at="2026-09-08T10:05:00Z",
        provenance={
            "source": "csv",
            "import_review": {
                "status": "PARTIAL",
                "decision": "USER_REVIEW_REQUIRED",
                "coverage": {
                    "status": "UNKNOWN",
                    "trade_snapshot": trade_snapshot,
                    "realized_pnl": "UNKNOWN",
                    "commission": "UNKNOWN",
                    "funding_transfer": "NOT_AVAILABLE",
                    "account_scope": "NOT_AVAILABLE",
                    "market_context": "NOT_AVAILABLE",
                },
            },
        },
    )
    adapter = TradeReadAdapter(
        legacy_driver=driver,
        projection_repo=EvidenceTradeProjectionRepository(driver.db_path),
    )

    summary = adapter.get_evidence_pack("H07-COVERAGE")["coverage_summary"]

    assert summary["trade_snapshot"] == trade_snapshot
    assert summary["realized_pnl"] == "UNKNOWN"
    assert summary["fees"] == "UNKNOWN"
    assert summary["overall"] == "UNKNOWN"
