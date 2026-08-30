import pytest
import numpy as np
from app.quant.quant_engine import quant_engine, QuantEngine

class TestQuantEngineMetrics:
    """Institutional-grade pytest validation suite for quant financial metrics."""

    def test_mae_mfe_long_position(self):
        # Entry: 100.0, Stop Loss: 95.0 -> Risk Unit = 5.0
        # Price path hits low of 92.0 (-8.0) and high of 115.0 (+15.0)
        prices = [98.0, 95.0, 92.0, 105.0, 112.0, 115.0, 110.0]
        res = quant_engine.calculate_mae_mfe(entry_price=100.0, price_series=prices, side="BUY", stop_loss=95.0)
        
        assert res["risk_unit"] == 5.0
        assert res["mae_price"] == 92.0
        assert res["mfe_price"] == 115.0
        # MAE: (92 - 100) / 5 = -1.6 R
        assert pytest.approx(res["mae"], 0.001) == -1.6
        # MFE: (115 - 100) / 5 = +3.0 R
        assert pytest.approx(res["mfe"], 0.001) == 3.0

    def test_mae_mfe_short_position(self):
        # Entry: 100.0, Stop Loss: 105.0 -> Risk Unit = 5.0
        # Price path hits high of 107.0 (-7.0 adverse) and low of 85.0 (+15.0 favorable)
        prices = [102.0, 107.0, 98.0, 92.0, 85.0, 90.0]
        res = quant_engine.calculate_mae_mfe(entry_price=100.0, price_series=prices, side="SELL", stop_loss=105.0)

        assert res["risk_unit"] == 5.0
        assert res["mae_price"] == 107.0
        assert res["mfe_price"] == 85.0
        # MAE for short: (100 - 107) / 5 = -1.4 R
        assert pytest.approx(res["mae"], 0.001) == -1.4
        # MFE for short: (100 - 85) / 5 = +3.0 R
        assert pytest.approx(res["mfe"], 0.001) == 3.0

    def test_mae_mfe_missing_stop_loss_fallback(self):
        # When SL is None, default risk unit is 1% of entry (1.0 for 100.0)
        prices = [98.0, 102.0]
        res = quant_engine.calculate_mae_mfe(entry_price=100.0, price_series=prices, side="BUY", stop_loss=None)
        assert res["risk_unit"] == 1.0
        assert pytest.approx(res["mae"], 0.001) == -2.0
        assert pytest.approx(res["mfe"], 0.001) == 2.0

    def test_exit_efficiency_long(self):
        # Entry: 100.0, Exit: 108.0, MFE Price: 110.0
        # Efficiency = (108 - 100) / (110 - 100) = 8 / 10 = 0.80 (80%)
        eff = quant_engine.calculate_exit_efficiency(entry_price=100.0, exit_price=108.0, mfe_price=110.0, side="BUY")
        assert pytest.approx(eff, 0.001) == 0.8

    def test_exit_efficiency_short(self):
        # Entry: 100.0, Exit: 85.0, MFE Price: 80.0
        # Potential: 100 - 80 = 20, Actual: 100 - 85 = 15 -> Efficiency = 15 / 20 = 0.75
        eff = quant_engine.calculate_exit_efficiency(entry_price=100.0, exit_price=85.0, mfe_price=80.0, side="SELL")
        assert pytest.approx(eff, 0.001) == 0.75

    def test_exit_efficiency_zero_range_edge_case(self):
        # Flat trade: Entry = Exit = MFE
        eff = quant_engine.calculate_exit_efficiency(entry_price=100.0, exit_price=100.0, mfe_price=100.0, side="BUY")
        assert eff == 1.0

    def test_sqn_calculation(self):
        # Known R-multiples: [2.0, 2.0, 2.0, 2.0, 2.0] (zero variance edge case)
        assert quant_engine.calculate_sqn([2.0, 2.0, 2.0, 2.0]) == 0.0

        # Normal diverse R-multiples: [1.0, 2.0, -1.0, 3.0, -0.5, 2.5]
        # Sum = 7, N = 6, Mean = 7/6, Variance (ddof=1) = 8/3, Std = sqrt(8/3)
        # SQN = sqrt(6) * (7/6) / sqrt(8/3) = 1.75
        r_series = [1.0, 2.0, -1.0, 3.0, -0.5, 2.5]
        sqn = quant_engine.calculate_sqn(r_series)
        assert sqn > 0.0
        assert pytest.approx(sqn, 0.001) == 1.75

    def test_sqn_single_or_empty_trade_edge_case(self):
        assert quant_engine.calculate_sqn([]) == 0.0
        assert quant_engine.calculate_sqn([1.5]) == 0.0

    def test_sharpe_and_sortino_ratio(self):
        returns = [0.01, 0.02, -0.005, 0.015, -0.008, 0.03]
        sharpe = quant_engine.calculate_sharpe_ratio(returns, risk_free_rate=0.0)
        sortino = quant_engine.calculate_sortino_ratio(returns, target_return=0.0)

        assert sharpe > 0.0
        assert sortino > 0.0
        assert sortino > sharpe

    def test_sortino_zero_downside_edge_case(self):
        returns = [0.02, 0.03, 0.015, 0.04]
        sortino = quant_engine.calculate_sortino_ratio(returns, target_return=0.0)
        assert sortino > 0.0

    def test_expectancy_ev(self):
        # Win Rate = 60%, Avg Win = $250, Loss Rate = 40%, Avg Loss = $150
        # EV = (0.60 * 250) - (0.40 * 150) = 150 - 60 = +$90.0
        ev = quant_engine.calculate_expectancy(win_rate=0.60, avg_win=250.0, loss_rate=0.40, avg_loss=150.0)
        assert ev == 90.0

        # Percentage input (60, 40)
        ev_pct = quant_engine.calculate_expectancy(win_rate=60, avg_win=250.0, loss_rate=40, avg_loss=150.0)
        assert ev_pct == 90.0

    def test_max_drawdown(self):
        equity = [100.0, 110.0, 120.0, 105.0, 90.0, 100.0, 110.0]
        dd = quant_engine.calculate_max_drawdown(equity)
        assert dd["max_drawdown_amount"] == 30.0
        assert dd["max_drawdown_pct"] == 25.0

    def test_full_performance_suite_integration(self):
        pnls = [500.0, -200.0, 800.0, -150.0, 300.0, 600.0, -250.0]
        r_multiples = [2.5, -1.0, 4.0, -0.75, 1.5, 3.0, -1.25]
        scorecard = quant_engine.calculate_full_performance_suite(pnls, r_multiples=r_multiples, initial_capital=10000.0)

        assert scorecard["total_trades"] == 7
        assert scorecard["win_rate"] > 50.0
        assert scorecard["profit_factor"] > 1.0
        assert scorecard["expectancy"] > 0.0
        assert scorecard["sqn"] > 0.0
        assert scorecard["sharpe_ratio"] > 0.0
        assert scorecard["total_pnl"] == sum(pnls)

    def test_full_performance_suite_empty_case(self):
        scorecard = quant_engine.calculate_full_performance_suite([])
        assert scorecard["total_trades"] == 0
        assert scorecard["win_rate"] == 0.0
        assert scorecard["profit_factor"] == 0.0