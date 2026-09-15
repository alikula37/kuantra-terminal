"""
Pytest Verification Suite for Multi-Asset Portfolio Aggregator & Risk Analytics Engine.
Validates multi-asset classification, R-multiple exposure, equity curve progression,
peak-to-trough drawdown math, daily heatmap aggregation, and REST API endpoints.
"""

import asyncio
from datetime import datetime, timedelta, timezone

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
from app.services.quote_refresh import QuoteRefreshService
from app.services.trade_read_adapter import trade_read_adapter


class _FakeQuoteFetcher:
    def __init__(self, prices):
        self.prices = prices

    async def fetch_quote(self, symbol, source):
        if symbol not in self.prices:
            raise RuntimeError("no quote configured")
        return {
            "status": "LIVE",
            "price": self.prices[symbol],
            "price_kind": "LAST",
            "source_id": source,
            "source_symbol": symbol,
            "observed_at": datetime.now(timezone.utc).isoformat(),
        }


def _quote_service(monkeypatch, trades, prices):
    fetcher = _FakeQuoteFetcher(prices)
    service = QuoteRefreshService(fetcher=fetcher)
    asyncio.run(service.refresh(trades))
    monkeypatch.setattr("app.services.portfolio_service.quote_refresh_service", service)
    return service


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
        with patch.object(trade_read_adapter, "list_trades", return_value=[]):
            summary = service.get_portfolio_summary()
            assert summary["initial_balance"] == 50000.0
            assert summary["total_equity"] == 50000.0
            assert summary["net_pnl"] == 0.0
            assert summary["net_pnl_pct"] == 0.0
            assert summary["today_pnl"] == 0.0
            assert summary["win_rate"] == 0.0
            assert summary["profit_factor"] == 0.0
            assert summary["avg_r_multiple"] is None
            assert summary["known_r_trades"] == 0
            assert summary["open_risk_basis"] == "COMPLETE"
            assert summary["profit_factor_basis"] == "READY"
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

        with patch.object(trade_read_adapter, "list_trades", return_value=mock_trades):
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

    def test_canceled_tombstones_are_excluded_from_performance_breakdown(self):
        """Audit tombstones remain journal-visible but cannot create analytics buckets."""
        service = PortfolioAnalyticsService()
        mock_trades = [
            {
                "symbol": "BTCUSDT",
                "status": "CLOSED",
                "pnl": 125.0,
                "entry_price": 60000.0,
                "qty": 0.1,
            },
            {
                "symbol": "BTCUSDT",
                "status": "CANCELED",
                "pnl": 125.0,
                "entry_price": 60000.0,
                "qty": 0.1,
            },
            {
                "symbol": "XAUUSD",
                "status": "CANCELED",
                "pnl": 0.0,
                "entry_price": 2500.0,
                "qty": 1.0,
            },
        ]

        with patch.object(trade_read_adapter, "list_trades", return_value=mock_trades):
            breakdown = service.get_multi_asset_breakdown()

        assert [item["symbol"] for item in breakdown] == ["BTCUSDT"]
        assert breakdown[0]["net_pnl"] == 125.0
        assert breakdown[0]["trade_count"] == 1

    def test_risk_exposure_and_r_multiple_calculation(self):
        """Validates stop loss risk summation for long, short, and unhedged open positions."""
        service = PortfolioAnalyticsService(default_initial_balance=100000.0)
        mock_trades = [
            # Long BTC: Entry 65,000, SL 64,000, Qty 0.5 -> Risk = 1,000 * 0.5 = 500 USD
            {"symbol": "BTCUSDT", "status": "OPEN", "side": "BUY", "entry_price": 65000.0, "stop_loss": 64000.0, "qty": 0.5, "qty_unit": "BASE"},
            # Short ETH: Entry 3,500, SL 3,600, Qty 2.0 -> Risk = 100 * 2.0 = 200 USD
            {"symbol": "ETHUSDT", "status": "OPEN", "side": "SELL", "entry_price": 3500.0, "stop_loss": 3600.0, "qty": 2.0, "qty_unit": "BASE"},
            # Unhedged SOL (No SL): Entry 150, Qty 10.0 -> Risk = 1,500 * 0.02 = 30 USD
            {"symbol": "SOLUSDT", "status": "OPEN", "side": "BUY", "entry_price": 150.0, "stop_loss": None, "qty": 10.0, "qty_unit": "BASE"}
        ]

        with patch.object(trade_read_adapter, "list_trades", return_value=mock_trades):
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

        with patch.object(trade_read_adapter, "list_trades", return_value=mock_trades):
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
            assert len(curve) == 5
            assert curve[0]["symbol"] == "INITIAL"
            assert curve[0]["equity"] == 100000.0
            assert curve[0]["cumulative_pnl"] == 0.0
            assert curve[1]["equity"] == 105000.0
            assert curve[2]["equity"] == 95000.0
            assert curve[3]["equity"] == 97000.0
            assert curve[4]["equity"] == 112000.0

    def test_open_risk_and_r_basis_distinguish_unknown_from_zero(self):
        """Unverified units and missing R data must be reported as unknown."""
        service = PortfolioAnalyticsService(default_initial_balance=100000.0)
        mock_trades = [
            {"symbol": "BTCUSDT", "status": "OPEN", "side": "BUY", "entry_price": 100.0,
             "stop_loss": 95.0, "qty": 2.0, "qty_unit": "BASE"},
            {"symbol": "XAUUSD", "status": "OPEN", "side": "BUY", "entry_price": 2000.0,
             "stop_loss": None, "qty": 1.0, "qty_unit": "UNKNOWN"},
            {"symbol": "ETHUSDT", "status": "CLOSED", "pnl": 10.0, "r_multiple": None,
             "qty_unit": "BASE", "exit_time": "2026-08-28T16:00:00Z"},
        ]

        with patch.object(trade_read_adapter, "list_trades", return_value=mock_trades):
            summary = service.get_portfolio_summary()

        assert summary["active_positions_count"] == 2
        assert summary["unverified_open_positions"] == 1
        assert summary["open_risk_basis"] == "PARTIAL"
        assert summary["known_r_trades"] == 0
        assert summary["avg_r_multiple"] is None
        assert summary["unknown_pnl_trades"] == 0

        all_unverified = [mock_trades[1], {"symbol": "GOLD", "status": "OPEN", "side": "BUY",
                                           "entry_price": 2000.0, "qty": 1.0, "qty_unit": "UNKNOWN"}]
        with patch.object(trade_read_adapter, "list_trades", return_value=all_unverified):
            summary = service.get_portfolio_summary()
        assert summary["open_risk_basis"] == "NOT_AVAILABLE"
        assert summary["open_risk_usd"] == 0.0
        assert summary["open_risk_r"] == 0.0

    def test_live_equity_prices_open_positions_from_refreshed_quotes(self, monkeypatch):
        """Mark-to-market equity adds covered open results to the realized ledger."""
        service = PortfolioAnalyticsService(default_initial_balance=100000.0)
        mock_trades = [
            {"id": "C-1", "symbol": "BTCUSDT", "status": "CLOSED", "pnl": 50.0,
             "qty_unit": "BASE", "exit_time": "2026-08-28T16:00:00Z"},
            {"id": "O-1", "symbol": "BTCUSDT", "status": "OPEN", "side": "BUY",
             "entry_price": 100.0, "qty": 2.0, "qty_unit": "BASE",
             "price_source": "binance_public", "price_source_symbol": "BTCUSDT"},
            {"id": "O-2", "symbol": "ETHUSDT", "status": "OPEN", "side": "SELL",
             "entry_price": 200.0, "qty": 1.0, "qty_unit": "BASE",
             "price_source": "binance_public", "price_source_symbol": "ETHUSDT"},
        ]
        _quote_service(monkeypatch, mock_trades, {"BTCUSDT": 110.0, "ETHUSDT": 190.0})

        with patch.object(trade_read_adapter, "list_trades", return_value=mock_trades):
            summary = service.get_portfolio_summary()

        assert summary["total_equity"] == 100050.0
        assert summary["unrealized_pnl_usd"] == 30.0  # +20 long, +10 short
        assert summary["live_equity"] == 100080.0
        assert summary["live_equity_basis"] == "COMPLETE"
        assert summary["live_positions_covered"] == 2
        assert summary["live_positions_unpriced"] == 0
        assert summary["live_quotes_stale"] is False
        assert summary["oldest_live_quote_age_seconds"] is not None
        assert summary["unrealized_pnl_pct"] == pytest.approx(0.03, abs=0.001)

    def test_live_equity_basis_distinguishes_partial_and_unavailable(self, monkeypatch):
        """An unpriced or unverified position is counted, never valued at entry price."""
        service = PortfolioAnalyticsService(default_initial_balance=100000.0)
        mock_trades = [
            {"id": "O-1", "symbol": "BTCUSDT", "status": "OPEN", "side": "BUY",
             "entry_price": 100.0, "qty": 1.0, "qty_unit": "BASE",
             "price_source": "binance_public", "price_source_symbol": "BTCUSDT"},
            {"id": "O-2", "symbol": "XAUUSD", "status": "OPEN", "side": "BUY",
             "entry_price": 2000.0, "qty": 1.0, "qty_unit": "UNKNOWN"},
        ]
        _quote_service(monkeypatch, mock_trades, {"BTCUSDT": 105.0})

        with patch.object(trade_read_adapter, "list_trades", return_value=mock_trades):
            summary = service.get_portfolio_summary()
        assert summary["live_equity_basis"] == "PARTIAL"
        assert summary["live_positions_covered"] == 1
        assert summary["live_positions_unpriced"] == 1
        assert summary["unrealized_pnl_usd"] == 5.0
        assert summary["live_equity"] == 100005.0

        unpriced_only = [mock_trades[0].copy(), {
            "id": "O-3", "symbol": "GOLD", "status": "OPEN", "side": "BUY",
            "entry_price": 2000.0, "qty": 1.0, "qty_unit": "UNKNOWN",
        }]
        _quote_service(monkeypatch, unpriced_only, {})
        with patch.object(trade_read_adapter, "list_trades", return_value=unpriced_only):
            summary = service.get_portfolio_summary()
        assert summary["live_equity"] is None
        assert summary["live_equity_basis"] == "NOT_AVAILABLE"
        assert summary["unrealized_pnl_usd"] == 0.0
        assert summary["total_equity"] == 100000.0

    def test_live_equity_uses_stale_last_known_and_flags_it(self, monkeypatch):
        """A failed refresh can only contribute the explicitly stale last known price."""
        service = PortfolioAnalyticsService(default_initial_balance=100000.0)
        mock_trades = [
            {"id": "O-1", "symbol": "BTCUSDT", "status": "OPEN", "side": "BUY",
             "entry_price": 100.0, "qty": 1.0, "qty_unit": "BASE",
             "price_source": "binance_public", "price_source_symbol": "BTCUSDT"},
        ]
        quote_service = QuoteRefreshService(fetcher=_FakeQuoteFetcher({}))
        observed = (datetime.now(timezone.utc) - timedelta(seconds=90)).isoformat()
        quote_service._cache[("binance_public", "BTCUSDT")] = {
            "kind": "error",
            "reason": "PROVIDER_UNAVAILABLE",
            "failures": 1,
            "retry_at": datetime.now(timezone.utc) + timedelta(seconds=60),
            "last_known_quote": {
                "status": "LIVE", "price": 108.0, "price_kind": "LAST",
                "source_id": "binance_public", "source_symbol": "BTCUSDT",
                "observed_at": observed,
            },
        }
        monkeypatch.setattr("app.services.portfolio_service.quote_refresh_service", quote_service)

        with patch.object(trade_read_adapter, "list_trades", return_value=mock_trades):
            summary = service.get_portfolio_summary()

        assert summary["unrealized_pnl_usd"] == 8.0
        assert summary["live_equity"] == 100008.0
        assert summary["live_equity_basis"] == "COMPLETE"
        assert summary["live_quotes_stale"] is True
        assert summary["oldest_live_quote_age_seconds"] >= 89.0
        assert summary["oldest_live_quote_observed_at"] == observed

    def test_open_exposure_and_margin_cover_only_verified_units(self, monkeypatch):
        """Exposure sums verified notionals; margin needs a recorded leverage."""
        service = PortfolioAnalyticsService(default_initial_balance=100000.0)
        mock_trades = [
            {"id": "O-1", "symbol": "BTCUSDT", "status": "OPEN", "side": "BUY",
             "entry_price": 100.0, "qty": 2.0, "leverage": 10, "qty_unit": "BASE"},
            {"id": "O-2", "symbol": "ETHUSDT", "status": "OPEN", "side": "BUY",
             "entry_price": 50.0, "qty": 4.0, "qty_unit": "BASE"},
            {"id": "O-3", "symbol": "XAUUSD", "status": "OPEN", "side": "BUY",
             "entry_price": 2000.0, "qty": 1.0, "qty_unit": "UNKNOWN"},
        ]
        _quote_service(monkeypatch, mock_trades, {})

        with patch.object(trade_read_adapter, "list_trades", return_value=mock_trades):
            summary = service.get_portfolio_summary()

        assert summary["open_notional_usd"] == 400.0  # 200 + 200, the unknown unit excluded
        assert summary["open_margin_usd"] == 20.0  # only the 10x leg contributes 200/10
        assert summary["open_margin_positions"] == 1
        assert summary["open_exposure_basis"] == "PARTIAL"
        assert summary["open_exposure_unpriced"] == 1

        all_unverified = [mock_trades[2]]
        with patch.object(trade_read_adapter, "list_trades", return_value=all_unverified):
            summary = service.get_portfolio_summary()
        assert summary["open_exposure_basis"] == "NOT_AVAILABLE"
        assert summary["open_notional_usd"] == 0.0
        assert summary["open_margin_usd"] == 0.0

    def test_daily_pnl_heatmap_aggregation(self):
        """Validates daily aggregation, win rate, and intensity normalization for calendar heatmap."""
        service = PortfolioAnalyticsService()
        mock_trades = [
            {"status": "CLOSED", "pnl": 400.0, "exit_time": "2026-08-28T10:00:00Z"},
            {"status": "CLOSED", "pnl": -100.0, "exit_time": "2026-08-28T14:00:00Z"},
            {"status": "CLOSED", "pnl": 1000.0, "exit_time": "2026-08-29T11:00:00Z"},
            {"status": "CLOSED", "pnl": -500.0, "exit_time": "2026-08-30T15:00:00Z"}
        ]

        with patch.object(trade_read_adapter, "list_trades", return_value=mock_trades):
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

        # 5. POST /api/v1/portfolio/set-initial-balance
        res_set = client.post("/api/v1/portfolio/set-initial-balance", json={"initial_balance": 25000.0})
        assert res_set.status_code == 200
        data_set = res_set.json()
        assert data_set["initial_balance"] == 25000.0
        assert data_set["total_equity"] >= 25000.0

    def test_clean_startup_zero_state(self):
        """Validates that a fresh installation with 0 trades returns exact zero-state metrics."""
        service = PortfolioAnalyticsService(default_initial_balance=0.0)
        with patch.object(trade_read_adapter, "list_trades", return_value=[]):
            summary = service.get_portfolio_summary()
            assert summary["initial_balance"] == 0.0
            assert summary["total_equity"] == 0.0
            assert summary["net_pnl"] == 0.0
            assert summary["net_pnl_pct"] == 0.0
            assert summary["today_pnl"] == 0.0
            assert summary["today_pnl_pct"] == 0.0
            assert summary["today_trades_count"] == {"wins": 0, "losses": 0, "total": 0, "unknown_pnl": 0}
            assert summary["unknown_pnl_trades"] == 0
            assert summary["open_risk_usd"] == 0.0
            assert summary["open_risk_r"] == 0.0
            assert summary["active_positions_count"] == 0
            assert summary["total_closed_trades"] == 0
            assert summary["win_rate"] == 0.0
            assert summary["profit_factor"] == 0.0
            assert summary["avg_r_multiple"] is None
            assert summary["known_r_trades"] == 0
            assert summary["open_risk_basis"] == "COMPLETE"
            assert summary["profit_factor_basis"] == "READY"
            assert summary["max_drawdown_usd"] == 0.0
            assert summary["max_drawdown_pct"] == 0.0

            breakdown = service.get_multi_asset_breakdown()
            assert breakdown == []

            heatmap = service.get_daily_pnl_heatmap()
            assert heatmap == []

    def test_set_user_initial_balance(self):
        """Verifies setting custom balance accurately updates total_equity and persists across service reloads."""
        service = PortfolioAnalyticsService()
        with patch.object(trade_read_adapter, "list_trades", return_value=[]):
            res = service.set_initial_balance(12500.0)
            assert res["initial_balance"] == 12500.0
            assert res["total_equity"] == 12500.0
            assert res["net_pnl"] == 0.0

            # Reload summary
            reloaded = service.get_portfolio_summary()
            assert reloaded["initial_balance"] == 12500.0
            assert reloaded["total_equity"] == 12500.0

    def test_zero_division_guard_all_metrics(self):
        """Validates that Win Rate, Profit Factor, Max Drawdown, and Avg R never produce NaN or inf with zero closed trades."""
        service = PortfolioAnalyticsService(default_initial_balance=0.0)
        with patch.object(trade_read_adapter, "list_trades", return_value=[]):
            summary = service.get_portfolio_summary()
            assert not any(str(v).lower() in ("nan", "inf", "-inf") for v in summary.values() if isinstance(v, (int, float)))
