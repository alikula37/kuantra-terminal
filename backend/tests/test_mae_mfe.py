"""Hand-calculated excursions, exclusion denominators and no-data contracts."""
import json

import pytest
from fastapi.testclient import TestClient

from app.db.sqlite_driver import sqlite_driver
from app.quant.candle_evidence import duckdb_driver
from app.quant.mae_mfe import MaeMfeAnalyzer


def test_long_trade_uses_only_its_window(recorded_trade, recorded_candles):
    point = MaeMfeAnalyzer.analyze_trade_excursion(recorded_trade, recorded_candles)
    assert point["status"] == "READY" and point["bar_count"] == 3
    assert point["risk_unit"] == 1
    assert point["mae_price"] == 99.2 and point["mfe_price"] == 104
    assert point["mae_r"] == pytest.approx(-0.8)
    assert point["mfe_r"] == 4 and point["r_multiple"] == 3
    assert point["exit_efficiency"] == 0.75
    assert point["pnl"] == 5.5
    assert point["provenance"]["r_multiple_basis"] == "GROSS_PRICE_MOVE_NOT_NET_PNL"


def test_short_trade_hand_calculation(recorded_trade, recorded_candles):
    recorded_trade.update(symbol="ETHUSDT", side="SHORT", entry_price=3000, exit_price=2800, stop_loss=3100, pnl=400)
    candles = [
        {**recorded_candles[i + 1], "symbol": "ETHUSDT", "open": o, "high": h, "low": low, "close": c}
        for i, (o, h, low, c) in enumerate([(3000, 3050, 2980, 3010), (3010, 3020, 2750, 2780), (2800, 2820, 2790, 2800)])
    ]
    point = MaeMfeAnalyzer.analyze_trade_excursion(recorded_trade, candles)
    assert point["status"] == "READY"
    assert point["risk_unit"] == 100
    assert point["mae_r"] == -0.5 and point["mfe_r"] == 2.5
    assert point["r_multiple"] == 2 and point["exit_efficiency"] == 0.8


@pytest.mark.parametrize("stop", [None, 0, -1, 100, 101, float("nan"), float("inf"), True])
def test_invalid_stop_keeps_price_evidence_but_no_r(recorded_trade, recorded_candles, stop):
    recorded_trade["stop_loss"] = stop
    recorded_trade["r_multiple"] = 42  # Imported R does not authorize fabricated risk.
    point = MaeMfeAnalyzer.analyze_trade_excursion(recorded_trade, recorded_candles)
    assert point["status"] == "READY" and point["mae_price"] == 99.2
    assert point["risk_reason"] == "MISSING_OR_INVALID_STOP"
    assert all(point[key] is None for key in ("risk_unit", "mae_r", "mfe_r", "r_multiple"))
    json.dumps(point, allow_nan=False)


def test_zero_pnl_and_zero_price_return_preserved(recorded_trade, recorded_candles):
    recorded_trade.update(pnl=0, exit_price=100)
    point = MaeMfeAnalyzer.analyze_trade_excursion(recorded_trade, recorded_candles)
    assert point["pnl"] == 0 and point["r_multiple"] == 0 and point["exit_efficiency"] == 0


def test_no_favorable_excursion_has_undefined_efficiency(recorded_trade, recorded_candles):
    recorded_trade["exit_price"] = 100
    candles = [{**c, "open": 100, "high": 100, "low": 100, "close": 100} for c in recorded_candles]
    point = MaeMfeAnalyzer.analyze_trade_excursion(recorded_trade, candles)
    assert point["mfe_r"] == 0 and point["exit_efficiency"] is None


def test_missing_history_never_estimates_from_pnl_or_tp(recorded_trade):
    point = MaeMfeAnalyzer.analyze_trade_excursion(recorded_trade, [])
    assert point["status"] == "NO_DATA"
    assert point["mae_price"] is None and point["mfe_r"] is None


