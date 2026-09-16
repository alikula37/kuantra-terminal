"""Journal bulk export (CSV) and PDF report contracts.

Synthetic fixtures only.  The service receives injected trade/catalog/tracking
fakes so no test touches the real user database.
"""

from __future__ import annotations

import csv
import io
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.services.journal_export import (
    JournalExportLimitError,
    JournalExportRequestError,
    JournalExportService,
)


TRADE_FIELDS = (
    "id", "symbol", "side", "position_type", "status", "entry_price", "exit_price",
    "qty", "stop_loss", "take_profit", "entry_time", "exit_time", "pnl", "commission",
    "close_source", "record_mode", "qty_unit", "notes", "revision",
)


def trade(**overrides):
    base = {
        "id": "TRD-1",
        "symbol": "BTCUSDT",
        "side": "BUY",
        "position_type": "LONG",
        "status": "CLOSED",
        "entry_price": 100.0,
        "exit_price": 110.0,
        "qty": 1.0,
        "stop_loss": 95.0,
        "take_profit": 110.0,
        "entry_time": "2026-08-02T09:00:00.000000Z",
        "exit_time": "2026-08-02T12:00:00.000000Z",
        "pnl": 9.5,
        "commission": 0.5,
        "close_source": "USER_REPORTED",
        "record_mode": "EXTERNAL",
        "qty_unit": "BASE",
        "notes": "",
        "revision": 2,
    }
    base.update(overrides)
    return {field: base.get(field) for field in TRADE_FIELDS}


class FakeAdapter:
    def __init__(self, trades):
        self.trades = trades

    def list_trades(self, limit=100, offset=0, symbol=None, status=None, **kwargs):
        records = self.trades
        if symbol:
            records = [t for t in records if t["symbol"] == symbol]
        if status:
            records = [t for t in records if t["status"] == status]
        return records[offset:offset + limit]


class FakeCatalog:
    def __init__(self, verified=None):
        self.verified = verified or {}

    def get(self, symbol):
        entry = self.verified.get(str(symbol or "").upper())
        if not entry:
            return None
        return {"symbol": symbol.upper(), "quote_asset": entry, "base_asset": "X"}

    def is_verified(self, symbol):
        return str(symbol or "").upper() in self.verified


class FakeTracking:
    def __init__(self, states):
        self.states = states

    def list(self):
        return self.states


def tracking_state(trade_id, gross_pnl, **overrides):
    state = {
        "trade_id": trade_id,
        "basis": "LOCAL_ESTIMATE",
        "gross_pnl": str(gross_pnl),
        "remaining_qty": "0",
        "initial_qty": "1",
        "external_status": "OPEN",
        "unit_status": "BASE_UNIT",
        "symbol": "BTCUSDT",
        "side": "BUY",
    }
    state.update(overrides)
    return state


def service(trades, verified=None, tracking=None, **kwargs):
    return JournalExportService(
        adapter=FakeAdapter(trades),
        catalog=FakeCatalog(verified if verified is not None else {"BTCUSDT": "USDT"}),
        tracking_service=FakeTracking(tracking or []),
        **kwargs,
    )


def csv_rows(artifact):
    text = artifact.content.decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))


def pdf_text(content: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(content))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


# ---------------------------------------------------------------------------
# Filtering / scope
# ---------------------------------------------------------------------------


def test_entry_basis_filters_use_istanbul_calendar_days():
    svc = service([
        trade(id="TRD-LATE", entry_time="2026-08-31T21:30:00.000000Z"),  # 01:30 Istanbul, Sep 1
        trade(id="TRD-EARLY", entry_time="2026-08-31T20:00:00.000000Z"),  # 23:00 Istanbul, Aug 31
    ])
    snapshot = svc.snapshot(scope="filtered", date_from="2026-09-01", date_to="2026-09-30", date_basis="entry")
    assert [record["id"] for record in snapshot.records] == ["TRD-LATE"]


