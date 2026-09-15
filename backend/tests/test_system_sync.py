"""Full dual-database sync: honest endpoint outcomes, never a fabricated success."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.db.sqlite_driver import SQLiteDriver
from app.db.sync_pipeline import SyncPipeline
from main import create_app


def _trade(**overrides):
    value = {
        "id": "SYNC-1",
        "symbol": "BTCUSDT",
        "side": "BUY",
        "entry_price": 100.0,
        "qty": 1.0,
        "entry_time": "2026-09-15T10:00:00Z",
        "status": "OPEN",
        "notes": "sync fixture",
    }
    value.update(overrides)
    return value


def _use_driver(monkeypatch, driver):
    monkeypatch.setattr("app.db.sync_pipeline.sqlite_driver", driver)
    monkeypatch.setattr(
        "app.db.sync_pipeline.duckdb_driver",
        type("DuckDBDisabled", (), {"is_available": False})(),
    )


def test_full_sync_endpoint_reports_unavailable_duckdb(monkeypatch, tmp_path):
    driver = SQLiteDriver(str(tmp_path / "journal.sqlite"))
    _use_driver(monkeypatch, driver)

    response = TestClient(create_app()).post("/api/v1/system/sync/full")

    assert response.status_code == 200
    assert response.json() == {
        "available": False,
        "coverage_ready": False,
        "synced": 0,
        "reason": "DUCKDB_UNAVAILABLE",
    }


def test_full_sync_endpoint_syncs_ready_evidence_projection(monkeypatch, tmp_path):
    driver = SQLiteDriver(str(tmp_path / "journal.sqlite"))
    _use_driver(monkeypatch, driver)
    SyncPipeline.record_and_sync_trade(_trade(), source="manual")

    synced = []

    class RecordingDuckDB:
        is_available = True

        @staticmethod
        def sync_all_trades(trades):
            synced.extend(trades)
            return len(trades)

    monkeypatch.setattr("app.db.sync_pipeline.duckdb_driver", RecordingDuckDB())
    response = TestClient(create_app()).post("/api/v1/system/sync/full")

    assert response.status_code == 200
    payload = response.json()
    assert payload["available"] is True
    assert payload["coverage_ready"] is True
    assert payload["synced"] == 1
    assert payload["reason"] is None
    assert synced[0]["id"] == "SYNC-1"


def test_full_sync_endpoint_reports_blocked_coverage(monkeypatch, tmp_path):
    driver = SQLiteDriver(str(tmp_path / "journal.sqlite"))
    driver.insert_trade(_trade(id="LEGACY-1"))
    monkeypatch.setattr("app.db.sync_pipeline.sqlite_driver", driver)

    class UnexpectedDuckDB:
        is_available = True

        @staticmethod
        def sync_all_trades(_trades):
            raise AssertionError("blocked full sync must not reach DuckDB")

    monkeypatch.setattr("app.db.sync_pipeline.duckdb_driver", UnexpectedDuckDB())
    response = TestClient(create_app()).post("/api/v1/system/sync/full")

    assert response.status_code == 200
    assert response.json() == {
        "available": True,
        "coverage_ready": False,
        "synced": 0,
        "reason": "COVERAGE_INCOMPLETE",
    }
