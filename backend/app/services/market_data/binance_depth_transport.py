"""Bounded async transport boundary for injected Binance depth sources.

This module does not import a websocket or HTTP client.  It coordinates an
injected async event source and snapshot fetcher so the real network adapter can
be added later without changing sequence, recovery or persistence semantics.
"""

from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass
from enum import Enum
from typing import Any, AsyncIterable, Awaitable, Callable, Mapping, Optional

from .binance_depth_ingestor import (
    BinanceDepthIngestor,
    DepthIngestDecision,
    DepthIngestResult,
    DepthIngestorState,
)


class DepthTransportDecision(str, Enum):
    COMPLETED = "COMPLETED"
    STOPPED = "STOPPED"
    SNAPSHOT_RETRY_REQUIRED = "SNAPSHOT_RETRY_REQUIRED"
    SNAPSHOT_REJECTED = "SNAPSHOT_REJECTED"
    SOURCE_FAILED = "SOURCE_FAILED"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"
    PERSISTENCE_FAILED = "PERSISTENCE_FAILED"


@dataclass(frozen=True)
class BinanceDepthTransportConfig:
    symbol: str
    rest_base_url: str = "https://api.binance.com"
    websocket_base_url: str = "wss://stream.binance.com:9443/ws"
    stream_suffix: str = "@depth@100ms"
    queue_size: int = 512

    def __post_init__(self) -> None:
        normalized_symbol = str(self.symbol).strip().upper()
        if not normalized_symbol:
            raise ValueError("symbol must be non-empty")
        if not self.rest_base_url.startswith("https://"):
            raise ValueError("rest_base_url must use https")
        if not self.websocket_base_url.startswith("wss://"):
            raise ValueError("websocket_base_url must use wss")
        if not isinstance(self.stream_suffix, str) or not self.stream_suffix.startswith("@depth"):
            raise ValueError("stream_suffix must be a Binance depth stream suffix")
        if isinstance(self.queue_size, bool) or not isinstance(self.queue_size, int) or self.queue_size <= 0:
            raise ValueError("queue_size must be a positive integer")
        object.__setattr__(self, "symbol", normalized_symbol)

    @property
    def snapshot_url(self) -> str:
        return f"{self.rest_base_url.rstrip('/')}/api/v3/depth?symbol={self.symbol}&limit=5000"

    @property
    def stream_url(self) -> str:
        return f"{self.websocket_base_url.rstrip('/')}/{self.symbol.lower()}{self.stream_suffix}"


@dataclass(frozen=True)
class DepthTransportResult:
    decision: DepthTransportDecision
    reason_code: str
    snapshot: Optional[DepthIngestResult]
    events: tuple[DepthIngestResult, ...]
    source_verified: bool = False
    source_error: Optional[str] = None

    @property
    def processed_event_count(self) -> int:
        return len(self.events)

    @property
    def gap_event_count(self) -> int:
        """Count sequence gaps observed by the ingestor in this cycle."""

        return sum(
            1
            for event in self.events
            if event.decision is DepthIngestDecision.GAP_DETECTED
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision.value,
            "reason_code": self.reason_code,
            "snapshot": self.snapshot.as_dict() if self.snapshot else None,
            "events_processed": self.processed_event_count,
            "gap_events": self.gap_event_count,
            "source_verified": self.source_verified,
            "source_error": self.source_error,
        }


