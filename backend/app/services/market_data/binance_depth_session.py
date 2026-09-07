"""Bounded reconnect/session coordination for public Binance depth cycles."""

from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional, Protocol

from .binance_depth_transport import (
    DepthTransportDecision,
    DepthTransportResult,
)


class DepthSessionDecision(str, Enum):
    COMPLETED = "COMPLETED"
    STOPPED = "STOPPED"
    EXHAUSTED = "EXHAUSTED"
    SNAPSHOT_REJECTED = "SNAPSHOT_REJECTED"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"
    PERSISTENCE_FAILED = "PERSISTENCE_FAILED"


@dataclass(frozen=True)
class BinanceDepthReconnectPolicy:
    """Explicit reconnect/backoff budget; values are bounded and deterministic."""

    max_reconnects: int = 3
    backoff_initial_seconds: float = 1.0
    backoff_max_seconds: float = 30.0
    max_source_events_per_cycle: Optional[int] = None
    retry_recovery: bool = False

    def __post_init__(self) -> None:
        if isinstance(self.max_reconnects, bool) or not isinstance(self.max_reconnects, int) or self.max_reconnects < 0:
            raise ValueError("max_reconnects must be a non-negative integer")
        if not isinstance(self.retry_recovery, bool):
            raise ValueError("retry_recovery must be a boolean")
        for name, value in (
            ("backoff_initial_seconds", self.backoff_initial_seconds),
            ("backoff_max_seconds", self.backoff_max_seconds),
        ):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be a non-negative finite number")
        if self.backoff_max_seconds < self.backoff_initial_seconds:
            raise ValueError("backoff_max_seconds must be >= backoff_initial_seconds")
        if self.max_source_events_per_cycle is not None and (
            isinstance(self.max_source_events_per_cycle, bool)
            or not isinstance(self.max_source_events_per_cycle, int)
            or self.max_source_events_per_cycle <= 0
        ):
            raise ValueError("max_source_events_per_cycle must be a positive integer when supplied")


class DepthCycleRunner(Protocol):
    async def run_once(
        self,
        *,
        stop_event: Optional[asyncio.Event] = None,
        max_source_events: Optional[int] = None,
    ) -> DepthTransportResult:
        """Run one bounded network/fixture cycle."""


@dataclass(frozen=True)
class DepthSessionResult:
    decision: DepthSessionDecision
    reason_code: str
    attempts: int
    reconnects: int
    cycles: tuple[DepthTransportResult, ...]
    source_verified: bool = False

    @property
    def processed_event_count(self) -> int:
        return sum(cycle.processed_event_count for cycle in self.cycles)

    def _cycle_count(self, decision: DepthTransportDecision) -> int:
        return sum(1 for cycle in self.cycles if cycle.decision is decision)

    @property
    def gap_event_count(self) -> int:
        return sum(cycle.gap_event_count for cycle in self.cycles)

    def continuity_metrics(self) -> dict[str, int]:
        """Return aggregate lifecycle metrics derived from immutable cycles."""

        return {
            "cycle_count": len(self.cycles),
            "reconnect_count": self.reconnects,
            "processed_event_count": self.processed_event_count,
            "gap_event_count": self.gap_event_count,
            "completed_cycle_count": self._cycle_count(DepthTransportDecision.COMPLETED),
            "stopped_cycle_count": self._cycle_count(DepthTransportDecision.STOPPED),
            "source_failure_cycle_count": self._cycle_count(DepthTransportDecision.SOURCE_FAILED),
            "snapshot_retry_cycle_count": self._cycle_count(DepthTransportDecision.SNAPSHOT_RETRY_REQUIRED),
            "snapshot_rejected_cycle_count": self._cycle_count(DepthTransportDecision.SNAPSHOT_REJECTED),
            "recovery_required_cycle_count": self._cycle_count(DepthTransportDecision.RECOVERY_REQUIRED),
            "persistence_failure_cycle_count": self._cycle_count(DepthTransportDecision.PERSISTENCE_FAILED),
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision.value,
            "reason_code": self.reason_code,
            "attempts": self.attempts,
            "reconnects": self.reconnects,
            "processed_event_count": self.processed_event_count,
            "source_verified": self.source_verified,
            "cycles": [cycle.as_dict() for cycle in self.cycles],
            "continuity": self.continuity_metrics(),
        }


