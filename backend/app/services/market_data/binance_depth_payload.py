"""Strict Binance depth payload normalization and venue-book projection.

This module is intentionally separate from ``services.matching.order_book``.
The latter is an explicit local matching/simulation book; this module represents
observed venue liquidity and never creates fills.  It also keeps prices and
quantities as :class:`decimal.Decimal` values until JSON output, avoiding a
float round-trip in the market-data path.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, Mapping, Optional, Sequence

from .binance_depth_sequence import DepthSequenceDecision, DepthSequenceResult


class DepthPayloadError(ValueError):
    """Raised when a Binance snapshot/delta payload is ambiguous or malformed."""


class DepthBookDecision(str, Enum):
    SNAPSHOT_APPLIED = "SNAPSHOT_APPLIED"
    UPDATE_APPLIED = "UPDATE_APPLIED"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class DepthLevel:
    """One normalized price-level update."""

    price: Decimal
    quantity: Decimal

    def as_pair(self) -> list[str]:
        return [_decimal_text(self.price), _decimal_text(self.quantity)]


@dataclass(frozen=True)
class NormalizedDepthSnapshot:
    symbol: str
    last_update_id: int
    bids: tuple[DepthLevel, ...]
    asks: tuple[DepthLevel, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "lastUpdateId": self.last_update_id,
            "bids": [level.as_pair() for level in self.bids],
            "asks": [level.as_pair() for level in self.asks],
            "source_verified": False,
        }


@dataclass(frozen=True)
class NormalizedDepthUpdate:
    symbol: str
    first_update_id: int
    final_update_id: int
    previous_update_id: Optional[int]
    bids: tuple[DepthLevel, ...]
    asks: tuple[DepthLevel, ...]
    event_time_ms: Optional[int] = None
    transaction_time_ms: Optional[int] = None

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": "BINANCE_DEPTH_V1",
            "source_feed": "BINANCE_WS_DEPTH",
            "symbol": self.symbol,
            "U": self.first_update_id,
            "u": self.final_update_id,
            "b": [level.as_pair() for level in self.bids],
            "a": [level.as_pair() for level in self.asks],
            "source_verified": False,
        }
        if self.previous_update_id is not None:
            payload["pu"] = self.previous_update_id
        if self.event_time_ms is not None:
            payload["E"] = self.event_time_ms
        if self.transaction_time_ms is not None:
            payload["T"] = self.transaction_time_ms
        return payload


@dataclass(frozen=True)
class DepthBookResult:
    decision: DepthBookDecision
    reason_code: str
    symbol: str
    last_update_id: Optional[int]
    bid_levels: int
    ask_levels: int
    changed_levels: int = 0
    removed_levels: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision.value,
            "reason_code": self.reason_code,
            "symbol": self.symbol,
            "last_update_id": self.last_update_id,
            "bid_levels": self.bid_levels,
            "ask_levels": self.ask_levels,
            "changed_levels": self.changed_levels,
            "removed_levels": self.removed_levels,
        }


def normalize_snapshot(payload: Mapping[str, Any], symbol: str) -> NormalizedDepthSnapshot:
    """Normalize a Binance REST depth snapshot without inventing defaults."""

    expected_symbol = _symbol(symbol)
    if not isinstance(payload, Mapping):
        raise DepthPayloadError("snapshot must be an object")
    last_update_id = _update_id(payload, "lastUpdateId")
    bids = _levels(payload, "bids", side="bids")
    asks = _levels(payload, "asks", side="asks")
    return NormalizedDepthSnapshot(expected_symbol, last_update_id, bids, asks)


def normalize_update(payload: Mapping[str, Any], symbol: str) -> NormalizedDepthUpdate:
    """Normalize one Binance websocket diff-depth event."""

    expected_symbol = _symbol(symbol)
    if not isinstance(payload, Mapping):
        raise DepthPayloadError("depth event must be an object")
    event_symbol = payload.get("s")
    if not isinstance(event_symbol, str) or event_symbol.strip().upper() != expected_symbol:
        raise DepthPayloadError("event symbol is missing or does not match the expected symbol")
    if payload.get("e") not in (None, "depthUpdate"):
        raise DepthPayloadError("unexpected depth event type")

    first_update_id = _update_id(payload, "U")
    final_update_id = _update_id(payload, "u")
    if final_update_id < first_update_id:
        raise DepthPayloadError("final update ID precedes first update ID")
    previous_value = payload.get("pu")
    previous_update_id = _update_id(payload, "pu") if previous_value is not None else None
    event_time_ms = _optional_timestamp(payload, "E")
    transaction_time_ms = _optional_timestamp(payload, "T")
    bids = _levels(payload, "b", side="bids")
    asks = _levels(payload, "a", side="asks")
    return NormalizedDepthUpdate(
        symbol=expected_symbol,
        first_update_id=first_update_id,
        final_update_id=final_update_id,
        previous_update_id=previous_update_id,
        bids=bids,
        asks=asks,
        event_time_ms=event_time_ms,
        transaction_time_ms=transaction_time_ms,
    )


class BinanceDepthBook:
    """Venue L2 projection; it is not an execution/matching engine."""

    def __init__(self, symbol: str):
        self.symbol = _symbol(symbol)
        self._bids: dict[Decimal, Decimal] = {}
        self._asks: dict[Decimal, Decimal] = {}
        self._last_update_id: Optional[int] = None

    @property
    def last_update_id(self) -> Optional[int]:
        return self._last_update_id

    def load_snapshot(self, snapshot: NormalizedDepthSnapshot) -> DepthBookResult:
        self._ensure_symbol(snapshot.symbol)
        bids = _levels_to_book(snapshot.bids)
        asks = _levels_to_book(snapshot.asks)
        self._bids = bids
        self._asks = asks
        self._last_update_id = snapshot.last_update_id
        return self._result(DepthBookDecision.SNAPSHOT_APPLIED, "SNAPSHOT_APPLIED")

    def apply_update(
        self,
        update: NormalizedDepthUpdate,
        sequence: DepthSequenceResult,
    ) -> DepthBookResult:
        """Apply levels only after an independent sequence ``APPLIED`` decision."""

        self._ensure_symbol(update.symbol)
        if sequence.decision is not DepthSequenceDecision.APPLIED:
            return self._result(DepthBookDecision.REJECTED, "SEQUENCE_NOT_APPLIED")
        if self._last_update_id is None:
            return self._result(DepthBookDecision.REJECTED, "SNAPSHOT_REQUIRED")
        if sequence.event_final_update_id != update.final_update_id:
            return self._result(DepthBookDecision.REJECTED, "SEQUENCE_EVENT_ID_MISMATCH")
        expected_next = self._last_update_id + 1
        if not (update.first_update_id <= expected_next <= update.final_update_id):
            return self._result(DepthBookDecision.REJECTED, "BOOK_SEQUENCE_GAP")
        if update.previous_update_id is not None and update.previous_update_id != self._last_update_id:
            return self._result(DepthBookDecision.REJECTED, "BOOK_PREVIOUS_ID_MISMATCH")

        changed = 0
        removed = 0
        next_bids = dict(self._bids)
        next_asks = dict(self._asks)
        for levels, target in (
            (update.bids, next_bids),
            (update.asks, next_asks),
        ):
            for level in levels:
                if level.quantity == 0:
                    if target.pop(level.price, None) is not None:
                        removed += 1
                else:
                    target[level.price] = level.quantity
                    changed += 1

        self._bids = next_bids
        self._asks = next_asks
        self._last_update_id = update.final_update_id
        return self._result(
            DepthBookDecision.UPDATE_APPLIED,
            "DEPTH_UPDATE_APPLIED",
            changed_levels=changed,
            removed_levels=removed,
        )

    def as_dict(self, *, depth: Optional[int] = 20) -> dict[str, Any]:
        """Return deterministic JSON-safe levels; no float conversion occurs."""

        if depth is not None and (isinstance(depth, bool) or not isinstance(depth, int) or depth <= 0):
            raise ValueError("depth must be a positive integer or None")
        bids = sorted(self._bids.items(), key=lambda item: item[0], reverse=True)
        asks = sorted(self._asks.items(), key=lambda item: item[0])
        if depth is not None:
            bids = bids[:depth]
            asks = asks[:depth]
        best_bid = bids[0][0] if bids else None
        best_ask = asks[0][0] if asks else None
        return {
            "symbol": self.symbol,
            "status": "IN_MEMORY_UNVERIFIED" if self._last_update_id is not None else "NO_DATA",
            "provenance": "BINANCE_DEPTH_PAYLOAD",
            "source_verified": False,
            "caveat": "Venue depth levels are sequence-checked in memory; no canonical feed persistence is connected.",
            "last_update_id": self._last_update_id,
            "best_bid": _decimal_text(best_bid) if best_bid is not None else None,
            "best_ask": _decimal_text(best_ask) if best_ask is not None else None,
            "bids": [[_decimal_text(price), _decimal_text(quantity)] for price, quantity in bids],
            "asks": [[_decimal_text(price), _decimal_text(quantity)] for price, quantity in asks],
        }

    def _ensure_symbol(self, symbol: str) -> None:
        if _symbol(symbol) != self.symbol:
            raise DepthPayloadError("book symbol does not match payload symbol")

    def _result(
        self,
        decision: DepthBookDecision,
        reason_code: str,
        *,
        changed_levels: int = 0,
        removed_levels: int = 0,
    ) -> DepthBookResult:
        return DepthBookResult(
            decision=decision,
            reason_code=reason_code,
            symbol=self.symbol,
            last_update_id=self._last_update_id,
            bid_levels=len(self._bids),
            ask_levels=len(self._asks),
            changed_levels=changed_levels,
            removed_levels=removed_levels,
        )


def _symbol(value: str) -> str:
    normalized = str(value).strip().upper()
    if not normalized:
        raise DepthPayloadError("symbol must be non-empty")
    return normalized


def _update_id(payload: Mapping[str, Any], field_name: str) -> int:
    value = payload.get(field_name)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise DepthPayloadError(f"{field_name} must be a non-negative integer")
    return value


def _optional_timestamp(payload: Mapping[str, Any], field_name: str) -> Optional[int]:
    if payload.get(field_name) is None:
        return None
    return _update_id(payload, field_name)


def _levels(payload: Mapping[str, Any], field_name: str, *, side: str) -> tuple[DepthLevel, ...]:
    raw_levels = payload.get(field_name)
    if not isinstance(raw_levels, list):
        raise DepthPayloadError(f"{side} must be an array")
    levels: list[DepthLevel] = []
    seen: set[Decimal] = set()
    for index, raw_level in enumerate(raw_levels):
        if not isinstance(raw_level, (list, tuple)) or len(raw_level) != 2:
            raise DepthPayloadError(f"{side}[{index}] must be a [price, quantity] pair")
        price = _decimal(raw_level[0], f"{side}[{index}].price", positive=True)
        quantity = _decimal(raw_level[1], f"{side}[{index}].quantity", positive=False)
        if price in seen:
            raise DepthPayloadError(f"{side} contains duplicate price {price}")
        seen.add(price)
        levels.append(DepthLevel(price, quantity))
    return tuple(levels)


def _decimal(value: Any, field_name: str, *, positive: bool) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise DepthPayloadError(f"{field_name} must be a finite decimal")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise DepthPayloadError(f"{field_name} must be a finite decimal") from exc
    if not parsed.is_finite() or parsed < 0 or (positive and parsed <= 0):
        raise DepthPayloadError(f"{field_name} must be {'positive' if positive else 'non-negative'} and finite")
    return parsed


def _decimal_text(value: Decimal) -> str:
    normalized = format(value.normalize(), "f")
    return "0" if normalized in {"", "-0"} else normalized


def _levels_to_book(levels: Sequence[DepthLevel]) -> dict[Decimal, Decimal]:
    return {level.price: level.quantity for level in levels if level.quantity != 0}


__all__ = [
    "BinanceDepthBook",
    "DepthBookDecision",
    "DepthBookResult",
    "DepthLevel",
    "DepthPayloadError",
    "NormalizedDepthSnapshot",
    "NormalizedDepthUpdate",
    "normalize_snapshot",
    "normalize_update",
]