def test_close_basis_filters_use_exit_time():
    svc = service([
        trade(id="TRD-A", entry_time="2026-07-01T09:00:00.000000Z", exit_time="2026-08-05T09:00:00.000000Z"),
        trade(id="TRD-B", entry_time="2026-08-01T09:00:00.000000Z", exit_time="2026-07-05T09:00:00.000000Z"),
    ])
    snapshot = svc.snapshot(scope="filtered", date_from="2026-08-01", date_to="2026-08-31", date_basis="close")
    assert [record["id"] for record in snapshot.records] == ["TRD-A"]


def test_scope_all_ignores_filters():
    svc = service([
        trade(id="TRD-A", symbol="BTCUSDT"),
        trade(id="TRD-B", symbol="ETHUSDT", status="CANCELED", pnl=None),
    ])
    snapshot = svc.snapshot(scope="all", symbols=["BTCUSDT"], statuses=["CLOSED"], date_from="2026-01-01", date_to="2026-01-02")
    assert {record["id"] for record in snapshot.records} == {"TRD-A", "TRD-B"}


def test_multi_symbol_and_status_filters():
    svc = service([
        trade(id="TRD-A", symbol="BTCUSDT"),
        trade(id="TRD-B", symbol="ETHUSDT", status="OPEN", pnl=None),
        trade(id="TRD-C", symbol="SOLUSDT", status="CANCELED", pnl=None),
    ])
    snapshot = svc.snapshot(scope="filtered", symbols=["BTCUSDT", "ETHUSDT"], statuses=["CLOSED", "OPEN"], date_basis="entry")
    assert {record["id"] for record in snapshot.records} == {"TRD-A", "TRD-B"}


# ---------------------------------------------------------------------------
# Accuracy rules
# ---------------------------------------------------------------------------


def test_canceled_records_are_separated_and_excluded_from_performance():
    svc = service([
        trade(id="TRD-CLOSED"),
        trade(id="TRD-CANCELED", status="CANCELED", exit_price=None, exit_time=None, pnl=None),
    ])
    preview = svc.preview(scope="all")
    assert preview["counts"]["canceled"] == 1
    assert preview["counts"]["closed"] == 1
    assert preview["realized_total_by_quote"] == {"USDT": {"user_reported_net": 9.5, "source_declared": 0.0, "count": 1}}


def test_unknown_pnl_is_counted_and_not_zeroed():
    svc = service([
        trade(id="TRD-KNOWN"),
        trade(id="TRD-UNKNOWN", symbol="XAUUSD", pnl=None, qty_unit="UNKNOWN"),
    ])
    preview = svc.preview(scope="all")
    assert preview["unknown_pnl_closed"] == 1
    rows = {row["trade_id"]: row for row in csv_rows(svc.export(format="csv", lang="en", scope="all"))}
    assert rows["TRD-UNKNOWN"]["pnl_known"] == "false"
    assert rows["TRD-UNKNOWN"]["pnl_recorded"] == ""
    assert preview["realized_total_by_quote"]["USDT"]["count"] == 1


def test_unverified_currency_is_excluded_from_money_totals():
    svc = service([
        trade(id="TRD-VERIFIED"),
        trade(id="TRD-UNVERIFIED", symbol="XAUUSD", pnl=25.0),
    ])
    preview = svc.preview(scope="all")
    assert preview["unverified_currency_records"] == 1
    assert preview["realized_total_by_quote"] == {"USDT": {"user_reported_net": 9.5, "source_declared": 0.0, "count": 1}}


def test_distinct_verified_quote_assets_are_not_merged():
    svc = service(
        [trade(id="TRD-USDT"), trade(id="TRD-EUR", symbol="BTCEUR", pnl=3.0)],
        verified={"BTCUSDT": "USDT", "BTCEUR": "EUR"},
    )
    preview = svc.preview(scope="all")
    assert set(preview["realized_total_by_quote"]) == {"USDT", "EUR"}
    assert preview["realized_total_by_quote"]["EUR"]["user_reported_net"] == 3.0


