"""Bounded snapshot/event-buffer coordination for Binance depth streams.

The coordinator is deliberately transport-free.  A future websocket adapter
can feed events into :meth:`ingest_event` and hand REST snapshots to
:meth:`apply_snapshot`; this module decides when replay is safe.  It never
opens a network connection, mutates price levels, or fills a missing sequence
with synthetic data.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Any, Deque, Mapping, Optional

from .binance_depth_sequence import (
    BinanceDepthSequenceValidator,
    DepthSequenceDecision,
    DepthSequenceResult,
    DepthSequenceState,
)


class DepthRecoveryState(str, Enum):
    """Coordinator lifecycle around the validator and bounded event buffer."""

    AWAITING_SNAPSHOT = "AWAITING_SNAPSHOT"
    LIVE = "LIVE"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"


class DepthRecoveryDecision(str, Enum):
    """Outcome returned to the transport adapter."""

    BUFFERED = "BUFFERED"
    SNAPSHOT_RETRY_REQUIRED = "SNAPSHOT_RETRY_REQUIRED"
    SNAPSHOT_APPLIED = "SNAPSHOT_APPLIED"
    LIVE_APPLIED = "LIVE_APPLIED"
    STALE_IGNORED = "STALE_IGNORED"
    GAP_DETECTED = "GAP_DETECTED"
    BUFFER_OVERFLOW = "BUFFER_OVERFLOW"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class DepthRecoveryResult:
    """Immutable result suitable for logs, metrics and adapter tests."""

    decision: DepthRecoveryDecision
    state: DepthRecoveryState
    reason_code: str
    last_update_id: Optional[int]
    buffered_events: int
    replayed_events: int = 0
    dropped_stale_events: int = 0
    requires_snapshot: bool = False
    sequence: Optional[DepthSequenceResult] = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision.value,
            "state": self.state.value,
            "reason_code": self.reason_code,
            "last_update_id": self.last_update_id,
            "buffered_events": self.buffered_events,
            "replayed_events": self.replayed_events,
            "dropped_stale_events": self.dropped_stale_events,
            "requires_snapshot": self.requires_snapshot,
            "sequence": self.sequence.as_dict() if self.sequence else None,
        }


class BinanceDepthRecoveryCoordinator:
    """Coordinate bounded pre-snapshot buffering and sequence-safe replay."""

    def __init__(self, symbol: str, *, max_buffer_events: int = 2_000):
        if isinstance(max_buffer_events, bool) or not isinstance(max_buffer_events, int):
            raise ValueError("max_buffer_events must be a positive integer")
        if max_buffer_events <= 0:
            raise ValueError("max_buffer_events must be a positive integer")

        self.symbol = str(symbol).strip().upper()
        if not self.symbol:
            raise ValueError("symbol must be non-empty")
        self.max_buffer_events = max_buffer_events
        self.validator = BinanceDepthSequenceValidator(self.symbol)
        self._buffer: Deque[Mapping[str, Any]] = deque()
        self._state = DepthRecoveryState.AWAITING_SNAPSHOT

    @property
    def state(self) -> DepthRecoveryState:
        return self._state

    @property
    def last_update_id(self) -> Optional[int]:
        return self.validator.last_update_id

    @property
    def buffered_count(self) -> int:
        return len(self._buffer)

    def start_buffering(self) -> DepthRecoveryResult:
        """Start a new snapshot cycle after a gap or connection reset."""

        self._buffer.clear()
        self._state = DepthRecoveryState.AWAITING_SNAPSHOT
        return self._result(
            DepthRecoveryDecision.BUFFERED,
            "BUFFER_RESET_FOR_NEW_SNAPSHOT",
            requires_snapshot=True,
        )

    def ingest_event(self, event: Mapping[str, Any]) -> DepthRecoveryResult:
        """Buffer or sequence-check one raw depth event."""

        if self._state == DepthRecoveryState.RECOVERY_REQUIRED:
            return self._result(
                DepthRecoveryDecision.RECOVERY_REQUIRED,
                "START_NEW_SNAPSHOT_CYCLE",
                requires_snapshot=True,
            )

        if self._state == DepthRecoveryState.LIVE:
            sequence = self.validator.accept_delta(event)
            if sequence.decision is DepthSequenceDecision.APPLIED:
                return self._result(
                    DepthRecoveryDecision.LIVE_APPLIED,
                    sequence.reason_code,
                    sequence=sequence,
                )
            if sequence.decision is DepthSequenceDecision.STALE_IGNORED:
                return self._result(
                    DepthRecoveryDecision.STALE_IGNORED,
                    sequence.reason_code,
                    sequence=sequence,
                )
            self._state = DepthRecoveryState.RECOVERY_REQUIRED
            return self._result(
                DepthRecoveryDecision.GAP_DETECTED
                if sequence.decision is DepthSequenceDecision.GAP_DETECTED
                else DepthRecoveryDecision.REJECTED,
                sequence.reason_code,
                requires_snapshot=True,
                sequence=sequence,
            )

        try:
            # Validate identity/range before storing the event.  This prevents
            # an unbounded or cross-symbol buffer from becoming a recovery
            # source later.
            self.validator.event_range(event)
        except (TypeError, ValueError) as exc:
            self._state = DepthRecoveryState.RECOVERY_REQUIRED
            return self._result(
                DepthRecoveryDecision.REJECTED,
                f"INVALID_BUFFERED_EVENT:{exc}",
                requires_snapshot=True,
            )

        if len(self._buffer) >= self.max_buffer_events:
            self._buffer.clear()
            self._state = DepthRecoveryState.RECOVERY_REQUIRED
            return self._result(
                DepthRecoveryDecision.BUFFER_OVERFLOW,
                "EVENT_BUFFER_LIMIT_EXCEEDED",
                requires_snapshot=True,
            )

        self._buffer.append(dict(event))
        return self._result(
            DepthRecoveryDecision.BUFFERED,
            "EVENT_BUFFERED_BEFORE_SNAPSHOT",
            requires_snapshot=True,
        )

    def apply_snapshot(self, snapshot: Mapping[str, Any]) -> DepthRecoveryResult:
        """Install a snapshot and replay buffered events in arrival order."""

        if self._state == DepthRecoveryState.RECOVERY_REQUIRED:
            return self._result(
                DepthRecoveryDecision.RECOVERY_REQUIRED,
                "START_NEW_SNAPSHOT_CYCLE_BEFORE_APPLYING",
                requires_snapshot=True,
            )

        try:
            snapshot_id = self.validator.snapshot_update_id(snapshot)
        except (TypeError, ValueError) as exc:
            return self._result(
                DepthRecoveryDecision.REJECTED,
                f"INVALID_SNAPSHOT:{exc}",
                requires_snapshot=True,
            )

        if self._buffer:
            first_update_id, _ = self.validator.event_range(self._buffer[0])
            if snapshot_id < first_update_id:
                return self._result(
                    DepthRecoveryDecision.SNAPSHOT_RETRY_REQUIRED,
                    "SNAPSHOT_BEHIND_FIRST_BUFFERED_EVENT",
                    requires_snapshot=True,
                )

        snapshot_result = self.validator.load_snapshot(snapshot)
        if snapshot_result.decision is not DepthSequenceDecision.SNAPSHOT_ACCEPTED:
            return self._result(
                DepthRecoveryDecision.REJECTED,
                snapshot_result.reason_code,
                requires_snapshot=True,
                sequence=snapshot_result,
            )

        replayed = 0
        dropped_stale = 0
        buffered_events = list(self._buffer)
        self._buffer.clear()
        for event in buffered_events:
            sequence = self.validator.accept_delta(event)
            if sequence.decision is DepthSequenceDecision.STALE_IGNORED:
                dropped_stale += 1
                continue
            if sequence.decision is not DepthSequenceDecision.APPLIED:
                self._state = DepthRecoveryState.RECOVERY_REQUIRED
                return self._result(
                    DepthRecoveryDecision.GAP_DETECTED
                    if sequence.decision is DepthSequenceDecision.GAP_DETECTED
                    else DepthRecoveryDecision.REJECTED,
                    sequence.reason_code,
                    replayed_events=replayed,
                    dropped_stale_events=dropped_stale,
                    requires_snapshot=True,
                    sequence=sequence,
                )
            replayed += 1

        self._state = DepthRecoveryState.LIVE
        return self._result(
            DepthRecoveryDecision.SNAPSHOT_APPLIED,
            "SNAPSHOT_AND_BUFFER_REPLAYED",
            replayed_events=replayed,
            dropped_stale_events=dropped_stale,
            sequence=snapshot_result,
        )

    def _result(
        self,
        decision: DepthRecoveryDecision,
        reason_code: str,
        *,
        replayed_events: int = 0,
        dropped_stale_events: int = 0,
        requires_snapshot: bool = False,
        sequence: Optional[DepthSequenceResult] = None,
    ) -> DepthRecoveryResult:
        return DepthRecoveryResult(
            decision=decision,
            state=self._state,
            reason_code=reason_code,
            last_update_id=self.validator.last_update_id,
            buffered_events=len(self._buffer),
            replayed_events=replayed_events,
            dropped_stale_events=dropped_stale_events,
            requires_snapshot=requires_snapshot,
            sequence=sequence,
        )


__all__ = [
    "BinanceDepthRecoveryCoordinator",
    "DepthRecoveryDecision",
    "DepthRecoveryResult",
    "DepthRecoveryState",
]
