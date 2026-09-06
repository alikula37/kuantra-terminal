"""Fail-closed Binance diff-depth sequence validation.

This module deliberately does not open a websocket, fetch a REST snapshot, or
mutate an order book.  It is the small, deterministic contract that a future
transport adapter must satisfy before a depth update can be applied to any
local book or marked as source-verified.

Binance spot's documented snapshot/diff procedure is based on ``lastUpdateId``
from the REST snapshot and ``U``/``u`` ranges from the websocket event.  Some
derivatives streams also expose ``pu``; once present, the previous event ID
must match exactly.  A gap never gets repaired with synthetic events: the
validator transitions to ``GAP`` and requires a fresh snapshot.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Optional


class DepthSequenceState(str, Enum):
    """Lifecycle state of one symbol-specific depth sequence."""

    COLD = "COLD"
    READY = "READY"
    LIVE = "LIVE"
    GAP = "GAP"


class DepthSequenceDecision(str, Enum):
    """Decision returned for a snapshot or one incoming diff event."""

    SNAPSHOT_ACCEPTED = "SNAPSHOT_ACCEPTED"
    SNAPSHOT_REQUIRED = "SNAPSHOT_REQUIRED"
    APPLIED = "APPLIED"
    STALE_IGNORED = "STALE_IGNORED"
    GAP_DETECTED = "GAP_DETECTED"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class DepthSequenceResult:
    """Immutable, serialisable outcome of one validator operation."""

    decision: DepthSequenceDecision
    state: DepthSequenceState
    reason_code: str
    last_update_id: Optional[int]
    event_first_update_id: Optional[int] = None
    event_final_update_id: Optional[int] = None
    requires_snapshot: bool = False

    @property
    def accepted(self) -> bool:
        """Whether the caller may apply the event to its local book."""

        return self.decision in {
            DepthSequenceDecision.SNAPSHOT_ACCEPTED,
            DepthSequenceDecision.APPLIED,
        }

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-safe representation for telemetry and audit logs."""

        return {
            "decision": self.decision.value,
            "state": self.state.value,
            "reason_code": self.reason_code,
            "last_update_id": self.last_update_id,
            "event_first_update_id": self.event_first_update_id,
            "event_final_update_id": self.event_final_update_id,
            "requires_snapshot": self.requires_snapshot,
        }


