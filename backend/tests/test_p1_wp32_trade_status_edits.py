"""Editable trade status for a note-style journal.

Canceled trades can be restored to open or closed, completed trades can be
reopened, and an open trade can be closed from the editor with user-reported
exit data.  Every transition is revisioned and previous values stay in the
append-only correction provenance.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api import endpoints
from app.db import sync_pipeline as sync_pipeline_module
from app.db.repositories.evidence_projection_repo import EvidenceTradeProjectionRepository
from app.db.sqlite_driver import SQLiteDriver
from app.services import portfolio_service as portfolio_service_module
from app.services.local_tracking import LocalTrackingService
from app.services.trade_edit import TradeEditService
from app.services.trade_read_adapter import TradeReadAdapter
from main import create_app


def _naive_input(value: datetime) -> str:
    return value.replace(second=0, microsecond=0).isoformat()


@pytest.fixture
def journal(monkeypatch, tmp_path):
    driver = SQLiteDriver(str(tmp_path / "status-edits.sqlite"))
    monkeypatch.setattr(endpoints, "sqlite_driver", driver)
    monkeypatch.setattr(sync_pipeline_module, "sqlite_driver", driver)
    monkeypatch.setattr(sync_pipeline_module, "duckdb_driver", SimpleNamespace(is_available=False))
    adapter = TradeReadAdapter(
        legacy_driver=driver,
        projection_repo=EvidenceTradeProjectionRepository(driver.db_path),
    )
    monkeypatch.setattr(endpoints, "trade_read_adapter", adapter)
    monkeypatch.setattr(portfolio_service_module, "trade_read_adapter", adapter)
    monkeypatch.setattr(endpoints, "trade_edit_service", TradeEditService(driver))
    return driver, TestClient(create_app())


def _create(client: TestClient, **overrides) -> dict:
    payload = {
        "symbol": "BTCUSDT",
        "side": "BUY",
        "position_type": "LONG",
        "entry_price": 100,
        "qty": 2,
        "qty_unit": "BASE",
        "price_source": "manual",
        "price_status": "UNAVAILABLE",
        "price_origin": "MANUAL",
    }
    payload.update(overrides)
    response = client.post("/api/v1/trades", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def test_canceled_trade_can_be_restored_to_open_and_tracked(journal):
    driver, client = journal
    trade = _create(client)
    canceled = client.delete(f"/api/v1/trades/{trade['id']}").json()["trade"]
    assert canceled["status"] == "CANCELED"
    revision = canceled["revision"]

    restored = client.patch(
        f"/api/v1/trades/{trade['id']}",
        json={"expected_revision": revision, "status": "OPEN"},
    )
    assert restored.status_code == 200, restored.text
    body = restored.json()
    assert body["trade"]["status"] == "OPEN"
    assert body["revision"] == revision + 1
    assert body["changed_fields"]["status"] == {"from": "CANCELED", "to": "OPEN"}
    assert driver.get_trade(trade["id"])["status"] == "OPEN"

    # The restored trade behaves like a normal open position again.
    plan = client.patch(
        f"/api/v1/trades/{trade['id']}",
        json={
            "expected_revision": body["revision"],
            "local_tracking": {
                "expected_revision": 0,
                "enabled": True,
                "source_id": "binance_public",
                "source_symbol": "BTCUSDT",
                "stop_loss": 95,
                "targets": [{"price": 110, "percent": 100}],
            },
        },
    )
    assert plan.status_code == 200, plan.text
    assert LocalTrackingService(driver).get(trade["id"])["targets"][0]["price"] == "110"

    adapter = endpoints.trade_read_adapter
    assert adapter.projection_repo.rebuild(dry_run=False)["ledger_valid"] is True
    assert adapter.get_trade(trade["id"])["status"] == "OPEN"


def test_canceled_trade_can_be_closed_with_user_reported_exit(journal):
    driver, client = journal
    entry_wall = datetime.now(timezone.utc) - timedelta(days=2)
    trade = _create(client, entry_time=_naive_input(entry_wall))
    canceled = client.delete(f"/api/v1/trades/{trade['id']}").json()["trade"]
    exit_wall = datetime.now(timezone.utc) - timedelta(days=1)

    closed = client.patch(
        f"/api/v1/trades/{trade['id']}",
        json={
            "expected_revision": canceled["revision"],
            "status": "CLOSED",
            "exit_price": 112,
            "exit_time": _naive_input(exit_wall),
        },
    )
    assert closed.status_code == 200, closed.text
    body = closed.json()
    assert body["trade"]["status"] == "CLOSED"
    assert body["trade"]["close_source"] == "USER_REPORTED"
    assert body["trade"]["pnl"] == pytest.approx(24)
    assert driver.get_trade(trade["id"])["status"] == "CLOSED"


def test_closed_trade_can_be_reopened_with_previous_values_preserved(journal):
    driver, client = journal
    trade = _create(client)
    closed = client.post(f"/api/v1/trades/{trade['id']}/close", json={"exit_price": 110}).json()

    reopened = client.patch(
        f"/api/v1/trades/{trade['id']}",
        json={"expected_revision": closed["revision"], "status": "OPEN"},
    )
    assert reopened.status_code == 200, reopened.text
    body = reopened.json()
    assert body["trade"]["status"] == "OPEN"
    assert body["trade"]["exit_price"] is None
    assert body["trade"]["exit_time"] is None
    assert body["trade"]["pnl"] == 0.0
    assert body["changed_fields"]["exit_price"]["from"] == 110
    assert body["changed_fields"]["pnl"]["from"] == pytest.approx(20)

    # The close was a correction, not a deletion: the ledger still has it.
    revisions = client.get(f"/api/v1/trades/{trade['id']}/revisions").json()["revisions"]
    assert any("exit_price" in revision["changed_fields"] for revision in revisions)
    summary = client.get("/api/v1/portfolio/summary").json()
    assert summary["total_closed_trades"] == 0


def test_open_trade_closes_from_editor_with_required_exit_data(journal):
    driver, client = journal
    entry_wall = datetime.now(timezone.utc) - timedelta(days=1)
    trade = _create(client, entry_time=_naive_input(entry_wall))
    missing = client.patch(
        f"/api/v1/trades/{trade['id']}",
        json={"expected_revision": 1, "status": "CLOSED"},
    )
    assert missing.status_code == 422
    assert missing.json()["detail"]["reason"] == "EXIT_REQUIRED_FOR_CLOSED"
    assert driver.get_trade(trade["id"])["status"] == "OPEN"

    exit_wall = datetime.now(timezone.utc) - timedelta(hours=1)
    closed = client.patch(
        f"/api/v1/trades/{trade['id']}",
        json={
            "expected_revision": 1,
            "status": "CLOSED",
            "exit_price": 90,
            "exit_time": _naive_input(exit_wall),
        },
    )
    assert closed.status_code == 200, closed.text
    assert closed.json()["trade"]["pnl"] == pytest.approx(-20)
    assert closed.json()["trade"]["close_source"] == "USER_REPORTED"


def test_unverified_unit_close_from_editor_stores_unknown_pnl(journal):
    driver, client = journal
    entry_wall = datetime.now(timezone.utc) - timedelta(days=1)
    trade = _create(
        client,
        symbol="XAUUSD",
        qty_unit="UNKNOWN",
        entry_price=2000,
        entry_time=_naive_input(entry_wall),
    )
    exit_wall = datetime.now(timezone.utc) - timedelta(hours=1)
    closed = client.patch(
        f"/api/v1/trades/{trade['id']}",
        json={
            "expected_revision": 1,
            "status": "CLOSED",
            "exit_price": 2100,
            "exit_time": _naive_input(exit_wall),
        },
    )
    assert closed.status_code == 200, closed.text
    assert closed.json()["trade"]["pnl"] is None


def test_closed_policy_still_requires_reopen_for_field_edits(journal):
    _, client = journal
    trade = _create(client)
    closed = client.post(f"/api/v1/trades/{trade['id']}/close", json={"exit_price": 110}).json()
    blocked = client.patch(
        f"/api/v1/trades/{trade['id']}",
        json={"expected_revision": closed["revision"], "qty": 5},
    )
    assert blocked.status_code == 422
    assert blocked.json()["detail"]["reason"] == "TRADE_CLOSED_NOTES_ONLY"

    notes = client.patch(
        f"/api/v1/trades/{trade['id']}",
        json={"expected_revision": closed["revision"], "notes": "post-close note"},
    )
    assert notes.status_code == 200
    assert notes.json()["trade"]["notes"] == "post-close note"


def test_cancel_from_closed_keeps_close_data_as_tombstone(journal):
    driver, client = journal
    trade = _create(client)
    closed = client.post(f"/api/v1/trades/{trade['id']}/close", json={"exit_price": 110}).json()

    rejected = client.patch(
        f"/api/v1/trades/{trade['id']}",
        json={"expected_revision": closed["revision"], "status": "CANCELED", "qty": 5},
    )
    assert rejected.status_code == 422

    canceled = client.patch(
        f"/api/v1/trades/{trade['id']}",
        json={"expected_revision": closed["revision"], "status": "CANCELED"},
    )
    assert canceled.status_code == 200, canceled.text
    stored = driver.get_trade(trade["id"])
    assert stored["status"] == "CANCELED"
    assert stored["exit_price"] == 110


def test_status_transitions_require_current_revision(journal):
    _, client = journal
    trade = _create(client)
    canceled = client.delete(f"/api/v1/trades/{trade['id']}").json()["trade"]
    stale = client.patch(
        f"/api/v1/trades/{trade['id']}",
        json={"expected_revision": 1, "status": "OPEN"},
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["reason"] == "REVISION_CONFLICT"
    assert canceled["revision"] == 2


def test_invalid_status_value_is_rejected(journal):
    _, client = journal
    trade = _create(client)
    invalid = client.patch(
        f"/api/v1/trades/{trade['id']}",
        json={"expected_revision": 1, "status": "PENDING"},
    )
    assert invalid.status_code == 422
