"""
Pre-Execution Risk Gatekeeper & Guardrail Engine for Kuantra Terminal.
Validates orders prior to exchange routing:
- Max Loss % Risk per Trade against Account Equity
- Stop-Loss Distance & Mathematical Sanity
- Free Quote/Base Balance Sufficiency
- Prop Firm Compliance Daily Drawdown Proximity Guard
"""

import logging
from typing import Dict, Any, Optional, Tuple
from app.services.compliance_engine import compliance_engine
from app.services.settings_service import settings_service

logger = logging.getLogger("risk_guard")


class RiskGuard:
    """Institutional pre-trade risk interception and sizing validator."""

    def __init__(self, default_max_risk_pct: float = 5.0):
        self.default_max_risk_pct = default_max_risk_pct

    def get_max_risk_pct(self) -> float:
        """Retrieves user-configured maximum risk percentage per trade from SQLite."""
        try:
            settings = settings_service.get_settings()
            if "max_risk_pct_per_trade" in settings and settings["max_risk_pct_per_trade"] is not None:
                return float(settings["max_risk_pct_per_trade"])
        except Exception:
            pass
        return self.default_max_risk_pct

    def validate_pre_execution_risk(
        self,
        order: Dict[str, Any],
        account_balance: Optional[float] = None,
        free_balance: Optional[float] = None
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Runs comprehensive pre-execution risk inspection:
        Returns (is_approved: bool, reason: str, metadata: dict)
        """
        symbol = str(order.get("symbol", "BTCUSDT")).upper()
        side = str(order.get("side", "BUY")).upper()
        qty = float(order.get("qty", 1.0))
        price = float(order.get("price", 0.0))
        stop_loss = float(order["stop_loss"]) if order.get("stop_loss") is not None else None
        take_profit = float(order["take_profit"]) if order.get("take_profit") is not None else None
        mode = str(order.get("mode", "PAPER")).upper()

        if price <= 0 or qty <= 0:
            return False, "INVALID_ORDER_PARAMETERS: Price and Qty must be strictly positive.", {
                "price": price,
                "qty": qty
            }

        # 1. Resolve Account Capital
        if account_balance is None or account_balance <= 0:
            try:
                settings = settings_service.get_settings()
                account_balance = float(settings.get("user_initial_balance") or 10000.0)
            except Exception:
                account_balance = 10000.0

        order_notional = price * qty
        max_allowed_risk_pct = self.get_max_risk_pct()
        max_allowed_risk_usd = (max_allowed_risk_pct / 100.0) * account_balance

        # 2. Stop-Loss Direction Sanity Check
        if stop_loss is not None:
            if side in ("BUY", "LONG") and stop_loss >= price:
                return False, f"INVALID_STOP_LOSS: For BUY/LONG orders, Stop-Loss (${stop_loss}) must be below Entry Price (${price}).", {
                    "entry_price": price,
                    "stop_loss": stop_loss,
                    "side": side
                }
            if side in ("SELL", "SHORT") and stop_loss <= price:
                return False, f"INVALID_STOP_LOSS: For SELL/SHORT orders, Stop-Loss (${stop_loss}) must be above Entry Price (${price}).", {
                    "entry_price": price,
                    "stop_loss": stop_loss,
                    "side": side
                }

            # Calculate actual dollar risk
            risk_per_unit = abs(price - stop_loss)
            total_dollar_risk = risk_per_unit * qty
            risk_pct_of_account = (total_dollar_risk / account_balance) * 100.0 if account_balance > 0 else 100.0

            # 3. Max Risk per Trade Enforcement
            if risk_pct_of_account > max_allowed_risk_pct:
                reason = (
                    f"ORDER_REJECTED_EXCESSIVE_RISK: Trade risk is {risk_pct_of_account:.2f}% (${total_dollar_risk:.2f}), "
                    f"exceeding maximum permitted risk threshold of {max_allowed_risk_pct:.1f}% (${max_allowed_risk_usd:.2f})."
                )
                logger.warning(f"[RISK-GUARD] {reason}")
                return False, reason, {
                    "total_dollar_risk": round(total_dollar_risk, 2),
                    "risk_pct": round(risk_pct_of_account, 2),
                    "max_allowed_risk_pct": max_allowed_risk_pct,
                    "max_allowed_risk_usd": round(max_allowed_risk_usd, 2),
                    "stage": "MAX_RISK_BREACH"
                }
        else:
            total_dollar_risk = order_notional * 0.05 # conservative 5% assumption if no SL
            risk_pct_of_account = (total_dollar_risk / account_balance) * 100.0 if account_balance > 0 else 0.0

        # 4. Prop Firm Compliance Drawdown Proximity Check
        compliance_eval = compliance_engine.evaluate_compliance()
        if compliance_eval.get("status") == "BREACHED":
            return False, "ORDER_REJECTED_PROP_FIRM_BREACH: Prop firm maximum or daily drawdown has been breached.", {
                "compliance": compliance_eval,
                "stage": "PROP_FIRM_BREACH"
            }

        # Check if account is within 0.5% margin of max daily drawdown breach
        daily_loss_pct = compliance_eval.get("daily_loss_pct", 0.0)
        daily_loss_limit = compliance_eval.get("max_daily_loss_limit_pct", 5.0)
        if daily_loss_pct > (daily_loss_limit - 0.5):
            reason = (
                f"ORDER_REJECTED_NEAR_DRAWDOWN_LIMIT: Current daily loss ({daily_loss_pct:.2f}%) "
                f"is within 0.5% of max daily drawdown limit ({daily_loss_limit:.1f}%)."
            )
            logger.warning(f"[RISK-GUARD] {reason}")
            return False, reason, {
                "daily_loss_pct": daily_loss_pct,
                "daily_loss_limit": daily_loss_limit,
                "stage": "NEAR_DRAWDOWN_BREACH"
            }

        # 5. Free Balance Check (In Live mode if free_balance is known)
        if mode == "LIVE" and free_balance is not None and free_balance > 0:
            if order_notional > free_balance * 1.05: # allow 5% margin tolerance for leverage
                reason = f"ORDER_REJECTED_INSUFFICIENT_BALANCE: Order value (${order_notional:.2f}) exceeds free balance (${free_balance:.2f})."
                logger.warning(f"[RISK-GUARD] {reason}")
                return False, reason, {
                    "order_notional": order_notional,
                    "free_balance": free_balance,
                    "stage": "INSUFFICIENT_BALANCE"
                }

        logger.info(
            f"[RISK-GUARD] Order Approved for {symbol} ({side} {qty} @ ${price}). "
            f"Risk: ${total_dollar_risk:.2f} ({risk_pct_of_account:.2f}% of ${account_balance:,.2f})."
        )

        return True, "RISK_VALIDATION_PASSED", {
            "order_notional": round(order_notional, 2),
            "dollar_risk": round(total_dollar_risk, 2),
            "risk_pct": round(risk_pct_of_account, 2),
            "account_balance": round(account_balance, 2),
            "max_allowed_risk_pct": max_allowed_risk_pct,
            "mode": mode,
            "stage": "CLEARED"
        }


risk_guard = RiskGuard()
