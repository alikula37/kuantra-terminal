"""
Test Suite for Authentic CCXT Execution Engine & Pre-Execution Risk Gatekeeper.
Verifies encrypted credential management, mocked CCXT order dispatching,
pre-trade risk validation, paper trading sandbox, and REST API endpoints.
"""

import pytest
import time
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from main import create_app
from app.services.exchange.credentials_manager import ExchangeCredentialsManager, exchange_credentials_manager
from app.services.execution.ccxt_engine import CCXTExecutionEngine, ccxt_execution_engine
from app.quant.risk_guard import RiskGuard, risk_guard
from app.db.sqlite_driver import sqlite_driver

app = create_app()
client = TestClient(app)


class TestExchangeCredentialsAndEncryption:
    """Tests for AES-256-GCM encrypted credential persistence and round-trips."""

    def test_credentials_encryption_and_decryption(self):
        mgr = ExchangeCredentialsManager()
        raw_key = "binance_live_api_key_test_12345678"
        raw_secret = "binance_live_secret_key_ultra_secure_987654"

        saved = mgr.save_credentials(
            exchange_id="binance_futures",
            name="Test Binance Futures",
            api_key=raw_key,
            api_secret=raw_secret,
            is_testnet=True
        )

        assert saved["exchange_id"] == "binance_futures"
        assert saved["api_key_masked"] == "bina...5678"
        assert saved["is_testnet"] is True

        decrypted = mgr.get_decrypted_credentials("binance_futures")
        assert decrypted is not None
        assert decrypted["api_key"] == raw_key
        assert decrypted["api_secret"] == raw_secret
        assert decrypted["is_testnet"] is True

    def test_credentials_manager_crud(self):
        mgr = ExchangeCredentialsManager()
        # Save OKX with passphrase
        mgr.save_credentials(
            exchange_id="okx",
            api_key="okx_key_abc_123",
            api_secret="okx_secret_def_456",
            passphrase="okx_passphrase_789",
            is_testnet=False
        )

        configs = mgr.list_configured_exchanges()
        okx_cfg = next((c for c in configs if c["exchange_id"] == "okx"), None)
        assert okx_cfg is not None
        assert okx_cfg["is_configured"] is True
        assert okx_cfg["has_passphrase"] is True

        # Delete
        assert mgr.delete_credentials("okx") is True
        assert mgr.get_decrypted_credentials("okx") is None


class TestPreExecutionRiskGatekeeper:
    """Tests for pre-execution stop loss distance and maximum risk per trade checks."""

    def test_risk_guard_blocks_excessive_risk(self):
        # 10,000 account, order buying 1.0 BTC at 65000 with SL at 60000 -> $5,000 risk (50% of account) -> EXCEEDS 2.5%
        order_payload = {
            "symbol": "BTCUSDT",
            "side": "BUY",
            "qty": 1.0,
            "price": 65000.0,
            "stop_loss": 60000.0,
            "mode": "PAPER"
        }

        guard = RiskGuard(default_max_risk_pct=2.5)
        approved, reason, meta = guard.validate_pre_execution_risk(order_payload, account_balance=10000.0)

        assert approved is False
        assert "EXCESSIVE_RISK" in reason
        assert meta["risk_pct"] == 50.0
        assert meta["max_allowed_risk_pct"] == 2.5

    def test_risk_guard_approves_disciplined_order(self):
        # 10,000 account, order buying 0.1 BTC at 65000 with SL at 64000 -> $100 risk (1% of account) -> UNDER 2.5%
        order_payload = {
            "symbol": "BTCUSDT",
            "side": "BUY",
            "qty": 0.1,
            "price": 65000.0,
            "stop_loss": 64000.0,
            "mode": "PAPER"
        }

        guard = RiskGuard(default_max_risk_pct=2.5)
        approved, reason, meta = guard.validate_pre_execution_risk(order_payload, account_balance=10000.0)

        assert approved is True
        assert approved is True
        assert meta["risk_pct"] == 1.0

    def test_risk_guard_stop_loss_direction_validation(self):
        # BUY order with SL higher than entry -> Invalid
        invalid_buy = {
            "symbol": "ETHUSDT",
            "side": "BUY",
            "qty": 1.0,
            "price": 3000.0,
            "stop_loss": 3500.0,
            "mode": "PAPER"
        }
        guard = RiskGuard()
        approved, reason, _ = guard.validate_pre_execution_risk(invalid_buy, account_balance=10000.0)
        assert approved is False
        assert "INVALID_STOP_LOSS" in reason

        # SELL order with SL lower than entry -> Invalid
        invalid_sell = {
            "symbol": "ETHUSDT",
            "side": "SELL",
            "qty": 1.0,
            "price": 3000.0,
            "stop_loss": 2500.0,
            "mode": "PAPER"
        }
        approved, reason, _ = guard.validate_pre_execution_risk(invalid_sell, account_balance=10000.0)
        assert approved is False
        assert "INVALID_STOP_LOSS" in reason


