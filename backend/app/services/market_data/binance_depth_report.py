"""Fail-closed verifier for Binance depth soak reports."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Mapping, Optional


REPORT_SCHEMA_VERSION = "BINANCE_DEPTH_SOAK_REPORT_V1"
_SYMBOL_RE = re.compile(r"^[A-Z0-9][A-Z0-9._-]{2,29}$")
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_DECISIONS = {
    "COMPLETED",
    "STOPPED",
    "EXHAUSTED",
    "SNAPSHOT_REJECTED",
    "RECOVERY_REQUIRED",
    "PERSISTENCE_FAILED",
}
_CYCLE_DECISIONS = _DECISIONS | {"SOURCE_FAILED", "SNAPSHOT_RETRY_REQUIRED"}
_SUCCESS_DECISIONS = {"COMPLETED", "STOPPED"}


class DepthSoakReportVerdict(str, Enum):
    INVALID = "INVALID"
    VALID_OFFLINE_FIXTURE = "VALID_OFFLINE_FIXTURE"
    VALID_TESTNET_OBSERVATION_UNVERIFIED = "VALID_TESTNET_OBSERVATION_UNVERIFIED"
    FAILED_OBSERVATION = "FAILED_OBSERVATION"


@dataclass(frozen=True)
class DepthSoakReportVerification:
    ok: bool
    verdict: DepthSoakReportVerdict
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    mode: Optional[str] = None
    environment: Optional[str] = None
    symbol: Optional[str] = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "verdict": self.verdict.value,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "mode": self.mode,
            "environment": self.environment,
            "symbol": self.symbol,
        }


def verify_depth_soak_report(
    payload: Any,
    *,
    expected_mode: Optional[str] = None,
    minimum_elapsed_ms: float = 0.0,
    require_durable: bool = True,
) -> DepthSoakReportVerification:
    """Verify one persisted soak report without repairing or promoting it."""

    errors: list[str] = []
    warnings: list[str] = [
        "source_verified remains false; this report is not production market-data proof",
        "execution_authority remains false; this report cannot authorize orders",
    ]
    if isinstance(minimum_elapsed_ms, bool) or not isinstance(minimum_elapsed_ms, (int, float)):
        raise ValueError("minimum_elapsed_ms must be a finite non-negative number")
    if not math.isfinite(minimum_elapsed_ms) or minimum_elapsed_ms < 0:
        raise ValueError("minimum_elapsed_ms must be a finite non-negative number")
    if not isinstance(payload, Mapping):
        return DepthSoakReportVerification(False, DepthSoakReportVerdict.INVALID, ("report must be an object",), tuple(warnings))

    mode = payload.get("mode")
    environment = payload.get("environment")
    symbol = payload.get("symbol")
    if payload.get("schema_version") != REPORT_SCHEMA_VERSION:
        errors.append("unsupported or missing schema_version")
    if mode not in {"fixture", "testnet"}:
        errors.append("mode must be fixture or testnet")
    if expected_mode is not None and mode != expected_mode:
        errors.append(f"mode does not match expected mode {expected_mode}")
    expected_environment = {"fixture": "offline", "testnet": "testnet"}.get(mode)
    if expected_environment is not None and environment != expected_environment:
        errors.append("environment does not match mode")
    if not isinstance(symbol, str) or not _SYMBOL_RE.fullmatch(symbol):
        errors.append("symbol must be a normalized market symbol")

    started_at = payload.get("started_at")
    if not isinstance(started_at, str):
        errors.append("started_at is required")
    else:
        try:
            parsed = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                errors.append("started_at must include timezone")
        except ValueError:
            errors.append("started_at must be an ISO-8601 timestamp")

    elapsed_ms = payload.get("elapsed_ms")
    if isinstance(elapsed_ms, bool) or not isinstance(elapsed_ms, (int, float)) or not math.isfinite(elapsed_ms):
        errors.append("elapsed_ms must be finite")
    elif elapsed_ms < minimum_elapsed_ms:
        errors.append("elapsed_ms is below the required minimum")

    if payload.get("source_verified") is not False:
        errors.append("source_verified must remain false")
    if payload.get("execution_authority") is not False:
        errors.append("execution_authority must remain false")

    session = payload.get("session")
    attempts = reconnects = 0
    decision = None
    if not isinstance(session, Mapping):
        errors.append("session must be an object")
    else:
        decision = session.get("decision")
        if decision not in _DECISIONS:
            errors.append("session decision is unsupported")
        attempts = _non_negative_int(session.get("attempts"), "session.attempts", errors)
        reconnects = _non_negative_int(session.get("reconnects"), "session.reconnects", errors)
        processed = _non_negative_int(session.get("processed_event_count"), "session.processed_event_count", errors)
        if reconnects > attempts:
            errors.append("session.reconnects exceeds attempts")
        if session.get("source_verified") is not False:
            errors.append("session.source_verified must remain false")
        cycles = session.get("cycles")
        if not isinstance(cycles, list):
            errors.append("session.cycles must be an array")
        elif len(cycles) > attempts:
            errors.append("session.cycles exceeds attempts")
        else:
            cycle_decisions: list[str] = []
            cycle_processed_total = 0
            for index, cycle in enumerate(cycles):
                if not isinstance(cycle, Mapping):
                    errors.append(f"session.cycles[{index}] must be an object")
                    continue
                cycle_processed_total += _non_negative_int(
                    cycle.get("events_processed"),
                    f"session.cycles[{index}].events_processed",
                    errors,
                )
                cycle_decision = cycle.get("decision")
                if cycle_decision not in _CYCLE_DECISIONS:
                    errors.append(f"session.cycles[{index}].decision is unsupported")
                elif isinstance(cycle_decision, str):
                    cycle_decisions.append(cycle_decision)
                if cycle.get("source_verified") is not False:
                    errors.append(f"session.cycles[{index}].source_verified must remain false")
            if processed != cycle_processed_total:
                errors.append("session.processed_event_count must equal cycle event totals")
            if decision in _SUCCESS_DECISIONS:
                if not cycle_decisions:
                    errors.append("successful session must contain a terminal cycle")
                elif cycle_decisions[-1] not in _SUCCESS_DECISIONS:
                    errors.append("successful session must end with a successful terminal cycle")
                if any(
                    cycle_decision in {"PERSISTENCE_FAILED", "SNAPSHOT_REJECTED"}
                    for cycle_decision in cycle_decisions[:-1]
                ):
                    errors.append("terminal cycle failure cannot be followed by another cycle")
        if processed < 0:
            errors.append("session.processed_event_count must be non-negative")

    chain = payload.get("chain")
    chain_event_count = None
    if not isinstance(chain, Mapping):
        errors.append("chain must be an object")
    else:
        if chain.get("valid") is not True:
            errors.append("chain.valid must be true")
        chain_event_count = _non_negative_int(chain.get("event_count"), "chain.event_count", errors)
        if chain.get("errors") != []:
            errors.append("chain.errors must be empty")
        head_hash = chain.get("head_hash")
        if not isinstance(head_hash, str) or not _HASH_RE.fullmatch(head_hash):
            errors.append("chain.head_hash must be a SHA-256 digest")

    persistence = payload.get("persistence")
    if require_durable:
        if not isinstance(persistence, Mapping):
            errors.append("persistence must be an object")
        else:
            if persistence.get("valid") is not True:
                errors.append("persistence.valid must be true")
            persistence_event_count = _non_negative_int(
                persistence.get("event_count"), "persistence.event_count", errors
            )
            if chain_event_count is not None and persistence_event_count != chain_event_count:
                errors.append("persistence.event_count must match chain.event_count")
            if persistence.get("errors") != []:
                errors.append("persistence.errors must be empty")

    if mode == "fixture":
        if decision != "COMPLETED":
            errors.append("fixture report must complete successfully")
        if payload.get("remaining_fixture_cycles") != 0:
            errors.append("fixture cycles must be exhausted")

    if errors:
        return DepthSoakReportVerification(
            False,
            DepthSoakReportVerdict.INVALID,
            tuple(errors),
            tuple(warnings),
            mode if isinstance(mode, str) else None,
            environment if isinstance(environment, str) else None,
            symbol if isinstance(symbol, str) else None,
        )
    if decision not in _SUCCESS_DECISIONS:
        warnings.append("session did not reach COMPLETED or STOPPED")
        return DepthSoakReportVerification(
            False,
            DepthSoakReportVerdict.FAILED_OBSERVATION,
            ("session decision is not a successful observation",),
            tuple(warnings),
            mode,
            environment,
            symbol,
        )
    verdict = (
        DepthSoakReportVerdict.VALID_OFFLINE_FIXTURE
        if mode == "fixture"
        else DepthSoakReportVerdict.VALID_TESTNET_OBSERVATION_UNVERIFIED
    )
    return DepthSoakReportVerification(True, verdict, (), tuple(warnings), mode, environment, symbol)


def _non_negative_int(value: Any, field: str, errors: list[str]) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        errors.append(f"{field} must be a non-negative integer")
        return 0
    return value


__all__ = [
    "REPORT_SCHEMA_VERSION",
    "DepthSoakReportVerification",
    "DepthSoakReportVerdict",
    "verify_depth_soak_report",
]
