"""
Pytest Verification Suite for Multi-Asset Portfolio Aggregator & Risk Analytics Engine.
Validates multi-asset classification, R-multiple exposure, equity curve progression,
peak-to-trough drawdown math, daily heatmap aggregation, and REST API endpoints.
"""

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from main import create_app
from app.services.portfolio_service import (
    PortfolioAnalyticsService,
    portfolio_service,
    classify_asset_class
)
from app.db.sqlite_driver import sqlite_driver


class TestPortfolioAnalyticsService:
    """Comprehensive test suite for portfolio analytics and risk exposure engine."""

    def test_asset_classification(self):
        """Validates classification of heterogeneous asset symbols."""
        assert classify_asset_class("BTCUSDT") == "crypto"
        assert classify_asset_class("ETH/USDT") == "crypto"
        assert classify_asset_class("SOL-USDC") == "crypto"
        assert classify_asset_class("EURUSD") == "forex"
        assert classify_asset_class("GBP/USD") == "forex"
        assert classify_asset_class("USDJPY=X") == "forex"
        assert classify_asset_class("XAUUSD") == "commodity"
        assert classify_asset_class("GOLD") == "commodity"
        assert classify_asset_class("CRUDE") == "commodity"
        assert classify_asset_class("SPY") == "equity"
        assert classify_asset_class("QQQ") == "equity"
        assert classify_asset_class("NVDA") == "equity"
        assert classify_asset_class("^GSPC") == "equity"

    def test_empty_portfolio_summary_defaults(self):
        """Validates that an empty portfolio summary returns stable default metrics without division errors."""
        service = PortfolioAnalyticsService(default_initial_balance=50000.0)
        with patch.object(sqlite_driver, "list_trades", return_value=[]):
            summary = service.get_portfolio_summary()
            assert summary["initial_balance"] == 50000.0
            assert summary["total_equity"] == 50000.0
            assert summary["net_pnl"] == 0.0
            assert summary["net_pnl_pct"] == 0.0
            assert summary["today_pnl"] == 0.0
            assert summary["win_rate"] == 0.0
            assert summary["profit_factor"] == 0.0
            assert summary["avg_r_multiple"] == 0.0
            assert summary["open_risk_usd"] == 0.0
            assert summary["open_risk_r"] == 0.0
            assert summary["active_positions_count"] == 0
            assert summary["total_closed_trades"] == 0
            assert summary["max_drawdown_usd"] == 0.0
            assert summary["max_drawdown_pct"] == 0.0

    def test_multi_asset_pnl_aggregation(self):
        """Validates multi-asset grouping, win rate, and volume calculation across crypto, forex, and commodities."""
        service = PortfolioAnalyticsService()
        mock_trades = [
            # Crypto: BTCUSDT (2 closed trades, 1 win, 1 loss)
            {"symbol": "BTCUSDT", "status": "CLOSED", "pnl": 500.0, "entry_price": 60000.0, "qty": 0.5},
            {"symbol": "BTCUSDT", "status": "CLOSED", "pnl": -100.0, "entry_price": 61000.0, "qty": 0.5},
            # Forex: EURUSD (1 closed trade win)
            {"symbol": "EURUSD", "status": "CLOSED", "pnl": 250.0, "entry_price": 1.0850, "qty": 100000.0},
            # Commodity: XAUUSD (1 closed trade loss, 1 open position)
            {"symbol": "XAUUSD", "status": "CLOSED", "pnl": -150.0, "entry_price": 2500.0, "qty": 10.0},
            {"symbol": "XAUUSD", "status": "OPEN", "pnl": 0.0, "entry_price": 2510.0, "qty": 5.0},
            # Equity: SPY (1 closed trade win)
            {"symbol": "SPY", "status": "CLOSED", "pnl": 300.0, "entry_price": 550.0, "qty": 100.0}
        ]

        with patch.object(sqlite_driver, "list_trades", return_value=mock_trades):
            breakdown = service.get_multi_asset_breakdown()
            assert len(breakdown) == 4

            by_symbol = {b["symbol"]: b for b in breakdown}
            # BTCUSDT
            assert by_symbol["BTCUSDT"]["asset_class"] == "crypto"
            assert by_symbol["BTCUSDT"]["net_pnl"] == 400.0
            assert by_symbol["BTCUSDT"]["trade_count"] == 2
            assert by_symbol["BTCUSDT"]["win_rate"] == 50.0

            # EURUSD
            assert by_symbol["EURUSD"]["asset_class"] == "forex"
            assert by_symbol["EURUSD"]["net_pnl"] == 250.0
            assert by_symbol["EURUSD"]["win_rate"] == 100.0

            # XAUUSD
            assert by_symbol["XAUUSD"]["asset_class"] == "commodity"
            assert by_symbol["XAUUSD"]["net_pnl"] == -150.0
            assert by_symbol["XAUUSD"]["open_positions"] == 1
            assert by_symbol["XAUUSD"]["trade_count"] == 2

            # SPY
            assert by_symbol["SPY"]["asset_class"] == "equity"
            assert by_symbol["SPY"]["net_pnl"] == 300.0

    def test_risk_exposure_and_r_multiple_calculation(self):
        """Validates stop loss risk summation for long, short, and unhedged open positions."""
        service = PortfolioAnalyticsService(default_initial_balance=100000.0)
        mock_trades = [
            # Long BTC: Entry 65,000, SL 64,000, Qty 0.5 -> Risk = 1,000 * 0.5 = 500 USD
            {"symbol": "BTCUSDT", "status": "OPEN", "side": "BUY", "entry_price": 65000.0, "stop_loss": 64000.0, "qty": 0.5},
            # Short ETH: Entry 3,500, SL 3,600, Qty 2.0 -> Risk = 100 * 2.0 = 200 USD
            {"symbol": "ETHUSDT", "status": "OPEN", "side": "SELL", "entry_price": 3500.0, "stop_loss": 3600.0, "qty": 2.0},
            # Unhedged SOL (No SL): Entry 150, Qty 10.0 -> Risk = 1,500 * 0.02 = 30 USD
            {"symbol": "SOLUSDT", "status": "OPEN", "side": "BUY", "entry_price": 150.0, "stop_loss": None, "qty": 10.0}
        ]

        with patch.object(sqlite_driver, "list_trades", return_value=mock_trades):
            summary = service.get_portfolio_summary()
            assert summary["active_positions_count"] == 3
            assert summary["open_risk_r"] == 3.0
            assert summary["open_risk_usd"] == 730.0  # 500 + 200 + 30

    def test_equity_curve_and_drawdown_math(self):
        """Validates sequential equity tracking, peak detection, and max drawdown calculations."""
        service = PortfolioAnalyticsService(default_initial_balance=100000.0)
        mock_trades = [
            {"symbol": "BTCUSDT", "status": "CLOSED", "pnl": 5000.0, "r_multiple": 2.5, "exit_time": "2026-08-25T10:00:00Z"},  # Eq: 105k, Peak: 105k, DD: 0%
            {"symbol": "ETHUSDT", "status": "CLOSED", "pnl": -10000.0, "r_multiple": -1.0, "exit_time": "2026-08-26T12:00:00Z"}, # Eq: 95k, Peak: 105k, DD: 10k (9.52%)
            {"symbol": "SOLUSDT", "status": "CLOSED", "pnl": 2000.0, "r_multiple": 1.0, "exit_time": "2026-08-27T14:00:00Z"},   # Eq: 97k, Peak: 105k, DD: 8k (7.62%)
            {"symbol": "BTCUSDT", "status": "CLOSED", "pnl": 15000.0, "r_multiple": 3.0, "exit_time": "2026-08-28T16:00:00Z"}   # Eq: 112k, Peak: 112k, DD: 0%
        ]

        with patch.object(sqlite_driver, "list_trades", return_value=mock_trades):
            summary = service.get_portfolio_summary()
            assert summary["net_pnl"] == 12000.0  # 5000 - 10000 + 2000 + 15000
            assert summary["total_equity"] == 112000.0
            assert summary["net_pnl_pct"] == 12.0
            assert summary["total_closed_trades"] == 4
            assert summary["win_rate"] == 75.0  # 3 wins out of 4
            assert summary["avg_r_multiple"] == pytest.approx(1.375, abs=0.01)  # (2.5 - 1.0 + 1.0 + 3.0) / 4 = 1.375
            assert summary["gross_profit"] == 22000.0
            assert summary["gross_loss"] == 10000.0
            assert summary["profit_factor"] == 2.2  # 22000 / 10000
            assert summary["max_drawdown_usd"] == 10000.0
            assert summary["max_drawdown_pct"] == pytest.approx(9.52, abs=0.01)

            # Check equity curve series points
            curve = service.get_equity_curve_series(initial_balance=100000.0)
            assert len(curve) == 4
            assert curve[0]["equity"] == 105000.0
            assert curve[1]["equity"] == 95000.0
            assert curve[2]["equity"] == 97000.0
            assert curve[3]["equity"] == 112000.0

    def test_daily_pnl_heatmap_aggregation(self):
        """Validates daily aggregation, win rate, and intensity normalization for calendar heatmap."""
        service = PortfolioAnalyticsService()
        mock_trades = [
            {"status": "CLOSED", "pnl": 400.0, "exit_time": "2026-08-28T10:00:00Z"},
            {"status": "CLOSED", "pnl": -100.0, "exit_time": "2026-08-28T14:00:00Z"},
            {"status": "CLOSED", "pnl": 1000.0, "exit_time": "2026-08-29T11:00:00Z"},
            {"status": "CLOSED", "pnl": -500.0, "exit_time": "2026-08-30T15:00:00Z"}
        ]

        with patch.object(sqlite_driver, "list_trades", return_value=mock_trades):
            heatmap = service.get_daily_pnl_heatmap()
            assert len(heatmap) == 3

            by_date = {h["date"]: h for h in heatmap}
            # 2026-08-28: PnL = +300 (2 trades, 1 win 1 loss -> 50% win rate)
            assert by_date["2026-08-28"]["pnl"] == 300.0
            assert by_date["2026-08-28"]["trades_count"] == 2
            assert by_date["2026-08-28"]["win_rate"] == 50.0

            # 2026-08-29: PnL = +1000 (Max day, intensity = 1.0)
            assert by_date["2026-08-29"]["pnl"] == 1000.0
            assert by_date["2026-08-29"]["intensity"] == 1.0

            # 2026-08-30: PnL = -500 (Intensity = -0.5)
            assert by_date["2026-08-30"]["pnl"] == -500.0
            assert by_date["2026-08-30"]["intensity"] == -0.5

    def test_portfolio_rest_api_endpoints(self):
        """Validates that all portfolio REST API endpoints return HTTP 200 with valid schema."""
        app = create_app()
        client = TestClient(app)

        # 1. GET /api/v1/portfolio/summary
        res_sum = client.get("/api/v1/portfolio/summary?initial_balance=100000")
        assert res_sum.status_code == 200
        data_sum = res_sum.json()
        assert "total_equity" in data_sum
        assert "net_pnl" in data_sum
        assert "open_risk_usd" in data_sum
        assert "win_rate" in data_sum

        # 2. GET /api/v1/portfolio/multi-asset-breakdown
        res_break = client.get("/api/v1/portfolio/multi-asset-breakdown")
        assert res_break.status_code == 200
        assert isinstance(res_break.json(), list)

        # 3. GET /api/v1/portfolio/equity-curve
        res_curve = client.get("/api/v1/portfolio/equity-curve?initial_balance=100000")
        assert res_curve.status_code == 200
        assert isinstance(res_curve.json(), list)

        # 4. GET /api/v1/portfolio/heatmap
        res_heat = client.get("/api/v1/portfolio/heatmap")
        assert res_heat.status_code == 200
        assert isinstance(res_heat.json(), list)
