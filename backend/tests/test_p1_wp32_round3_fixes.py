"""P1-WP32 round-3 fixes: plan-only edits and instrument verification.

1. A local plan edit that changes only TP2/TP3, allocations or the enabled flag
   must be persisted with its own revision comparison; `no_change` is only
   correct after the whole plan payload has been compared.
2. A symbol suffix alone must never grant verified base-unit status.  Monetary
   math requires provider-confirmed instrument identity or an explicit
   quantity-unit contract (`qty_unit=BASE`).
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


def _plan(stop: float = 95, targets: list | None = None, source: str | None = "binance_public") -> dict:
    return {
        "enabled": True,
        "source_id": source,
        "source_symbol": "BTCUSDT" if source else None,
        "targets": targets or [
            {"price": 110, "percent": 50},
            {"price": 120, "percent": 30},
            {"price": 130, "percent": 20},
        ],
        "stop_loss": stop,
    }


@pytest.fixture
def journal(monkeypatch, tmp_path):
    driver = SQLiteDriver(str(tmp_path / "round3.sqlite"))
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


# -- 1. plan-only edits ---------------------------------------------------


def test_plan_only_tp2_change_is_saved_with_plan_revision(journal):
    driver, client = journal
    trade = _create(client, qty_unit="BASE", local_tracking=_plan())
    response = client.patch(
        f"/api/v1/trades/{trade['id']}",
        json={
            "expected_revision": 1,
            "local_tracking": {
                "expected_revision": 1,
                "enabled": True,
                "source_id": "binance_public",
                "source_symbol": "BTCUSDT",
                "stop_loss": 95,
                "targets": [
                    {"price": 110, "percent": 50},
                    {"price": 118, "percent": 30},
                    {"price": 130, "percent": 20},
                ],
            },
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["no_change"] is False
    assert body["revision"] == 2
    assert body["tracking"]["revision"] == 2
    assert [t["price"] for t in body["tracking"]["targets"]] == ["110", "118", "130"]
    # Trade-level mirrors did not move because TP1/stop stayed the same.
    assert body["trade"]["take_profit"] == 110
    assert body["trade"]["stop_loss"] == 95
    state = LocalTrackingService(driver).get(trade["id"])
    assert state["targets"][1]["price"] == "118"


def test_plan_only_percent_and_enabled_changes_are_saved(journal):
    driver, client = journal
    trade = _create(client, qty_unit="BASE", local_tracking=_plan())

    percents = client.patch(
        f"/api/v1/trades/{trade['id']}",
        json={
            "expected_revision": 1,
            "local_tracking": {
                "expected_revision": 1,
                "enabled": True,
                "source_id": "binance_public",
                "source_symbol": "BTCUSDT",
                "stop_loss": 95,
                "targets": [
                    {"price": 110, "percent": 40},
                    {"price": 120, "percent": 35},
                    {"price": 130, "percent": 25},
                ],
            },
        },
    )
    assert percents.status_code == 200, percents.text
    assert percents.json()["no_change"] is False
    assert percents.json()["tracking"]["revision"] == 2
    assert [t["percent"] for t in percents.json()["tracking"]["targets"]] == ["40", "35", "25"]

    disabled = client.patch(
        f"/api/v1/trades/{trade['id']}",
        json={
            "expected_revision": 2,
            "local_tracking": {
                "expected_revision": 2,
                "enabled": False,
                "source_id": "binance_public",
                "source_symbol": "BTCUSDT",
                "stop_loss": 95,
                "targets": [
                    {"price": 110, "percent": 40},
                    {"price": 120, "percent": 35},
                    {"price": 130, "percent": 25},
                ],
            },
        },
    )
    assert disabled.status_code == 200, disabled.text
    assert disabled.json()["no_change"] is False
    assert disabled.json()["tracking"]["enabled"] is False
    assert LocalTrackingService(driver).get(trade["id"])["enabled"] is False


def test_identical_plan_payload_is_still_no_change(journal):
    driver, client = journal
    trade = _create(client, qty_unit="BASE", local_tracking=_plan())
    identical = client.patch(
        f"/api/v1/trades/{trade['id']}",
        json={"expected_revision": 1, "local_tracking": {**_plan(), "expected_revision": 1}},
    )
    assert identical.status_code == 200
    body = identical.json()
    assert body["no_change"] is True
    assert body["revision"] == 1
    assert LocalTrackingService(driver).get(trade["id"])["revision"] == 1


def test_plan_only_edit_validates_plan_revision(journal):
    _, client = journal
    trade = _create(client, qty_unit="BASE", local_tracking=_plan())
    first = client.patch(
        f"/api/v1/trades/{trade['id']}",
        json={
            "expected_revision": 1,
            "local_tracking": {
                "expected_revision": 1,
                "enabled": True,
                "source_id": "binance_public",
                "source_symbol": "BTCUSDT",
                "stop_loss": 95,
                "targets": [
                    {"price": 110, "percent": 50},
                    {"price": 118, "percent": 30},
                    {"price": 130, "percent": 20},
                ],
            },
        },
    )
    assert first.status_code == 200
    stale = client.patch(
        f"/api/v1/trades/{trade['id']}",
        json={
            "expected_revision": 2,
            "local_tracking": {
                "expected_revision": 1,
                "enabled": True,
                "source_id": "binance_public",
                "source_symbol": "BTCUSDT",
                "stop_loss": 95,
                "targets": [
                    {"price": 110, "percent": 50},
                    {"price": 119, "percent": 30},
                    {"price": 130, "percent": 20},
                ],
            },
        },
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["reason"] == "TRACKING_CONFLICT"


# -- 2. verified unit basis ----------------------------------------------


def test_suffix_alone_never_grants_verified_base_unit():
    for symbol in ("EURUSD", "GBPUSD", "FAKEUSD", "USDTRY", "BTCUSDT", "AAPL"):
        basis = instrument_unit_basis(symbol)
        assert basis["contract_size"] == "UNVERIFIED", symbol
        summary = position_summary(
            symbol=symbol, position_type="LONG", side="BUY",
            entry_price=100, qty=2, leverage=10, exit_price=110,
        )
        assert summary["monetary_calculation"]["status"] == "UNAVAILABLE", symbol
        assert summary["notional"]["value"] is None, symbol
        assert summary["returns"]["gross_pnl"] is None, symbol
        assert summary["returns"]["price_return_pct"] == pytest.approx(10), symbol


def test_explicit_qty_unit_contract_enables_math():
    summary = position_summary(
        symbol="EURUSD", position_type="LONG", side="BUY",
        entry_price=1.10, qty=1000, leverage=10, exit_price=1.12,
        qty_unit="BASE",
    )
    assert summary["instrument"]["verification"] == "EXPLICIT_QTY_UNIT"
    assert summary["monetary_calculation"]["status"] == "READY"
    assert summary["notional"]["value"] == pytest.approx(1100)
    assert summary["returns"]["gross_pnl"] == pytest.approx(20)


def test_provider_labels_and_suffixes_do_not_enable_math():
    # Round 4 supersedes the earlier provider-identity path: a client-supplied
    # provider label is not verification, so only the explicit declaration
    # enables monetary math.
    for symbol in ("BTCUSDT", "EURUSD", "FAKEUSD"):
        summary = position_summary(
            symbol=symbol, position_type="LONG", side="BUY",
            entry_price=100, qty=2, leverage=10, exit_price=110,
        )
        assert summary["instrument"]["verification"] == "NONE", symbol
        assert summary["monetary_calculation"]["status"] == "UNAVAILABLE", symbol
        assert summary["notional"]["value"] is None, symbol


def test_trade_records_qty_unit_and_close_gates_money(journal):
    driver, client = journal
    manual = _create(client, symbol="EURUSD", entry_price=1.10, qty=1000)
    assert manual["qty_unit"] == "UNKNOWN"
    closed = client.post(f"/api/v1/trades/{manual['id']}/close", json={"exit_price": 1.12})
    assert closed.status_code == 200, closed.text
    assert closed.json()["pnl"] is None

    declared = _create(client, symbol="EURUSD", entry_price=1.10, qty=1000, qty_unit="BASE")
    assert declared["qty_unit"] == "BASE"
    closed_declared = client.post(f"/api/v1/trades/{declared['id']}/close", json={"exit_price": 1.12})
    assert closed_declared.status_code == 200
    assert closed_declared.json()["pnl"] == pytest.approx(20)

    verified = _create(
        client,
        entry_price=100,
        qty=2,
        qty_unit="BASE",
    )
    closed_verified = client.post(f"/api/v1/trades/{verified['id']}/close", json={"exit_price": 110})
    assert closed_verified.json()["pnl"] == pytest.approx(20)


def test_local_plan_gate_requires_explicit_declaration(journal):
    driver, client = journal
    # A provider-looking plan identity without a declaration is rejected.
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
            "local_tracking": _plan(),
        },
    )
    assert rejected.status_code == 422
    assert "explicit unit declaration" in rejected.text

    declared = _create(client, qty_unit="BASE", local_tracking=_plan())
    assert LocalTrackingService(driver).get(declared["id"]) is not None

    # Explicit quantity-unit contract allows a display-only source (gold ounces).
    explicit = _create(
        client,
        symbol="XAUUSD",
        entry_price=2000,
        qty=2,
        qty_unit="BASE",
        local_tracking={
            "enabled": True,
            "source_id": "biquote_public",
            "source_symbol": "XAUUSD",
            "targets": [{"price": 2100, "percent": 100}],
            "stop_loss": 1950,
        },
    )
    state = LocalTrackingService(driver).get(explicit["id"])
    assert state["targets"][0]["price"] == "2100"


def test_qty_unit_edit_is_revisioned(journal):
    driver, client = journal
    trade = _create(client, symbol="EURUSD", entry_price=1.10, qty=1000)
    edited = client.patch(
        f"/api/v1/trades/{trade['id']}",
        json={"expected_revision": 1, "qty_unit": "BASE"},
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["no_change"] is False
    assert edited.json()["trade"]["qty_unit"] == "BASE"
    assert driver.get_trade(trade["id"])["qty_unit"] == "BASE"
    rebuilt = client.get(f"/api/v1/trades/{trade['id']}").json()
    assert rebuilt["qty_unit"] == "BASE"
    assert rebuilt["sizing"]["monetary_calculation"]["status"] == "READY"
