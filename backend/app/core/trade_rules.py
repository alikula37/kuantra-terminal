"""Shared validation rules for journal trade entry and correction.

Reason codes are stable machine strings; the UI maps them to localized text.
Messages are English fallbacks only and never the primary user contract.
"""

from __future__ import annotations

import math
from typing import Any, Optional


class TradeRuleError(ValueError):
    def __init__(self, reason: str, message: str, *, field: Optional[str] = None):
        super().__init__(message)
        self.reason = reason
        self.field = field


def _finite(value: Any, *, field: str, reason: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise TradeRuleError(reason, f"{field} must be numeric.", field=field) from exc
    if not math.isfinite(number):
        raise TradeRuleError(reason, f"{field} must be finite.", field=field)
    return number


def normalize_leverage(value: Any, position_type: str) -> Optional[float]:
    """Return the user-declared leverage or ``None`` when it does not apply.

    Leverage is journal metadata only; it never changes exchange settings and it
    never multiplies the price-derived profit of the position.
    """

    if value is None or value == "":
        return None
    number = _finite(value, field="leverage", reason="LEVERAGE_INVALID")
    normalized_type = str(position_type or "UNKNOWN").upper()
    if normalized_type == "SPOT":
        if number != 1:
            raise TradeRuleError(
                "LEVERAGE_SPOT_NOT_ALLOWED",
                "Spot purchases have no leverage.",
                field="leverage",
            )
        return None
    if number < 1 or number > 1000:
        raise TradeRuleError(
            "LEVERAGE_OUT_OF_RANGE",
            "Declared leverage must be between 1 and 1000.",
            field="leverage",
        )
    return number


def validate_stop_and_targets(
    *,
    entry_price: float,
    side: str,
    stop_loss: Any,
    take_profit: Any,
) -> tuple[Optional[float], Optional[float]]:
    long = str(side or "").upper() in {"BUY", "LONG"}
    stop_value: Optional[float] = None
    target_value: Optional[float] = None
    if stop_loss not in (None, ""):
        stop_value = _finite(stop_loss, field="stop_loss", reason="STOP_INVALID")
        if stop_value <= 0 or (long and stop_value >= entry_price) or (not long and stop_value <= entry_price):
            raise TradeRuleError(
                "STOP_WRONG_SIDE",
                "The stop loss must sit on the loss side of the entry price.",
                field="stop_loss",
            )
    if take_profit not in (None, ""):
        target_value = _finite(take_profit, field="take_profit", reason="TARGET_INVALID")
        if target_value <= 0 or (long and target_value <= entry_price) or (not long and target_value >= entry_price):
            raise TradeRuleError(
                "TARGET_WRONG_SIDE",
                "The take profit must sit on the profit side of the entry price.",
                field="take_profit",
            )
    return stop_value, target_value


def validate_notes(value: Any) -> str:
    text = "" if value is None else str(value)
    if any(ord(character) < 32 for character in text):
        raise TradeRuleError("NOTES_INVALID", "Notes cannot contain control characters.", field="notes")
    if len(text) > 2000:
        raise TradeRuleError("NOTES_TOO_LONG", "Notes are limited to 2000 characters.", field="notes")
    return text
