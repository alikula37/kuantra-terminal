"""
Pre-Execution Risk Gatekeeper & Guardrail Engine for Kuantra Terminal.

The guard remains the deterministic authority for an order decision. Every
decision is tagged with an immutable risk-policy snapshot and appended to the
canonical evidence ledger before it is returned to an execution caller.
"""

import logging
import math
from typing import Dict, Any, Optional, Tuple

from app.services.compliance_engine import compliance_engine
from app.services.settings_service import settings_service
from app.services.risk_policy_service import risk_policy_service

logger = logging.getLogger("risk_guard")


class RiskGuard:
    """Institutional pre-trade risk interception and sizing validator."""

    def __init__(self, default_max_risk_pct: float = 5.0, policy_id: Optional[str] = None):
        self.default_max_risk_pct = float(default_max_risk_pct)
        self.policy_id = policy_id or (
            "default-risk-policy"
            if self.default_max_risk_pct == 5.0
            else f"risk-guard-{self.default_max_risk_pct:g}"
        )

    def _get_policy(self) -> Dict[str, Any]:
        """Resolve a stable policy identity without changing legacy defaults."""
        if self.policy_id == risk_policy_service.DEFAULT_POLICY_ID:
            policy = risk_policy_service.ensure_default_policy(self.default_max_risk_pct)
            # Existing settings UI writes this key directly. Convert a changed
            # value into an explicit new policy version instead of silently
            # changing the meaning of an already-recorded decision.
            configured = settings_service.get_setting("max_risk_pct_per_trade", None)
            if configured is not None:
                try:
                    configured_value = float(configured)
                    if configured_value != float(policy["max_risk_pct_per_trade"]):
                        policy = risk_policy_service.create_policy(
                            self.policy_id,
                            configured_value,
                            daily_loss_guard_band_pct=float(policy.get("daily_loss_guard_band_pct", 0.5)),
                            description="Default deterministic pre-trade risk policy",
                        )
                except (TypeError, ValueError):
                    # Invalid legacy settings are ignored here; the existing
                    # active snapshot remains the safe source of truth.
                    pass
            return policy
        return risk_policy_service.ensure_policy(self.policy_id, self.default_max_risk_pct)

    def get_max_risk_pct(self) -> float:
        """Retrieve the active, versioned maximum risk percentage."""
        try:
            return float(self._get_policy()["max_risk_pct_per_trade"])
        except Exception:
            # Keep a conservative legacy fallback for non-gating callers.
            try:
                settings = settings_service.get_settings()
                if settings.get("max_risk_pct_per_trade") is not None:
                    return float(settings["max_risk_pct_per_trade"])
            except Exception:
                pass
            return self.default_max_risk_pct

    @staticmethod
    def _policy_metadata(policy: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "policy_id": policy.get("policy_id"),
            "policy_version": policy.get("version"),
            "policy_snapshot_sha256": policy.get("snapshot_sha256"),
        }

    def _decision(
        self,
        order: Dict[str, Any],
        policy: Dict[str, Any],
        approved: bool,
        reason: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """Attach policy identity and persist the decision before returning."""
        result_metadata = {**self._policy_metadata(policy), **(metadata or {})}
        try:
            event = risk_policy_service.record_evaluation(
                policy,
                order,
                approved=approved,
                reason=reason,
                metadata=result_metadata,
            )
            result_metadata["risk_event_id"] = event["event_id"]
            result_metadata["risk_event_created"] = bool(event.get("created"))
            return approved, reason, result_metadata
        except Exception as exc:
            # No order decision is trusted if its policy evidence cannot be
            # durably recorded. This is intentionally fail-closed.
            logger.error("[RISK-GUARD] Unable to persist risk decision evidence: %s", exc)
            result_metadata.update({"stage": "RISK_EVIDENCE_UNAVAILABLE", "evidence_error": str(exc)})
            return (
                False,
                "ORDER_REJECTED_RISK_EVIDENCE_UNAVAILABLE: Risk decision could not be durably recorded.",
                result_metadata,
            )

    def validate_pre_execution_risk(
        self,
        order: Dict[str, Any],
        account_balance: Optional[float] = None,
        free_balance: Optional[float] = None,
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Run comprehensive pre-execution risk inspection.

        Returns ``(is_approved, reason, metadata)``. The method does not
        submit orders; execution callers must still enforce their own mode and
        routing gates.
        """
        try:
            policy = self._get_policy()
        except Exception as exc:
            logger.error("[RISK-GUARD] Unable to load risk policy: %s", exc)
            return (
                False,
                "ORDER_REJECTED_RISK_POLICY_UNAVAILABLE: Risk policy could not be loaded.",
                {"stage": "RISK_POLICY_UNAVAILABLE", "evidence_error": str(exc)},
            )

        symbol = str(order.get("symbol", "BTCUSDT")).upper()
        side = str(order.get("side", "BUY")).upper()
        qty = float(order.get("qty", 1.0))
        price = float(order.get("price", 0.0))
        stop_loss = float(order["stop_loss"]) if order.get("stop_loss") is not None else None
        take_profit = float(order["take_profit"]) if order.get("take_profit") is not None else None
        mode = str(order.get("mode", "PAPER")).upper()

        if price <= 0 or qty <= 0:
            return self._decision(
                order,
                policy,
                False,
                "INVALID_ORDER_PARAMETERS: Price and Qty must be strictly positive.",
                {"price": price, "qty": qty},
            )

        # 1. Resolve Account Capital
        if account_balance is None or account_balance <= 0:
            try:
                settings = settings_service.get_settings()
                account_balance = float(settings.get("user_initial_balance") or 10000.0)
            except Exception:
                account_balance = 10000.0

        order_notional = price * qty
        max_allowed_risk_pct = float(policy["max_risk_pct_per_trade"])
        daily_loss_guard_band_pct = float(policy.get("daily_loss_guard_band_pct", 0.5))
        max_allowed_risk_usd = (max_allowed_risk_pct / 100.0) * account_balance

        # 2. Stop-Loss Direction Sanity Check
        if stop_loss is not None:
            if side in ("BUY", "LONG") and stop_loss >= price:
                return self._decision(
                    order,
                    policy,
                    False,
                    f"INVALID_STOP_LOSS: For BUY/LONG orders, Stop-Loss (${stop_loss}) must be below Entry Price (${price}).",
                    {"entry_price": price, "stop_loss": stop_loss, "side": side},
                )
            if side in ("SELL", "SHORT") and stop_loss <= price:
                return self._decision(
                    order,
                    policy,
                    False,
                    f"INVALID_STOP_LOSS: For SELL/SHORT orders, Stop-Loss (${stop_loss}) must be above Entry Price (${price}).",
                    {"entry_price": price, "stop_loss": stop_loss, "side": side},
                )

            risk_per_unit = abs(price - stop_loss)
            total_dollar_risk = risk_per_unit * qty
            risk_pct_of_account = (total_dollar_risk / account_balance) * 100.0 if account_balance > 0 else 100.0

            # 3. Max Risk per Trade Enforcement
            if risk_pct_of_account > max_allowed_risk_pct:
                reason = (
                    f"ORDER_REJECTED_EXCESSIVE_RISK: Trade risk is {risk_pct_of_account:.2f}% (${total_dollar_risk:.2f}), "
                    f"exceeding maximum permitted risk threshold of {max_allowed_risk_pct:.1f}% (${max_allowed_risk_usd:.2f})."
                )
                logger.warning("[RISK-GUARD] %s", reason)
                return self._decision(
                    order,
                    policy,
                    False,
                    reason,
                    {
                        "total_dollar_risk": round(total_dollar_risk, 2),
                        "risk_pct": round(risk_pct_of_account, 2),
                        "max_allowed_risk_pct": max_allowed_risk_pct,
                        "max_allowed_risk_usd": round(max_allowed_risk_usd, 2),
                        "stage": "MAX_RISK_BREACH",
                    },
                )
        else:
            total_dollar_risk = order_notional * 0.05
            risk_pct_of_account = (total_dollar_risk / account_balance) * 100.0 if account_balance > 0 else 0.0

        # 4. Prop Firm Compliance Drawdown Proximity Check
        compliance_eval = compliance_engine.evaluate_compliance()
        if compliance_eval.get("overall_status") == "BREACHED":
            return self._decision(
                order,
                policy,
                False,
                "ORDER_REJECTED_PROP_FIRM_BREACH: Prop firm maximum or daily drawdown has been breached.",
                {"compliance": compliance_eval, "stage": "PROP_FIRM_BREACH"},
            )

        # A missing or malformed compliance response must not silently bypass
        # this gate.
        try:
            daily_loss_pct = float(compliance_eval["daily_loss_pct_of_account"])
            daily_loss_limit = float(compliance_eval["daily_loss_limit_pct"])
        except (KeyError, TypeError, ValueError):
            return self._decision(
                order,
                policy,
                False,
                "ORDER_REJECTED_COMPLIANCE_DATA_UNAVAILABLE: Daily loss data is unavailable for risk validation.",
                {"compliance": compliance_eval, "stage": "COMPLIANCE_DATA_UNAVAILABLE"},
            )

        if (
            not math.isfinite(daily_loss_pct)
            or not math.isfinite(daily_loss_limit)
            or daily_loss_pct < 0
            or daily_loss_limit <= 0
        ):
            return self._decision(
                order,
                policy,
                False,
                "ORDER_REJECTED_COMPLIANCE_DATA_UNAVAILABLE: Daily loss data is invalid for risk validation.",
                {"compliance": compliance_eval, "stage": "COMPLIANCE_DATA_UNAVAILABLE"},
            )

        if daily_loss_pct >= (daily_loss_limit - daily_loss_guard_band_pct):
            reason = (
                f"ORDER_REJECTED_NEAR_DRAWDOWN_LIMIT: Current daily loss ({daily_loss_pct:.2f}%) "
                f"is within {daily_loss_guard_band_pct:g} percentage points of the daily loss limit ({daily_loss_limit:.1f}%)."
            )
            logger.warning("[RISK-GUARD] %s", reason)
            return self._decision(
                order,
                policy,
                False,
                reason,
                {
                    "daily_loss_pct": daily_loss_pct,
                    "daily_loss_limit": daily_loss_limit,
                    "stage": "NEAR_DRAWDOWN_BREACH",
                },
            )

        # 5. Free Balance Check (In Live mode if free_balance is known)
        if mode == "LIVE" and free_balance is not None and free_balance > 0:
            if order_notional > free_balance * 1.05:
                reason = f"ORDER_REJECTED_INSUFFICIENT_BALANCE: Order value (${order_notional:.2f}) exceeds free balance (${free_balance:.2f})."
                logger.warning("[RISK-GUARD] %s", reason)
                return self._decision(
                    order,
                    policy,
                    False,
                    reason,
                    {
                        "order_notional": order_notional,
                        "free_balance": free_balance,
                        "stage": "INSUFFICIENT_BALANCE",
                    },
                )

        logger.info(
            "[RISK-GUARD] Order Approved for %s (%s %s @ $%s). Risk: $%.2f (%.2f%% of $%s).",
            symbol,
            side,
            qty,
            price,
            total_dollar_risk,
            risk_pct_of_account,
            f"{account_balance:,.2f}",
        )

        return self._decision(
            order,
            policy,
            True,
            "RISK_VALIDATION_PASSED",
            {
                "order_notional": round(order_notional, 2),
                "dollar_risk": round(total_dollar_risk, 2),
                "risk_pct": round(risk_pct_of_account, 2),
                "account_balance": round(account_balance, 2),
                "max_allowed_risk_pct": max_allowed_risk_pct,
                "mode": mode,
                "stage": "CLEARED",
            },
        )


risk_guard = RiskGuard()
