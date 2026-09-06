"""P1-WP11 fixture/export broker lifecycle and reconciliation contracts."""

import json
import io
from pathlib import Path

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
