"""OP-01 open position review: a read-only snapshot of existing candles.

The closed-trade replay contract (complete entry→exit window) is untouched.
This module builds a separate view for an **open** trade from the existing
SQLite market candle cache: no exit data is required, no performance numbers
are produced, and nothing is written to the journal, the plan or the ledger.

Identity is exact: candles are read only from the trade symbol's own cache
bucket.  A same-looking label (``GOLD`` vs ``XAUUSD`` vs ``GC=F``) never
substitutes another instrument, and ``source_verified``-style flags are never
invented.  Provider provenance is only reported when the in-session manual
refresh actually fetched data; pre-existing cached rows are honestly UNKNOWN.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

MAX_OPEN_REVIEW_BARS = 2_000
FRESH_DELAY_SECONDS = 300
TIMEFRAME_SECONDS = {
    "1m": 60, "5m": 300, "15m": 900, "30m": 1_800,
    "1h": 3_600, "4h": 14_400, "1d": 86_400,
}
GAP_NOTE = "RANGE_NOT_ASSESSABLE"


class OpenReviewError(ValueError):
    def __init__(self, reason: str, message: str, status: str = "NO_DATA"):
        super().__init__(message)
        self.reason, self.message, self.status = reason, message, status

    def to_dict(self) -> Dict[str, Any]:
        return {"status": self.status, "reason": self.reason, "message": self.message}


def _finite(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _instant(value: Any) -> Optional[int]:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return int(parsed.astimezone(timezone.utc).timestamp())


def _iso(ts: Optional[int]) -> Optional[str]:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, timezone.utc).isoformat().replace("+00:00", "Z")


def _normalize_seconds(ts: int) -> int:
    """Provider payloads are millisecond epochs; reviews work in seconds."""

    return ts // 1000 if ts >= 100_000_000_000 else ts


def _bar_floor(ts: int, interval: Optional[int]) -> int:
    if not interval or interval <= 0:
        return ts
    return (ts // interval) * interval


def normalize_open_trade(trade: Dict[str, Any]) -> Dict[str, Any]:
    if not trade:
        raise OpenReviewError("TRADE_NOT_FOUND", "The recorded trade was not found.")
    if str(trade.get("status") or "").upper() != "OPEN":
        raise OpenReviewError("TRADE_NOT_OPEN", "The chart review only covers open or closed trades.")
    symbol = str(trade.get("symbol") or "").strip().upper()
    side = str(trade.get("side") or "").upper()
    if not symbol or side not in ("BUY", "LONG", "SELL", "SHORT"):
        raise OpenReviewError("INVALID_TRADE", "The recorded symbol and trade side must be valid.")
    entry = _finite(trade.get("entry_price"))
    if entry is None or entry <= 0:
        raise OpenReviewError("INVALID_TRADE", "A positive finite entry price is required.")
    entry_ts = _instant(trade.get("entry_time"))
    if entry_ts is None:
        raise OpenReviewError("INVALID_TRADE", "A valid recorded entry time is required.")
    return {**trade, "symbol": symbol, "side": side, "entry_price": entry, "entry_timestamp": entry_ts}


def _clean_candles(raw_candles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    ordered: List[Dict[str, Any]] = []
    seen: Dict[int, Dict[str, Any]] = {}
    for raw in raw_candles:
        try:
            ts = int(raw["timestamp"])
            ohlc = tuple(float(raw[key]) for key in ("open", "high", "low", "close"))
            volume = float(raw.get("volume") or 0.0)
        except (KeyError, TypeError, ValueError):
            continue
        if any(not math.isfinite(value) for value in (*ohlc, volume)):
            continue
        ts = _normalize_seconds(ts)
        candle = {"timestamp": ts, "open": ohlc[0], "high": ohlc[1], "low": ohlc[2],
                  "close": ohlc[3], "volume": volume}
        existing = seen.get(ts)
        if existing is not None:
            if (existing["open"], existing["high"], existing["low"], existing["close"]) != ohlc:
                raise OpenReviewError("CONFLICTING_CANDLES",
                                      "Conflicting duplicate candles were found for this window.")
            continue
        seen[ts] = candle
        ordered.append(candle)
    ordered.sort(key=lambda candle: candle["timestamp"])
    return ordered


@dataclass
class OpenPositionEvidence:
    trade: Dict[str, Any]
    candles: List[Dict[str, Any]]
    timeframe: str
    entry_index: int
    entry_bar_present: bool
    history_status: str
    coverage: Dict[str, Any] = field(default_factory=dict)
    freshness: Dict[str, Any] = field(default_factory=dict)
    provenance: Dict[str, Any] = field(default_factory=dict)

    @property
    def symbol(self) -> str:
        return str(self.trade["symbol"])


FREE_QUOTE_PROVIDERS = ("binance_public", "bybit_public", "yahoo_public", "stooq_public", "biquote_public")


def declared_provider_identity(trade: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """Return the trade's declared provider identity, or None when unusable."""

    provider = str(trade.get("price_source") or "").strip().lower()
    provider_symbol = str(trade.get("price_source_symbol") or "").strip()
    if provider not in FREE_QUOTE_PROVIDERS or not provider_symbol:
        return None
    return {"provider": provider, "provider_symbol": provider_symbol.upper()}