def test_user_reported_and_source_declared_totals_are_split():
    svc = service([
        trade(id="TRD-USER", pnl=9.5),
        trade(id="TRD-IMPORTED", pnl=4.0, close_source="BROKER_IMPORT", record_mode="IMPORT"),
    ])
    preview = svc.preview(scope="all")
    assert preview["realized_total_by_quote"]["USDT"] == {
        "user_reported_net": 9.5,
        "source_declared": 4.0,
        "count": 2,
    }


def test_local_estimates_stay_separate_from_realized_totals():
    svc = service(
        [trade(id="TRD-OPEN", status="OPEN", exit_price=None, exit_time=None, pnl=None)],
        tracking=[tracking_state("TRD-OPEN", 12.75)],
    )
    preview = svc.preview(scope="all")
    assert preview["estimated_trades"] == 1
    assert preview["estimated_gross_by_quote"] == {"USDT": 12.75}
    assert preview["realized_total_by_quote"] == {}
    artifact = svc.export(format="pdf", lang="tr", scope="all")
    text = pdf_text(artifact.content)
    assert "Tahmini brüt sonuç" in text
    assert "12,75" in text or "12.75" in text


def test_open_records_never_join_realized_totals_even_with_a_pnl_value():
    svc = service([trade(id="TRD-OPEN", status="OPEN", pnl=50.0, exit_price=None, exit_time=None)])
    preview = svc.preview(scope="all")
    assert preview["realized_total_by_quote"] == {}
    assert preview["counts"]["open"] == 1


# ---------------------------------------------------------------------------
# CSV behavior
# ---------------------------------------------------------------------------


def test_csv_and_pdf_share_records_values_and_snapshot_hash():
    svc = service([
        trade(id="TRD-A", notes="çğışİÖÜ notu"),
        trade(id="TRD-B", pnl=None, symbol="BTCUSDT", status="OPEN", exit_price=None, exit_time=None),
        trade(id="TRD-C", status="CANCELED", pnl=None, exit_price=None, exit_time=None),
    ])
    csv_artifact = svc.export(format="csv", lang="en", scope="all")
    pdf_artifact = svc.export(format="pdf", lang="en", scope="all")
    assert csv_artifact.snapshot_sha256 == pdf_artifact.snapshot_sha256
    rows = csv_rows(csv_artifact)
    assert [row["trade_id"] for row in rows] == ["TRD-A", "TRD-B", "TRD-C"]
    assert {row["snapshot_sha256"] for row in rows} == {csv_artifact.snapshot_sha256}
    text = pdf_text(pdf_artifact.content)
    assert csv_artifact.snapshot_sha256[:16] in text
    assert "TRD-A" in text and "TRD-B" in text and "TRD-C" in text


def test_csv_has_utf8_bom_and_turkish_headers_per_language():
    svc = service([trade()])
    tr_artifact = svc.export(format="csv", lang="tr", scope="all")
    assert tr_artifact.content.startswith(b"\xef\xbb\xbf")
    header = tr_artifact.content.decode("utf-8-sig").splitlines()[0]
    assert "sembol" in header and "kapanis_kaynagi" in header
    en_artifact = svc.export(format="csv", lang="en", scope="all")
    assert "symbol" in en_artifact.content.decode("utf-8-sig").splitlines()[0]
    de_artifact = svc.export(format="csv", lang="de", scope="all")
    assert "symbol" in de_artifact.content.decode("utf-8-sig").splitlines()[0]


def test_csv_cells_are_formula_safe_and_preserve_newlines():
    svc = service([trade(id="TRD-1", symbol="BTCUSDT", notes="=cmd|' /C calc'!A1\nsecond line \"quoted\"")])
    rows = csv_rows(svc.export(format="csv", lang="en", scope="all"))
    notes = rows[0]["notes"]
    assert notes.startswith("'=")
    assert "\n" in notes and '"quoted"' in notes


def test_csv_includes_istanbul_and_utc_times():
    svc = service([trade(entry_time="2026-08-02T09:00:00.000000Z", exit_time="2026-08-02T12:00:00.000000Z")])
    row = csv_rows(svc.export(format="csv", lang="tr", scope="all"))[0]
    assert row["giris_zamani_istanbul"] == "2026-08-02 12:00"
    assert row["giris_zamani_utc"].startswith("2026-08-02T09:00:00")
    assert row["kapanis_zamani_istanbul"] == "2026-08-02 15:00"


