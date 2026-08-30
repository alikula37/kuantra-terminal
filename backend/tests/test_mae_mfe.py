import pytest
from app.quant.mae_mfe import MaeMfeAnalyzer, mae_mfe_analyzer

class TestMaeMfeAnalytics:
    """Test suite for MAE / MFE Excursion and Best-Exit efficiency analysis."""

    def test_long_trade_excursion_analysis(self):
        trade = {
            "id": "T-101",
            "symbol": "BTCUSDT",
            "side": "BUY",
            "entry_price": 60000.0,
            "exit_price": 63000.0,
            "stop_loss": 59000.0,  # 1R = $1,000
            "take_profit": 65000.0,
            "pnl": 3000.0,
            "r_multiple": 3.0,
            "status": "CLOSED"
        }
        candles = [
            {"high": 60500.0, "low": 59200.0, "close": 59800.0},
            {"high": 64000.0, "low": 59500.0, "close": 63500.0},
            {"high": 63200.0, "low": 62800.0, "close": 63000.0}
        ]
        res = MaeMfeAnalyzer.analyze_trade_excursion(trade, candles=candles)
        
        # Risk unit = 1000.0
        assert res["risk_unit"] == 1000.0
        # Lowest price = 59200 -> MAE = (59200 - 60000) / 1000 = -0.8 R
        assert res["mae_price"] == 59200.0
        assert pytest.approx(res["mae_r"], 0.01) == -0.8
        # Highest price = 64000 -> MFE = (64000 - 60000) / 1000 = +4.0 R
        assert res["mfe_price"] == 64000.0
        assert pytest.approx(res["mfe_r"], 0.01) == 4.0
        # Actual move = 63000 - 60000 = 3000. Potential = 64000 - 60000 = 4000
        # Exit Efficiency = 3000 / 4000 = 0.75 (75%)
        assert pytest.approx(res["exit_efficiency"], 0.01) == 0.75

    def test_short_trade_excursion_analysis(self):
        trade = {
            "id": "T-102",
            "symbol": "ETHUSDT",
            "side": "SELL",
            "entry_price": 3000.0,
            "exit_price": 2800.0,
            "stop_loss": 3100.0,  # 1R = $100
            "take_profit": 2700.0,
            "pnl": 200.0,
            "r_multiple": 2.0,
            "status": "CLOSED"
        }
        candles = [
            {"high": 3050.0, "low": 2980.0, "close": 3010.0},
            {"high": 3020.0, "low": 2750.0, "close": 2780.0},
            {"high": 2820.0, "low": 2790.0, "close": 2800.0}
        ]
        res = MaeMfeAnalyzer.analyze_trade_excursion(trade, candles=candles)
        
        # Risk unit = 100.0
        assert res["risk_unit"] == 100.0
        # Highest adverse price = 3050.0 -> MAE = (3000 - 3050) / 100 = -0.5 R
        assert res["mae_price"] == 3050.0
        assert pytest.approx(res["mae_r"], 0.01) == -0.5
        # Lowest favorable price = 2750.0 -> MFE = (3000 - 2750) / 100 = +2.5 R
        assert res["mfe_price"] == 2750.0
        assert pytest.approx(res["mfe_r"], 0.01) == 2.5
        # Actual move = 3000 - 2800 = 200. Potential = 3000 - 2750 = 250
        # Exit Efficiency = 200 / 250 = 0.80 (80%)
        assert pytest.approx(res["exit_efficiency"], 0.01) == 0.80

    def test_missing_stop_loss_fallback(self):
        trade = {
            "id": "T-103",
            "symbol": "SOLUSDT",
            "side": "BUY",
            "entry_price": 100.0,
            "exit_price": 105.0,
            "stop_loss": None, # Should default to 1% of entry = 1.0
            "pnl": 5.0,
            "status": "CLOSED"
        }
        res = MaeMfeAnalyzer.analyze_trade_excursion(trade, candles=[])
        assert res["risk_unit"] == 1.0
        assert res["exit_efficiency"] >= 0.0

    def test_scatter_aggregation_and_sensitivities(self):
        data = mae_mfe_analyzer.get_mae_mfe_scatter_data()
        assert "points" in data
        assert "stop_loss_sensitivities" in data
        assert len(data["stop_loss_sensitivities"]) > 0
        assert "recommended_target_r" in data
        assert data["recommended_target_r"] > 0