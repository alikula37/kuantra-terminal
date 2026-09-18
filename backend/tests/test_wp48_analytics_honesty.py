"""WP48: no invented analytics, OLAP simulation separation, candle persistence robustness."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.db.duckdb_driver import DuckDBDriver


def _closed_trade(trade_id: str, *, record_mode: str, pnl: float):
    return {
        "id": trade_id, "symbol": "BTCUSDT", "side": "BUY", "status": "CLOSED",
        "entry_price": 100.0, "exit_price": 100.0 + pnl, "qty": 1.0, "pnl": pnl,
        "r_multiple": 1.0, "commission": 0.0, "record_mode": record_mode,
        "entry_time": "2026-09-18T08:00:00Z", "exit_time": "2026-09-18T09:00:00Z",
    }


# ---------------------------------------------------------------------------
# OLAP record_mode and simulation separation
# ---------------------------------------------------------------------------


def test_aggregated_stats_exclude_simulations_and_count_them(tmp_path):
    driver = DuckDBDriver(str(tmp_path / "olap.duckdb"))
    driver.sync_trade(_closed_trade("REAL-1", record_mode="EXTERNAL", pnl=50.0))
    driver.sync_trade(_closed_trade("SIM-1", record_mode="SIMULATION", pnl=900.0))

    stats = driver.get_aggregated_stats()
    # Real metrics only contain the external trade; the simulation is counted
    # separately and never leaks into the real totals.
    assert stats["total_trades"] == 1
    assert stats["total_pnl"] == 50.0
    assert stats["simulation_trades"] == 1
    assert stats["known_pnl_trades"] == 1


def test_olap_rows_carry_the_record_mode(tmp_path):
    driver = DuckDBDriver(str(tmp_path / "olap2.duckdb"))
    driver.sync_trade(_closed_trade("SIM-2", record_mode="SIMULATION", pnl=10.0))
    with driver.get_connection() as conn:
        row = conn.execute("SELECT record_mode FROM olap_trades WHERE id='SIM-2'").fetchone()
    assert row[0] == "SIMULATION"


def test_legacy_rows_without_record_mode_stay_real(tmp_path):
    driver = DuckDBDriver(str(tmp_path / "olap3.duckdb"))
    # A legacy row: the column exists but is NULL, which must behave like before.
    driver.sync_trade(_closed_trade("LEGACY-1", record_mode="", pnl=25.0))
    stats = driver.get_aggregated_stats()
    assert stats["total_trades"] == 1
    assert stats["total_pnl"] == 25.0
    assert stats["simulation_trades"] == 0


# ---------------------------------------------------------------------------
# Pivot: no invented seed data
# ---------------------------------------------------------------------------


def test_pivot_never_invents_rows_when_no_closed_trades(tmp_path):
    from app.db.sqlite_driver import SQLiteDriver
    from app.quant.pivot_engine import PivotEngine

    driver = SQLiteDriver(str(tmp_path / "pivot.sqlite"))
    with patch("app.quant.pivot_engine.sqlite_driver", driver):
        grid = PivotEngine.compute_pivot_grid(group_by=["symbol"])
    assert grid["rows"] == []
    assert grid["total_buckets"] == 0
    assert grid["basis"] == "NO_CLOSED_TRADES"
    # The former seed payload invented "18 trades / 9450 USD" style rows; no
    # monetary value may appear without recorded closed trades.
    assert "9450" not in str(grid)


# ---------------------------------------------------------------------------
# Candle persistence robustness under a locked DuckDB
# ---------------------------------------------------------------------------


def test_closed_candle_persistence_retries_and_logs_once(monkeypatch):
    from app.websocket import binance_client as module

    calls = {"n": 0}
    warnings = {"n": 0}

    def flaky_insert(_candles):
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("Conflicting lock is held")

    monkeypatch.setattr(module, "duckdb_driver", SimpleNamespace(insert_candles=flaky_insert))
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(module.logger, "warning", lambda *args, **kwargs: warnings.__setitem__("n", warnings["n"] + 1))

    module._persist_closed_candle({"symbol": "BTCUSDT"})
    assert calls["n"] == 3  # retried past the lock
    assert warnings["n"] == 0  # a successful retry is not a warning

    # A permanently locked store warns once per process and then stays quiet.
    def locked_insert(_candles):
        calls["n"] += 1
        raise RuntimeError("Conflicting lock is held")

    monkeypatch.setattr(module, "duckdb_driver", SimpleNamespace(insert_candles=locked_insert))
    calls["n"] = 0
    module._persist_closed_candle({"symbol": "BTCUSDT"})
    assert calls["n"] == 3
    assert warnings["n"] == 1
    module._persist_closed_candle({"symbol": "BTCUSDT"})
    assert warnings["n"] == 1


def test_quant_endpoint_and_symbol_breakdown_exclude_simulations(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from main import create_app

    from app.api import endpoints
    from app.db import sync_pipeline as sync_pipeline_module
    from app.db.sqlite_driver import SQLiteDriver as Driver

    driver = Driver(str(tmp_path / "quant.sqlite"))
    reader = SimpleNamespace(
        get_trade=driver.get_trade,
        get_open_trades=driver.get_open_trades,
        list_trades=lambda limit=100, offset=0, **kwargs: driver.list_trades(limit=limit, offset=offset, **kwargs),
    )
    monkeypatch.setattr(endpoints, "sqlite_driver", driver)
    monkeypatch.setattr(endpoints, "trade_read_adapter", reader)
    monkeypatch.setattr(sync_pipeline_module, "sqlite_driver", driver)
    monkeypatch.setattr(sync_pipeline_module, "duckdb_driver", SimpleNamespace(is_available=False))
    client = TestClient(create_app())

    payload = {
        "symbol": "XAUUSD", "side": "BUY", "position_type": "LONG",
        "entry_price": 4300.0, "size_input_mode": "NOTIONAL", "notional_size": 1000.0,
        "qty_unit": "USD", "leverage": 10, "stop_loss": 4270.0, "take_profit": 4360.0,
        "status": "OPEN", "entry_time": "2026-09-18T08:00:00Z",
        "price_source": "biquote_public", "price_source_symbol": "XAUUSD",
        "price_status": "UNAVAILABLE", "price_origin": "MANUAL",
    }
    sim = client.post("/api/v1/trades", json={**payload, "record_mode": "SIMULATION"}).json()
    real = client.post("/api/v1/trades", json={**payload, "record_mode": "EXTERNAL"}).json()
    for trade in (sim, real):
        client.post(f"/api/v1/trades/{trade['id']}/close", json={"exit_price": 4343.0, "commission": 1.0})

    quant = client.get("/api/v1/analytics/quant").json()
    assert quant["total_trades"] == 1            # the real closed trade only
    assert quant["simulation_trades"] == 1
    assert abs(float(quant["total_pnl"]) - 9.0) < 1e-9

    # DuckDB breakdown: a simulation row must not create a real bucket.
    olap = DuckDBDriver(str(tmp_path / "quant-olap.duckdb"))
    olap.sync_trade(_closed_trade("REAL-Q", record_mode="EXTERNAL", pnl=50.0))
    olap.sync_trade(_closed_trade("SIM-Q", record_mode="SIMULATION", pnl=900.0))
    symbols = {row["symbol"] for row in olap.get_symbol_breakdown()}
    assert symbols == {"BTCUSDT"}
    totals = {row["symbol"]: row["total_pnl"] for row in olap.get_symbol_breakdown()}
    assert totals["BTCUSDT"] == 50.0