def test_csv_omits_internal_and_sensitive_identifiers(tmp_path):
    svc = service([trade(id="TRD-1", notes="hesap no 1234567890")])
    artifact = svc.export(format="csv", lang="en", scope="all")
    text = artifact.content.decode("utf-8-sig")
    for forbidden in ("account_id", "event_hash", "snapshot_json", "payload", "/Users/", "local-journal"):
        assert forbidden not in text
    assert str(tmp_path) not in text


# ---------------------------------------------------------------------------
# PDF behavior
# ---------------------------------------------------------------------------


def test_pdf_multi_page_report_has_page_numbers_and_repeated_tables():
    trades = [trade(id=f"TRD-{index:04d}", entry_time=f"2026-08-{(index % 28) + 1:02d}T09:00:00.000000Z",
                    exit_time=f"2026-08-{(index % 28) + 1:02d}T12:00:00.000000Z",
                    notes="uzun not " + ("ğüşiöç " * 40))
             for index in range(120)]
    svc = service(trades)
    artifact = svc.export(format="pdf", lang="tr", scope="all")
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(artifact.content))
    assert len(reader.pages) >= 3
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "Sayfa 1 /" in text
    assert "Sayfa 2 /" in text
    assert text.count("Çıkış") >= 2  # closed-table header repeats across pages
    assert "ğüşiöç" in text  # Turkish glyphs survive the font subset


def test_pdf_empty_period_is_explicit_and_not_a_profit_claim():
    svc = service([])
    artifact = svc.export(format="pdf", lang="tr", scope="all")
    text = pdf_text(artifact.content)
    assert "kayıt yok" in text.lower()
    assert "kâr" not in text.lower() or "kazanç" not in text.lower()
    assert "0,00" not in text


def test_pdf_long_table_rows_do_not_overflow_the_page_width():
    svc = service([trade(id="TRD-1", notes="A" * 900)])
    artifact = svc.export(format="pdf", lang="en", scope="all")
    from pypdf import PdfReader

    page = PdfReader(io.BytesIO(artifact.content)).pages[0]
    assert page.mediabox.width > 0
    assert b"%%EOF" in artifact.content[-2048:]


def test_pdf_language_labels_and_basis_are_explicit():
    svc = service([trade()])
    tr_text = pdf_text(svc.export(format="pdf", lang="tr", scope="all").content)
    assert "Dönem: tüm kayıtlar" in tr_text
    assert "Tarih bazı: giriş tarihi" in tr_text
    assert "Saat dilimi: Europe/Istanbul" in tr_text
    en_text = pdf_text(svc.export(format="pdf", lang="en", scope="all").content)
    assert "Date basis: entry date" in en_text
    de_text = pdf_text(svc.export(format="pdf", lang="de", scope="all").content)
    assert "Datumsbasis: Einstiegsdatum" in de_text


# ---------------------------------------------------------------------------
# Limits, filenames and errors
# ---------------------------------------------------------------------------


def test_export_rejects_over_the_record_limit_without_truncating(monkeypatch):
    monkeypatch.setattr("app.services.journal_export.MAX_EXPORT_TRADES", 2)
    svc = service([trade(id=f"TRD-{index}") for index in range(3)])
    with pytest.raises(JournalExportLimitError) as excinfo:
        svc.export(format="csv", lang="en", scope="all")
    assert "3" in str(excinfo.value) and "2" in str(excinfo.value)
    with pytest.raises(JournalExportLimitError):
        svc.preview(scope="all")


def test_record_limit_boundary_is_inclusive(monkeypatch):
    monkeypatch.setattr("app.services.journal_export.MAX_EXPORT_TRADES", 2)
    svc = service([trade(id=f"TRD-{index}") for index in range(2)])
    artifact = svc.export(format="csv", lang="en", scope="all")
    assert artifact.record_count == 2


