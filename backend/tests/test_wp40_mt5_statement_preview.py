"""WP40 — MT5 HTML statement preview: safe, read-only parsing contract.

This suite covers the preview-only package: a single, explicitly defined
English MT5 "ReportHistory" HTML template is parsed in memory, nothing is
written anywhere, no timezone or financial value is invented, and unsupported
variants fail closed.  The synthetic fixtures below describe the supported
template contract; they are not XM compatibility evidence.
"""

from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.api import endpoints
from app.core.input_limits import MAX_STATEMENT_BYTES, MAX_STATEMENT_PREVIEW_ROWS
from app.db.repositories.evidence_ledger_repo import EvidenceLedgerRepository
from app.db.sqlite_driver import SQLiteDriver
from app.services.mt5_statement_preview import (
    PARSER_VERSION,
    Mt5StatementPreviewError,
    preview_mt5_html_report,
)
from main import create_app

_ACCOUNT_NUMBER = "87654321"
_ACCOUNT_OWNER = "Pilot Owner Name"
_HEADER_BLOCK = f"""
<table>
  <tr><td>XM Global Limited</td></tr>
  <tr><td>Account: {_ACCOUNT_NUMBER} (USD, XM Global Limited)</td></tr>
  <tr><td>Name: {_ACCOUNT_OWNER}</td></tr>
  <tr><td>Date: 2026.09.10 12:00:00</td></tr>
</table>
"""


def _orders_table(rows: list[list[str]]) -> str:
    header = (
        "<tr><td>Open Time</td><td>Order</td><td>Symbol</td><td>Type</td>"
        "<td>Volume</td><td>Price</td><td>S/L</td><td>T/P</td><td>Time</td><td>State</td></tr>"
    )
    body = "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows)
    return f"<table><tr><td>Orders</td></tr>{header}{body}</table>"


def _deals_table(rows: list[list[str]]) -> str:
    header = (
        "<tr><td>Time</td><td>Deal</td><td>Symbol</td><td>Type</td><td>Direction</td>"
        "<td>Volume</td><td>Price</td><td>Order</td><td>Commission</td><td>Fee</td>"
        "<td>Swap</td><td>Profit</td><td>Balance</td></tr>"
    )
    body = "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows)
    return f"<table><tr><td>Deals</td></tr>{header}{body}</table>"


def _order_row(order_id: str = "1001", **overrides: str) -> list[str]:
    row = [
        "2026.09.01 10:00:00", order_id, "XAUUSD", "buy",
        "0.10", "2500.00", "2480.00", "2550.00", "2026.09.01 10:00:00", "filled",
    ]
    for index, value in overrides.items():
        row[int(index)] = value
    return row


def _deal_row(deal_id: str = "5001", order_id: str = "1001", **overrides: str) -> list[str]:
    row = [
        "2026.09.01 10:00:00", deal_id, "XAUUSD", "buy", "in",
        "0.10", "2500.00", order_id, "-0.50", "0.00", "0.00", "0.00", "10000.00",
    ]
    for index, value in overrides.items():
        row[int(index)] = value
    return row


def _report(orders: list[list[str]] | None = None, deals: list[list[str]] | None = None,
            *, extra_html: str = "", include_positions: bool = True) -> bytes:
    orders = orders if orders is not None else [_order_row()]
    deals = deals if deals is not None else [
        _deal_row(),
        _deal_row("5002", "1001", **{
            "0": "2026.09.10 11:00:00",
            "3": "sell",
            "4": "out",
            "6": "2510.00",
            "11": "100.00",
            "12": "10099.20",
        }),
    ]
    positions = ""
    if include_positions:
        positions = (
            "<table><tr><td>Positions</td></tr><tr><td>Time</td><td>Position</td><td>Symbol</td>"
            "<td>Type</td><td>Volume</td><td>Price</td></tr>"
            "<tr><td>2026.09.10 11:00:00</td><td>9001</td><td>XAUUSD</td><td>buy</td><td>0.10</td>"
            "<td>2510.00</td></tr></table>"
            "<table><tr><td>Working Orders</td></tr><tr><td>Order</td></tr><tr><td>2001</td></tr></table>"
            "<table><tr><td>Summary</td></tr><tr><td>Balance</td><td>10099.20</td></tr></table>"
        )
    html = (
        "<html><head><title>Trade Report</title></head><body>"
        + _HEADER_BLOCK
        + _orders_table(orders)
        + _deals_table(deals)
        + positions
        + extra_html
        + "</body></html>"
    )
    return html.encode("utf-8")


