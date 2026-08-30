import hmac
import hashlib
import json
import time
import pytest
from app.websocket.tv_sync import tv_sync_manager
from app.api.webhook_tv import verify_hmac_signature, verify_passphrase, WEBHOOK_SECRET_KEY
from app.services.data_adapters.twelvedata_adapter import twelvedata_adapter
from app.services.data_adapters.polygon_adapter import polygon_adapter
from app.services.data_adapters.mt5_adapter import mt5_adapter
from app.services.data_adapters.multi_asset_manager import multi_asset_manager
from app.services.execution.order_router import order_router
from app.services.execution.risk_interceptor import risk_interceptor

class TestPhase11TradingViewAndMultiAsset:
    """Test suite for TradingView Chrome Extension sync, Webhook HMAC, Multi-Asset Adapters, and Risk Routing."""

    @pytest.mark.asyncio
    async def test_tv_companion_websocket_sync(self):
        # Update symbol via simulated extension message
        await tv_sync_manager.handle_extension_message({
            "symbol": "XAUUSD",
            "timeframe": "1h",
            "exchange": "OANDA"
        })

        st = tv_sync_manager.get_sync_state()
        assert st["active_symbol"] == "XAUUSD"
        assert st["active_timeframe"] == "1h"
        assert st["active_exchange"] == "OANDA"
        assert st["last_sync_timestamp"] > 0

    def test_hmac_sha256_webhook_signature_and_passphrase(self):
        payload = json.dumps({
            "symbol": "BTCUSDT",
            "action": "BUY",
            "price": 64900.0,
            "stop_loss": 64000.0,
            "take_profit": 67000.0
        }).encode("utf-8")

        # Valid HMAC signature
        valid_sig = hmac.new(WEBHOOK_SECRET_KEY.encode("utf-8"), payload, hashlib.sha256).hexdigest()
        assert verify_hmac_signature(payload, valid_sig) is True
        assert verify_hmac_signature(payload, "invalid_mock_signature_hex") is False
        assert verify_hmac_signature(payload, None) is False

        # Passphrase verification
        assert verify_passphrase(WEBHOOK_SECRET_KEY) is True
        assert verify_passphrase("wrong_passphrase") is False

    def test_multi_asset_data_adapters_normalization(self):
        # 1. TwelveData
        tick = twelvedata_adapter.parse_tick({"symbol": "EUR/USD", "price": 1.0875, "bid": 1.0874, "ask": 1.0876})
        assert tick["symbol"] == "EURUSD"
        assert tick["price"] == 1.0875
        assert tick["source"] == "TWELVEDATA"

        # 2. Polygon.io
        trade = polygon_adapter.parse_trade({"sym": "NVDA", "p": 129.20, "s": 250})
        assert trade["symbol"] == "NVDA"
        assert trade["price"] == 129.20
        assert trade["size"] == 250
        assert trade["source"] == "POLYGON_IO"

        # 3. MetaTrader 5
        quote = mt5_adapter.get_symbol_quote("XAUUSD")
        assert quote["symbol"] == "XAUUSD"
        assert quote["bid"] > 0
        assert quote["source"] == "METATRADER_5"

        statuses = multi_asset_manager.get_all_statuses()
        assert "twelvedata" in statuses
        assert "polygon" in statuses
        assert "mt5" in statuses

    def test_order_routing_and_execution(self):
        # Route order to Binance
        bin_order = order_router.route_order({
            "symbol": "BTCUSDT",
            "side": "BUY",
            "qty": 0.25,
            "price": 64500.0,
            "exchange": "BINANCE",
            "stop_loss": 63800.0,
            "take_profit": 66000.0
        })
        assert bin_order["status"] == "EXECUTED"
        assert bin_order["order"]["exchange"] == "BINANCE"
        assert bin_order["order"]["status"] == "FILLED"

        # Route order to OKX
        okx_order = order_router.route_order({
            "symbol": "ETHUSDT",
            "side": "SELL",
            "qty": 1.5,
            "price": 3250.0,
            "exchange": "OKX"
        })
        assert okx_order["status"] == "EXECUTED"
        assert okx_order["order"]["exchange"] == "OKX"

    def test_behavioral_tilt_and_prop_shield_guardrail_blocking(self):
        # 1. Normal execution with calm tilt
        risk_interceptor.max_allowed_tilt_score = 75.0
        approved_order = order_router.route_order({
            "symbol": "SOLUSDT",
            "side": "BUY",
            "qty": 10.0,
            "price": 145.0
        })
        assert approved_order["status"] == "EXECUTED"

        # 2. Blocked execution when Tilt Guardrail triggers
        risk_interceptor.max_allowed_tilt_score = -5.0 # Force threshold breach
        blocked_order = order_router.route_order({
            "symbol": "SOLUSDT",
            "side": "BUY",
            "qty": 10.0,
            "price": 145.0
        })
        assert blocked_order["status"] == "REJECTED_RISK_GUARDRAIL"
        assert "ORDER_BLOCKED_HIGH_TILT" in blocked_order["reason"]

        # Reset threshold to default
        risk_interceptor.max_allowed_tilt_score = 75.0