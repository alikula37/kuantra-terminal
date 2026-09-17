"""Position sizing and return separation for journal trades.

The journal only knows what the user declared: quantity, entry price and an
optional leverage.  It never queries an exchange, so it must not present a
liquidation price, a verified margin requirement or a contract multiplier as
fact.  This module keeps the three return layers explicitly separate:

* ``price_return_pct`` — raw direction-adjusted price move, no leverage.
* ``position_return_pct`` — gross/net profit divided by the position notional.
* ``margin_return_pct`` — profit divided by the estimated margin, which is the
  only layer where the declared leverage multiplies the result.

Price profit itself is ``(exit - entry) * qty`` and is never multiplied by
leverage.

Monetary amounts are produced only under an explicit user quantity-unit
contract (``qty_unit=BASE``), which the journal labels as a user declaration.
A client-supplied provider label or a symbol suffix such as ``USD`` is never
verification: the backend cannot prove that the instrument exists, is the same
product, or uses base-unit quantity.  Until a server-verified instrument
catalog exists, price discovery alone must not enable monetary math.
Unverified amounts return ``None`` with an explicit
``CONTRACT_SIZE_UNVERIFIED`` reason instead of a ``price * qty`` figure that
could be off by an unknown multiplier.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Optional

# Quote suffixes only label the quote currency for display.  They do not
# establish that the quantity is the base unit of a listed instrument.
_KNOWN_QUOTE_SUFFIXES = (
    "USDT",
    "USDC",
    "BUSD",
    "FDUSD",
    "USD",
    "EUR",
    "TRY",
    "BTC",
    "ETH",
)
_MACRO_SYMBOLS = frozenset(
    {
        "XAUUSD",
        "XAUUSD=X",
        "GOLD",
        "XAGUSD",
        "XAGUSD=X",
        "XPTUSD",
        "XPDUSD",
        "WTIUSD",
        "BRENTUSD",
        "USOIL",
        "UKOIL",
        "NATGASUSD",
        "NGUSD",
        "SPXUSD",
        "NASUSD",
        "US30",
        "GER40",
        "DAX40",
    }
)
_PROVIDER_SEPARATORS = ("=", "^", "/", ":", " ")

# Quotes considered USD (or USD-pegged) for exact position-value math.  Other
# quotes still produce monetary figures from the USD position value, but the
# result is labeled approximate instead of silently treated as exact.
_USD_PEGGED_QUOTES = frozenset({"USD", "USDT", "USDC", "BUSD", "FDUSD", "TUSD"})


def classify_instrument(symbol: str) -> Dict[str, Any]:
    """Classify an instrument for display only (kind/base/quote).

    ``contract_size`` is always ``UNVERIFIED`` here; use
    :func:`instrument_unit_basis` with the recorded evidence to decide whether
    monetary math is allowed.
    """

    raw = str(symbol or "").strip().upper()
    if raw in _MACRO_SYMBOLS:
        return {
            "kind": "MACRO_OR_COMMODITY",
            "base": raw,
            "quote": "UNSPECIFIED",
            "contract_size": "UNVERIFIED",
        }
    if any(separator in raw for separator in _PROVIDER_SEPARATORS):
        return {
            "kind": "GENERIC",
            "base": raw,
            "quote": "UNSPECIFIED",
            "contract_size": "UNVERIFIED",
        }
    for suffix in _KNOWN_QUOTE_SUFFIXES:
        if len(raw) > len(suffix) and raw.endswith(suffix):
            return {
                "kind": "CRYPTO_PAIR",
                "base": raw[: -len(suffix)],
                "quote": suffix,
                "contract_size": "UNVERIFIED",
            }
    return {
        "kind": "GENERIC",
        "base": raw,
        "quote": "UNSPECIFIED",
        "contract_size": "UNVERIFIED",
    }


def instrument_unit_basis(
    symbol: str,
    *,
    qty_unit: Optional[str] = None,
    server_verified: bool = False,
) -> Dict[str, Any]:
    """Return the unit basis plus whether monetary math is allowed.

    Accepted bases:

    * ``server_verified`` — the backend itself confirmed the symbol in the
      provider's public instrument metadata (spot, base-unit quantity);
    * an explicit user ``qty_unit=BASE`` declaration; or
    * an explicit user ``qty_unit=USD`` declaration — ``qty`` is then the
      position value in USD, which needs no contract-size verification.

    Client-supplied provider labels and symbol suffixes are never verification.
    """

    identity = classify_instrument(symbol)
    declared = str(qty_unit or "UNKNOWN").strip().upper()
    if declared == "USD":
        verification = "EXPLICIT_USD_VALUE"
        source = "USER_DECLARATION"
        contract_size = "USD_NOTIONAL"
    elif declared == "BASE":
        verification = "EXPLICIT_QTY_UNIT"
        source = "USER_DECLARATION"
        contract_size = "BASE_UNIT"
    elif server_verified:
        verification = "PROVIDER_CATALOG"
        source = "PROVIDER_CATALOG"
        contract_size = "BASE_UNIT"
    else:
        verification = "NONE"
        source = "NONE"
        contract_size = "UNVERIFIED"
    return {
        **identity,
        "contract_size": contract_size,
        "verification": verification,
        "verification_source": source,
        "qty_unit": declared if declared in {"BASE", "USD"} else "UNKNOWN",
    }


def monetary_basis(contract_size: str) -> Dict[str, Optional[str]]:
    """Explicit monetary-calculation status for one instrument."""

    if contract_size in {"BASE_UNIT", "USD_NOTIONAL"}:
        return {"status": "READY", "reason": None}
    return {"status": "UNAVAILABLE", "reason": "CONTRACT_SIZE_UNVERIFIED"}


def _finite(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def position_summary(
    *,
    symbol: str,
    position_type: str,
    side: str,
    entry_price: Any,
    qty: Any,
    leverage: Any = None,
    exit_price: Any = None,
    commission: Any = None,
    size_input_mode: str = "QTY",
    qty_unit: Optional[str] = None,
    server_verified: bool = False,
) -> Dict[str, Any]:
    """Return a labeled sizing/return summary for one trade.

    Unknown inputs produce ``None`` values with an explicit reason instead of a
    synthetic zero.  No liquidation or exchange-margin claim is produced, and
    no monetary figure is produced at all without an explicit base-unit
    declaration.
    """

    instrument = instrument_unit_basis(
        symbol,
        qty_unit=qty_unit,
        server_verified=server_verified,
    )
    entry = _finite(entry_price)
    quantity = _finite(qty)
    exit_value = _finite(exit_price)
    declared = _finite(leverage)
    if declared is not None and declared <= 0:
        declared = None
    normalized_type = str(position_type or "UNKNOWN").upper()
    normalized_side = str(side or "").upper()
    long = normalized_side in {"BUY", "LONG"}
    warnings = []
    monetary = monetary_basis(instrument["contract_size"])
    monetary_ready = monetary["status"] == "READY"
    usd_notional = instrument["contract_size"] == "USD_NOTIONAL"

    if instrument["contract_size"] == "UNVERIFIED":
        warnings.append("CONTRACT_SIZE_UNVERIFIED")
    if (usd_notional and instrument["kind"] == "CRYPTO_PAIR"
            and instrument["quote"] not in _USD_PEGGED_QUOTES):
        # The position value is in USD but the price series is not; the money
        # figure is an explicit approximation instead of silent precision.
        warnings.append("QUOTE_NOT_USD_APPROXIMATE")

    if normalized_type == "SPOT":
        leverage_value: Optional[float] = 1.0
        leverage_source = "SPOT_IMPLIED"
    elif declared is not None:
        leverage_value = declared
        leverage_source = "USER_DECLARED"
    else:
        leverage_value = None
        leverage_source = "NOT_DECLARED"
        warnings.append("LEVERAGE_NOT_DECLARED")

    notional: Optional[float] = None
    margin: Optional[float] = None
    margin_source = "UNKNOWN"
    if monetary_ready and quantity is not None:
        if usd_notional:
            # ``qty`` carries the declared position value in USD.
            notional = quantity
        elif entry is not None:
            notional = entry * quantity
    if notional is not None:
        if normalized_type == "SPOT":
            margin = notional
            margin_source = "SPOT_FULL_PAYMENT"
        elif leverage_value is not None:
            margin = notional / leverage_value
            margin_source = "ESTIMATED_FROM_DECLARED_LEVERAGE"
    elif not monetary_ready:
        margin_source = "UNVERIFIED_CONTRACT_SIZE"

    fees_recorded = commission is not None and _finite(commission) not in (None, 0.0)
    fee_basis = "RECORDED" if fees_recorded else "UNKNOWN"
    if not fees_recorded:
        warnings.append("FEES_UNKNOWN")

    result: Dict[str, Any] = {
        "symbol": str(symbol or "").strip().upper(),
        "position_type": normalized_type,
        "instrument": instrument,
        "size_input_mode": str(size_input_mode or "QTY").upper(),
        "monetary_calculation": monetary,
        "quantity": {
            "value": quantity,
            "unit": "USD" if usd_notional else ("BASE" if instrument["contract_size"] == "BASE_UNIT" else "UNKNOWN"),
            "source": "USER_DECLARED",
        },
        "leverage": {"value": leverage_value, "source": leverage_source},
        "notional": {
            "value": notional,
            "currency": "USD" if usd_notional else (
                instrument["quote"] if instrument["kind"] == "CRYPTO_PAIR" else "UNSPECIFIED"),
            "basis": "USD_POSITION_VALUE" if usd_notional else "ENTRY_PRICE_TIMES_QUANTITY",
            "source": "COMPUTED_FROM_DECLARED_INPUTS" if monetary_ready else "UNVERIFIED_CONTRACT_SIZE",
        },
        "margin_estimate": {"value": margin, "source": margin_source},
        "fee_basis": fee_basis,
        "warnings": warnings,
    }

    price_return: Optional[float] = None
    if entry is not None and entry > 0 and exit_value is not None:
        direction = 1.0 if long else -1.0
        price_return = direction * (exit_value - entry) / entry

    if not monetary_ready:
        # The percentage move is unit-free and remains informative; every
        # monetary figure is withheld with an explicit reason.
        result["returns"] = {
            "price_return_pct": price_return * 100.0 if price_return is not None else None,
            "gross_pnl": None,
            "position_return_pct_gross": None,
            "position_return_pct_net": None,
            "margin_return_pct_gross": None,
            "margin_return_pct_net": None,
            "monetary_basis": monetary,
        }
        return result

    if entry is None or quantity is None or exit_value is None or entry <= 0:
        result["returns"] = None
        return result

    direction = 1.0 if long else -1.0
    if usd_notional:
        # Position value math: PnL = direction x price-return x USD value.
        gross_pnl = direction * (exit_value - entry) / entry * quantity
    else:
        gross_pnl = direction * (exit_value - entry) * quantity
    returns: Dict[str, Any] = {
        "price_return_pct": price_return * 100.0 if price_return is not None else None,
        "gross_pnl": gross_pnl,
        "monetary_basis": monetary,
    }
    if notional not in (None, 0.0):
        returns["position_return_pct_gross"] = gross_pnl / notional * 100.0
        if fees_recorded:
            net_pnl = gross_pnl - float(commission)
            returns["position_return_pct_net"] = net_pnl / notional * 100.0
        if margin not in (None, 0.0):
            returns["margin_return_pct_gross"] = gross_pnl / margin * 100.0
            if fees_recorded:
                returns["margin_return_pct_net"] = (gross_pnl - float(commission)) / margin * 100.0
    result["returns"] = returns
    return result