# ---------------------------------------------------------------------------
# Supported template and section contracts
# ---------------------------------------------------------------------------


def test_supported_english_report_parses_orders_and_deals_separately():
    preview = preview_mt5_html_report(_report())

    assert preview["preview_only"] is True
    assert preview["format"] == "MT5_HTML_REPORT"
    assert preview["language"] == "EN"
    assert preview["parser_version"] == PARSER_VERSION
    assert preview["counts"] == {
        "orders": 1,
        "deals": 2,
        "rows_total": 3,
        "rows_ok": 3,
        "rows_with_errors": 0,
    }
    assert [row["source_identity"] for row in preview["orders"]] == ["1001"]
    assert [row["source_identity"] for row in preview["deals"]] == ["5001", "5002"]
    assert preview["orders"][0]["source_identity_kind"] == "SOURCE_ORDER_ID"
    assert all(row["source_identity_kind"] == "SOURCE_DEAL_ID" for row in preview["deals"])
    assert preview["deals"][1]["related_order_id"] == "1001"
    assert preview["date_range"] == {
        "start_source": "2026.09.01 10:00:00",
        "end_source": "2026.09.10 11:00:00",
    }


def test_order_and_deal_identity_kinds_are_never_substituted():
    preview = preview_mt5_html_report(_report())
    order_ids = {row["source_identity"] for row in preview["orders"]}
    deal_ids = {row["source_identity"] for row in preview["deals"]}
    assert order_ids.isdisjoint(deal_ids)
    assert preview["deals"][0]["related_order_id"] == "1001"
    assert "related_order_id" not in preview["deals"][0] or preview["deals"][0]["related_order_id"] != preview["deals"][0]["source_identity"]


def test_out_of_scope_sections_are_reported_not_silently_dropped():
    preview = preview_mt5_html_report(_report())
    assert preview["unsupported_sections"] == ["Positions", "Working Orders", "Summary"]
    assert "OUT_OF_SCOPE_SECTIONS_PRESENT" in preview["warnings"]


# ---------------------------------------------------------------------------
# Fail-closed format detection
# ---------------------------------------------------------------------------


def test_wrong_platform_or_unknown_template_is_rejected():
    mt4_like = (
        b"<html><body><table><tr><td>Closed Transactions</td></tr>"
        b"<tr><td>Ticket</td><td>Open Time</td><td>Type</td><td>Size</td></tr>"
        b"<tr><td>1</td><td>2026.09.01 10:00:00</td><td>buy</td><td>0.10</td></tr>"
        b"</table></body></html>"
    )
    with pytest.raises(Mt5StatementPreviewError, match="UNSUPPORTED_TEMPLATE"):
        preview_mt5_html_report(mt4_like)


def test_unsupported_language_is_rejected():
    translated = (
        "<html><body>"
        + _HEADER_BLOCK.replace("Account:", "Konto:")
        + "<table><tr><td>Aufträge</td></tr>"
          "<tr><td>Eröffnungszeit</td><td>Auftrag</td><td>Symbol</td><td>Typ</td>"
          "<td>Volumen</td><td>Preis</td></tr>"
          "<tr><td>2026.09.01 10:00:00</td><td>1001</td><td>XAUUSD</td><td>buy</td>"
          "<td>0.10</td><td>2500.00</td></tr></table>"
          "<table><tr><td>Deals</td></tr>"
          "<tr><td>Zeit</td><td>Deal</td><td>Symbol</td><td>Typ</td><td>Richtung</td>"
          "<td>Volumen</td><td>Preis</td><td>Auftrag</td></tr>"
          "<tr><td>2026.09.01 10:00:00</td><td>5001</td><td>XAUUSD</td><td>buy</td>"
          "<td>in</td><td>0.10</td><td>2500.00</td><td>1001</td></tr></table>"
        + "</body></html>"
    ).encode("utf-8")
    with pytest.raises(Mt5StatementPreviewError, match="UNSUPPORTED_LANGUAGE"):
        preview_mt5_html_report(translated)


@pytest.mark.parametrize("payload", [b"", b"<html><body></body></html>", b"<html><body><table></table></body></html>"])
def test_empty_or_truncated_document_is_rejected(payload):
    with pytest.raises(Mt5StatementPreviewError, match="UNSUPPORTED_TEMPLATE"):
        preview_mt5_html_report(payload)