def load_open_position_evidence(
    trade: Dict[str, Any],
    *,
    snapshot: Dict[str, Any],
    now: Optional[datetime] = None,
) -> OpenPositionEvidence:
    """Build the review from a snapshot fetched from the trade's declared provider.

    The snapshot must come from the declared provider and the declared provider
    symbol; candles cached earlier with unknown provenance are never used, and a
    provider that would substitute a different product fails closed.
    """

    normalized = normalize_open_trade(trade)
    symbol = normalized["symbol"]
    reference = now or datetime.now(timezone.utc)
    reference_ts = int(reference.timestamp())

    declared = declared_provider_identity(normalized)
    if declared is None:
        raise OpenReviewError(
            "PROVIDER_NOT_DECLARED",
            "The trade has no declared free public provider and instrument symbol; a chart match cannot be established.")
    snapshot_provider = str((snapshot or {}).get("provider") or "").strip().lower()
    snapshot_symbol = str((snapshot or {}).get("provider_symbol") or "").strip().upper()
    if snapshot_provider != declared["provider"] or snapshot_symbol != declared["provider_symbol"]:
        raise OpenReviewError(
            "PROVIDER_IDENTITY_MISMATCH",
            "The fetched candles do not belong to the trade's declared provider identity; nothing was substituted.")

    candles = _clean_candles((snapshot or {}).get("candles") or [])
    if not candles:
        raise OpenReviewError(
            "PROVIDER_FETCH_FAILED",
            "The declared provider returned no usable candles for this instrument.")

    timeframe = str((snapshot or {}).get("interval") or "1m")
    interval = TIMEFRAME_SECONDS.get(timeframe)

    bars_truncated = False
    limit = MAX_OPEN_REVIEW_BARS
    if len(candles) > limit:
        candles = candles[-limit:]
        bars_truncated = True

    entry_bar_ts = _bar_floor(normalized["entry_timestamp"], interval)
    first_ts = candles[0]["timestamp"]
    last_ts = candles[-1]["timestamp"]
    if last_ts < entry_bar_ts:
        raise OpenReviewError(
            "NO_CANDLES_SINCE_ENTRY",
            "The cached candles end before this trade's entry; refresh the market data to see the open position.")
    entry_index = next((index for index, candle in enumerate(candles)
                        if candle["timestamp"] >= entry_bar_ts), len(candles) - 1)
    entry_bar_present = candles[entry_index]["timestamp"] == entry_bar_ts
    history_status = "FULL_SINCE_ENTRY" if first_ts <= entry_bar_ts else "PARTIAL_SINCE_ENTRY"
    missing_before_entry_minutes = (
        max(0, (first_ts - entry_bar_ts) // 60) if history_status == "PARTIAL_SINCE_ENTRY" else 0
    )

    gap_ranges: List[Dict[str, Optional[str]]] = []
    gap_count = 0
    if interval:
        for previous, current in zip(candles, candles[1:]):
            expected = previous["timestamp"] + interval
            if current["timestamp"] != expected:
                gap_count += 1
                if len(gap_ranges) < 5:
                    gap_ranges.append({"start_utc": _iso(expected),
                                       "end_utc": _iso(current["timestamp"])})

    last_state = "UNKNOWN"
    delay_indicator = "UNKNOWN"
    age_seconds: Optional[int] = None
    if interval:
        age_seconds = max(0, reference_ts - last_ts)
        last_state = "OPEN" if age_seconds < interval else "CLOSED"
        delay_indicator = "FRESH_DELAY" if age_seconds <= FRESH_DELAY_SECONDS else "DELAYED"

    fetched_at = (snapshot or {}).get("fetched_at")
    coverage = {
        "bars": len(candles),
        "coverage_start_utc": _iso(first_ts),
        "coverage_end_utc": _iso(last_ts),
        "entry_bar_present": entry_bar_present,
        "missing_before_entry_minutes": missing_before_entry_minutes,
        "gap_count": gap_count,
        "gap_ranges": gap_ranges,
        "gap_note": GAP_NOTE,
        "bars_truncated": bars_truncated,
    }
    freshness = {
        "last_candle_time_utc": _iso(last_ts),
        "last_candle_age_seconds": age_seconds,
        "last_candle_state": last_state,
        "delay_indicator": delay_indicator,
        "provider_latency": "UNKNOWN",
        "last_download_at": fetched_at,
        "refresh_result": "REFRESHED",
    }
    provenance = {
        "store": "DECLARED_PROVIDER_FETCH",
        "source": declared["provider"],
        "quality": "BAR_APPROXIMATION",
        "source_verified": False,
        "timeframe": timeframe,
        "instrument": symbol,
        "declared_symbol": declared["provider_symbol"],
        "identity_verified": True,
        "identity_note": "PROVIDER_MATCH_ESTABLISHED_IN_SESSION",
        "provider": declared["provider"],
        "provider_symbol": snapshot_symbol,
        "provider_note": "NOT_BROKER_EXECUTION_EVIDENCE",
        "fetched_at": fetched_at,
    }
    return OpenPositionEvidence(
        trade=normalized, candles=candles, timeframe=timeframe, entry_index=entry_index,
        entry_bar_present=entry_bar_present, history_status=history_status,
        coverage=coverage, freshness=freshness, provenance=provenance,
    )
