"""Shared, read-only evidence boundary for historical *bar approximation*.

Validated OHLC coverage is not authenticated market data, broker reconciliation,
or intrabar/tick replay.  Legacy rows may still have no venue/feed identity;
newly ingested rows carry that identity without being promoted to verified
market truth unless the source explicitly opts in.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
from typing import Any

from app.db.duckdb_driver import duckdb_driver

MAX_TRADE_MINUTES = 20_000
# A duration at the limit can overlap two partial boundary minutes.
MAX_TRADE_BARS = MAX_TRADE_MINUTES + 1
MAX_CONTEXT_BARS = 300
MAX_QUERY_ROWS = MAX_TRADE_BARS + 2 * MAX_CONTEXT_BARS


def provenance() -> dict[str, Any]:
    return {
        "quality": "BAR_APPROXIMATION",
        "source": "DUCKDB_CANDLES",
        "source_verified": False,
        "timeframe": "1m",
        "timezone": "UTC",
        "naive_timestamp_policy": "ASSUME_UTC",
        "trade_interval": "[entry_time, exit_time); zero-duration uses entry bar",
        "r_multiple_basis": "GROSS_PRICE_MOVE_NOT_NET_PNL",
        "pnl_basis": "RECORDED_TRADE_PNL",
        "unrealized_pnl_basis": "LINEAR_PRICE_DELTA_TIMES_RECORDED_QUANTITY",
        "limitations": [
            "Full boundary-bar highs/lows may occur before entry or after exit; intrabar order is unknown.",
            "Rows without complete verified venue/feed provenance remain approximate; this is not tick or broker-fill evidence.",
            "R uses the recorded stop, not a verified initial-stop history; fees/slippage are not modeled.",
            "Replay unrealized PnL assumes a linear instrument and recorded base-unit quantity, not inverse or contract-multiplier valuation.",
        ],
    }


def _utc_bar_label(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat().replace("+00:00", "Z")


def market_context_attachment(evidence: "CandleEvidence") -> dict[str, Any]:
    """Build a deterministic, explicitly approximate market-context attachment."""

    candles = [dict(candle) for candle in evidence.candles]
    fingerprint_body = {
        "trade": {
            "id": str(evidence.trade["id"]),
            "symbol": evidence.trade["symbol"],
            "side": evidence.trade["side"],
            "entry_time": evidence.trade["entry_time"],
            "exit_time": evidence.trade["exit_time"],
            "entry_price": evidence.trade["entry_price"],
            "exit_price": evidence.trade["exit_price"],
        },
        "entry_index": evidence.entry_index,
        "exit_index": evidence.exit_index,
        "candles": candles,
    }
    canonical = json.dumps(
        fingerprint_body,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    fingerprint = hashlib.sha256(canonical).hexdigest()
    first_time = int(candles[0]["time"])
    last_time = int(candles[-1]["time"])
    trade_candles = evidence.trade_candles
    candle_provenance = _provenance_summary(candles)
    return {
        "quality": "BAR_APPROXIMATION",
        "source": "DUCKDB_CANDLES",
        "source_verified": candle_provenance["source_verified"],
        "venue": candle_provenance["venue"],
        "feed": candle_provenance["feed"],
        "sequence_coverage": candle_provenance["sequence_coverage"],
        "provenance_complete": candle_provenance["provenance_complete"],
        "ingested_at_start": candle_provenance["ingested_at_start"],
        "ingested_at_end": candle_provenance["ingested_at_end"],
        "symbol": evidence.trade["symbol"],
        "timeframe": "1m",
        "timezone": "UTC",
        "context_start": _utc_bar_label(first_time),
        "context_end_exclusive": _utc_bar_label(last_time + 60),
        "trade_start": evidence.trade["entry_time"],
        "trade_end": evidence.trade["exit_time"],
        "bar_count": len(candles),
        "trade_bar_count": len(trade_candles),
        "lookback_bars": evidence.entry_index,
        "lookforward_bars": len(candles) - evidence.exit_index - 1,
        "entry_index": evidence.entry_index,
        "exit_index": evidence.exit_index,
        "complete_trade_window": True,
        "fingerprint_sha256": fingerprint,
        "limitations": provenance()["limitations"],
    }


class EvidenceError(ValueError):
    def __init__(self, reason: str, message: str, status: str = "NO_DATA"):
        super().__init__(message)
        self.reason, self.message, self.status = reason, message, status

    def to_dict(self) -> dict[str, Any]:
        return {"status": self.status, "reason": self.reason, "message": self.message, "provenance": provenance()}


def finite_number(value: Any) -> float | None:
    """Do not serialize NaN/Infinity or accept booleans as financial values."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError, OverflowError):
        return None


