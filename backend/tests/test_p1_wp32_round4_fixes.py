"""P1-WP32 round-4: provider labels must not grant unit verification.

A client-supplied ``price_source``/``price_source_symbol`` pair is not
verification: the backend cannot prove the instrument exists, is the same
product, or uses base-unit quantity.  Until such a verified catalog exists, the
only basis for monetary math is an explicit user ``qty_unit=BASE`` declaration,
and the result is labeled as a user declaration.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api import endpoints
from app.core.position_math import instrument_unit_basis, position_summary
from app.db import sync_pipeline as sync_pipeline_module
from app.db.repositories.evidence_projection_repo import EvidenceTradeProjectionRepository
from app.db.sqlite_driver import SQLiteDriver
from app.services.local_tracking import LocalTrackingService
from app.services.trade_edit import TradeEditService
from app.services.trade_read_adapter import TradeReadAdapter
from main import create_app


@pytest.fixture
def journal(monkeypatch, tmp_path):
    driver = SQLiteDriver(str(tmp_path / "round4.sqlite"))
    monkeypatch.setattr(endpoints, "sqlite_driver", driver)
    monkeypatch.setattr(sync_pipeline_module, "sqlite_driver", driver)
    monkeypatch.setattr(sync_pipeline_module, "duckdb_driver", SimpleNamespace(is_available=False))
    adapter = TradeReadAdapter(
        legacy_driver=driver,
        projection_repo=EvidenceTradeProjectionRepository(driver.db_path),
    )
    monkeypatch.setattr(endpoints, "trade_read_adapter", adapter)
    monkeypatch.setattr(endpoints, "trade_edit_service", TradeEditService(driver))
    return driver, TestClient(create_app())


def _create(client: TestClient, **overrides) -> dict:
    payload = {
        "symbol": "BTCUSDT",
        "side": "BUY",
        "position_type": "LONG",
        "entry_price": 100,
        "qty": 2,
        "price_source": "manual",
        "price_status": "UNAVAILABLE",
        "price_origin": "MANUAL",
    }
    payload.update(overrides)
    response = client.post("/api/v1/trades", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def test_client_provider_labels_never_grant_verified_unit():
    # The unit-basis function accepts only an explicit declaration; provider
    # labels are not part of its contract at all.
    for symbol in ("FAKEUSD", "BTCUSDT", "EURUSD", "GBPUSD"):
        basis = instrument_unit_basis(symbol)
        assert basis["contract_size"] == "UNVERIFIED", symbol
        assert basis["verification"] == "NONE", symbol
        assert basis["verification_source"] == "NONE", symbol

    summary = position_summary(
        symbol="FAKEUSD", position_type="LONG", side="BUY",
        entry_price=100, qty=2, leverage=10, exit_price=110,
    )
    assert summary["instrument"]["verification"] == "NONE"
    assert summary["monetary_calculation"]["status"] == "UNAVAILABLE"
    assert summary["notional"]["value"] is None
    assert summary["returns"]["gross_pnl"] is None


def test_only_explicit_user_declaration_enables_math():
    declared = position_summary(
        symbol="EURUSD", position_type="LONG", side="BUY",
        entry_price=1.10, qty=1000, leverage=10, exit_price=1.12,
        qty_unit="BASE",
    )
    assert declared["instrument"]["verification"] == "EXPLICIT_QTY_UNIT"
    assert declared["instrument"]["verification_source"] == "USER_DECLARATION"
    assert declared["monetary_calculation"]["status"] == "READY"
    assert declared["notional"]["value"] == pytest.approx(1100)
    assert declared["returns"]["gross_pnl"] == pytest.approx(20)

    basis = instrument_unit_basis("FAKEUSD", qty_unit="BASE")
    assert basis["contract_size"] == "BASE_UNIT"
    assert basis["verification_source"] == "USER_DECLARATION"
    undeclared = instrument_unit_basis("FAKEUSD")
    assert undeclared["contract_size"] == "UNVERIFIED"
    assert undeclared["verification_source"] == "NONE"


def test_api_close_and_plan_gate_fake_provider_label(journal):
    driver, client = journal
    fake = _create(
        client,
        symbol="FAKEUSD",
        price_source="binance_public",
        price_source_symbol="FAKEUSD",
        price_status="LIVE",
        price_observed_at=datetime.now(timezone.utc).isoformat(),
        price_origin="PUBLIC_QUOTE",
    )
    assert fake["sizing"]["monetary_calculation"]["status"] == "UNAVAILABLE"
    closed = client.post(f"/api/v1/trades/{fake['id']}/close", json={"exit_price": 120})
    assert closed.status_code == 200
    assert closed.json()["pnl"] is None

    rejected = client.post(
        "/api/v1/trades",
        json={
            "symbol": "FAKEUSD",
            "side": "BUY",
            "position_type": "LONG",
            "entry_price": 100,
            "qty": 2,
            "price_source": "binance_public",
            "price_source_symbol": "FAKEUSD",
            "price_status": "LIVE",
            "price_observed_at": datetime.now(timezone.utc).isoformat(),
            "price_origin": "PUBLIC_QUOTE",
            "local_tracking": {
                "enabled": True,
                "source_id": "binance_public",
                "source_symbol": "FAKEUSD",
                "targets": [{"price": 120, "percent": 100}],
                "stop_loss": 90,
            },
        },
    )
    assert rejected.status_code == 422
    assert "base-unit" in rejected.text
    # Only the first (closed) trade exists; the rejected create rolled back.
    assert len(driver.list_trades(limit=10)) == 1


def test_api_explicit_declaration_flow_stays_open(journal):
    driver, client = journal
    trade = _create(
        client,
        symbol="FAKEUSD",
        qty_unit="BASE",
        local_tracking={
            "enabled": True,
            "source_id": "binance_public",
            "source_symbol": "FAKEUSD",
            "targets": [{"price": 120, "percent": 100}],
            "stop_loss": 90,
        },
    )
    assert trade["qty_unit"] == "BASE"
    assert trade["sizing"]["instrument"]["verification"] == "EXPLICIT_QTY_UNIT"
    assert trade["sizing"]["instrument"]["verification_source"] == "USER_DECLARATION"
    assert trade["sizing"]["monetary_calculation"]["status"] == "READY"
    assert LocalTrackingService(driver).get(trade["id"])["targets"][0]["price"] == "120"

    closed = client.post(f"/api/v1/trades/{trade['id']}/close", json={"exit_price": 120})
    assert closed.json()["pnl"] == pytest.approx(40)

    # An open trade can revoke the declaration with a revisioned edit, and the
    # unit gate applies again without touching any stored close evidence.
    open_declared = _create(client, symbol="FAKEUSD", qty_unit="BASE")
    assert open_declared["sizing"]["monetary_calculation"]["status"] == "READY"
    revoked = client.patch(
        f"/api/v1/trades/{open_declared['id']}",
        json={"expected_revision": 1, "qty_unit": "UNKNOWN"},
    )
    assert revoked.status_code == 200, revoked.text
    assert revoked.json()["trade"]["qty_unit"] == "UNKNOWN"
    refetched = client.get(f"/api/v1/trades/{open_declared['id']}").json()
    assert refetched["sizing"]["monetary_calculation"]["status"] == "UNAVAILABLE"


def test_plan_gate_requires_declaration_not_provider_label(journal):
    driver, client = journal
    # A trustworthy-looking provider label on the trade does not enable a plan.
    rejected = client.post(
        "/api/v1/trades",
        json={
            "symbol": "BTCUSDT",
            "side": "BUY",
            "position_type": "LONG",
            "entry_price": 100,
            "qty": 2,
            "price_source": "binance_public",
            "price_source_symbol": "BTCUSDT",
            "price_status": "LIVE",
            "price_observed_at": datetime.now(timezone.utc).isoformat(),
            "price_origin": "PUBLIC_QUOTE",
            "local_tracking": {
                "enabled": True,
                "source_id": "binance_public",
                "source_symbol": "BTCUSDT",
                "targets": [{"price": 120, "percent": 100}],
                "stop_loss": 90,
            },
        },
    )
    assert rejected.status_code == 422

    declared = _create(
        client,
        qty_unit="BASE",
        local_tracking={
            "enabled": True,
            "source_id": "binance_public",
            "source_symbol": "BTCUSDT",
            "targets": [{"price": 120, "percent": 100}],
            "stop_loss": 90,
        },
    )
    assert LocalTrackingService(driver).get(declared["id"]) is not None
