"""
Authentic CCXT Exchange Execution Engine & Hybrid Paper/Live Routing for Kuantra Terminal.
Directly routes orders to Binance Spot, Binance USDⓈ-M Futures, and OKX REST APIs.
Enforces authentic credential decryption, pre-execution risk checks, and automatic OLTP/OLAP sync.
"""

import time
import logging
import math
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

import ccxt
from app.services.exchange.credentials_manager import exchange_credentials_manager
from app.quant.risk_guard import risk_guard
from app.db.sqlite_driver import sqlite_driver
from app.db.sync_pipeline import sync_pipeline
from app.services.settings_service import settings_service

logger = logging.getLogger("ccxt_engine")


class CCXTExecutionEngine:
    """Universal multi-venue exchange execution engine with Paper & Live execution modes."""

    EXCHANGE_CLASS_MAP = {
        "binance_spot": ccxt.binance,
        "binance_futures": ccxt.binanceusdm,
        "okx": ccxt.okx,
    }

    def __init__(self):
        self._cached_clients: Dict[str, ccxt.Exchange] = {}

    @classmethod
    def format_symbol_for_ccxt(cls, symbol: str, exchange_id: str) -> str:
        """Standardizes ticker symbol to CCXT market pair notation (e.g. BTC/USDT or BTC/USDT:USDT)."""
        clean = symbol.upper().replace("/", "").replace("_", "").replace("-", "").strip()
        if clean.endswith("USDT"):
            base = clean[:-4]
            if exchange_id == "binance_futures":
                return f"{base}/USDT:USDT"
            return f"{base}/USDT"
        if clean.endswith("USD"):
            base = clean[:-3]
            return f"{base}/USD"
        return clean

    def get_client(self, exchange_id: str) -> ccxt.Exchange:
        """Instantiates authenticated CCXT exchange client from encrypted SQLite store."""
        exchange_id = exchange_id.lower().strip()
        if exchange_id not in self.EXCHANGE_CLASS_MAP:
            raise ValueError(f"Unsupported exchange '{exchange_id}'. Supported: {list(self.EXCHANGE_CLASS_MAP.keys())}")

        creds = exchange_credentials_manager.get_decrypted_credentials(exchange_id)
        if not creds or not creds.get("api_key") or not creds.get("api_secret"):
            raise ValueError(
                f"Missing API credentials for '{exchange_id}'. "
                "Please configure and save your API Key & Secret in Settings."
            )

        exchange_class = self.EXCHANGE_CLASS_MAP[exchange_id]
        config: Dict[str, Any] = {
            "apiKey": creds["api_key"].strip(),
            "secret": creds["api_secret"].strip(),
            "enableRateLimit": True,
            "timeout": 15000,
        }
        if creds.get("passphrase"):
            config["password"] = creds["passphrase"].strip()

        client = exchange_class(config)
        if creds.get("is_testnet"):
            client.set_sandbox_mode(True)

        return client

    def sync_exchange_balances(self, exchange_id: str = "binance_futures") -> Dict[str, Any]:
        """Queries live wallet equity and available free margin from exchange."""
        exchange_id = exchange_id.lower().strip()
        try:
            client = self.get_client(exchange_id)
            raw_balance = client.fetch_balance()
            
            free_usdt = float(raw_balance.get("free", {}).get("USDT", 0.0) or raw_balance.get("free", {}).get("USD", 0.0) or 0.0)
            total_usdt = float(raw_balance.get("total", {}).get("USDT", 0.0) or raw_balance.get("total", {}).get("USD", 0.0) or 0.0)
            used_margin = float(raw_balance.get("used", {}).get("USDT", 0.0) or 0.0)

            # Store in settings as cached live balance
            settings_service.update_settings({
                "last_synced_exchange": exchange_id,
                "last_synced_balance": total_usdt,
                "last_synced_free_balance": free_usdt
            })

            return {
                "success": True,
                "exchange_id": exchange_id,
                "free_quote": free_usdt,
                "total_equity": total_usdt,
                "used_margin": used_margin,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            logger.error(f"[CCXT-BALANCE] Failed to sync balances from '{exchange_id}': {e}")
            return {
                "success": False,
                "exchange_id": exchange_id,
                "error": str(e)
            }

    def create_order(
        self,
        symbol: str,
        side: str,
        order_type: str = "MARKET",
        qty: float = 1.0,
        price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        exchange_id: str = "binance_futures",
        mode: str = "PAPER",
        notes: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Dispatches order with Pre-Execution Risk Gatekeeper inspection:
        - In PAPER mode: Simulates local execution with internal fills.
        - In LIVE mode: Dispatches genuine REST order via CCXT to exchange.
        """
        exchange_id = exchange_id.lower().strip()
        mode = mode.upper().strip()
        side = side.upper().strip()
        order_type = order_type.upper().strip()
        symbol = symbol.upper().strip()

        if mode == "PAPER":
            try:
                paper_price = float(price)
            except (TypeError, ValueError):
                paper_price = None
            if paper_price is None or not math.isfinite(paper_price) or paper_price <= 0:
                return {
                    "success": False,
                    "status": "REJECTED",
                    "reason": "ORDER_REJECTED_PRICE_UNAVAILABLE: Paper execution requires a finite positive price.",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

        order_payload = {
            "symbol": symbol,
            "side": side,
            "order_type": order_type,
            "qty": float(qty),
            "price": float(price or 0.0),
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "exchange": exchange_id,
            "mode": mode
        }

        # 1. Pre-Execution Risk Gatekeeper Inspection
        is_approved, risk_reason, risk_meta = risk_guard.validate_pre_execution_risk(order_payload)
        if not is_approved:
            logger.warning(f"[CCXT-ENGINE] Order BLOCKED by Risk Guard: {risk_reason}")
            return {
                "success": False,
                "status": "REJECTED",
                "reason": risk_reason,
                "risk_metadata": risk_meta,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

        now_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # 2. PAPER EXECUTION SANDBOX
        if mode == "PAPER":
            order_id = f"PAPER-{exchange_id[:3].upper()}-{int(time.time()*1000)}"
            fill_price = paper_price
            
            trade_record = {
                "id": order_id,
                "symbol": symbol,
                "side": side,
                "entry_price": fill_price,
                "exit_price": None,
                "qty": qty,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "entry_time": now_ts,
                "exit_time": None,
                "status": "OPEN",
                "pnl": 0.0,
                "r_multiple": None,
                "commission": 0.0,
                "notes": notes or f"Paper Mode ({exchange_id})"
            }

            saved = sync_pipeline.record_and_sync_trade(trade_record)
            logger.info(f"[CCXT-ENGINE] Paper simulated order logged: {order_id} ({side} {qty} {symbol} @ ${fill_price})")

            return {
                "success": True,
                "mode": "PAPER",
                "status": "FILLED",
                "order_id": order_id,
                "exchange": "BINANCE" if "BINANCE" in exchange_id.upper() else exchange_id.upper(),
                "symbol": symbol,
                "side": side,
                "qty": qty,
                "price": fill_price,
                "trade": saved,
                "risk_metadata": risk_meta,
                "timestamp": now_ts
            }

        # 3. LIVE CCXT EXCHANGE EXECUTION
        try:
            client = self.get_client(exchange_id)
            ccxt_symbol = self.format_symbol_for_ccxt(symbol, exchange_id)
            order_params = params.copy() if params else {}

            if stop_loss:
                order_params["stopLoss"] = {"price": float(stop_loss)}
            if take_profit:
                order_params["takeProfit"] = {"price": float(take_profit)}

            logger.info(f"[CCXT-ENGINE] Dispatching LIVE {order_type} {side} {qty} {ccxt_symbol} to {exchange_id}...")
            
            raw_order = client.create_order(
                symbol=ccxt_symbol,
                type=order_type.lower(),
                side=side.lower(),
                amount=qty,
                price=price if order_type == "LIMIT" else None,
                params=order_params
            )

            order_id = str(raw_order.get("id") or f"LIVE-{int(time.time()*1000)}")
            fill_price = float(raw_order.get("price") or raw_order.get("average") or price or 0.0)
            order_status = str(raw_order.get("status") or "OPEN").upper()

            trade_record = {
                "id": f"EXCH-{order_id}",
                "symbol": symbol,
                "side": side,
                "entry_price": fill_price,
                "exit_price": None,
                "qty": qty,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "entry_time": now_ts,
                "exit_time": None,
                "status": "OPEN" if order_status in ("OPEN", "NEW") else "CLOSED",
                "pnl": 0.0,
                "r_multiple": None,
                "commission": float(raw_order.get("fee", {}).get("cost", 0.0) or 0.0),
                "notes": notes or f"Live Execution #{order_id} on {exchange_id}"
            }

            saved = sync_pipeline.record_and_sync_trade(trade_record)
            logger.info(f"[CCXT-ENGINE] Live order placed on {exchange_id}: ID {order_id}, Status: {order_status}")

            return {
                "success": True,
                "mode": "LIVE",
                "status": order_status,
                "order_id": order_id,
                "exchange": "BINANCE" if "BINANCE" in exchange_id.upper() else exchange_id.upper(),
                "symbol": symbol,
                "side": side,
                "qty": qty,
                "price": fill_price,
                "raw_order": raw_order,
                "trade": saved,
                "risk_metadata": risk_meta,
                "timestamp": now_ts
            }

        except ccxt.AuthenticationError as e:
            logger.error(f"[CCXT-ENGINE] Live Order Authentication Error: {e}")
            return {
                "success": False,
                "status": "AUTHENTICATION_FAILED",
                "reason": f"Exchange API authentication rejected: {str(e)}",
                "timestamp": now_ts
            }
        except ccxt.InsufficientFunds as e:
            logger.warning(f"[CCXT-ENGINE] Insufficient Funds on {exchange_id}: {e}")
            return {
                "success": False,
                "status": "INSUFFICIENT_FUNDS",
                "reason": f"Insufficient margin or balance on {exchange_id}: {str(e)}",
                "timestamp": now_ts
            }
        except Exception as e:
            logger.error(f"[CCXT-ENGINE] Live Execution Error: {e}")
            return {
                "success": False,
                "status": "EXECUTION_ERROR",
                "reason": str(e),
                "timestamp": now_ts
            }

    def fetch_open_orders(self, exchange_id: str = "binance_futures", symbol: Optional[str] = None, mode: str = "PAPER") -> List[Dict[str, Any]]:
        """Retrieves active open orders from exchange or local paper database."""
        if mode.upper() == "PAPER":
            return sqlite_driver.get_open_trades()

        try:
            client = self.get_client(exchange_id)
            ccxt_symbol = self.format_symbol_for_ccxt(symbol, exchange_id) if symbol else None
            return client.fetch_open_orders(symbol=ccxt_symbol)
        except Exception as e:
            logger.error(f"[CCXT-ORDERS] Error fetching open orders from {exchange_id}: {e}")
            return []

    def cancel_order(self, order_id: str, symbol: Optional[str] = None, exchange_id: str = "binance_futures", mode: str = "PAPER") -> Dict[str, Any]:
        """Cancels open order on exchange or marks as canceled in local paper journal."""
        if mode.upper() == "PAPER":
            sqlite_driver.update_trade(order_id, {"status": "CANCELED"})
            return {"success": True, "order_id": order_id, "status": "CANCELED", "mode": "PAPER"}

        try:
            client = self.get_client(exchange_id)
            ccxt_symbol = self.format_symbol_for_ccxt(symbol, exchange_id) if symbol else None
            res = client.cancel_order(order_id, symbol=ccxt_symbol)
            sqlite_driver.update_trade(f"EXCH-{order_id}", {"status": "CANCELED"})
            return {"success": True, "order_id": order_id, "status": "CANCELED", "raw": res, "mode": "LIVE"}
        except Exception as e:
            logger.error(f"[CCXT-CANCEL] Failed to cancel order {order_id} on {exchange_id}: {e}")
            return {"success": False, "order_id": order_id, "error": str(e)}


ccxt_execution_engine = CCXTExecutionEngine()
