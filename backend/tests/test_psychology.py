import pytest
from app.psychology.psychology_engine import PsychologyEngine, psychology_engine

class TestBehavioralPsychologyEngine:
    """Test suite for Algorithmic Psychology, FOMO, Revenge Trading & Tilt Engine."""

    def test_fomo_detector_extreme_chase(self):
        trade = {
            "id": "T-FOMO-1",
            "symbol": "BTCUSDT",
            "side": "BUY",
            "entry_price": 66000.0
        }
        # 20 steady candles around 63,000, then huge pump bar up to 66,100
        candles = [{"open": 63000.0, "high": 63200.0, "low": 62900.0, "close": 63100.0} for _ in range(20)]
        candles.append({"open": 63100.0, "high": 66100.0, "low": 63050.0, "close": 66000.0})

        res = PsychologyEngine.detect_fomo_entry(trade, candles)
        assert res["is_fomo"] is True
        assert res["d_ema_distance"] > 2.5
        assert res["severity"] in ("HIGH", "CRITICAL")
        assert res["anomaly_type"] == "FOMO_CHASE"

    def test_fomo_detector_disciplined_entry(self):
        trade = {
            "id": "T-SAFE-1",
            "symbol": "BTCUSDT",
            "side": "BUY",
            "entry_price": 63150.0
        }
        # Entry right near EMA20 (63,100)
        candles = [{"open": 63000.0, "high": 63300.0, "low": 62900.0, "close": 63100.0} for _ in range(20)]
        candles.append({"open": 63100.0, "high": 63250.0, "low": 63050.0, "close": 63150.0})

        res = PsychologyEngine.detect_fomo_entry(trade, candles)
        assert res["is_fomo"] is False
        assert res["d_ema_distance"] < 1.5
        assert res["severity"] == "NORMAL"

    def test_revenge_trading_detector_rapid_re_entry_with_size_escalation(self):
        prev_trade = {
            "id": "T-PREV-LOSS",
            "symbol": "BTCUSDT",
            "pnl": -750.0,  # Loss
            "qty": 1.0,
            "exit_time": "2026-08-30T10:00:00"
        }
        curr_trade = {
            "id": "T-CURR-REVENGE",
            "symbol": "BTCUSDT",
            "qty": 2.0,     # 2x lot size
            "entry_time": "2026-08-30T10:01:15"  # 75 seconds later (<180s)
        }

        res = PsychologyEngine.detect_revenge_trading(curr_trade, prev_trade)
        assert res["is_revenge"] is True
        assert res["delta_seconds"] == 75
        assert res["lot_escalation_ratio"] == 2.0
        assert res["anomaly_type"] == "REVENGE_TRADING"

    def test_impulsive_re_entry_without_lot_escalation(self):
        prev_trade = {
            "id": "T-PREV-WIN",
            "symbol": "ETHUSDT",
            "pnl": 200.0,
            "qty": 1.0,
            "exit_time": "2026-08-30T10:00:00"
        }
        curr_trade = {
            "id": "T-CURR-FAST",
            "symbol": "ETHUSDT",
            "qty": 1.0,     # Normal 1x lot size
            "entry_time": "2026-08-30T10:00:45"  # 45 seconds later (<180s)
        }

        res = PsychologyEngine.detect_revenge_trading(curr_trade, prev_trade)
        assert res["is_revenge"] is False
        assert res["is_impulsive"] is True
        assert res["anomaly_type"] == "IMPULSIVE_CHURN"

    def test_session_tilt_score_progression(self):
        # Scenario 1: Clean trading (Calm)
        t_clean = [
            {"id": "T1", "entry_price": 60000.0, "qty": 1.0, "pnl": 500.0, "status": "CLOSED", "entry_time": "2026-08-30T09:00:00", "exit_time": "2026-08-30T09:30:00"},
            {"id": "T2", "entry_price": 60500.0, "qty": 1.0, "pnl": 300.0, "status": "CLOSED", "entry_time": "2026-08-30T10:00:00", "exit_time": "2026-08-30T10:30:00"}
        ]
        res_calm = PsychologyEngine.calculate_session_tilt_score(t_clean)
        assert res_calm["status"] == "CALM"
        assert res_calm["tilt_score"] < 30

        # Scenario 2: Consecutive loss streak + revenge sizing (High Tilt)
        t_tilted = [
            {"id": "T1", "entry_price": 60000.0, "qty": 1.0, "pnl": -500.0, "status": "CLOSED", "entry_time": "2026-08-30T09:00:00", "exit_time": "2026-08-30T09:30:00"},
            {"id": "T2", "entry_price": 60100.0, "qty": 2.0, "pnl": -1000.0, "status": "CLOSED", "entry_time": "2026-08-30T09:31:00", "exit_time": "2026-08-30T09:40:00"},
            {"id": "T3", "entry_price": 60200.0, "qty": 3.0, "pnl": -1500.0, "status": "CLOSED", "entry_time": "2026-08-30T09:41:00", "exit_time": "2026-08-30T09:50:00"}
        ]
        res_tilt = PsychologyEngine.calculate_session_tilt_score(t_tilted, daily_loss_utilization_pct=85.0)
        assert res_tilt["status"] in ("HIGH_TILT", "BREACH_RISK")
        assert res_tilt["tilt_score"] >= 60
        assert res_tilt["consecutive_losses"] == 3

    def test_mental_fatigue_matrix_computation(self):
        res = psychology_engine.compute_mental_fatigue_matrix()
        assert "inflection_point" in res
        assert "early_win_rate_pct" in res
        assert "late_win_rate_pct" in res
        assert "matrix" in res
        assert len(res["matrix"]) == 8
        assert res["early_win_rate_pct"] > res["late_win_rate_pct"]

    def test_anomaly_scanner(self):
        res = psychology_engine.get_all_anomalies()
        assert "total_anomalies_count" in res
        assert "anomalies" in res