def test_missing_deals_section_is_rejected_even_with_orders():
    html = (
        "<html><body>" + _HEADER_BLOCK + _orders_table([_order_row()]) + "</body></html>"
    ).encode("utf-8")
    with pytest.raises(Mt5StatementPreviewError, match="MISSING_SECTION"):
        preview_mt5_html_report(html)


# ---------------------------------------------------------------------------
# Row-level behaviour: mixed valid/invalid, ambiguity, time, money
# ---------------------------------------------------------------------------


def test_mixed_rows_are_split_into_ok_and_error_rows():
    deals = [
        _deal_row("5001"),
        _deal_row("5002", **{"1": ""}),
        _deal_row("5003", **{"0": "not-a-time"}),
        _deal_row("5004", **{"5": "0.1 0"}),
    ]
    preview = preview_mt5_html_report(_report(orders=[], deals=deals))
    assert preview["counts"] == {
        "orders": 0,
        "deals": 4,
        "rows_total": 4,
        "rows_ok": 1,
        "rows_with_errors": 3,
    }
    reasons = sorted(error["reason"] for error in preview["row_errors"])
    assert reasons == ["MISSING_DEAL_ID", "UNPARSED_NUMBER", "UNPARSED_TIME"]
    assert all("source_row" in error and error["section"] == "deal" for error in preview["row_errors"])
    assert [row["source_identity"] for row in preview["deals"]] == ["5001"]


def test_missing_order_identity_is_a_row_error_never_a_deal_identity():
    deals = [_deal_row("5001", **{"7": ""})]
    preview = preview_mt5_html_report(_report(orders=[], deals=deals))
    assert preview["counts"]["rows_with_errors"] == 1
    assert preview["row_errors"][0]["reason"] == "MISSING_ORDER_REFERENCE"
    assert preview["deals"] == []


def test_source_time_is_preserved_and_never_converted_to_utc():
    preview = preview_mt5_html_report(_report())
    row = preview["deals"][0]
    assert row["time_source"] == "2026.09.01 10:00:00"
    assert row["time_local"] == "2026-09-01T10:00:00"
    assert preview["time_basis"] == "SOURCE_LOCAL_TIME_UNVERIFIED"
    assert "SOURCE_TIME_BASIS_UNVERIFIED" in preview["warnings"]


def test_ambiguous_number_format_keeps_source_text_and_is_not_guessed():
    deals = [_deal_row("5001", **{"5": "2,500.00"}), _deal_row("5002", **{"5": "0,10"})]
    preview = preview_mt5_html_report(_report(orders=[], deals=deals))
    assert preview["deals"] == []
    assert {error["reason"] for error in preview["row_errors"]} == {"UNPARSED_NUMBER"}
    assert preview["counts"]["rows_with_errors"] == 2


def test_missing_financial_values_stay_absent_and_are_not_zero():
    deals = [
        _deal_row("5001", **{"8": "", "9": "", "10": "", "11": ""}),
    ]
    preview = preview_mt5_html_report(_report(orders=[], deals=deals))
    row = preview["deals"][0]
    for field in ("commission", "fee", "swap", "reported_profit"):
        assert row[field] is None
        assert row[f"{field}_source"] in ("", None)
    assert row["reported_profit"] != "0"


def test_quantity_is_labelled_as_source_lots_and_never_converted():
    preview = preview_mt5_html_report(_report())
    row = preview["deals"][0]
    assert row["volume_source"] == "0.10"
    assert row["volume"] == "0.1"
    assert row["volume_unit"] == "SOURCE_LOT"
    assert "volume_ounces" not in row
    assert preview["quantity_unit"] == "SOURCE_LOT"


# ---------------------------------------------------------------------------
# Limits, masking, hash and safety metadata
# ---------------------------------------------------------------------------


def test_row_limit_is_enforced_with_explicit_limit_error():
    deals = [_deal_row(str(6000 + index)) for index in range(MAX_STATEMENT_PREVIEW_ROWS + 3)]
    preview = preview_mt5_html_report(_report(orders=[], deals=deals))
    assert preview["counts"]["deals"] == MAX_STATEMENT_PREVIEW_ROWS + 3
    assert len(preview["deals"]) == MAX_STATEMENT_PREVIEW_ROWS
    assert preview["deals_truncated"] is True
    assert preview["limits"]["max_preview_rows"] == MAX_STATEMENT_PREVIEW_ROWS


