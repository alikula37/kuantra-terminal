"""P1-WP11 fixture/export broker lifecycle and reconciliation contracts."""

import json
import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from main import create_app
from app.db.repositories.evidence_ledger_repo import EvidenceLedgerRepository
from app.services.broker_import_service import BrokerImportService


FIXTURES = Path(__file__).parent / "fixtures" / "broker"


def _fixture(name: str):
    path = FIXTURES / name
    content = path.read_bytes()
    return json.loads(content), content


def test_binance_fixture_normalizes_and_reconciles(tmp_path):
    payload, source_bytes = _fixture("binance_orders_fills.json")
    ledger = EvidenceLedgerRepository(str(tmp_path / "ledger.sqlite"))
    service = BrokerImportService(ledger)

    report = service.import_json_document(
        "BINANCE",
        source_bytes,
        source_name="binance-orders-fills.json",
    )

    assert report["status"] == "RECONCILED"
    assert report["order_count"] == 2
    assert report["fill_count"] == 2
    assert report["reconciled_order_count"] == 2
    assert report["ledger_created_count"] == 4
    assert report["rejected_row_count"] == 0
    assert len(list(ledger.export_events(account_id="local-broker-import"))) == 4

    events = list(ledger.export_events(account_id="local-broker-import"))
    fill_event = next(event for event in events if event["event_type"] == "FillRecorded")
    assert fill_event["venue"] == "BINANCE"
    assert fill_event["provenance"]["source_file_sha256"] == report["source_file_sha256"]
    assert fill_event["provenance"]["source_row_number"] == 3
    assert "raw_payload" not in fill_event
    assert fill_event["normalized_payload"]["broker_lifecycle"]["external_fill_id"] == "BN-FILL-1"


def test_reimport_is_idempotent_even_when_source_manifest_repeats(tmp_path):
    payload, source_bytes = _fixture("binance_orders_fills.json")
    ledger = EvidenceLedgerRepository(str(tmp_path / "ledger.sqlite"))
    service = BrokerImportService(ledger)
    kwargs = {
        "venue": "BINANCE",
        "orders": payload["orders"],
        "fills": payload["fills"],
        "source_name": "daily-export.json",
        "source_bytes": source_bytes,
    }

    first = service.import_records(**kwargs)
    second = service.import_records(**{**kwargs, "source_name": "renamed-export.json"})
    assert first["ledger_created_count"] == 4
    assert second["ledger_created_count"] == 0
    assert second["ledger_duplicate_count"] == 4
    assert len(list(ledger.export_events(account_id="local-broker-import"))) == 4
    assert ledger.verify_chain(account_id="local-broker-import")["valid"] is True


def test_okx_aliases_normalize_without_live_connector(tmp_path):
    payload, source_bytes = _fixture("okx_orders_fills.json")
    service = BrokerImportService(EvidenceLedgerRepository(str(tmp_path / "ledger.sqlite")))
    report = service.import_records(
        "OKX",
        orders=payload["orders"],
        fills=payload["fills"],
        source_name="okx-orders-fills.json",
        source_bytes=source_bytes,
    )
    assert report["status"] == "RECONCILED"
    assert report["order_count"] == 2
    assert report["fill_count"] == 1
    assert report["orphan_fill_order_count"] == 0


def test_mismatch_or_orphan_is_explicitly_unreconciled(tmp_path):
    service = BrokerImportService(EvidenceLedgerRepository(str(tmp_path / "ledger.sqlite")))
    report = service.import_records(
        "BINANCE",
        orders=[{
            "orderId": "BAD-1",
            "symbol": "BTCUSDT",
            "side": "BUY",
            "status": "FILLED",
            "origQty": "2",
            "executedQty": "2",
            "avgPrice": "100",
            "updateTime": 1788256800000,
        }],
        fills=[{
            "id": "ORPHAN-FILL",
            "orderId": "UNKNOWN-ORDER",
            "symbol": "BTCUSDT",
            "side": "BUY",
            "qty": "1",
            "price": "100",
            "time": 1788256800000,
        }],
    )
    assert report["status"] == "UNRECONCILED"
    assert {item["type"] for item in report["discrepancies"]} >= {
        "MISSING_FILL_ROWS",
        "ORPHAN_FILL",
    }


def test_invalid_row_is_rejected_without_fabricated_timestamp(tmp_path):
    service = BrokerImportService(EvidenceLedgerRepository(str(tmp_path / "ledger.sqlite")))
    report = service.import_records(
        "OKX",
        orders=[{
            "ordId": "INVALID-1",
            "instId": "BTC-USDT-SWAP",
            "side": "buy",
            "state": "filled",
            "sz": "1",
            "accFillSz": "1",
            "uTime": "",
        }],
    )
    assert report["status"] == "UNRECONCILED"
    assert report["rejected_row_count"] == 1
    assert report["ledger_event_count"] == 0
    assert "occurred_at is required" in report["rejected_rows"][0]["reason"]


