"""Deterministic fixture/soak harness for Binance depth reconnect proof."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Mapping, Optional, Sequence

from .binance_depth_ingestor import BinanceDepthIngestor
from .binance_depth_session import (
    BinanceDepthReconnectPolicy,
    BinanceDepthSession,
    DepthSessionDecision,
    DepthSessionResult,
)
from .binance_depth_transport import (
    BinanceDepthTransport,
    BinanceDepthTransportConfig,
    DepthTransportDecision,
    DepthTransportResult,
)


@dataclass(frozen=True)
class DepthFixtureCycle:
    """One bounded snapshot/event cycle; failure injection is explicit."""

    snapshot: Mapping[str, Any]
    events: tuple[Mapping[str, Any], ...] = ()
    failure_reason: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.snapshot, Mapping):
            raise ValueError("snapshot must be a mapping")
        if not isinstance(self.events, tuple):
            object.__setattr__(self, "events", tuple(self.events))
        if any(not isinstance(event, Mapping) for event in self.events):
            raise ValueError("events must contain mappings")
        if self.failure_reason is not None and not str(self.failure_reason).strip():
            raise ValueError("failure_reason must be non-empty when supplied")


class BinanceDepthFixtureRunner:
    """Implement the session cycle protocol using deterministic fixtures."""

    def __init__(
        self,
        ingestor: BinanceDepthIngestor,
        config: BinanceDepthTransportConfig,
        cycles: Sequence[DepthFixtureCycle],
    ) -> None:
        self.transport = BinanceDepthTransport(ingestor, config)
        self._cycles: Deque[DepthFixtureCycle] = deque(cycles)

    @property
    def remaining_cycles(self) -> int:
        return len(self._cycles)

    async def run_once(
        self,
        *,
        stop_event=None,
        max_source_events=None,
    ) -> DepthTransportResult:
        if not self._cycles:
            return DepthTransportResult(
                decision=DepthTransportDecision.SOURCE_FAILED,
                reason_code="FIXTURE_CYCLES_EXHAUSTED",
                snapshot=None,
                events=(),
                source_error="no fixture cycle remains",
            )
        cycle = self._cycles.popleft()

        async def event_source():
            for event in cycle.events:
                yield event
            if cycle.failure_reason is not None:
                raise ConnectionError(cycle.failure_reason)

        async def snapshot_fetcher():
            return cycle.snapshot

        return await self.transport.run_once(
            event_source=event_source(),
            snapshot_fetcher=snapshot_fetcher,
            stop_event=stop_event,
            max_source_events=max_source_events,
        )


@dataclass(frozen=True)
class DepthSoakReport:
    session: DepthSessionResult
    chain_report: Mapping[str, Any]
    persistence_report: Optional[Mapping[str, Any]]
    remaining_fixture_cycles: int
    source_verified: bool = False

    @property
    def decision(self) -> DepthSessionDecision:
        return self.session.decision

    @property
    def reason_code(self) -> str:
        return self.session.reason_code

    def as_dict(self) -> dict[str, Any]:
        return {
            "decision": self.session.decision.value,
            "reason_code": self.session.reason_code,
            "attempts": self.session.attempts,
            "reconnects": self.session.reconnects,
            "processed_event_count": self.session.processed_event_count,
            "chain": dict(self.chain_report),
            "persistence": dict(self.persistence_report) if self.persistence_report else None,
            "remaining_fixture_cycles": self.remaining_fixture_cycles,
            "source_verified": self.source_verified,
        }


class BinanceDepthSoakHarness:
    """Run a reconnect scenario and report chain/durability invariants."""

    def __init__(
        self,
        ingestor: BinanceDepthIngestor,
        config: BinanceDepthTransportConfig,
        cycles: Sequence[DepthFixtureCycle],
        *,
        policy: BinanceDepthReconnectPolicy | None = None,
    ) -> None:
        self.ingestor = ingestor
        self.runner = BinanceDepthFixtureRunner(ingestor, config, cycles)
        self.session = BinanceDepthSession(self.runner, policy)

    async def run(self, *, stop_event=None) -> DepthSoakReport:
        session_result = await self.session.run(stop_event=stop_event)
        sink = self.ingestor.event_sink
        persistence_report = None
        if sink is not None and hasattr(sink, "recovery_report"):
            persistence_report = sink.recovery_report()
        return DepthSoakReport(
            session=session_result,
            chain_report=self.ingestor.chain.verify(),
            persistence_report=persistence_report,
            remaining_fixture_cycles=self.runner.remaining_cycles,
            source_verified=False,
        )


__all__ = [
    "BinanceDepthFixtureRunner",
    "BinanceDepthSoakHarness",
    "DepthFixtureCycle",
    "DepthSoakReport",
]
