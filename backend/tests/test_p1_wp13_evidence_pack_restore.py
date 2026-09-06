"""P1-WP13 deterministic Evidence Pack export and restore drill contracts."""

import hashlib
import json

import pytest
from fastapi.testclient import TestClient

from main import create_app
from app.api import endpoints
from app.db.repositories.evidence_ledger_repo import EvidenceLedgerRepository
from app.db.sqlite_driver import SQLiteDriver
from app.services.evidence_pack_export import (
    EvidencePackExportError,
    EvidencePackExportService,
)
from app.services.maintenance.db_maintenance import DatabaseMaintenanceEngine


PACK = {
    "trade_id": "EXPORT-1",
    "trade": {
        "id": "EXPORT-1",
        "symbol": "BTCUSDT",
        "side": "BUY",
        "entry_price": 100.0,
        "exit_price": 105.0,
        "qty": 1.0,
        "entry_time": "2026-09-06T10:00:00Z",
        "exit_time": "2026-09-06T10:05:00Z",
        "status": "CLOSED",
        "pnl": 5.0,
    },
    "read_source": "typed_projection",
    "coverage": {"ready": True, "projected_count": 1},
    "ledger_integrity": {"valid": True, "checked_events": 2, "errors": []},
    "events": [],
    "event_count": 0,
    "market_context": {"status": "NO_DATA", "candles": []},
}


class _FakeTradeReader:
    def get_evidence_pack(self, trade_id):
        return {**PACK, "trade_id": trade_id, "trade": {**PACK["trade"], "id": trade_id}}


def test_json_and_html_exports_are_deterministic_and_hashed():
    service = EvidencePackExportService(_FakeTradeReader())

    first = service.export("EXPORT-1", "json")
    second = service.export("EXPORT-1", "json")
    html = service.export("EXPORT-1", "html")

    assert first.content == second.content
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.payload_sha256 == hashlib.sha256(
        json.dumps(PACK, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    envelope = json.loads(first.content)
    assert envelope["artifact_type"] == "kuantra.trade_evidence_pack"
    assert envelope["payload_sha256"] == first.payload_sha256
    assert html.media_type.startswith("text/html")
    assert html.content.startswith(b"<!doctype html>")
    assert b"Payload SHA-256" in html.content


def test_export_rejects_secret_fields_and_unsafe_trade_ids():
    class SecretReader:
        def get_evidence_pack(self, _trade_id):
            return {**PACK, "api_key": "must-not-export"}

    service = EvidencePackExportService(SecretReader())
    with pytest.raises(EvidencePackExportError, match="not exportable"):
        service.export("EXPORT-1")
    with pytest.raises(EvidencePackExportError, match="trade_id"):
        EvidencePackExportService(_FakeTradeReader()).export("../secret")


def test_evidence_export_endpoint_returns_artifact_headers(monkeypatch):
    monkeypatch.setattr(
        endpoints,
        "evidence_pack_export_service",
        EvidencePackExportService(_FakeTradeReader()),
    )
    response = TestClient(create_app()).get("/api/v1/trades/EXPORT-1/evidence/export?format=json")
    assert response.status_code == 200
    assert response.headers["x-kuantra-evidence-artifact-version"] == "1"
    assert response.headers["x-kuantra-evidence-payload-sha256"]
    assert response.headers["content-disposition"].endswith('kuantra-evidence-EXPORT-1.json"')
    assert response.json()["artifact_type"] == "kuantra.trade_evidence_pack"


def test_sqlite_backup_hash_chain_and_duckdb_restore_drill(tmp_path):
    sqlite_path = tmp_path / "source.sqlite"
    SQLiteDriver(str(sqlite_path))
    ledger = EvidenceLedgerRepository(str(sqlite_path))
    ledger.append_event(
        event_type="IntentRecorded",
        account_id="local-journal",
        venue="local-journal",
        idempotency_key="restore-drill-1",
        normalized_payload={
            "trade": {
                "id": "RESTORE-1",
                "symbol": "BTCUSDT",
                "side": "BUY",
                "entry_price": 100.0,
                "qty": 1.0,
                "entry_time": "2026-09-06T10:00:00Z",
                "status": "OPEN",
                "pnl": 0.0,
                "commission": 0.0,
            }
        },
        occurred_at="2026-09-06T10:00:00Z",
        adapter_version="p1-wp13-test",
        correlation_id="RESTORE-1",
    )

    engine = DatabaseMaintenanceEngine(
        sqlite_path=str(sqlite_path),
        duckdb_path=str(tmp_path / "source.duckdb"),
        backup_dir=str(tmp_path / "backups"),
    )
    result = engine.create_sqlite_shadow_backup()

    assert result["status"] == "SUCCESS"
    assert len(result["backup_sha256"]) == 64
    assert result["restore_verification"]["status"] == "VERIFIED"
    assert result["restore_verification"]["ledger_integrity"]["valid"] is True
    assert result["restore_verification"]["hydration"]["status"] == "HYDRATED"