class TestCCXTExecutionEngine:
    """Tests for CCXT exchange order dispatching and paper sandbox routing."""

    def test_paper_trading_fallback(self):
        # Dispatch paper order with realistic parameters
        res = ccxt_execution_engine.create_order(
            symbol="SOLUSDT",
            side="BUY",
            order_type="MARKET",
            qty=2.0,
            price=145.0,
            stop_loss=140.0,
            take_profit=155.0,
            mode="PAPER",
            notes="Pytest paper execution"
        )

        assert res["success"] is True
        assert res["mode"] == "PAPER"
        assert res["status"] == "FILLED"
        assert "PAPER-" in res["order_id"]

        # Verify trade recorded in SQLite
        db_trade = sqlite_driver.get_trade(res["order_id"])
        assert db_trade is not None
        assert db_trade["symbol"] == "SOLUSDT"
        assert db_trade["entry_price"] == 145.0
        assert db_trade["stop_loss"] == 140.0

    @patch.object(CCXTExecutionEngine, "get_client")
    def test_ccxt_order_dispatch_mocked(self, mock_get_client):
        mock_ccxt_instance = MagicMock()
        mock_ccxt_instance.create_order.return_value = {
            "id": "10987654321",
            "status": "closed",
            "price": 64500.0,
            "average": 64500.0,
            "amount": 0.05,
            "fee": {"cost": 1.25, "currency": "USDT"}
        }
        mock_get_client.return_value = mock_ccxt_instance

        res = ccxt_execution_engine.create_order(
            symbol="BTCUSDT",
            side="BUY",
            order_type="LIMIT",
            qty=0.05,
            price=64500.0,
            stop_loss=64000.0,
            take_profit=66000.0,
            exchange_id="binance_futures",
            mode="LIVE"
        )

        assert res["success"] is True
        assert res["mode"] == "LIVE"
        assert res["order_id"] == "10987654321"
        assert res["price"] == 64500.0

        mock_ccxt_instance.create_order.assert_called_once()
        call_kwargs = mock_ccxt_instance.create_order.call_args[1]
        assert call_kwargs["symbol"] == "BTC/USDT:USDT"
        assert call_kwargs["type"] == "limit"
        assert call_kwargs["side"] == "buy"
        assert call_kwargs["amount"] == 0.05

    @patch.object(CCXTExecutionEngine, "get_client")
    def test_balance_synchronizer(self, mock_get_client):
        mock_ccxt_instance = MagicMock()
        mock_ccxt_instance.fetch_balance.return_value = {
            "free": {"USDT": 14500.50},
            "total": {"USDT": 18200.00},
            "used": {"USDT": 3699.50}
        }
        mock_get_client.return_value = mock_ccxt_instance

        res = ccxt_execution_engine.sync_exchange_balances("binance_futures")
        assert res["success"] is True
        assert res["free_quote"] == 14500.50
        assert res["total_equity"] == 18200.00
        assert res["used_margin"] == 3699.50


class TestExchangeRestApiEndpoints:
    """Tests for FastAPI execution and credential routes."""

    def test_exchange_endpoints_lifecycle(self):
        # 1. Save credentials via REST
        save_res = client.post("/api/v1/exchange/credentials", json={
            "exchange_id": "binance_spot",
            "name": "Binance Spot Main",
            "api_key": "api_test_spot_key_8888",
            "api_secret": "api_test_spot_secret_9999",
            "is_testnet": True
        })
        assert save_res.status_code == 200
        data = save_res.json()
        assert data["exchange_id"] == "binance_spot"
        assert "api_test_spot_key" not in data["api_key_masked"]

        # 2. List credentials
        list_res = client.get("/api/v1/exchange/credentials")
        assert list_res.status_code == 200
        configs = list_res.json()
        spot_entry = next((c for c in configs if c["exchange_id"] == "binance_spot"), None)
        assert spot_entry is not None
        assert spot_entry["is_configured"] is True

        # 3. Dispatch Paper Order via REST
        order_res = client.post("/api/v1/execution/order", json={
            "symbol": "BTCUSDT",
            "side": "BUY",
            "order_type": "MARKET",
            "qty": 0.05,
            "price": 64200.0,
            "stop_loss": 63800.0,
            "mode": "PAPER"
        })
        assert order_res.status_code == 200
        order_data = order_res.json()
        assert order_data["success"] is True
        assert order_data["mode"] == "PAPER"

        # 4. Dispatch Excessive Risk Order -> Expect 422
        excessive_order = client.post("/api/v1/execution/order", json={
            "symbol": "BTCUSDT",
            "side": "BUY",
            "order_type": "MARKET",
            "qty": 10.0,
            "price": 65000.0,
            "stop_loss": 55000.0,
            "mode": "PAPER"
        })
        assert excessive_order.status_code == 422

        # 5. Delete credentials
        del_res = client.delete("/api/v1/exchange/credentials/binance_spot")
        assert del_res.status_code == 200