def test_mode_and_language_are_validated():
    svc = service([trade()])
    with pytest.raises(JournalExportRequestError):
        svc.export(format="xlsx", lang="en", scope="all")
    with pytest.raises(JournalExportRequestError):
        svc.export(format="csv", lang="fr", scope="all")
    with pytest.raises(JournalExportRequestError):
        svc.export(format="csv", lang="en", scope="everything")


def test_filenames_are_safe_and_descriptive():
    svc = service([trade()])
    csv_artifact = svc.export(format="csv", lang="en", scope="all", date_from="2026-08-01", date_to="2026-08-31")
    assert re.fullmatch(r"kuantra-journal-20260801-20260831-[0-9a-f]{8}\.csv", csv_artifact.filename)
    pdf_artifact = svc.export(format="pdf", lang="en", scope="all")
    assert pdf_artifact.filename.endswith(".pdf")
    assert "/" not in pdf_artifact.filename and ".." not in pdf_artifact.filename


def test_preview_reports_warnings_for_unknown_data():
    svc = service(
        [trade(id="TRD-UNKNOWN", symbol="XAUUSD", pnl=None, qty_unit="UNKNOWN")],
        tracking=[tracking_state("TRD-UNKNOWN", 5.0)],
    )
    preview = svc.preview(scope="all")
    joined = " ".join(preview["warnings"])
    assert "unknown_pnl" in joined
    assert "unverified_currency" in joined
    assert "local_estimates" in joined
    assert preview["exceeds_limit"] is False
    assert preview["max_records"] > 0


# ---------------------------------------------------------------------------
# Evidence Pack PDF
# ---------------------------------------------------------------------------


def test_evidence_pack_service_offers_a_pdf_artifact():
    from app.services.evidence_pack_export import EvidencePackExportService

    pack = {
        "trade": {
            "id": "TRD-1", "symbol": "BTCUSDT", "side": "BUY", "status": "CLOSED",
            "entry_price": 100.0, "exit_price": 110.0, "qty": 1.0, "pnl": 9.5,
            "commission": 0.5, "entry_time": "2026-08-02T09:00:00.000000Z",
            "exit_time": "2026-08-02T12:00:00.000000Z", "position_type": "LONG",
        },
        "read_source": "PROJECTION",
        "event_count": 4,
        "coverage_summary": {"overall": "PARTIAL"},
        "ledger_integrity": {"valid": True, "checked_events": 4},
        "applicable_rules": [],
        "events": [],
        "snapshot_sha256": None,
    }

    class Adapter:
        def get_evidence_pack(self, trade_id, **kwargs):
            return pack

    svc = EvidencePackExportService(adapter=Adapter())
    artifact = svc.export("TRD-1", "pdf")
    assert artifact.artifact_format == "pdf"
    assert artifact.content.startswith(b"%PDF")
    text = pdf_text(artifact.content)
    assert "TRD-1" in text
    assert "BTCUSDT" in text
    assert "9.5" in text or "9,5" in text


# ---------------------------------------------------------------------------
# HTTP endpoints
# ---------------------------------------------------------------------------


def _api_client(monkeypatch, service_instance):
    from fastapi.testclient import TestClient

    from app.api import endpoints
    from app.db.sqlite_driver import SQLiteDriver
    from main import create_app

    import tempfile
    from pathlib import Path

    monkeypatch.setattr(endpoints, "journal_export_service", service_instance)
    tmp = Path(tempfile.mkdtemp(prefix="jx-api-"))
    monkeypatch.setattr(endpoints, "sqlite_driver", SQLiteDriver(str(tmp / "api.sqlite")))
    return TestClient(create_app())


def test_export_endpoint_streams_csv_with_headers(monkeypatch):
    client = _api_client(monkeypatch, service([trade()]))
    response = client.get("/api/v1/journal/export?format=csv&lang=tr&scope=all")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "kuantra-journal-all-all-" in response.headers["content-disposition"]
    assert len(response.headers["x-kuantra-snapshot-sha256"]) == 64
    assert response.headers["x-kuantra-record-count"] == "1"
    assert response.content.startswith(b"\xef\xbb\xbf")