def utc_timestamp(value: Any) -> float:
    try:
        if isinstance(value, bool) or value is None:
            raise ValueError()
        if isinstance(value, (int, float)):
            result = float(value)
        else:
            parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            result = parsed.timestamp()
        # datetime bounds also protect range arithmetic and platform conversions.
        if not math.isfinite(result) or not 0 <= result < 253402300740:
            raise ValueError()
        return result
    except (TypeError, ValueError, OverflowError, OSError) as exc:
        raise EvidenceError("INVALID_TIMESTAMP", "A valid UTC-compatible timestamp is required.") from exc


def _candle_provenance(raw: dict[str, Any]) -> dict[str, Any]:
    """Return meaningful provenance fields while ignoring legacy defaults."""
    venue = str(raw.get("venue") or "UNVERIFIED").strip().upper()
    feed = str(raw.get("feed") or raw.get("source") or "UNVERIFIED").strip().upper()
    event_id = raw.get("source_event_id")
    event_id = str(event_id).strip() if event_id is not None and str(event_id).strip() else None

    sequence = raw.get("source_sequence")
    if sequence is not None and sequence != "":
        if isinstance(sequence, bool):
            raise EvidenceError("INVALID_CANDLE_PROVENANCE", "Candle source sequence must be a non-negative integer.")
        try:
            sequence = int(sequence)
        except (TypeError, ValueError, OverflowError) as exc:
            raise EvidenceError("INVALID_CANDLE_PROVENANCE", "Candle source sequence must be a non-negative integer.") from exc
        if sequence < 0:
            raise EvidenceError("INVALID_CANDLE_PROVENANCE", "Candle source sequence must be a non-negative integer.")
    else:
        sequence = None

    verified = raw.get("source_verified") is True or raw.get("source_verified") == 1
    meaningful = bool(
        event_id is not None
        or sequence is not None
        or verified
        or venue != "UNVERIFIED"
        or feed != "UNVERIFIED"
    )
    if not meaningful:
        return {}
    if verified and (venue == "UNVERIFIED" or feed == "UNVERIFIED"):
        raise EvidenceError(
            "INVALID_CANDLE_PROVENANCE",
            "Verified candles require explicit venue and feed provenance.",
        )

    result: dict[str, Any] = {
        "venue": venue,
        "feed": feed,
        "source_verified": verified,
    }
    if event_id is not None:
        result["source_event_id"] = event_id
    if sequence is not None:
        result["source_sequence"] = sequence
    if raw.get("ingested_at") is not None:
        try:
            result["ingested_at"] = datetime.fromtimestamp(
                utc_timestamp(raw["ingested_at"]), timezone.utc
            ).isoformat()
        except EvidenceError as exc:
            raise EvidenceError(
                "INVALID_CANDLE_PROVENANCE",
                "Candle ingestion timestamp must be valid.",
            ) from exc
    return result


def _provenance_summary(candles: list[dict[str, Any]]) -> dict[str, Any]:
    records = [_candle_provenance(candle) for candle in candles]
    meaningful = [record for record in records if record]
    if not meaningful:
        return {
            "venue": "UNVERIFIED",
            "feed": "UNVERIFIED",
            "source_verified": False,
            "sequence_coverage": "NONE",
            "provenance_complete": False,
            "ingested_at_start": None,
            "ingested_at_end": None,
        }

    venues = {record.get("venue", "UNVERIFIED") for record in meaningful}
    feeds = {record.get("feed", "UNVERIFIED") for record in meaningful}
    sequences = sum("source_sequence" in record for record in records)
    if sequences == 0:
        sequence_coverage = "NONE"
    elif sequences == len(candles):
        sequence_coverage = "COMPLETE"
    else:
        sequence_coverage = "PARTIAL"
    complete = len(meaningful) == len(candles) and all(
        record.get("venue") != "UNVERIFIED"
        and record.get("feed") != "UNVERIFIED"
        and "ingested_at" in record
        for record in records
    )
    ingestion_times = [record["ingested_at"] for record in records if "ingested_at" in record]
    return {
        "venue": next(iter(venues)) if len(venues) == 1 else "MULTI_VENUE",
        "feed": next(iter(feeds)) if len(feeds) == 1 else "MULTI_FEED",
        "source_verified": complete and all(record.get("source_verified") is True for record in records),
        "sequence_coverage": sequence_coverage,
        "provenance_complete": complete,
        "ingested_at_start": min(ingestion_times) if ingestion_times else None,
        "ingested_at_end": max(ingestion_times) if ingestion_times else None,
    }