class BinanceDepthSession:
    """Retry bounded source failures and optional sequence recovery cycles."""

    def __init__(
        self,
        cycle_runner: DepthCycleRunner,
        policy: BinanceDepthReconnectPolicy | None = None,
    ) -> None:
        self.cycle_runner = cycle_runner
        self.policy = policy or BinanceDepthReconnectPolicy()

    async def run(self, *, stop_event: Optional[asyncio.Event] = None) -> DepthSessionResult:
        attempts = 0
        reconnects = 0
        cycles: list[DepthTransportResult] = []

        while True:
            if stop_event is not None and stop_event.is_set():
                return self._result(
                    DepthSessionDecision.STOPPED,
                    "STOP_EVENT_SET",
                    attempts,
                    reconnects,
                    cycles,
                )

            attempts += 1
            try:
                cycle = await self.cycle_runner.run_once(
                    stop_event=stop_event,
                    max_source_events=self.policy.max_source_events_per_cycle,
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                return self._result(
                    DepthSessionDecision.EXHAUSTED,
                    f"CYCLE_RUNNER_EXCEPTION:{type(exc).__name__}",
                    attempts,
                    reconnects,
                    cycles,
                )
            cycles.append(cycle)

            if cycle.decision is DepthTransportDecision.COMPLETED:
                return self._result(
                    DepthSessionDecision.COMPLETED,
                    "SOURCE_CYCLE_COMPLETED",
                    attempts,
                    reconnects,
                    cycles,
                )
            if cycle.decision is DepthTransportDecision.STOPPED:
                return self._result(
                    DepthSessionDecision.STOPPED,
                    cycle.reason_code,
                    attempts,
                    reconnects,
                    cycles,
                )
            if cycle.decision is DepthTransportDecision.PERSISTENCE_FAILED:
                return self._result(
                    DepthSessionDecision.PERSISTENCE_FAILED,
                    cycle.reason_code,
                    attempts,
                    reconnects,
                    cycles,
                )
            if cycle.decision is DepthTransportDecision.RECOVERY_REQUIRED and not self.policy.retry_recovery:
                return self._result(
                    DepthSessionDecision.RECOVERY_REQUIRED,
                    cycle.reason_code,
                    attempts,
                    reconnects,
                    cycles,
                )
            if cycle.decision is DepthTransportDecision.SNAPSHOT_REJECTED:
                return self._result(
                    DepthSessionDecision.SNAPSHOT_REJECTED,
                    cycle.reason_code,
                    attempts,
                    reconnects,
                    cycles,
                )

            retryable_decisions = {
                DepthTransportDecision.SOURCE_FAILED,
                DepthTransportDecision.SNAPSHOT_RETRY_REQUIRED,
            }
            if self.policy.retry_recovery:
                retryable_decisions.add(DepthTransportDecision.RECOVERY_REQUIRED)
            if cycle.decision not in retryable_decisions:
                return self._result(
                    DepthSessionDecision.EXHAUSTED,
                    f"UNHANDLED_CYCLE_DECISION:{cycle.decision.value}",
                    attempts,
                    reconnects,
                    cycles,
                )

            if reconnects >= self.policy.max_reconnects:
                return self._result(
                    DepthSessionDecision.EXHAUSTED,
                    "RECONNECT_BUDGET_EXHAUSTED",
                    attempts,
                    reconnects,
                    cycles,
                )

            reconnects += 1
            delay = min(
                self.policy.backoff_initial_seconds * (2 ** (reconnects - 1)),
                self.policy.backoff_max_seconds,
            )
            if not await self._wait_backoff(delay, stop_event):
                return self._result(
                    DepthSessionDecision.STOPPED,
                    "STOP_EVENT_SET_DURING_BACKOFF",
                    attempts,
                    reconnects,
                    cycles,
                )

    async def _wait_backoff(self, delay: float, stop_event: Optional[asyncio.Event]) -> bool:
        if stop_event is None:
            if delay:
                await asyncio.sleep(delay)
            return True
        if stop_event.is_set():
            return False
        if not delay:
            return not stop_event.is_set()
        sleep_task = asyncio.create_task(asyncio.sleep(delay))
        stop_task = asyncio.create_task(stop_event.wait())
        try:
            done, _ = await asyncio.wait(
                {sleep_task, stop_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            return sleep_task in done and not stop_event.is_set()
        finally:
            for task in (sleep_task, stop_task):
                if not task.done():
                    task.cancel()
            await asyncio.gather(sleep_task, stop_task, return_exceptions=True)

    @staticmethod
    def _result(
        decision: DepthSessionDecision,
        reason_code: str,
        attempts: int,
        reconnects: int,
        cycles: list[DepthTransportResult],
    ) -> DepthSessionResult:
        return DepthSessionResult(
            decision=decision,
            reason_code=reason_code,
            attempts=attempts,
            reconnects=reconnects,
            cycles=tuple(cycles),
            source_verified=False,
        )


__all__ = [
    "BinanceDepthReconnectPolicy",
    "BinanceDepthSession",
    "DepthSessionDecision",
    "DepthSessionResult",
]
