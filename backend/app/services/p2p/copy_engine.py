"""
Zero-Knowledge Copy-Trading Engine for Kuantra Terminal.
Enables Master Traders to broadcast cryptographically signed signals and Followers to scale positions dynamically based on local equity.
"""

import time
import json
import hashlib
import hmac
import logging
import os
from typing import Dict, Any, List, Optional
from app.services.p2p.mesh_node import p2p_mesh_node
from app.services.execution.order_router import order_router
from app.db.sqlite_driver import sqlite_driver

logger = logging.getLogger("copy_engine")

COPY_SIGNAL_SECRET_ENV = "KUANTRA_COPY_SIGNAL_SECRET"
_COPY_SIGNAL_FIELDS = (
    "signal_id", "master_node_id", "symbol", "side", "entry_price",
    "stop_loss", "take_profit", "risk_pct", "timestamp",
)


def _copy_signal_secret() -> str:
    return str(os.environ.get(COPY_SIGNAL_SECRET_ENV) or "").strip()


def copy_signal_secret_configured() -> bool:
    """True when an owner-configured shared secret can sign and verify copy signals."""
    return bool(_copy_signal_secret())


def _copy_signal_payload(signal: Dict[str, Any]) -> bytes:
    canonical = {field: signal.get(field) for field in _COPY_SIGNAL_FIELDS}
    return json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sign_copy_signal(signal: Dict[str, Any], secret: str) -> str:
    """Shared HMAC-SHA256 signing routine for master signals."""
    return hmac.new(secret.encode("utf-8"), _copy_signal_payload(signal), hashlib.sha256).hexdigest()

class ZeroKnowledgeCopyEngine:
    """Master signal publisher & Follower dynamic equity scaling copy executor."""

    def __init__(self):
        self.signal_history: List[Dict[str, Any]] = []
        try:
            init_bal = float(sqlite_driver.get_setting("user_initial_balance") or 0.0)
        except Exception:
            init_bal = 0.0
        self.follower_settings = {
            "is_auto_copy_enabled": True,
            "follower_equity": init_bal if init_bal > 0 else 10000.0,
            "max_risk_per_trade_pct": 2.0,
            "allowed_masters": ["12D3KooW-AlphaQuant", p2p_mesh_node.node_id]
        }

    def create_master_signal(
        self,
        symbol: str,
        side: str, # "BUY" | "SELL"
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        risk_pct: float = 1.0, # 1% account risk
        notes: str = ""
    ) -> Dict[str, Any]:
        """Constructs and cryptographically signs a Zero-Knowledge signal payload."""
        sig_id = f"SIG-{symbol.upper()}-{int(time.time() * 1000)}"
        t_now = time.time()

        raw_payload = f"{sig_id}:{symbol}:{side}:{entry_price}:{stop_loss}:{take_profit}:{risk_pct}:{t_now}"
        signature = hmac.new(p2p_mesh_node.privkey.encode(), raw_payload.encode(), hashlib.sha256).hexdigest()

        signal = {
            "signal_id": sig_id,
            "master_node_id": p2p_mesh_node.node_id,
            "master_pubkey": p2p_mesh_node.pubkey,
            "symbol": symbol.upper(),
            "side": side.upper(),
            "entry_price": round(entry_price, 2),
            "stop_loss": round(stop_loss, 2),
            "take_profit": round(take_profit, 2),
            "risk_pct": round(risk_pct, 2),
            "notes": notes,
            "signature": signature,
            "timestamp": t_now
        }

        # Broadcast across P2P Mesh
        secret = _copy_signal_secret()
        if secret:
            signal["signature"] = sign_copy_signal(signal, secret)
        p2p_mesh_node.broadcast_signal(signal)
        self.signal_history.append(signal)

        logger.info(f"[COPY MASTER] Created & broadcasted signal {sig_id} for {symbol}")
        return signal

    def verify_signal(self, signal: Dict[str, Any]) -> bool:
        """Verifies cryptographic signature integrity of received signal."""
        sig_id = signal.get("signal_id")
        symbol = signal.get("symbol")
        side = signal.get("side")
        entry_price = signal.get("entry_price")
        stop_loss = signal.get("stop_loss")
        take_profit = signal.get("take_profit")
        risk_pct = signal.get("risk_pct")
        t_val = signal.get("timestamp")
        signature = signal.get("signature")

        if not all([sig_id, symbol, side, entry_price, stop_loss, take_profit, signature]):
            return False

        secret = _copy_signal_secret()
        if not secret:
            # Fail closed: without the owner-configured secret, signature
            # verification is impossible and no signal may execute.
            return False
        expected = sign_copy_signal(signal, secret)
        try:
            return hmac.compare_digest(str(signature), expected)
        except Exception:
            return False

    def calculate_follower_lot_size(
        self,
        signal: Dict[str, Any],
        follower_equity: Optional[float] = None
    ) -> float:
        """
        Dynamic Proportional Equity Scaling:
        Risk $ = Follower Equity * (Risk % / 100)
        Risk Per Unit = |Entry Price - Stop Loss|
        Follower Lot Size = Risk $ / Risk Per Unit
        """
        equity = follower_equity or self.follower_settings["follower_equity"]
        risk_pct = min(signal.get("risk_pct", 1.0), self.follower_settings["max_risk_per_trade_pct"])

        entry_p = float(signal["entry_price"])
        sl_p = float(signal["stop_loss"])
        price_risk = abs(entry_p - sl_p)

        if price_risk <= 0:
            price_risk = entry_p * 0.01

        risk_dollars = equity * (risk_pct / 100.0)
        raw_qty = risk_dollars / price_risk

        # Clamp to realistic precision (e.g. 0.01 lots min)
        return round(max(0.01, min(100.0, raw_qty)), 2)

    def execute_copy_signal(
        self,
        signal: Dict[str, Any],
        follower_equity: Optional[float] = None,
        exchange: str = "BINANCE"
    ) -> Dict[str, Any]:
        """Verifies signature, computes local lot size, and routes order through Risk Interceptor."""
        if not self.verify_signal(signal):
            return {"status": "REJECTED", "reason": "INVALID_CRYPTOGRAPHIC_SIGNATURE"}

        lot_size = self.calculate_follower_lot_size(signal, follower_equity)

        order_payload = {
            "symbol": signal["symbol"],
            "side": signal["side"],
            "qty": lot_size,
            "price": signal["entry_price"],
            "stop_loss": signal["stop_loss"],
            "take_profit": signal["take_profit"],
            "exchange": exchange,
            "source": f"P2P_COPY_{signal['master_node_id']}"
        }

        # Dispatch through smart order router (which enforces tilt, biometrics, compliance)
        exec_res = order_router.route_order(order_payload)

        return {
            "copy_status": "PROCESSED",
            "signal_id": signal["signal_id"],
            "calculated_lot_size": lot_size,
            "router_execution": exec_res,
            "timestamp": time.time()
        }

    def get_signal_history(self) -> List[Dict[str, Any]]:
        """Returns recent broadcasted/received signals."""
        if not self.signal_history:
            # Provide sample initial signals
            self.create_master_signal(
                symbol="BTCUSDT",
                side="BUY",
                entry_price=64800.0,
                stop_loss=63900.0,
                take_profit=67500.0,
                risk_pct=1.0,
                notes="4H Bullish SFP rejection at key liquidity shelf"
            )
        return self.signal_history

copy_trading_engine = ZeroKnowledgeCopyEngine()
