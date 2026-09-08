"""
Test Suite for Multi-Format CSV Trade Ingestion Engine & Endpoints.
Verifies authentic parsing of Binance, Bybit, MetaTrader (MT4/MT5), and Generic Kuantra formats,
idempotent deduplication, dynamic R-multiple calculation, and FastAPI REST endpoints.
"""

import pytest
import io
import time
from fastapi.testclient import TestClient
from main import create_app
from app.services.csv_importer import CsvTradeImporterService, csv_trade_importer
from app.db.sqlite_driver import sqlite_driver

app = create_app()
client = TestClient(app)


class TestCsvTradeImporterEngine:
    """Tests for multi-broker CSV parser, normalization, and deduplication logic."""

    def test_import_binance_futures_csv(self):
        t_base = int(time.time())
        binance_csv = (
            "Date(UTC),Pair,Side,Price,Executed,Fee,Realized Profit\n"
            f"2026-08-25 10:15:{t_base % 60:02d},BTCUSDT,BUY,64200.50,0.25,1.20,0.00\n"
            f"2026-08-25 15:45:{t_base % 60:02d},BTCUSDT,SELL,65800.00,0.25,1.25,400.00\n"
            f"2026-08-26 09:20:{t_base % 60:02d},ETHUSDT,SELL_SHORT,3450.00,2.0,1.50,-120.00\n"
        )
        
        format_type, delimiter = CsvTradeImporterService.detect_format_and_dialect(binance_csv)
        assert format_type == "BINANCE"
        assert delimiter == ","

        res = csv_trade_importer.parse_and_import_csv(binance_csv.encode("utf-8"), "binance_futures.csv")
        assert res["success"] is True
        assert res["detected_format"] == "BINANCE"
        assert res["imported"] >= 1
        assert len(res["errors"]) == 0

        # Verify trades in SQLite
        trades = sqlite_driver.list_trades(limit=10, symbol="BTCUSDT")
        assert len(trades) >= 1
        symbols = [t["symbol"] for t in trades]
        assert "BTCUSDT" in symbols

    def test_import_bybit_closed_pnl_csv(self):
        t_base = int(time.time()) + 100
        bybit_csv = (
            "Contracts,Closing Direction,Entry Price,Exit Price,Qty,Closed P&L,Fee,Trade Time,Closed Time\n"
            f"SOLUSDT,Close Long,142.50,154.20,10.0,117.00,0.50,2026-08-27 12:00:{t_base % 60:02d},2026-08-27 16:30:{t_base % 60:02d}\n"
            f"ETHUSDT,Close Short,3500.00,3420.00,3.0,240.00,0.40,2026-08-28 08:00:{t_base % 60:02d},2026-08-28 14:00:{t_base % 60:02d}\n"
        )

        format_type, delimiter = CsvTradeImporterService.detect_format_and_dialect(bybit_csv)
        assert format_type == "BYBIT"

        res = csv_trade_importer.parse_and_import_csv(bybit_csv.encode("utf-8"), "bybit_pnl.csv")
        assert res["success"] is True
        assert res["detected_format"] == "BYBIT"
        assert res["imported"] >= 1

        if res["trades"]:
            trade_id = res["trades"][0]["id"]
            db_trade = sqlite_driver.get_trade(trade_id)
            assert db_trade is not None
            assert db_trade["status"] == "CLOSED"
            assert db_trade["pnl"] == 117.00

    def test_import_metatrader_report(self):
        t_base = int(time.time()) + 200
        mt_csv = (
            "Ticket;Open Time;Type;Size;Item;Price;S / L;T / P;Close Time;Price;Commission;Taxes;Swap;Profit\n"
            f"849201;2026.08.29 11:30:{t_base % 60:02d};buy;1.00;EURUSD;1.08500;1.08200;1.09200;2026.08.29 17:45:{t_base % 60:02d};1.09050;-2.50;0.00;0.00;550.00\n"
            f"849202;2026.08.30 08:15:{t_base % 60:02d};sell;0.50;XAUUSD;2520.00;2530.00;2490.00;2026.08.30 13:00:{t_base % 60:02d};2505.00;-3.00;0.00;0.00;750.00\n"
        )

        format_type, delimiter = CsvTradeImporterService.detect_format_and_dialect(mt_csv)
        assert format_type == "METATRADER"
        assert delimiter == ";"

        res = csv_trade_importer.parse_and_import_csv(mt_csv.encode("utf-8"), "Statement.csv")
        assert res["success"] is True
        assert res["detected_format"] == "METATRADER"
        assert res["imported"] >= 1

        eur_trades = sqlite_driver.list_trades(limit=5, symbol="EURUSD")
        assert len(eur_trades) >= 1
        assert eur_trades[0]["stop_loss"] == 1.08200
        assert eur_trades[0]["r_multiple"] is not None

    def test_import_generic_kuantra_csv(self):
        t_base = int(time.time()) + 300
        generic_csv = (
            "symbol,side,entry_price,exit_price,qty,stop_loss,take_profit,entry_time,exit_time,status,pnl,r_multiple,commission,notes\n"
            f"AVAXUSDT,BUY,28.50,32.00,10.0,27.00,34.00,2026-08-30T10:00:{t_base % 60:02d}Z,2026-08-30T16:00:{t_base % 60:02d}Z,CLOSED,35.00,2.33,0.50,Generic test trade\n"
        )

        res = csv_trade_importer.parse_and_import_csv(generic_csv.encode("utf-8"), "generic.csv")
        assert res["success"] is True
        assert res["detected_format"] == "GENERIC_KUANTRA"
        assert res["imported"] == 1

    def test_duplicate_reimport_idempotency(self):
        t_base = int(time.time()) + 400
        sample_csv = (
            "symbol,side,entry_price,exit_price,qty,entry_time,exit_time,status,pnl,commission\n"
            f"DOTUSDT,BUY,4.50,5.20,100.0,2026-08-28T09:00:{t_base % 60:02d}Z,2026-08-28T18:00:{t_base % 60:02d}Z,CLOSED,70.0,0.10\n"
        )

        # 1st import -> imports 1 row
        res1 = csv_trade_importer.parse_and_import_csv(sample_csv.encode("utf-8"), "dot.csv")
        assert res1["imported"] == 1
        assert res1["duplicates_skipped"] == 0

        # 2nd import (identical content) -> imports 0, skips 1 duplicate
        res2 = csv_trade_importer.parse_and_import_csv(sample_csv.encode("utf-8"), "dot.csv")
        assert res2["imported"] == 0
        assert res2["duplicates_skipped"] == 1

    def test_malformed_csv_blocks_partial_import(self):
        corrupt_csv = (
            "symbol,side,entry_price,qty,entry_time,pnl,commission\n"
            "BTCUSDT,BUY,invalid_number,1.0,2026-08-30T09:00:00Z,0,0\n"
            "ETHUSDT,SELL,3200.0,0.0,2026-08-30T09:30:00Z,0,0\n"
            "NEARUSDT,BUY,4.50,20.0,2026-08-30T10:00:00Z,0,0\n"
        )

        res = csv_trade_importer.parse_and_import_csv(corrupt_csv.encode("utf-8"), "corrupt.csv")
        assert res["success"] is False
        assert res["imported"] == 0  # Mixed input requires review before any write
        assert len(res["errors"]) == 2  # 2 rows had parsing/validation errors
        assert res["import_review"]["status"] == "PARTIAL"
        assert sqlite_driver.list_trades(limit=10, symbol="NEARUSDT") == []

    def test_csv_import_and_preview_endpoints(self):
        t_base = int(time.time()) + 500
        test_csv_content = (
            "symbol,side,entry_price,exit_price,qty,entry_time,exit_time,status,pnl,commission\n"
            f"LINKUSDT,BUY,11.50,13.20,50.0,2026-08-29T12:00:{t_base % 60:02d}Z,2026-08-29T19:00:{t_base % 60:02d}Z,CLOSED,85.0,0.2\n"
        )

        # Test Preview endpoint
        preview_res = client.post(
            "/api/v1/journal/preview-csv",
            files={"file": ("preview_test.csv", io.BytesIO(test_csv_content.encode("utf-8")), "text/csv")}
        )
        assert preview_res.status_code == 200
        preview_data = preview_res.json()
        assert preview_data["detected_format"] == "GENERIC_KUANTRA"
        assert preview_data["total_rows_parsed"] == 1
        assert len(preview_data["preview_trades"]) == 1

        # Test Import endpoint
        import_res = client.post(
            "/api/v1/journal/import-csv",
            files={"file": ("import_test.csv", io.BytesIO(test_csv_content.encode("utf-8")), "text/csv")}
        )
        assert import_res.status_code == 200
        import_data = import_res.json()
        assert import_data["success"] is True
        assert "portfolio_summary" in import_data

        # Test Template endpoint
        template_res = client.get("/api/v1/journal/template-csv")
        assert template_res.status_code == 200
        assert "text/csv" in template_res.headers.get("content-type", "")
        assert "symbol,side,entry_price" in template_res.text