def test_decimal_lifecycle_values_are_exact_and_json_safe(tmp_path):
    service = BrokerImportService(EvidenceLedgerRepository(str(tmp_path / "ledger.sqlite")))
    report = service.import_records(
        "BINANCE",
        orders=[{
            "orderId": "DECIMAL-1",
            "symbol": "BTCUSDT",
            "side": "BUY",
            "status": "FILLED",
            "origQty": "0.3",
            "executedQty": "0.3",
            "avgPrice": "100.00000001",
            "fee": "0.03",
            "commissionAsset": "USDT",
            "updateTime": 1788256800000,
        }],
        fills=[
            {
                "id": "DECIMAL-FILL-1",
                "orderId": "DECIMAL-1",
                "symbol": "BTCUSDT",
                "side": "BUY",
                "qty": "0.1",
                "price": "100.00000001",
                "commission": "0.01",
                "commissionAsset": "USDT",
                "time": 1788256800000,
            },
            {
                "id": "DECIMAL-FILL-2",
                "orderId": "DECIMAL-1",
                "symbol": "BTCUSDT",
                "side": "BUY",
                "qty": "0.2",
                "price": "100.00000001",
                "commission": "0.02",
                "commissionAsset": "USDT",
                "time": 1788256800001,
            },
        ],
    )

    assert report["status"] == "RECONCILED"
    assert report["fee_reconciliation_status"] == "RECONCILED"
    event = next(event for event in service.ledger_repo.export_events(account_id="local-broker-import") if event["event_type"] == "FillRecorded")
    payload = event["normalized_payload"]["broker_lifecycle"]
    assert payload["numeric_encoding"] == "DECIMAL_STRING_V1"
    assert payload["numeric_units"]["filled_qty"] == "VENUE_NATIVE_QUANTITY"
    assert payload["numeric_units"]["fee"] == "CURRENCY:USDT"
    assert payload["filled_qty"] == "0.1"
    assert payload["price"] == "100.00000001"
    assert payload["fee"] == "0.01"


def test_missing_fee_is_not_treated_as_explicit_zero(tmp_path):
    service = BrokerImportService(EvidenceLedgerRepository(str(tmp_path / "ledger.sqlite")))
    order = {
        "orderId": "FEE-UNKNOWN",
        "symbol": "BTCUSDT",
        "side": "BUY",
        "status": "FILLED",
        "origQty": "1",
        "executedQty": "1",
        "avgPrice": "100",
        "fee": "0",
        "commissionAsset": "USDT",
        "updateTime": 1788256800000,
    }
    fill = {
        "id": "FEE-UNKNOWN-FILL",
        "orderId": "FEE-UNKNOWN",
        "symbol": "BTCUSDT",
        "side": "BUY",
        "qty": "1",
        "price": "100",
        "time": 1788256800000,
    }
    missing = service.import_records("BINANCE", orders=[order], fills=[fill])
    assert missing["status"] == "UNRECONCILED"
    assert missing["fee_reconciliation_status"] == "UNKNOWN"
    assert any(item["type"] == "FEE_DATA_INCOMPLETE" for item in missing["discrepancies"])

    explicit_zero = service.import_records(
        "BINANCE",
        orders=[{**order, "orderId": "FEE-ZERO", "fee": "0"}],
        fills=[{**fill, "id": "FEE-ZERO-FILL", "orderId": "FEE-ZERO", "commission": "0", "commissionAsset": "USDT"}],
    )
    assert explicit_zero["status"] == "RECONCILED"
    assert explicit_zero["fee_reconciliation_status"] == "RECONCILED"
    event = next(event for event in service.ledger_repo.export_events(account_id="local-broker-import") if event["correlation_id"] == "FEE-ZERO")
    assert event["normalized_payload"]["broker_lifecycle"]["fee"] == "0"


