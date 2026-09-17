"""WP45: USD position value as the only trade sizing.

Traders size positions in USD, so ``qty_unit=USD`` stores the position value in
the ``qty`` column and every money figure (notional, margin, gross PnL, R) is
derived from the price return applied to that value — no contract-size
verification needed.  Non-USD-quoted pairs are computed approximately with an
explicit label.  Legacy BASE/UNKNOWN rows keep their old math.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from main import create_app

from app.api import endpoints
from app.db import sync_pipeline as sync_pipeline_module
from app.core.position_math import instrument_unit_basis, position_summary
from app.db.sqlite_driver import SQLiteDriver
from app.services.portfolio_service import PortfolioAnalyticsService
from app.services.trade_read_adapter import trade_read_adapter


def _isolated_journal(monkeypatch, tmp_path):
    from app.services import trade_edit as trade_edit_module
    from app.services.trade_edit import TradeEditService

    driver = SQLiteDriver(str(tmp_path / "wp45.sqlite"))
    monkeypatch.setattr(endpoints, "sqlite_driver", driver)
    monkeypatch.setattr(sync_pipeline_module, "sqlite_driver", driver)
    monkeypatch.setattr(sync_pipeline_module, "duckdb_driver", SimpleNamespace(is_available=False))
    monkeypatch.setattr(endpoints, "trade_edit_service", TradeEditService(driver=driver))
    return driver


def _usd_payload(**overrides):
    payload = {
        "symbol": "XAUUSD", "side": "BUY", "position_type": "LONG",
        "entry_price": 4300.0, "size_input_mode": "NOTIONAL", "notional_size": 1000.0,
        "qty_unit": "USD", "leverage": 10, "stop_loss": 4270.0, "take_profit": 4360.0,
        "status": "OPEN", "entry_time": "2026-09-17T09:00:00Z", "record_mode": "EXTERNAL",
        "price_source": "biquote_public", "price_source_symbol": "XAUUSD",
        "price_status": "UNAVAILABLE", "price_origin": "MANUAL",
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# Unit basis and position math
# ---------------------------------------------------------------------------


def test_usd_declaration_is_an_explicit_position_value_basis():
    basis = instrument_unit_basis("XAUUSD", qty_unit="USD")
    assert basis["contract_size"] == "USD_NOTIONAL"
    assert basis["verification"] == "EXPLICIT_USD_VALUE"
    assert basis["verification_source"] == "USER_DECLARATION"
    assert basis["qty_unit"] == "USD"
    assert instrument_unit_basis("XAUUSD", qty_unit="UNKNOWN")["contract_size"] == "UNVERIFIED"
    assert instrument_unit_basis("XAUUSD", qty_unit="BASE")["contract_size"] == "BASE_UNIT"


def test_usd_position_summary_prices_from_the_value_not_a_quantity():
    summary = position_summary(
        symbol="XAUUSD", position_type="LONG", side="BUY",
        entry_price=4300.0, qty=1000.0, leverage=10,
        exit_price=4343.0, qty_unit="USD",
    )
    assert summary["monetary_calculation"]["status"] == "READY"
    assert summary["quantity"]["unit"] == "USD"
    assert summary["notional"]["value"] == 1000.0
    assert summary["notional"]["basis"] == "USD_POSITION_VALUE"
    assert summary["margin_estimate"]["value"] == 100.0
    assert abs(summary["returns"]["gross_pnl"] - 10.0) < 1e-9  # 1 % of the value
    assert abs(summary["returns"]["position_return_pct_gross"] - 1.0) < 1e-9
    assert abs(summary["returns"]["margin_return_pct_gross"] - 10.0) < 1e-9
    assert "CONTRACT_SIZE_UNVERIFIED" not in summary["warnings"]


def test_usd_value_on_a_non_usd_quote_is_labeled_approximate():
    summary = position_summary(
        symbol="ETHBTC", position_type="LONG", side="BUY",
        entry_price=0.05, qty=500.0, leverage=5, exit_price=0.055, qty_unit="USD",
    )
    assert summary["monetary_calculation"]["status"] == "READY"
    assert "QUOTE_NOT_USD_APPROXIMATE" in summary["warnings"]
    assert abs(summary["returns"]["gross_pnl"] - 50.0) < 1e-9
    pegged = position_summary(
        symbol="BTCUSDT", position_type="LONG", side="BUY",
        entry_price=76000.0, qty=1000.0, leverage=5, exit_price=77000.0, qty_unit="USD",
    )
    assert "QUOTE_NOT_USD_APPROXIMATE" not in pegged["warnings"]


# ---------------------------------------------------------------------------
# API: create, close, edit
# ---------------------------------------------------------------------------


def test_create_stores_the_usd_value_and_computes_money_from_it(monkeypatch, tmp_path):
    driver = _isolated_journal(monkeypatch, tmp_path)
    client = TestClient(create_app())

    response = client.post("/api/v1/trades", json=_usd_payload())
    assert response.status_code == 200, response.text
    saved = response.json()
    assert saved["qty"] == 1000.0
    assert saved["qty_unit"] == "USD"
    assert saved["sizing"]["monetary_calculation"]["status"] == "READY"
    assert saved["sizing"]["notional"]["value"] == 1000.0

    closed = client.post(f"/api/v1/trades/{saved['id']}/close", json={"exit_price": 4343.0})
    assert closed.status_code == 200, closed.text
    body = closed.json()
    assert abs(float(body["pnl"]) - 10.0) < 1e-9
    # R = 10 USD / (30/4300 x 1000 USD) = 1.43
    assert abs(float(body["r_multiple"]) - round(10.0 / (30.0 / 4300.0 * 1000.0), 2)) < 1e-9

    reopened = driver.get_trade(saved["id"])
    assert reopened["qty"] == 1000.0 and reopened["qty_unit"] == "USD"


def test_edit_declares_the_usd_value_and_recomputes_the_close(monkeypatch, tmp_path):
    driver = _isolated_journal(monkeypatch, tmp_path)
    client = TestClient(create_app())

    created = client.post("/api/v1/trades", json=_usd_payload()).json()
    # A user-corrected USD value: 2000 USD at the same prices doubles the result.
    edited = client.patch(
        f"/api/v1/trades/{created['id']}",
        json={"expected_revision": created["revision"], "qty": 2000.0},
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["trade"]["qty"] == 2000.0
    assert driver.get_trade(created["id"])["qty_unit"] == "USD"

    closed = client.post(
        f"/api/v1/trades/{created['id']}/close",
        json={"exit_price": 4343.0},
    )
    assert closed.status_code == 200, closed.text
    assert abs(float(closed.json()["pnl"]) - 20.0) < 1e-9


def test_legacy_unknown_rows_still_withhold_money_and_accept_a_usd_declaration(monkeypatch, tmp_path):
    driver = _isolated_journal(monkeypatch, tmp_path)
    client = TestClient(create_app())

    legacy = client.post("/api/v1/trades", json={
        "symbol": "XAUUSD", "side": "BUY", "position_type": "LONG",
        "entry_price": 4300.0, "qty": 1.0, "qty_unit": "UNKNOWN",
        "status": "OPEN", "entry_time": "2026-09-17T09:00:00Z",
    }).json()
    assert legacy["sizing"]["monetary_calculation"]["status"] == "UNAVAILABLE"
    assert legacy["sizing"]["monetary_calculation"]["reason"] == "CONTRACT_SIZE_UNVERIFIED"

    declared = client.patch(
        f"/api/v1/trades/{legacy['id']}",
        json={"expected_revision": legacy["revision"], "qty": 1000.0, "qty_unit": "USD"},
    )
    assert declared.status_code == 200, declared.text
    assert declared.json()["trade"]["qty_unit"] == "USD"
    fetched = endpoints.attach_position_summary(driver.get_trade(legacy["id"]))
    assert fetched["sizing"]["monetary_calculation"]["status"] == "READY"
    assert fetched["sizing"]["quantity"]["unit"] == "USD"


def test_create_rejects_an_invalid_unit(monkeypatch, tmp_path):
    _isolated_journal(monkeypatch, tmp_path)
    client = TestClient(create_app())
    response = client.post("/api/v1/trades", json=_usd_payload(qty_unit="LOTS"))
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Local tracking and portfolio
# ---------------------------------------------------------------------------


def test_local_tracking_accepts_a_usd_value_plan_and_prices_closures(tmp_path):
    from app.services.local_tracking import LocalTrackingService

    driver = SQLiteDriver(str(tmp_path / "tracking.sqlite"))
    trade_id = "TRD-USD-PLAN"
    driver.record_trade_with_evidence(
        {
            "id": trade_id, "symbol": "XAUUSD", "side": "BUY", "status": "OPEN",
            "entry_price": 4300.0, "qty": 1000.0, "qty_unit": "USD",
            "stop_loss": 4270.0, "take_profit": 4360.0,
            "entry_time": "2026-09-17T09:00:00Z",
        },
        event_type="IntentRecorded", idempotency_key="wp45:1",
        occurred_at="2026-09-17T09:00:00Z", provenance={"source": "journal_external"},
    )
    service = LocalTrackingService(driver)
    state = service.edit(
        trade_id,
        {"enabled": True, "source_id": "biquote_public", "source_symbol": "XAUUSD",
         "stop_loss": 4270.0, "targets": [{"price": 4343.0, "percent": 100}]},
        expected_revision=0,
    )
    assert float(state["initial_qty"]) == 1000.0
    assert state["qty_unit"] == "USD"

    closed = service.observe(trade_id, {"price": 4343.0, "observed_at": "2026-09-17T10:00:00Z",
                                        "source_id": "biquote_public", "source_symbol": "XAUUSD"},
                             manual=True, expected_revision=state["revision"])
    assert float(closed["remaining_qty"]) == 0.0
    assert abs(float(closed["gross_pnl"]) - 10.0) < 0.01


def test_portfolio_risk_and_unrealized_use_the_usd_value(monkeypatch):
    service = PortfolioAnalyticsService(default_initial_balance=10000.0)
    trade = {
        "id": "TRD-USD-OPEN", "symbol": "XAUUSD", "side": "BUY", "status": "OPEN",
        "entry_price": 4300.0, "qty": 1000.0, "qty_unit": "USD", "stop_loss": 4270.0,
        "leverage": 10.0, "record_mode": "EXTERNAL", "entry_time": "2026-09-17T09:00:00Z",
    }
    quotes = SimpleNamespace(
        cached_quote=lambda _trade: {"price": 4343.0, "status": "LIVE",
                                     "observed_at": "2026-09-17T10:00:00Z", "stale": False},
    )
    with patch.object(trade_read_adapter, "list_trades", return_value=[trade]), \
         patch("app.services.portfolio_service.quote_refresh_service", quotes):
        summary = service.get_portfolio_summary()
    # Risk: 30/4300 x 1000 = 6.98 USD; margin: 1000 / 10 = 100 USD.
    assert abs(summary["open_risk_usd"] - round(30.0 / 4300.0 * 1000.0, 2)) < 0.01
    assert abs(summary["open_notional_usd"] - 1000.0) < 0.01
    assert abs(summary["open_margin_usd"] - 100.0) < 0.01
    # Unrealized: 43/4300 x 1000 = 10 USD.
    assert abs(summary["unrealized_pnl_usd"] - 10.0) < 0.01
    assert abs(summary["live_equity"] - 10010.0) < 0.01