def test_cell_limit_is_enforced_with_file_level_error():
    oversized_cell = "A" * 5000
    deals = [_deal_row("5001", **{"2": oversized_cell})]
    with pytest.raises(Mt5StatementPreviewError, match="CELL_LIMIT_EXCEEDED"):
        preview_mt5_html_report(_report(orders=[], deals=deals))


def test_account_is_masked_and_owner_name_never_appears():
    preview = preview_mt5_html_report(_report())
    assert preview["account"] == {
        "masked": "****4321",
        "basis": "SOURCE_DECLARED",
        "verified": False,
    }
    assert preview["account_currency"] == "USD"
    serialized = repr(preview)
    assert _ACCOUNT_NUMBER not in serialized
    assert _ACCOUNT_OWNER not in serialized
    assert "SOURCE_ACCOUNT_NOT_VERIFIED" in preview["warnings"]


def test_preview_carries_hash_parser_version_and_settings():
    payload = _report()
    preview = preview_mt5_html_report(payload)
    assert preview["parser_version"] == PARSER_VERSION
    assert preview["source_sha256"] == __import__("hashlib").sha256(payload).hexdigest()
    assert preview["source_size_bytes"] == len(payload)
    assert preview["parse_settings"]["timezone_conversion"] == "NONE"
    assert preview["parse_settings"]["financial_recalculation"] == "NONE"
    assert preview["limits"]["max_statement_bytes"] == MAX_STATEMENT_BYTES


def test_script_and_external_resources_are_not_interpreted():
    extra = (
        "<script>window.__kuantra_pwned = 1;</script>"
        '<img src="http://198.51.100.7/beacon.png">'
        '<link rel="stylesheet" href="http://198.51.100.7/style.css">'
    )
    preview = preview_mt5_html_report(_report(extra_html=extra))
    assert "pwned" not in repr(preview).lower()
    assert preview["counts"]["rows_ok"] == 3


# ---------------------------------------------------------------------------
# No persistence
# ---------------------------------------------------------------------------


def test_service_does_not_open_or_write_the_database(tmp_path, monkeypatch):
    database = tmp_path / "wp40.sqlite"
    driver = SQLiteDriver(str(database))
    monkeypatch.setattr(endpoints, "sqlite_driver", driver)
    before_events = EvidenceLedgerRepository(str(database)).count_events()

    preview_mt5_html_report(_report())

    assert driver.list_trades(limit=10) == []
    assert EvidenceLedgerRepository(str(database)).count_events() == before_events


def test_endpoint_previews_without_writing_and_without_secret_logs(tmp_path, monkeypatch, caplog):
    database = tmp_path / "wp40-endpoint.sqlite"
    driver = SQLiteDriver(str(database))
    monkeypatch.setattr(endpoints, "sqlite_driver", driver)
    client = TestClient(create_app())

    with caplog.at_level("DEBUG"):
        response = client.post(
            "/api/v1/broker/statement/preview-html",
            files={"file": ("xm-report.html", _report(), "text/html")},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["preview_only"] is True
    assert body["counts"]["deals"] == 2
    assert driver.list_trades(limit=10) == []
    assert EvidenceLedgerRepository(str(database)).count_events() == 0
    assert _ACCOUNT_OWNER not in caplog.text
    assert _ACCOUNT_NUMBER not in caplog.text


def test_endpoint_rejects_wrong_extension_and_oversized_uploads(tmp_path, monkeypatch):
    database = tmp_path / "wp40-limits.sqlite"
    monkeypatch.setattr(endpoints, "sqlite_driver", SQLiteDriver(str(database)))
    client = TestClient(create_app())

    wrong = client.post(
        "/api/v1/broker/statement/preview-html",
        files={"file": ("statement.csv", b"a,b,c", "text/csv")},
    )
    assert wrong.status_code == 400
    assert wrong.json()["detail"]["code"] == "UNSUPPORTED_FILE_TYPE"

    oversized = client.post(
        "/api/v1/broker/statement/preview-html",
        files={"file": ("big.html", b"<html>" + b"A" * (MAX_STATEMENT_BYTES + 1), "text/html")},
    )
    assert oversized.status_code == 413
