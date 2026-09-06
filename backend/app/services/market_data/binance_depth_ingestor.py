"""Injected Binance depth ingestion boundary.

The ingestor composes the transport-free coordinator, Decimal normalizer,
venue-book projection and canonical event chain.  A websocket/REST adapter can
feed raw messages into it later; this module itself never opens a network
connection and never marks offline fixtures as source-verified.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Optional

from .binance_depth_payload import (
    BinanceDepthBook,
    DepthBookResult,
    DepthPayloadError,
    normalize_snapshot,
    normalize_update,
)
from .binance_depth_recovery import (
    BinanceDepthRecoveryCoordinator,
    DepthRecoveryDecision,
    DepthRecoveryResult,
)
from .market_event_envelope import MarketEventChain, MarketEventEnvelope


class DepthIngestorState(str, Enum):
    AWAITING_SNAPSHOT = "AWAITING_SNAPSHOT"
    LIVE = "LIVE"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"
    PERSISTENCE_ERROR = "PERSISTENCE_ERROR"


class DepthIngestDecision(str, Enum):
    BUFFERED = "BUFFERED"
    SNAPSHOT_RETRY_REQUIRED = "SNAPSHOT_RETRY_REQUIRED"
    SNAPSHOT_APPLIED = "SNAPSHOT_APPLIED"
    LIVE_APPLIED = "LIVE_APPLIED"
    STALE_IGNORED = "STALE_IGNORED"
    GAP_DETECTED = "GAP_DETECTED"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"
    REJECTED = "REJECTED"
    PERSISTENCE_FAILED = "PERSISTENCE_FAILED"


@dataclass(frozen=True)
class DepthIngestResult:
    decision: DepthIngestDecision
    state: DepthIngestorState
    reason_code: str
    last_update_id: Optional[int]
    buffered_events: int
    applied_updates: int = 0
    envelopes_processed: int = 0
    source_verified: bool = False
    recovery: Optional[DepthRecoveryResult] = None
    book: Optional[DepthBookResult] = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision.value,
            "state": self.state.value,
            "reason_code": self.reason_code,
            "last_update_id": self.last_update_id,
            "buffered_events": self.buffered_events,
            "applied_updates": self.applied_updates,
            "envelopes_processed": self.envelopes_processed,
            "source_verified": self.source_verified,
            "recovery": self.recovery.as_dict() if self.recovery else None,
            "book": self.book.as_dict() if self.book else None,
        }


class BinanceDepthIngestor:
    """Compose validation/projection/persistence with explicit fail-closed states."""

    def __init__(
        self,
        symbol: str,
        *,
        max_buffer_events: int = 2_000,
        event_sink: Any = None,
        venue: str = "BINANCE",
    ):
        self.symbol = str(symbol).strip().upper()
        if not self.symbol:
            raise ValueError("symbol must be non-empty")
        self.venue = str(venue).strip().upper()
        if not self.venue:
            raise ValueError("venue must be non-empty")
        self.coordinator = BinanceDepthRecoveryCoordinator(
            self.symbol,
            max_buffer_events=max_buffer_events,
        )
        self.book = BinanceDepthBook(self.symbol)
        self.event_sink = event_sink
        existing_events = tuple(getattr(event_sink, "events", ())) if event_sink is not None else ()
        self.chain = MarketEventChain.from_events(existing_events, venue=self.venue)
        self._state = DepthIngestorState.AWAITING_SNAPSHOT

    @property
    def state(self) -> DepthIngestorState:
        return self._state

    @property
    def last_update_id(self) -> Optional[int]:
        return self.coordinator.last_update_id

    def start_buffering(self) -> DepthIngestResult:
        if self._state == DepthIngestorState.PERSISTENCE_ERROR:
            return self._result(DepthIngestDecision.PERSISTENCE_FAILED, "PERSISTENCE_ERROR_BLOCKS_RECOVERY")
        recovery = self.coordinator.start_buffering()
        self._state = DepthIngestorState.AWAITING_SNAPSHOT
        return self._result(
            DepthIngestDecision.BUFFERED,
            recovery.reason_code,
            recovery=recovery,
        )

    def ingest_event(self, payload: Mapping[str, Any]) -> DepthIngestResult:
        if self._state == DepthIngestorState.PERSISTENCE_ERROR:
            return self._result(DepthIngestDecision.PERSISTENCE_FAILED, "PERSISTENCE_ERROR_BLOCKS_INGEST")
        try:
            normalized = normalize_update(payload, self.symbol)
        except (DepthPayloadError, TypeError, ValueError) as exc:
            recovery = self.coordinator.start_buffering()
            self._state = DepthIngestorState.RECOVERY_REQUIRED
            return self._result(
                DepthIngestDecision.REJECTED,
                f"INVALID_DEPTH_PAYLOAD:{exc}",
                recovery=recovery,
            )

        recovery = self.coordinator.ingest_event(payload)
        if recovery.decision is DepthRecoveryDecision.BUFFERED:
            self._state = DepthIngestorState.AWAITING_SNAPSHOT
            return self._result(DepthIngestDecision.BUFFERED, recovery.reason_code, recovery=recovery)
        if recovery.decision is DepthRecoveryDecision.STALE_IGNORED:
            return self._result(DepthIngestDecision.STALE_IGNORED, recovery.reason_code, recovery=recovery)
        if recovery.decision is not DepthRecoveryDecision.LIVE_APPLIED:
            self._state = (
                DepthIngestorState.RECOVERY_REQUIRED
                if recovery.requires_snapshot
                else self._state
            )
            return self._result(
                DepthIngestDecision.GAP_DETECTED
                if recovery.decision is DepthRecoveryDecision.GAP_DETECTED
                else DepthIngestDecision.RECOVERY_REQUIRED
                if recovery.decision is DepthRecoveryDecision.RECOVERY_REQUIRED
                else DepthIngestDecision.REJECTED,
                recovery.reason_code,
                recovery=recovery,
            )

        sequence = recovery.applied_sequences[0]
        book_result = self.book.apply_update(normalized, sequence)
        if book_result.reason_code != "DEPTH_UPDATE_APPLIED":
            self._state = DepthIngestorState.RECOVERY_REQUIRED
            return self._result(
                DepthIngestDecision.REJECTED,
                f"BOOK_REJECTED:{book_result.reason_code}",
                recovery=recovery,
                book=book_result,
            )
        envelope = self.chain.append_update(normalized, sequence)
        if not self._persist(envelope):
            return self._result(
                DepthIngestDecision.PERSISTENCE_FAILED,
                "EVENT_SINK_APPEND_FAILED",
                recovery=recovery,
                book=book_result,
            )
        self._state = DepthIngestorState.LIVE
        return self._result(
            DepthIngestDecision.LIVE_APPLIED,
            recovery.reason_code,
            envelopes_processed=1,
            recovery=recovery,
            book=book_result,
        )

    def ingest_snapshot(self, payload: Mapping[str, Any]) -> DepthIngestResult:
        if self._state == DepthIngestorState.PERSISTENCE_ERROR:
            return self._result(DepthIngestDecision.PERSISTENCE_FAILED, "PERSISTENCE_ERROR_BLOCKS_INGEST")
        try:
            normalized_snapshot = normalize_snapshot(payload, self.symbol)
        except (DepthPayloadError, TypeError, ValueError) as exc:
            recovery = self.coordinator.start_buffering()
            self._state = DepthIngestorState.RECOVERY_REQUIRED
            return self._result(
                DepthIngestDecision.REJECTED,
                f"INVALID_DEPTH_SNAPSHOT:{exc}",
                recovery=recovery,
            )

        recovery = self.coordinator.apply_snapshot(payload)
        if recovery.decision is DepthRecoveryDecision.SNAPSHOT_RETRY_REQUIRED:
            self._state = DepthIngestorState.AWAITING_SNAPSHOT
            return self._result(
                DepthIngestDecision.SNAPSHOT_RETRY_REQUIRED,
                recovery.reason_code,
                recovery=recovery,
            )
        if recovery.decision is not DepthRecoveryDecision.SNAPSHOT_APPLIED:
            self._state = (
                DepthIngestorState.RECOVERY_REQUIRED
                if recovery.requires_snapshot
                else self._state
            )
            return self._result(
                DepthIngestDecision.RECOVERY_REQUIRED
                if recovery.decision is DepthRecoveryDecision.RECOVERY_REQUIRED
                else DepthIngestDecision.REJECTED,
                recovery.reason_code,
                recovery=recovery,
            )

        book_result = self.book.load_snapshot(normalized_snapshot)
        envelopes_processed = 0
        snapshot_envelope = self.chain.append_snapshot(normalized_snapshot)
        if not self._persist(snapshot_envelope):
            return self._result(
                DepthIngestDecision.PERSISTENCE_FAILED,
                "SNAPSHOT_SINK_APPEND_FAILED",
                recovery=recovery,
                book=book_result,
            )
        envelopes_processed += 1
        applied_updates = 0
        last_book_result = book_result
        try:
            for raw_event, sequence in zip(recovery.applied_events, recovery.applied_sequences):
                normalized_update = normalize_update(raw_event, self.symbol)
                last_book_result = self.book.apply_update(normalized_update, sequence)
                if last_book_result.reason_code != "DEPTH_UPDATE_APPLIED":
                    self._state = DepthIngestorState.RECOVERY_REQUIRED
                    return self._result(
                        DepthIngestDecision.REJECTED,
                        f"BOOK_REPLAY_REJECTED:{last_book_result.reason_code}",
                        envelopes_processed=envelopes_processed,
                        applied_updates=applied_updates,
                        recovery=recovery,
                        book=last_book_result,
                    )
                envelope = self.chain.append_update(normalized_update, sequence)
                if not self._persist(envelope):
                    return self._result(
                        DepthIngestDecision.PERSISTENCE_FAILED,
                        "REPLAY_SINK_APPEND_FAILED",
                        envelopes_processed=envelopes_processed,
                        applied_updates=applied_updates,
                        recovery=recovery,
                        book=last_book_result,
                    )
                envelopes_processed += 1
                applied_updates += 1
        except (DepthPayloadError, TypeError, ValueError) as exc:
            self._state = DepthIngestorState.RECOVERY_REQUIRED
            return self._result(
                DepthIngestDecision.REJECTED,
                f"REPLAY_NORMALIZATION_FAILED:{exc}",
                envelopes_processed=envelopes_processed,
                applied_updates=applied_updates,
                recovery=recovery,
                book=last_book_result,
            )

        self._state = DepthIngestorState.LIVE
        return self._result(
            DepthIngestDecision.SNAPSHOT_APPLIED,
            recovery.reason_code,
            envelopes_processed=envelopes_processed,
            applied_updates=applied_updates,
            recovery=recovery,
            book=last_book_result,
        )

    def _persist(self, envelope: MarketEventEnvelope) -> bool:
        if self.event_sink is None:
            return True
        try:
            self.event_sink.append(envelope)
            return True
        except Exception:
            self._state = DepthIngestorState.PERSISTENCE_ERROR
            return False

    def _result(
        self,
        decision: DepthIngestDecision,
        reason_code: str,
        *,
        envelopes_processed: int = 0,
        applied_updates: int = 0,
        recovery: Optional[DepthRecoveryResult] = None,
        book: Optional[DepthBookResult] = None,
    ) -> DepthIngestResult:
        return DepthIngestResult(
            decision=decision,
            state=self._state,
            reason_code=reason_code,
            last_update_id=self.last_update_id,
            buffered_events=recovery.buffered_events if recovery else self.coordinator.buffered_count,
            applied_updates=applied_updates,
            envelopes_processed=envelopes_processed,
            recovery=recovery,
            book=book,
        )


__all__ = [
    "BinanceDepthIngestor",
    "DepthIngestDecision",
    "DepthIngestResult",
    "DepthIngestorState",
]