def test_fee_currency_mismatch_and_multi_currency_are_explicit(tmp_path):
    service = BrokerImportService(EvidenceLedgerRepository(str(tmp_path / "ledger.sqlite")))
    order = {
        "orderId": "FEE-CURRENCY",
        "symbol": "BTCUSDT",
        "side": "BUY",
        "status": "FILLED",
        "origQty": "1",
        "executedQty": "1",
        "avgPrice": "100",
        "fee": "0.2",
        "commissionAsset": "USDT",
        "updateTime": 1788256800000,
    }
    fills = [
        {
            "id": "FEE-CURRENCY-1",
            "orderId": "FEE-CURRENCY",
            "symbol": "BTCUSDT",
            "side": "BUY",
            "qty": "0.5",
            "price": "100",
            "commission": "0.1",
            "commissionAsset": "USDT",
            "time": 1788256800000,
        },
        {
            "id": "FEE-CURRENCY-2",
            "orderId": "FEE-CURRENCY",
            "symbol": "BTCUSDT",
            "side": "BUY",
            "qty": "0.5",
            "price": "100",
            "commission": "0.1",
            "commissionAsset": "BNB",
            "time": 1788256800001,
        },
    ]
    multi_currency = service.import_records("BINANCE", orders=[order], fills=fills)
    assert multi_currency["status"] == "UNRECONCILED"
    assert multi_currency["fee_reconciliation_status"] == "UNRECONCILED"
    assert any(item["type"] == "MULTI_CURRENCY_FEES" for item in multi_currency["discrepancies"])
    assert any(item["type"] == "FEE_CURRENCY_MISMATCH" for item in multi_currency["discrepancies"])

    unknown_currency = service.import_records(
        "BINANCE",
        orders=[{**order, "orderId": "FEE-UNKNOWN-CURRENCY", "commissionAsset": None}],
        fills=[{**fills[0], "id": "FEE-UNKNOWN-CURRENCY-FILL", "orderId": "FEE-UNKNOWN-CURRENCY", "commissionAsset": None}],
    )
    assert unknown_currency["status"] == "UNRECONCILED"
    assert any(item["type"] == "FEE_CURRENCY_UNKNOWN" for item in unknown_currency["discrepancies"])


def test_signed_fee_rebate_is_preserved(tmp_path):
    service = BrokerImportService(EvidenceLedgerRepository(str(tmp_path / "ledger.sqlite")))
    report = service.import_records(
        "OKX",
        orders=[{
            "ordId": "REBATE-1",
            "instId": "BTC-USDT-SWAP",
            "side": "buy",
            "state": "filled",
            "sz": "1",
            "accFillSz": "1",
            "avgPx": "60000",
            "fee": "-0.10",
            "feeCcy": "BNB",
            "uTime": "1788256800000",
        }],
        fills=[
            {
                "fillId": "REBATE-FILL-1",
                "ordId": "REBATE-1",
                "instId": "BTC-USDT-SWAP",
                "side": "buy",
                "sz": "0.5",
                "fillPx": "60000",
                "fee": "-0.04",
                "feeCcy": "BNB",
                "ts": "1788256800000",
            },
            {
                "fillId": "REBATE-FILL-2",
                "ordId": "REBATE-1",
                "instId": "BTC-USDT-SWAP",
                "side": "buy",
                "sz": "0.5",
                "fillPx": "60000",
                "fee": "-0.06",
                "feeCcy": "BNB",
                "ts": "1788256800001",
            },
        ],
    )
    assert report["status"] == "RECONCILED"
    assert report["fee_reconciliation_status"] == "RECONCILED"
    event = next(event for event in service.ledger_repo.export_events(account_id="local-broker-import") if event["event_type"] == "FillRecorded")
    assert event["normalized_payload"]["broker_lifecycle"]["fee"] == "-0.04"


@pytest.mark.parametrize("field, value", [
    ("origQty", "NaN"),
    ("origQty", "Infinity"),
    ("origQty", "1,5"),
    ("avgPrice", "-1"),
])
def test_invalid_decimal_or_locale_values_are_rejected(field, value):
    row = {
        "orderId": "INVALID-DECIMAL",
        "symbol": "BTCUSDT",
        "side": "BUY",
        "status": "NEW",
        "origQty": "1",
        "executedQty": "0",
        "avgPrice": "100",
        "updateTime": 1788256800000,
    }
    row[field] = value
    records, rejected = BrokerImportService.normalize_records("BINANCE", orders=[row])
    assert records == []
    assert len(rejected) == 1
    assert "finite number" in rejected[0]["reason"] or "cannot be negative" in rejected[0]["reason"]


def test_local_json_import_endpoint_is_read_only_and_bounded():
    _, source_bytes = _fixture("okx_orders_fills.json")
    client = TestClient(create_app())
    response = client.post(
        "/api/v1/broker/import-json?venue=OKX",
        files={"file": ("okx-export.json", io.BytesIO(source_bytes), "application/json")},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "RECONCILED"
    assert response.json()["venue"] == "OKX"

    invalid = client.post(
        "/api/v1/broker/import-json?venue=OKX",
        files={"file": ("okx-export.csv", io.BytesIO(source_bytes), "text/csv")},
    )
    assert invalid.status_code == 400