def test_aggregate_uses_real_queries_and_exposes_exclusions(monkeypatch, recorded_trade, recorded_candles):
    trades = [recorded_trade, {**recorded_trade, "id": "NO-R", "stop_loss": None}, {**recorded_trade, "id": "MISSING", "symbol": "XUSDT"}]
    def list_trades(**kwargs):
        assert kwargs == {"limit": 1000, "status": "CLOSED", "symbol": None, "order_by_utc": True}
        return trades
    monkeypatch.setattr(sqlite_driver, "list_trades", list_trades)
    monkeypatch.setattr(duckdb_driver, "get_candles_range", lambda symbol, *a, **kw: recorded_candles if symbol == "BTCUSDT" else [])
    result = MaeMfeAnalyzer.get_mae_mfe_scatter_data()
    assert result["status"] == "READY"
    assert (result["total_candidates"], result["total_analyzed"], result["total_r_analyzed"]) == (3, 2, 1)
    assert result["excluded_trades"][0]["trade_id"] == "MISSING"
    assert result["excluded_trades"][0]["reason"] == "NO_CANDLE_HISTORY"
    assert result["average_mae_r"] == pytest.approx(-0.8)
    assert result["average_mfe_r"] == 4
    assert result["average_exit_efficiency_pct"] == 75
    assert result["recommended_target_r"] is None
    assert result["recommendation_status"] == "UNAVAILABLE_NOT_VALIDATED"
    assert result["stop_loss_sensitivities"][0]["survival_rate_pct"] == 0
    assert result["stop_loss_sensitivities"][2]["survival_rate_pct"] == 100
    assert all(s["sample_size"] == 1 for s in result["stop_loss_sensitivities"])


def test_no_r_aggregate_has_no_survival_or_r_averages(monkeypatch, recorded_trade, recorded_candles):
    monkeypatch.setattr(sqlite_driver, "list_trades", lambda **kw: [{**recorded_trade, "stop_loss": None}])
    monkeypatch.setattr(duckdb_driver, "get_candles_range", lambda *a, **kw: recorded_candles)
    result = MaeMfeAnalyzer.get_mae_mfe_scatter_data()
    assert result["total_analyzed"] == 1 and result["total_r_analyzed"] == 0
    assert result["average_mae_r"] is None and result["average_mfe_r"] is None
    assert result["stop_loss_sensitivities"] == []
    assert result["average_exit_efficiency_pct"] == 75


@pytest.mark.parametrize("unavailable", [False, True])
def test_empty_and_unavailable_aggregates_forward_truth_to_optimal_exits(test_app, monkeypatch, unavailable):
    def list_trades(**kwargs):
        if unavailable:
            raise RuntimeError("secret/path")
        return []
    monkeypatch.setattr(sqlite_driver, "list_trades", list_trades)
    data = TestClient(test_app).get("/api/v1/analytics/optimal-exits").json()
    assert data["status"] == ("UNAVAILABLE" if unavailable else "NO_DATA")
    assert data["total_analyzed"] == 0 and data["excluded_trades"] == []
    assert data["average_exit_efficiency_pct"] is None
    assert data["recommended_target_r"] is None and data["stop_loss_sensitivities"] == []
    assert data["provenance"]["source_verified"] is False
    assert "secret/path" not in json.dumps(data)


def test_all_candle_reads_failed_is_unavailable(monkeypatch, recorded_trade):
    monkeypatch.setattr(sqlite_driver, "list_trades", lambda **kw: [recorded_trade])
    def fail(*a, **kw):
        raise RuntimeError("secret/path")
    monkeypatch.setattr(duckdb_driver, "get_candles_range", fail)
    result = MaeMfeAnalyzer.get_mae_mfe_scatter_data()
    assert result["status"] == "UNAVAILABLE"
    assert result["total_candidates"] == 1 and result["total_analyzed"] == 0
    assert result["excluded_trades"][0]["reason"] == "CANDLE_STORE_UNAVAILABLE"


def test_nonfinite_derived_metrics_cannot_escape_json(recorded_trade, recorded_candles):
    recorded_trade.update(entry_price=1e-308, exit_price=1e308, stop_loss=0.5e-308, qty=1e308)
    point = MaeMfeAnalyzer.analyze_trade_excursion(recorded_trade, recorded_candles)
    assert point["mfe_r"] is None and point["r_multiple"] is None
    json.dumps(point, allow_nan=False)
