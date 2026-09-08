"""P1-WP24 canonical Evidence Pack and deterministic export boundaries."""

import csv
import hashlib
import io

import pytest
from fastapi.testclient import TestClient

from app.api import endpoints
from app.db.repositories.evidence_ledger_repo import EvidenceLedgerRepository, canonical_json
from app.db.repositories.evidence_projection_repo import EvidenceTradeProjectionRepository
from app.db.sqlite_driver import SQLiteDriver
from app.services.evidence_pack_export import EvidencePackExportError, EvidencePackExportService
from app.services.trade_read_adapter import TradeReadAdapter
from main import create_app


class _ExportReader:
    def __init__(self, pack):
        self.pack = pack

    def get_evidence_pack(self, _trade_id):
        return self.pack


def _export_pack():
    return {
        "trade_id": "U03-1",
        "trade": {
            "id": "U03-1",
            "symbol": "=HYPERLINK(\"https://unsafe.example\")",
            "side": "BUY",
            "status": "CLOSED",
            "pnl": 1.25,
            "notes": "<script>alert(1)</script>",
        },
        "read_source": "compatibility_legacy",
        "coverage": {"ready": False},
        "coverage_summary": {
            "overall": "PARTIAL",
            "fees": "UNKNOWN",
            "funding_transfer": "NOT_AVAILABLE",
            "market_context": "NOT_AVAILABLE",
        },
        "applicable_rules": [{
            "kind": "risk",
            "rule_id": "risk-policy",
            "version": "3",
            "snapshot_sha256": "a" * 64,
        }],
        "ledger_integrity": {"valid": True, "checked_events": 1, "errors": []},
        "events": [],
        "event_count": 1,
        "market_context": {"status": "NO_DATA", "candles": []},
    }


def test_csv_export_is_deterministic_and_formula_safe():
    service = EvidencePackExportService(_ExportReader(_export_pack()))

    first = service.export("U03-1", "csv")
    second = service.export("U03-1", "csv")

    assert first.content == second.content
    assert first.media_type.startswith("text/csv")
    rows = list(csv.DictReader(io.StringIO(first.content.decode("utf-8"))))
    assert rows[0]["trade_id"] == "U03-1"
    assert rows[0]["symbol"].startswith("'")
    assert not rows[0]["symbol"].startswith("=")
    assert "<script>" not in first.content.decode("utf-8")


def test_csv_endpoint_exposes_artifact_and_snapshot_headers(monkeypatch):
    monkeypatch.setattr(
        endpoints,
        "evidence_pack_export_service",
        EvidencePackExportService(_ExportReader(_export_pack())),
    )
    response = TestClient(create_app()).get("/api/v1/trades/U03-1/evidence/export?format=csv")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["content-disposition"].endswith('kuantra-evidence-U03-1.csv"')
    assert response.headers["x-kuantra-evidence-payload-sha256"]
    assert response.headers["x-kuantra-evidence-artifact-sha256"]


def test_invalid_snapshot_digest_fails_closed():
    pack = _export_pack()
    pack["snapshot_sha256"] = "0" * 64
    service = EvidencePackExportService(_ExportReader(pack))

    with pytest.raises(EvidencePackExportError, match="snapshot digest"):
        service.export("U03-1", "json")


def test_read_adapter_adds_snapshot_digest_coverage_summary_and_rules(tmp_path):
    db_path = tmp_path / "u03.sqlite"
    driver = SQLiteDriver(str(db_path))
    ledger = EvidenceLedgerRepository(str(db_path))
    ledger.append_event(
        event_type="RiskEvaluated",
        account_id="local-journal",
        venue="local-journal",
        idempotency_key="u03-risk-1",
        normalized_payload={
            "trade": {"id": "U03-ADAPTER", "symbol": "BTCUSDT"},
            "decision": {
                "policy_id": "risk-policy",
                "policy_version": 3,
                "policy_snapshot_sha256": "b" * 64,
            },
        },
        occurred_at="2026-09-08T10:00:00Z",
        received_at="2026-09-08T10:00:00Z",
        adapter_version="u03-test",
        correlation_id="U03-ADAPTER",
    )

    adapter = TradeReadAdapter(
        legacy_driver=driver,
        projection_repo=EvidenceTradeProjectionRepository(str(db_path)),
    )
    first = adapter.get_evidence_pack("U03-ADAPTER")
    second = adapter.get_evidence_pack("U03-ADAPTER")

    assert first == second
    assert first["coverage_summary"]["overall"] == "PARTIAL"
    assert first["coverage_summary"]["fees"] == "NOT_AVAILABLE"
    assert first["coverage_summary"]["funding_transfer"] == "NOT_AVAILABLE"
    assert first["coverage_summary"]["market_context"] == "NOT_AVAILABLE"
    assert first["applicable_rules"] == [{
        "kind": "risk",
        "rule_id": "risk-policy",
        "version": "3",
        "snapshot_sha256": "b" * 64,
        "event_id": first["events"][0]["event_id"],
        "event_hash": first["events"][0]["event_hash"],
    }]
    snapshot = {key: value for key, value in first.items() if key != "snapshot_sha256"}
    assert first["snapshot_sha256"] == hashlib.sha256(
        canonical_json(snapshot).encode("utf-8")
    ).hexdigest()
