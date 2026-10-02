"""Availability is additive metadata; legacy arithmetic and journal records stay intact."""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.services.portfolio_service import PortfolioAnalyticsService
from app.services.trade_read_adapter import trade_read_adapter
from app.db.sqlite_driver import sqlite_driver
from main import create_app


def closed(pnl, **extra):
    return {"symbol": "BTCUSDT", "status": "CLOSED", "record_mode": "EXTERNAL",
            "pnl": pnl, "exit_time": datetime.now(timezone.utc).isoformat(), **extra}


@pytest.mark.parametrize("rows,basis,known,unknown,rate,dd", [
    ([], "NO_DATA", 0, 0, 0.0, 0.0),
    ([closed(100, record_mode="SIMULATION"), closed(-10, status="CANCELED")],
     "NO_DATA", 0, 0, 0.0, 0.0),
    ([closed(None)], "NOT_AVAILABLE", 0, 1, 0.0, 0.0),
    ([closed(0)], "COMPLETE", 1, 0, 0.0, 0.0),
    ([closed(-10)], "COMPLETE", 1, 0, 0.0, 10.0),
    ([closed(10)], "COMPLETE", 1, 0, 100.0, 0.0),
    ([closed(0), closed(None)], "PARTIAL", 1, 1, 0.0, 0.0),
    ([closed(10), closed(-10), closed(None)], "PARTIAL", 2, 1, 50.0, 10.0),
])
def test_realized_metric_coverage_preserves_numbers(monkeypatch, rows, basis, known, unknown, rate, dd):
    monkeypatch.setattr(trade_read_adapter, "list_trades", lambda **_: rows)
    summary = PortfolioAnalyticsService(default_initial_balance=1000).get_portfolio_summary()
    assert summary["realized_pnl_basis"] == basis
    assert summary["known_pnl_trades"] == known
    assert summary["unknown_pnl_trades"] == unknown
    assert summary["total_closed_trades"] == known + unknown
    assert summary["drawdown_pct_basis"] == basis
    # Compatibility: no nullable replacement or changed formula for existing numbers.
    assert summary["win_rate"] == rate
    assert summary["max_drawdown_usd"] == dd
    assert isinstance(summary["profit_factor"], (int, float))
    assert isinstance(summary["max_drawdown_pct"], (int, float))
    assert summary["total_equity"] == 1000 + sum(float(t["pnl"]) for t in rows
        if t["status"] == "CLOSED" and t["record_mode"] != "SIMULATION" and t["pnl"] is not None)


def test_percentage_drawdown_without_configured_capital_is_unavailable(monkeypatch):
    monkeypatch.setattr(trade_read_adapter, "list_trades", lambda **_: [closed(-10)])
    summary = PortfolioAnalyticsService(default_initial_balance=0).get_portfolio_summary()
    assert summary["realized_pnl_basis"] == "COMPLETE"
    assert summary["drawdown_pct_basis"] == "NOT_AVAILABLE"
    assert summary["max_drawdown_usd"] == 10
    assert summary["max_drawdown_pct"] == 0  # legacy numeric calculation retained


def test_break_even_and_unknown_today_are_distinct(monkeypatch):
    monkeypatch.setattr(trade_read_adapter, "list_trades", lambda **_: [closed(0), closed(None)])
    summary = PortfolioAnalyticsService(default_initial_balance=1000).get_portfolio_summary()
    assert summary["today_trades_count"] == {"wins": 0, "losses": 0, "total": 2, "unknown_pnl": 1}
    assert summary["known_pnl_trades"] == 1


def test_summary_api_exposes_additive_coverage_without_writes(monkeypatch):
    monkeypatch.setenv("KUANTRA_MARKET_DATA_ENABLED", "false")
    rows = [closed(10), closed(None)]
    monkeypatch.setattr(trade_read_adapter, "list_trades", lambda **_: rows)
    def counts():
        with sqlite_driver.get_connection() as conn:
            return tuple(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                         for table in ("trades", "evidence_events", "local_tracking_projections"))
    before = counts()
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/portfolio/summary?initial_balance=1000")
    assert response.status_code == 200
    data = response.json()
    assert data["realized_pnl_basis"] == "PARTIAL"
    assert data["known_pnl_trades"] == 1
    assert data["drawdown_pct_basis"] == "PARTIAL"
    assert data["win_rate"] == 100
    assert counts() == before
    assert rows == [closed(10, exit_time=rows[0]["exit_time"]), closed(None, exit_time=rows[1]["exit_time"])]