def normalize_trade(trade: dict[str, Any]) -> dict[str, Any]:
    if not trade:
        raise EvidenceError("TRADE_NOT_FOUND", "The recorded trade was not found.")
    if str(trade.get("status", "")).upper() != "CLOSED":
        raise EvidenceError("TRADE_NOT_CLOSED", "Historical evidence currently supports closed trades only.")
    symbol = str(trade.get("symbol") or "").strip().upper()
    side = str(trade.get("side") or "").upper()
    if not symbol or side not in ("BUY", "LONG", "SELL", "SHORT"):
        raise EvidenceError("INVALID_TRADE", "The recorded symbol and trade side must be valid.")
    result = {**trade, "symbol": symbol, "side": side, "status": "CLOSED"}
    for key in ("entry_price", "exit_price", "qty"):
        value = finite_number(trade.get(key))
        if value is None or value <= 0:
            raise EvidenceError("INVALID_TRADE", "Positive finite entry/exit prices and quantity are required.")
        result[key] = value
    result["entry_timestamp"] = utc_timestamp(trade.get("entry_time"))
    result["exit_timestamp"] = utc_timestamp(trade.get("exit_time"))
    if result["exit_timestamp"] < result["entry_timestamp"]:
        raise EvidenceError("INVALID_TRADE_WINDOW", "Trade exit cannot precede entry.")
    for key in ("entry_time", "exit_time"):
        result[key] = datetime.fromtimestamp(result[key.replace("_time", "_timestamp")], timezone.utc).isoformat()
    result["pnl"] = finite_number(trade.get("pnl"))
    result["stop_loss"] = finite_number(trade.get("stop_loss"))
    result["take_profit"] = finite_number(trade.get("take_profit"))
    if result["take_profit"] is not None and result["take_profit"] <= 0:
        result["take_profit"] = None
    stop, entry = result["stop_loss"], result["entry_price"]
    is_long = side in ("BUY", "LONG")
    valid_stop = stop is not None and stop > 0 and (stop < entry if is_long else stop > entry)
    result["risk_unit"] = abs(entry - stop) if valid_stop else None
    result["risk_reason"] = None if valid_stop else "MISSING_OR_INVALID_STOP"
    return result


def trade_bar_bounds(trade: dict[str, Any]) -> tuple[int, int]:
    start = math.floor(trade["entry_timestamp"] / 60) * 60
    end = max(start + 60, math.ceil(trade["exit_timestamp"] / 60) * 60)
    if trade["exit_timestamp"] - trade["entry_timestamp"] > MAX_TRADE_MINUTES * 60:
        raise EvidenceError("WINDOW_TOO_LARGE", "The trade exceeds the 20,000 minute evidence limit.", "UNAVAILABLE")
    return start, end


@dataclass
class CandleEvidence:
    trade: dict[str, Any]
    candles: list[dict[str, Any]]
    entry_index: int
    exit_index: int

    @property
    def trade_candles(self) -> list[dict[str, Any]]:
        return self.candles[self.entry_index:self.exit_index + 1]

    @property
    def market_context(self) -> dict[str, Any]:
        return market_context_attachment(self)


