"""P1-WP10 fail-closed CSV import and source-hash contracts."""

import hashlib

import pytest

from app.db.repositories.evidence_ledger_repo import EvidenceLedgerRepository
from app.db.sqlite_driver import sqlite_driver
from app.services.csv_importer import CsvTradeImporterService, csv_trade_importer


def _csv_bytes(symbol: str = "P1WP10USDT") -> bytes:
    return (
        "symbol,side,entry_price,exit_price,qty,entry_time,exit_time,status,pnl,commission\n"
        f"{symbol},BUY,100.0,102.0,1.0,2026-09-06T10:00:00Z,2026-09-06T10:05:00Z,CLOSED,2.0,0.1\n"
    ).encode("utf-8")


def test_timestamp_parser_rejects_missing_or_unknown_values():
    with pytest.raises(ValueError, match="required"):
        CsvTradeImporterService.parse_timestamp(None)
    with pytest.raises(ValueError, match="Unrecognized"):
        CsvTradeImporterService.parse_timestamp("not-a-date")
    assert CsvTradeImporterService.parse_timestamp("2026-09-06T13:00:00+03:00") == "2026-09-06T10:00:00Z"


def test_preview_exposes_file_and_row_hash_without_raw_payload():
    content = _csv_bytes("PREVIEWP1USDT")
    preview = csv_trade_importer.parse_and_preview_csv(content, "preview.csv")
    assert preview["source_file_sha256"] == hashlib.sha256(content).hexdigest()
    row = preview["preview_trades"][0]
    assert row["source_row_number"] == 2
    assert len(row["source_row_sha256"]) == 64
    assert "raw_payload" not in row


def test_import_persists_source_hashes_in_canonical_event_provenance():
    content = _csv_bytes("IMPORTP1USDT")
    result = csv_trade_importer.parse_and_import_csv(content, "broker-export.csv")
    assert result["success"] is True
    assert result["imported"] == 1

    trade_id = result["trades"][0]["id"]
    events = EvidenceLedgerRepository(sqlite_driver.db_path).list_events_for_trade(trade_id)
    assert len(events) == 1
    provenance = events[0]["provenance"]
    assert provenance["source"] == "csv"
    assert provenance["source_ref"] == "broker-export.csv"
    assert provenance["format"] == "GENERIC_KUANTRA"
    assert provenance["source_file_sha256"] == hashlib.sha256(content).hexdigest()
    assert provenance["source_row_number"] == 2
    assert len(provenance["source_row_sha256"]) == 64


def test_missing_identity_or_timestamp_is_not_defaulted():
    content = (
        "symbol,side,entry_price,qty,entry_time\n"
        ",BUY,100.0,1.0,2026-09-06T10:00:00Z\n"
        "MISSINGTIMEUSDT,BUY,100.0,1.0,\n"
    )
    format_type, trades, errors = CsvTradeImporterService.parse_rows(content)
    assert format_type == "GENERIC_KUANTRA"
    assert trades == []
    assert len(errors) == 2
    assert any("Symbol is required" in error for error in errors)
    assert any("Timestamp is required" in error for error in errors)
