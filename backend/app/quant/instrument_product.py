"""P1-WP43 independent spot-product consistency check (read-only, free sources).

The module is pure: it classifies the trade's declared provider symbol into a
product key, selects at most ONE independent same-product free-source
candidate, and compares closes aligned by identical bars or by UTC day within a
documented tolerance.  Futures and tokenized metals live under distinct keys
and can never satisfy a spot key; "CONSISTENT" only means one independent free
source agreed within the recorded tolerance on the recorded overlap — it is
never broker execution evidence and never a product verification by itself.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

MIN_OVERLAP_BARS = 10
METAL_TOLERANCE_PCT = 0.5
FX_TOLERANCE_PCT = 0.2
PRODUCT_NOTE = "NOT_BROKER_EXECUTION_EVIDENCE"
DAY_CLOSE_NOTE = "LAST_BAR_CLOSE_PER_UTC_DAY_LATEST_DAY_EXCLUDED"


@dataclass(frozen=True)
class ProductSource:
    provider: str
    symbol: str
    interval: str

    @property
    def intraday(self) -> bool:
        return self.interval != "1d"


@dataclass(frozen=True)
class ProductDefinition:
    key: str
    asset_class: str
    tolerance_pct: Optional[float]
    sources: Tuple[ProductSource, ...]


@dataclass(frozen=True)
class IndependentCandidate:
    provider: str
    symbol: str
    interval: str

    @property
    def intraday(self) -> bool:
        return self.interval != "1d"


def _source(provider: str, symbol: str, interval: str) -> ProductSource:
    return ProductSource(provider=provider, symbol=symbol, interval=interval)


_SPOT_DEFINITIONS: Tuple[ProductDefinition, ...] = (
    ProductDefinition(
        key="SPOT_METAL:XAU:USD", asset_class="SPOT_METAL", tolerance_pct=METAL_TOLERANCE_PCT,
        sources=(
            _source("biquote_public", "XAUUSD", "1m"),
            _source("yahoo_public", "XAUUSD=X", "1m"),
            _source("stooq_public", "xauusd", "1d"),
        ),
    ),
    ProductDefinition(
        key="SPOT_METAL:XAG:USD", asset_class="SPOT_METAL", tolerance_pct=METAL_TOLERANCE_PCT,
        sources=(
            _source("yahoo_public", "XAGUSD=X", "1m"),
            _source("stooq_public", "xagusd", "1d"),
        ),
    ),
)

_FX_PAIRS: Dict[str, Tuple[str, str]] = {
    "EURUSD": ("EURUSD=X", "eurusd"),
    "GBPUSD": ("GBPUSD=X", "gbpusd"),
    "USDJPY": ("JPY=X", "usdjpy"),
    "AUDUSD": ("AUDUSD=X", "audusd"),
    "USDCAD": ("CAD=X", "usdcad"),
    "USDCHF": ("CHF=X", "usdchf"),
}

_FX_DEFINITIONS: Tuple[ProductDefinition, ...] = tuple(
    ProductDefinition(
        key=f"FX:{pair[:3]}:{pair[3:]}", asset_class="FX", tolerance_pct=FX_TOLERANCE_PCT,
        sources=(
            _source("yahoo_public", yahoo_symbol, "1m"),
            _source("stooq_public", stooq_symbol, "1d"),
        ),
    )
    for pair, (yahoo_symbol, stooq_symbol) in _FX_PAIRS.items()
)

# Futures and tokens are recognized structurally so a spot key can never accept
# them; each carries a single source, so no independent check is ever possible.
_FUTURE_DEFINITIONS: Tuple[ProductDefinition, ...] = tuple(
    ProductDefinition(
        key=f"FUTURE:{name}", asset_class="FUTURE", tolerance_pct=None,
        sources=(_source("yahoo_public", symbol, "1m"),),
    )
    for name, symbol in (("GC", "GC=F"), ("SI", "SI=F"), ("CL", "CL=F"))
)

DEFINITIONS: Tuple[ProductDefinition, ...] = (
    *_SPOT_DEFINITIONS, *_FX_DEFINITIONS, *_FUTURE_DEFINITIONS,
)


def _normalized_symbol(value: Any) -> str:
    raw = str(value or "").strip().upper()
    return raw.replace("/", "")


def _match_source(provider: str, provider_symbol: str) -> Optional[Tuple[ProductDefinition, ProductSource]]:
    declared_provider = str(provider or "").strip().lower()
    declared_symbol = _normalized_symbol(provider_symbol)
    if not declared_provider or not declared_symbol:
        return None
    for definition in DEFINITIONS:
        for source in definition.sources:
            if source.provider == declared_provider and source.symbol.upper() == declared_symbol:
                return definition, source
    return None


def product_definition(provider: str, provider_symbol: str) -> Optional[ProductDefinition]:
    """Classify a declared provider identity into a product key, or None.

    ``None`` means the symbol has no free-source product mapping and therefore
    cannot be checked at all (``NO_PRODUCT_KEY``).
    """

    match = _match_source(provider, provider_symbol)
    return match[0] if match else None


def independent_candidate(provider: str, provider_symbol: str) -> Optional[IndependentCandidate]:
    """Pick at most ONE independent same-product source, or None.

    A different provider is required; the same granularity as the declared
    source is preferred so an exact-bar comparison is possible, and a daily
    fetch is chosen when the declared source is daily or no intraday alias
    exists.  Futures/tokens (no tolerance) never receive a candidate.
    """

    match = _match_source(provider, provider_symbol)
    if match is None:
        return None
    definition, declared_source = match
    if definition.tolerance_pct is None:
        return None
    others = [source for source in definition.sources if source.provider != declared_source.provider]
    if not others:
        return None
    if declared_source.intraday:
        preferred = next((source for source in others if source.intraday), others[0])
    else:
        preferred = next((source for source in others if not source.intraday), others[0])
        if preferred.intraday:
            preferred = ProductSource(provider=preferred.provider, symbol=preferred.symbol, interval="1d")
    return IndependentCandidate(provider=preferred.provider, symbol=preferred.symbol, interval=preferred.interval)


def _clean_closes(raw_bars: Any) -> Dict[int, float]:
    closes: Dict[int, float] = {}
    if not isinstance(raw_bars, (list, tuple)):
        return closes
    for raw in raw_bars:
        if not isinstance(raw, dict):
            continue
        try:
            timestamp = int(raw["timestamp"])
            close = float(raw["close"])
        except (KeyError, TypeError, ValueError):
            continue
        if not math.isfinite(close) or close <= 0:
            continue
        timestamp = timestamp // 1000 if timestamp >= 100_000_000_000 else timestamp
        closes[timestamp] = close
    return closes


def _exact_pairs(declared: Dict[int, float], independent: Dict[int, float]) -> Tuple[List[Tuple[int, float, float]], str]:
    aligned = sorted(set(declared) & set(independent))
    return [(ts, declared[ts], independent[ts]) for ts in aligned], "EXACT_BAR"


def _day_closes(closes: Dict[int, float]) -> Dict[int, float]:
    days: Dict[int, float] = {}
    for timestamp in sorted(closes):
        days[timestamp // 86_400] = closes[timestamp]
    return days


def _day_pairs(declared: Dict[int, float], independent: Dict[int, float]) -> Tuple[List[Tuple[int, float, float]], str]:
    declared_days, independent_days = _day_closes(declared), _day_closes(independent)
    if not declared_days or not independent_days:
        return [], "UTC_DAY"
    latest_day = max(max(declared_days), max(independent_days))
    common = sorted(day for day in set(declared_days) & set(independent_days) if day < latest_day)
    return [(day, declared_days[day], independent_days[day]) for day in common], "UTC_DAY"


def _deviation_pct(declared_close: float, independent_close: float) -> Optional[float]:
    base = (declared_close + independent_close) / 2.0
    if base <= 0 or not math.isfinite(base):
        return None
    return abs(declared_close - independent_close) / base * 100.0


def _payload(
    *, status: str, reason: Optional[str], definition: Optional[ProductDefinition],
    declared_provider: str, declared_symbol: str,
    candidate: Optional[IndependentCandidate] = None,
    alignment: Optional[str] = None, overlap_bars: int = 0,
    median_deviation_pct: Optional[float] = None, max_deviation_pct: Optional[float] = None,
    checked_at: Optional[str] = None, reason_detail: Optional[str] = None,
    alignment_note: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "status": status,
        "reason": reason,
        "reason_detail": reason_detail,
        "product_key": definition.key if definition else None,
        "asset_class": definition.asset_class if definition else None,
        "declared_provider": declared_provider or None,
        "declared_symbol": declared_symbol or None,
        "independent_provider": candidate.provider if candidate else None,
        "independent_symbol": candidate.symbol if candidate else None,
        "alignment": alignment,
        "alignment_note": alignment_note,
        "overlap_bars": overlap_bars,
        "median_deviation_pct": median_deviation_pct,
        "max_deviation_pct": max_deviation_pct,
        "tolerance_pct": definition.tolerance_pct if definition else None,
        "checked_at": checked_at,
        "note": PRODUCT_NOTE,
    }


def not_run_payload(*, declared_provider: str = "", declared_symbol: str = "") -> Dict[str, Any]:
    """No check was performed (a session without the manual refresh)."""

    return _payload(
        status="UNVERIFIABLE", reason="CHECK_NOT_RUN",
        definition=product_definition(declared_provider, declared_symbol),
        declared_provider=declared_provider, declared_symbol=declared_symbol,
    )


def evaluate_product_consistency(
    *,
    declared_provider: str,
    declared_symbol: str,
    declared_candles: Any,
    candidate: Optional[IndependentCandidate],
    independent_candles: Any = None,
    failure_reason: Optional[str] = None,
    checked_at: Optional[str] = None,
) -> Dict[str, Any]:
    """Assemble the honest product-check payload; a single source never passes."""

    definition = product_definition(declared_provider, declared_symbol)
    if definition is None:
        return _payload(
            status="UNVERIFIABLE", reason="NO_PRODUCT_KEY", definition=None,
            declared_provider=declared_provider, declared_symbol=declared_symbol,
            checked_at=checked_at,
        )
    if definition.tolerance_pct is None or candidate is None:
        return _payload(
            status="UNVERIFIABLE", reason="NO_INDEPENDENT_SOURCE", definition=definition,
            declared_provider=declared_provider, declared_symbol=declared_symbol,
            checked_at=checked_at,
        )
    if failure_reason is not None:
        return _payload(
            status="UNVERIFIABLE", reason="FETCH_FAILED", definition=definition,
            declared_provider=declared_provider, declared_symbol=declared_symbol,
            candidate=candidate, checked_at=checked_at, reason_detail=str(failure_reason),
        )

    declared_closes = _clean_closes(declared_candles)
    independent_closes = _clean_closes(independent_candles)
    if not declared_closes or not independent_closes:
        return _payload(
            status="UNVERIFIABLE", reason="INSUFFICIENT_OVERLAP", definition=definition,
            declared_provider=declared_provider, declared_symbol=declared_symbol,
            candidate=candidate, checked_at=checked_at,
        )
    alignment = "EXACT_BAR" if (candidate.intraday and _source_intraday(declared_provider, declared_symbol)) else "UTC_DAY"
    if alignment == "EXACT_BAR":
        pairs, alignment = _exact_pairs(declared_closes, independent_closes)
    else:
        pairs, alignment = _day_pairs(declared_closes, independent_closes)
    overlap = len(pairs)
    if overlap < MIN_OVERLAP_BARS:
        return _payload(
            status="UNVERIFIABLE", reason="INSUFFICIENT_OVERLAP", definition=definition,
            declared_provider=declared_provider, declared_symbol=declared_symbol,
            candidate=candidate, alignment=alignment, overlap_bars=overlap,
            checked_at=checked_at,
            alignment_note=DAY_CLOSE_NOTE if alignment == "UTC_DAY" else None,
        )
    deviations = [deviation for deviation in
                  (_deviation_pct(a, b) for _, a, b in pairs) if deviation is not None]
    if len(deviations) < MIN_OVERLAP_BARS:
        return _payload(
            status="UNVERIFIABLE", reason="INSUFFICIENT_OVERLAP", definition=definition,
            declared_provider=declared_provider, declared_symbol=declared_symbol,
            candidate=candidate, alignment=alignment, overlap_bars=len(deviations),
            checked_at=checked_at,
            alignment_note=DAY_CLOSE_NOTE if alignment == "UTC_DAY" else None,
        )
    median_deviation = statistics.median(deviations)
    max_deviation = max(deviations)
    status = "CONSISTENT" if median_deviation <= definition.tolerance_pct else "DIVERGENT"
    return _payload(
        status=status, reason=None, definition=definition,
        declared_provider=declared_provider, declared_symbol=declared_symbol,
        candidate=candidate, alignment=alignment, overlap_bars=len(deviations),
        median_deviation_pct=median_deviation, max_deviation_pct=max_deviation,
        checked_at=checked_at,
        alignment_note=DAY_CLOSE_NOTE if alignment == "UTC_DAY" else None,
    )


def _source_intraday(provider: str, provider_symbol: str) -> bool:
    match = _match_source(provider, provider_symbol)
    return bool(match and match[1].intraday)