def load_candle_evidence(
    trade: dict[str, Any], candles: list[dict[str, Any]] | None = None,
    lookback_bars: int = 0, lookforward_bars: int = 0,
) -> CandleEvidence:
    """Require complete trade coverage; retain only contiguous optional context.

    Exact duplicate OHLCV rows collapse. Conflicting duplicates are rejected,
    never last-write-wins. A bounded query hitting its cap is rejected even if
    duplicates caused it: a truncated result cannot certify coverage.
    """
    normalized = normalize_trade(trade)
    start, end = trade_bar_bounds(normalized)
    for count in (lookback_bars, lookforward_bars):
        if isinstance(count, bool) or not isinstance(count, int) or not 0 <= count <= MAX_CONTEXT_BARS:
            raise EvidenceError("INVALID_CONTEXT_WINDOW", "Context must be 0 to 300 whole bars.", "UNAVAILABLE")
    query_start = max(0, start - lookback_bars * 60)
    query_end = end + lookforward_bars * 60
    if candles is None:
        try:
            candles = duckdb_driver.get_candles_range(
                normalized["symbol"], datetime.fromtimestamp(query_start, timezone.utc),
                datetime.fromtimestamp(query_end, timezone.utc), timeframe="1m", limit=MAX_QUERY_ROWS + 1,
            )
        except Exception as exc:
            # Never return a filesystem path, DB exception or credentials to UI.
            raise EvidenceError("CANDLE_STORE_UNAVAILABLE", "The recorded candle store could not be read.", "UNAVAILABLE") from exc
    if len(candles) > MAX_QUERY_ROWS:
        raise EvidenceError("CANDLE_ROW_LIMIT", "Candle history exceeds the bounded read limit; completeness is unknown.", "UNAVAILABLE")
    by_time: dict[int, dict[str, Any]] = {}
    for raw in candles:
        timestamp = utc_timestamp(raw.get("time", raw.get("timestamp")))
        # Supplied history may include other dates. They are not trade evidence.
        if not query_start <= timestamp < query_end:
            continue
        if timestamp % 60 != 0:
            raise EvidenceError("UNALIGNED_CANDLE", "One-minute candle timestamps must be minute-aligned.")
        if str(raw.get("symbol", normalized["symbol"])).upper() != normalized["symbol"] or raw.get("timeframe", "1m") != "1m":
            raise EvidenceError("CANDLE_IDENTITY_MISMATCH", "Candle symbol or timeframe does not match the recorded trade.")
        bar: dict[str, Any] = {"time": int(timestamp)}
        for key in ("open", "high", "low", "close"):
            number = finite_number(raw.get(key))
            if number is None or number <= 0:
                raise EvidenceError("INVALID_OHLC", "Candle OHLC values must be positive and finite.")
            bar[key] = number
        if bar["high"] < max(bar["open"], bar["close"], bar["low"]) or bar["low"] > min(bar["open"], bar["close"], bar["high"]):
            raise EvidenceError("INVALID_OHLC", "Candle high/low do not contain open/close.")
        bar["volume"] = finite_number(raw.get("volume"))
        if raw.get("volume") is not None and (bar["volume"] is None or bar["volume"] < 0):
            raise EvidenceError("INVALID_VOLUME", "Candle volume must be finite and nonnegative when recorded.")
        bar.update(_candle_provenance(raw))
        existing = by_time.get(bar["time"])
        if existing is not None and existing != bar:
            raise EvidenceError("CONFLICTING_CANDLES", "Conflicting OHLCV or provenance rows exist for the same minute.")
        by_time[bar["time"]] = bar
    if not by_time:
        raise EvidenceError("NO_CANDLE_HISTORY", "No recorded one-minute history covers this trade.")
    if any(t not in by_time for t in range(start, end, 60)):
        raise EvidenceError("INCOMPLETE_CANDLE_HISTORY", "At least one recorded minute is missing inside the trade window.")
    retained_start, retained_end = start, end
    while retained_start - 60 >= query_start and retained_start - 60 in by_time:
        retained_start -= 60
    while retained_end < query_end and retained_end in by_time:
        retained_end += 60
    ordered = [by_time[t] for t in range(retained_start, retained_end, 60)]
    return CandleEvidence(normalized, ordered, (start - retained_start) // 60, (end - retained_start) // 60 - 1)


def excursion_metrics(trade: dict[str, Any], candles: list[dict[str, Any]], *, closed: bool) -> dict[str, Any]:
    """Price excursions and gross-price R, not a net-return/optimal-exit model."""
    entry, risk = trade["entry_price"], trade["risk_unit"]
    anchors = [entry, trade["exit_price"]] if closed else [entry]
    highest = max(anchors + [c["high"] for c in candles])
    lowest = min(anchors + [c["low"] for c in candles])
    direction = 1 if trade["side"] in ("BUY", "LONG") else -1
    mae_price, mfe_price = (lowest, highest) if direction == 1 else (highest, lowest)
    exit_price = trade["exit_price"] if closed else candles[-1]["close"]
    move = direction * (exit_price - entry)
    favorable = direction * (mfe_price - entry)
    return {
        "mae_price": mae_price, "mfe_price": mfe_price,
        "mae_r": finite_number(direction * (mae_price - entry) / risk) if risk else None,
        "mfe_r": finite_number(favorable / risk) if risk else None,
        "r_multiple": finite_number(move / risk) if risk else None,
        # Undefined when there was no favorable excursion; never invent 100%.
        "exit_efficiency": finite_number(move / favorable) if favorable > 0 else None,
    }