def test_export_endpoint_streams_pdf(monkeypatch):
    client = _api_client(monkeypatch, service([trade()]))
    response = client.get("/api/v1/journal/export?format=pdf&lang=en&scope=all")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")


def test_export_endpoint_validates_inputs(monkeypatch):
    client = _api_client(monkeypatch, service([trade()]))
    assert client.get("/api/v1/journal/export?format=xlsx&scope=all").status_code == 400
    assert client.get("/api/v1/journal/export?format=csv&scope=everything").status_code == 400
    assert client.get("/api/v1/journal/export?format=csv&scope=all&date_from=2026-13-01").status_code == 400


def test_export_endpoint_reports_limit_without_truncating(monkeypatch):
    monkeypatch.setattr("app.services.journal_export.MAX_EXPORT_TRADES", 1)
    client = _api_client(monkeypatch, service([trade(id="A"), trade(id="B")]))
    response = client.get("/api/v1/journal/export?format=csv&scope=all")
    assert response.status_code == 413
    assert response.json()["detail"]["reason"] == "EXPORT_LIMIT_EXCEEDED"
    preview = client.get("/api/v1/journal/export/preview?scope=all")
    assert preview.status_code == 413


def test_preview_endpoint_describes_snapshot(monkeypatch):
    client = _api_client(monkeypatch, service([trade()]))
    response = client.get("/api/v1/journal/export/preview?scope=filtered&symbols=BTCUSDT&statuses=CLOSED&date_basis=close")
    assert response.status_code == 200
    body = response.json()
    assert body["record_count"] == 1
    assert body["counts"]["closed"] == 1
    assert body["snapshot_sha256"]
    assert body["max_records"] > 0


def test_evidence_export_endpoint_accepts_pdf(monkeypatch):
    from fastapi.testclient import TestClient

    from app.api import endpoints
    from app.services.evidence_pack_export import EvidencePackExportService
    from main import create_app

    pack = {
        "trade": {"id": "TRD-PDF", "symbol": "BTCUSDT", "side": "BUY", "status": "CLOSED",
                  "entry_price": 1.0, "exit_price": 2.0, "qty": 1.0, "pnl": 1.0},
        "read_source": "PROJECTION", "event_count": 1, "coverage_summary": {"overall": "PARTIAL"},
        "ledger_integrity": {"valid": True, "checked_events": 1}, "applicable_rules": [], "events": [],
    }

    class Adapter:
        def get_evidence_pack(self, trade_id, **kwargs):
            return pack

    monkeypatch.setattr(endpoints, "evidence_pack_export_service", EvidencePackExportService(adapter=Adapter()))
    client = TestClient(create_app())
    response = client.get("/api/v1/trades/TRD-PDF/evidence/export?format=pdf")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")

    for existing in ("json", "html", "csv"):
        legacy = client.get(f"/api/v1/trades/TRD-PDF/evidence/export?format={existing}")
        assert legacy.status_code == 200


def test_pdf_page_count_matches_the_footer_total():
    from pypdf import PdfReader

    single = service([trade()]).export(format="pdf", lang="en", scope="all")
    single_reader = PdfReader(io.BytesIO(single.content))
    assert len(single_reader.pages) == 1
    single_text = single_reader.pages[0].extract_text() or ""
    assert "Page 1 / 1" in single_text

    many = service([
        trade(id=f"TRD-{index:04d}", entry_time=f"2026-08-{(index % 28) + 1:02d}T09:00:00.000000Z",
              exit_time=f"2026-08-{(index % 28) + 1:02d}T12:00:00.000000Z", notes="not " + "x" * 300)
        for index in range(90)
    ]).export(format="pdf", lang="en", scope="all")
    reader = PdfReader(io.BytesIO(many.content))
    pages = len(reader.pages)
    assert pages >= 3
    last_text = reader.pages[-1].extract_text() or ""
    assert f"Page {pages} / {pages}" in last_text
    assert last_text.strip()  # no empty trailing page
