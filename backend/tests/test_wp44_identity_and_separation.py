"""WP44: entry-price provenance stays separate from the confirmed identity.

The reported real-UI flow (Binance BTCUSDT confirmed, then a hand-typed entry
price) must keep the provider identity on the trade row so the journal quote
refresh, the editor and the chart review all resolve the same identity; the
entry price itself stays an explicitly manual, unobserved record.  Simulation
records are practice data and never enter the real monetary aggregates.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient
from main import create_app

from app.api import endpoints
from app.api import webhook_tv
from app.db import sync_pipeline as sync_pipeline_module
from app.db.sqlite_driver import SQLiteDriver
from app.replay.replay_service import ReplayService
from app.services.portfolio_service import PortfolioAnalyticsService
from app.services.quote_refresh import QuoteRefreshService
from app.services.trade_read_adapter import trade_read_adapter


class _FakeFetcher:
    def __init__(self):
        self.calls = []

    async def fetch_quote(self, symbol, source):
        self.calls.append((symbol, source))
        return {
            "status": "LIVE",
            "price": 76000.0,
            "price_kind": "LAST",
            "source_id": source,
            "source_symbol": symbol,
            "observed_at": datetime.now(timezone.utc).isoformat(),
        }


def _isolated_journal(monkeypatch, tmp_path):
    driver = SQLiteDriver(str(tmp_path / "wp44.sqlite"))
    monkeypatch.setattr(endpoints, "sqlite_driver", driver)
    monkeypatch.setattr(webhook_tv, "sqlite_driver", driver)
    monkeypatch.setattr(sync_pipeline_module, "sqlite_driver", driver)
    monkeypatch.setattr(sync_pipeline_module, "duckdb_driver", SimpleNamespace(is_available=False))
    return driver


def _manual_identity_payload(**overrides):
    payload = {
        "symbol": "BTCUSDT", "side": "BUY", "position_type": "LONG",
        "entry_price": 76000.0, "qty": 0.001, "size_input_mode": "QTY", "qty_unit": "BASE",
        "leverage": 2, "stop_loss": 70000.0, "take_profit": 90000.0,
        "status": "OPEN", "entry_time": "2026-09-17T09:00:00Z", "record_mode": "SIMULATION",
        "price_source": "binance_public", "price_source_symbol": "BTCUSDT",
        "price_status": "UNAVAILABLE", "price_observed_at": None, "price_origin": "MANUAL",
        "local_tracking": {
            "enabled": True, "source_id": "binance_public", "source_symbol": "BTCUSDT",
            "stop_loss": 70000.0, "targets": [{"price": 90000.0, "percent": 100}],
        },
    }
    payload.update(overrides)
    return payload


def test_manual_entry_keeps_the_confirmed_identity_for_every_surface(monkeypatch, tmp_path):
    driver = _isolated_journal(monkeypatch, tmp_path)
    client = TestClient(create_app())

    response = client.post("/api/v1/trades", json=_manual_identity_payload())
    assert response.status_code == 200, response.text
    saved = response.json()
    assert saved["price_source"] == "binance_public"
    assert saved["price_source_symbol"] == "BTCUSDT"
    assert saved["price_origin"] == "MANUAL"
    assert saved["price_status"] == "UNAVAILABLE"
    assert saved["price_observed_at"] is None
    assert saved["record_mode"] == "SIMULATION"

    # Chart review resolves the confirmed identity instead of "no declaration".
    replay = ReplayService(
        trade_reader=type("Reader", (), {"get_trade": staticmethod(driver.get_trade),
                                         "list_events_for_trade": staticmethod(lambda *a, **k: [])})(),
        tracking_reader=type("Tracking", (), {"get": staticmethod(lambda trade_id: None)})(),
    )
    session = replay.create_session_for_trade(saved["id"])
    assert session["status"] == "NO_DATA"
    assert session["reason"] == "PROVIDER_MATCH_REQUIRED"
    assert session["provider"] == "binance_public"
    assert session["provider_symbol"] == "BTCUSDT"

    # The journal/editor quote refresh resolves the same identity and fetches LIVE.
    fetcher = _FakeFetcher()
    quotes = asyncio.run(QuoteRefreshService(fetcher=fetcher).refresh([driver.get_trade(saved["id"])]))
    quote = quotes["quotes"][saved["id"]]
    assert quote["quote_status"] == "LIVE"
    assert quote["source_id"] == "binance_public"
    assert quote["source_symbol"] == "BTCUSDT"
    assert fetcher.calls == [("BTCUSDT", "binance_public")]


def test_confirmed_free_source_identity_requires_its_provider_symbol(monkeypatch, tmp_path):
    _isolated_journal(monkeypatch, tmp_path)
    client = TestClient(create_app())

    response = client.post("/api/v1/trades", json=_manual_identity_payload(price_source_symbol=None))
    assert response.status_code == 422
    assert "provider symbol" in response.text


def test_manual_public_quote_claim_stays_rejected(monkeypatch, tmp_path):
    _isolated_journal(monkeypatch, tmp_path)
    client = TestClient(create_app())

    # A manual entry price can never carry a quote status ...
    status = client.post("/api/v1/trades", json=_manual_identity_payload(price_status="LIVE"))
    assert status.status_code == 422
    # ... and a PUBLIC_QUOTE claim still requires the full observation record.
    incomplete = client.post("/api/v1/trades", json=_manual_identity_payload(
        price_origin="PUBLIC_QUOTE", price_status="LIVE", price_observed_at=None))
    assert incomplete.status_code == 422
    assert "PUBLIC_QUOTE" in incomplete.text


def test_trade_without_identity_stays_honestly_unavailable(monkeypatch, tmp_path):
    driver = _isolated_journal(monkeypatch, tmp_path)
    client = TestClient(create_app())

    response = client.post("/api/v1/trades", json=_manual_identity_payload(
        price_source="manual", price_source_symbol=None, local_tracking=None))
    assert response.status_code == 200
    saved = response.json()

    fetcher = _FakeFetcher()
    quotes = asyncio.run(QuoteRefreshService(fetcher=fetcher).refresh([driver.get_trade(saved["id"])]))
    quote = quotes["quotes"][saved["id"]]
    assert quote["quote_status"] == "UNAVAILABLE"
    assert quote["reason"] == "NO_VERIFIED_QUOTE_IDENTITY"
    assert fetcher.calls == []  # no provider is ever invented from the symbol text

    replay = ReplayService(
        trade_reader=type("Reader", (), {"get_trade": staticmethod(driver.get_trade),
                                         "list_events_for_trade": staticmethod(lambda *a, **k: [])})(),
        tracking_reader=type("Tracking", (), {"get": staticmethod(lambda trade_id: None)})(),
    )
    session = replay.create_session_for_trade(saved["id"])
    assert session["reason"] == "PROVIDER_NOT_DECLARED"


def _closed(symbol: str, pnl: float, *, record_mode: str, exit_time: str = "2026-09-17T12:00:00Z"):
    return {
        "id": f"TRD-{symbol}-{record_mode}-{pnl}", "symbol": symbol, "side": "BUY",
        "status": "CLOSED", "entry_price": 100.0, "exit_price": 100.0 + pnl, "qty": 1.0,
        "pnl": pnl, "r_multiple": 1.0, "commission": 0.0, "record_mode": record_mode,
        "qty_unit": "BASE", "entry_time": "2026-09-17T11:00:00Z", "exit_time": exit_time,
    }


def test_simulation_records_never_enter_real_monetary_aggregates():
    service = PortfolioAnalyticsService(default_initial_balance=10000.0)
    real = _closed("BTCUSDT", 50.0, record_mode="EXTERNAL")
    practice = _closed("ETHUSDT", 900.0, record_mode="SIMULATION")
    practice_open = {
        "id": "TRD-SIM-OPEN", "symbol": "SOLUSDT", "side": "BUY", "status": "OPEN",
        "entry_price": 100.0, "qty": 1.0, "pnl": None, "commission": 0.0,
        "record_mode": "SIMULATION", "qty_unit": "BASE", "stop_loss": 90.0,
        "entry_time": "2026-09-17T11:30:00Z",
    }
    with patch.object(trade_read_adapter, "list_trades", return_value=[real, practice, practice_open]):
        summary = service.get_portfolio_summary()
        assert summary["net_pnl"] == 50.0
        assert summary["total_equity"] == 10050.0
        assert summary["total_closed_trades"] == 1
        assert summary["win_rate"] == 100.0
        assert summary["active_positions_count"] == 0
        assert summary["open_risk_r"] == 0.0
        assert summary["simulation_closed_trades"] == 1
        assert summary["simulation_open_positions"] == 1
        assert summary["simulation_realized_pnl"] == 900.0

        breakdown = {row["symbol"] for row in service.get_multi_asset_breakdown()}
        assert breakdown == {"BTCUSDT"}

        curve = service.get_equity_curve_series()
        assert all(point["symbol"] != "ETHUSDT" for point in curve)
        assert any(point["symbol"] == "BTCUSDT" for point in curve)

        heatmap = service.get_daily_pnl_heatmap()
        assert sum(day["pnl"] for day in heatmap) == 50.0


def test_simulation_exclusion_is_explicit_in_bucket_counts():
    """Simulation-only symbols never create a real-performance bucket."""

    service = PortfolioAnalyticsService(default_initial_balance=10000.0)
    practice = _closed("ETHUSDT", 900.0, record_mode="SIMULATION")
    with patch.object(trade_read_adapter, "list_trades", return_value=[practice]):
        assert service.get_multi_asset_breakdown() == []
        summary = service.get_portfolio_summary()
        assert summary["net_pnl"] == 0.0
        assert summary["total_closed_trades"] == 0
        assert summary["simulation_closed_trades"] == 1
        assert summary["simulation_realized_pnl"] == 900.0