class BinanceDepthTransport:
    """Coordinate injected async source/fetcher with an existing ingestor."""

    def __init__(self, ingestor: BinanceDepthIngestor, config: BinanceDepthTransportConfig):
        if ingestor.symbol != config.symbol:
            raise ValueError("ingestor symbol must match transport config")
        self.ingestor = ingestor
        self.config = config

    async def run_once(
        self,
        *,
        event_source: AsyncIterable[Mapping[str, Any]],
        snapshot_fetcher: Callable[[], Awaitable[Mapping[str, Any]] | Mapping[str, Any]],
        stop_event: Optional[asyncio.Event] = None,
        max_source_events: Optional[int] = None,
    ) -> DepthTransportResult:
        """Run one bounded source cycle; no network client is created here."""

        if max_source_events is not None and (
            isinstance(max_source_events, bool)
            or not isinstance(max_source_events, int)
            or max_source_events <= 0
        ):
            raise ValueError("max_source_events must be a positive integer when supplied")

        self.ingestor.start_buffering()
        queue: asyncio.Queue[object] = asyncio.Queue(maxsize=self.config.queue_size)
        sentinel = object()
        events: list[DepthIngestResult] = []
        source_errors: list[BaseException] = []

        async def produce() -> None:
            produced = 0
            try:
                async for event in event_source:
                    if stop_event is not None and stop_event.is_set():
                        break
                    await queue.put(event)
                    produced += 1
                    if max_source_events is not None and produced >= max_source_events:
                        break
            except BaseException as exc:  # surface source failure in result, never as fake success
                source_errors.append(exc)
            finally:
                try:
                    await queue.put(sentinel)
                except asyncio.CancelledError:
                    pass

        async def consume() -> None:
            while True:
                item = await queue.get()
                try:
                    if item is sentinel:
                        return
                    events.append(self.ingestor.ingest_event(item))
                finally:
                    queue.task_done()

        producer_task = asyncio.create_task(produce())
        consumer_task = asyncio.create_task(consume())
        snapshot_result: Optional[DepthIngestResult] = None
        try:
            try:
                snapshot_payload = snapshot_fetcher()
                if inspect.isawaitable(snapshot_payload):
                    snapshot_payload = await snapshot_payload
                snapshot_result = self.ingestor.ingest_snapshot(snapshot_payload)
            except Exception as exc:
                source_errors.append(exc)
                return DepthTransportResult(
                    decision=DepthTransportDecision.SOURCE_FAILED,
                    reason_code="SNAPSHOT_FETCH_FAILED",
                    snapshot=None,
                    events=tuple(events),
                    source_error=str(exc),
                )

            if snapshot_result.decision is DepthIngestDecision.SNAPSHOT_RETRY_REQUIRED:
                return DepthTransportResult(
                    decision=DepthTransportDecision.SNAPSHOT_RETRY_REQUIRED,
                    reason_code=snapshot_result.reason_code,
                    snapshot=snapshot_result,
                    events=tuple(events),
                )
            if snapshot_result.decision is not DepthIngestDecision.SNAPSHOT_APPLIED:
                return DepthTransportResult(
                    decision=DepthTransportDecision.SNAPSHOT_REJECTED,
                    reason_code=snapshot_result.reason_code,
                    snapshot=snapshot_result,
                    events=tuple(events),
                )

            await producer_task
            await consumer_task
            if source_errors:
                return DepthTransportResult(
                    decision=DepthTransportDecision.SOURCE_FAILED,
                    reason_code="EVENT_SOURCE_FAILED",
                    snapshot=snapshot_result,
                    events=tuple(events),
                    source_error=str(source_errors[0]),
                )
            if self.ingestor.state is DepthIngestorState.PERSISTENCE_ERROR:
                return DepthTransportResult(
                    decision=DepthTransportDecision.PERSISTENCE_FAILED,
                    reason_code="PERSISTENCE_ERROR_BLOCKS_TRANSPORT",
                    snapshot=snapshot_result,
                    events=tuple(events),
                )
            if self.ingestor.state is DepthIngestorState.RECOVERY_REQUIRED:
                return DepthTransportResult(
                    decision=DepthTransportDecision.RECOVERY_REQUIRED,
                    reason_code="INGESTOR_REQUIRES_RECOVERY",
                    snapshot=snapshot_result,
                    events=tuple(events),
                )
            stopped = stop_event is not None and stop_event.is_set()
            return DepthTransportResult(
                decision=DepthTransportDecision.STOPPED if stopped else DepthTransportDecision.COMPLETED,
                reason_code="STOP_EVENT_SET" if stopped else "SOURCE_CYCLE_COMPLETED",
                snapshot=snapshot_result,
                events=tuple(events),
            )
        finally:
            for task in (producer_task, consumer_task):
                if not task.done():
                    task.cancel()
            await asyncio.gather(producer_task, consumer_task, return_exceptions=True)


__all__ = [
    "BinanceDepthTransport",
    "BinanceDepthTransportConfig",
    "DepthTransportDecision",
    "DepthTransportResult",
]