class BinanceDepthSequenceValidator:
    """Validate Binance snapshot/diff ordering for one expected symbol.

    The validator is intentionally book-agnostic.  A caller should apply the
    ``b``/``a`` price-level changes only when ``accept_delta`` returns
    ``DepthSequenceDecision.APPLIED``.  It must discard its local book and
    fetch a new snapshot for every ``GAP_DETECTED`` or ``RECOVERY_REQUIRED``
    result.
    """

    def __init__(self, symbol: str):
        normalized = str(symbol).strip().upper()
        if not normalized:
            raise ValueError("symbol must be non-empty")
        self.symbol = normalized
        self._state = DepthSequenceState.COLD
        self._last_update_id: Optional[int] = None
        self._previous_id_mode: Optional[bool] = None

    @property
    def state(self) -> DepthSequenceState:
        return self._state

    @property
    def last_update_id(self) -> Optional[int]:
        return self._last_update_id

    @property
    def requires_snapshot(self) -> bool:
        return self._state in {
            DepthSequenceState.COLD,
            DepthSequenceState.GAP,
        }

    def load_snapshot(self, snapshot: Mapping[str, Any]) -> DepthSequenceResult:
        """Install a fresh REST snapshot and reset any prior recovery state.

        Only the sequence identity is interpreted here.  The transport/book
        layer remains responsible for validating and applying the price-level
        arrays.  Invalid snapshots do not mutate validator state.
        """

        try:
            if not isinstance(snapshot, Mapping):
                raise ValueError("snapshot must be an object")
            last_update_id = self._require_update_id(snapshot, "lastUpdateId")
        except ValueError as exc:
            return self._rejected(
                reason_code=f"INVALID_SNAPSHOT:{exc}",
                requires_snapshot=True,
            )

        self._last_update_id = last_update_id
        self._previous_id_mode = None
        self._state = DepthSequenceState.READY
        return DepthSequenceResult(
            decision=DepthSequenceDecision.SNAPSHOT_ACCEPTED,
            state=self._state,
            reason_code="SNAPSHOT_ACCEPTED",
            last_update_id=self._last_update_id,
        )

    def accept_delta(self, event: Mapping[str, Any]) -> DepthSequenceResult:
        """Validate one diff-depth event without mutating a local order book."""

        if self._state == DepthSequenceState.COLD:
            return self._result(
                DepthSequenceDecision.SNAPSHOT_REQUIRED,
                "SNAPSHOT_REQUIRED",
                requires_snapshot=True,
            )
        if self._state == DepthSequenceState.GAP:
            return self._result(
                DepthSequenceDecision.RECOVERY_REQUIRED,
                "RESNAPSHOT_REQUIRED_AFTER_GAP",
                requires_snapshot=True,
            )

        try:
            first_update_id, final_update_id, previous_update_id = self._parse_event(event)
        except ValueError as exc:
            # A malformed live event makes the current book untrustworthy.  Do
            # not try to guess whether only one field was lost; restart from a
            # fresh snapshot instead.
            self._state = DepthSequenceState.GAP
            return self._rejected(
                reason_code=f"INVALID_EVENT:{exc}",
                requires_snapshot=True,
            )

        assert self._last_update_id is not None
        if final_update_id <= self._last_update_id:
            return self._result(
                DepthSequenceDecision.STALE_IGNORED,
                "EVENT_ALREADY_INCLUDED_IN_LOCAL_BOOK",
                event_first_update_id=first_update_id,
                event_final_update_id=final_update_id,
            )

        expected_next = self._last_update_id + 1
        if self._state == DepthSequenceState.READY:
            # Binance's documented first buffered event must contain the first
            # update after the snapshot: U <= lastUpdateId+1 <= u.
            if not (first_update_id <= expected_next <= final_update_id):
                return self._mark_gap(
                    "INITIAL_EVENT_DOES_NOT_BRIDGE_SNAPSHOT",
                    first_update_id,
                    final_update_id,
                )
            self._previous_id_mode = previous_update_id is not None
        else:
            if self._previous_id_mode is True:
                if previous_update_id is None:
                    return self._mark_gap(
                        "PREVIOUS_UPDATE_ID_MISSING",
                        first_update_id,
                        final_update_id,
                    )
                if previous_update_id != self._last_update_id:
                    return self._mark_gap(
                        "PREVIOUS_UPDATE_ID_MISMATCH",
                        first_update_id,
                        final_update_id,
                    )
            elif self._previous_id_mode is False and previous_update_id is not None:
                return self._mark_gap(
                    "UNEXPECTED_PREVIOUS_UPDATE_ID",
                    first_update_id,
                    final_update_id,
                )

            if not (first_update_id <= expected_next <= final_update_id):
                return self._mark_gap(
                    "UPDATE_ID_GAP",
                    first_update_id,
                    final_update_id,
                )

        self._last_update_id = final_update_id
        self._state = DepthSequenceState.LIVE
        return self._result(
            DepthSequenceDecision.APPLIED,
            "CONTIGUOUS_UPDATE",
            event_first_update_id=first_update_id,
            event_final_update_id=final_update_id,
        )

    def _parse_event(self, event: Mapping[str, Any]) -> tuple[int, int, Optional[int]]:
        if not isinstance(event, Mapping):
            raise ValueError("event must be an object")
        event_symbol = event.get("s")
        if not isinstance(event_symbol, str) or event_symbol.strip().upper() != self.symbol:
            raise ValueError("symbol mismatch or missing symbol")
        if event.get("e") not in (None, "depthUpdate"):
            raise ValueError("unexpected event type")

        first_update_id = self._require_update_id(event, "U")
        final_update_id = self._require_update_id(event, "u")
        if final_update_id < first_update_id:
            raise ValueError("final update ID precedes first update ID")

        previous_value = event.get("pu")
        previous_update_id = (
            self._require_update_id(event, "pu") if previous_value is not None else None
        )
        return first_update_id, final_update_id, previous_update_id

    @staticmethod
    def _require_update_id(payload: Mapping[str, Any], field_name: str) -> int:
        value = payload.get(field_name)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{field_name} must be a non-negative integer")
        return value

    def _mark_gap(
        self,
        reason_code: str,
        first_update_id: int,
        final_update_id: int,
    ) -> DepthSequenceResult:
        self._state = DepthSequenceState.GAP
        return self._result(
            DepthSequenceDecision.GAP_DETECTED,
            reason_code,
            event_first_update_id=first_update_id,
            event_final_update_id=final_update_id,
            requires_snapshot=True,
        )

    def _result(
        self,
        decision: DepthSequenceDecision,
        reason_code: str,
        *,
        event_first_update_id: Optional[int] = None,
        event_final_update_id: Optional[int] = None,
        requires_snapshot: bool = False,
    ) -> DepthSequenceResult:
        return DepthSequenceResult(
            decision=decision,
            state=self._state,
            reason_code=reason_code,
            last_update_id=self._last_update_id,
            event_first_update_id=event_first_update_id,
            event_final_update_id=event_final_update_id,
            requires_snapshot=requires_snapshot,
        )

    def _rejected(self, *, reason_code: str, requires_snapshot: bool) -> DepthSequenceResult:
        return self._result(
            DepthSequenceDecision.REJECTED,
            reason_code,
            requires_snapshot=requires_snapshot,
        )


__all__ = [
    "BinanceDepthSequenceValidator",
    "DepthSequenceDecision",
    "DepthSequenceResult",
    "DepthSequenceState",
]
