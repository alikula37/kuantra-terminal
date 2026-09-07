"""Deterministic, offline fault-injection matrix for Binance depth recovery.

The matrix is deliberately fixture-only.  It exercises the same ingestor,
transport, bounded session and durable segment sink used by the testnet probe,
but never opens a network connection and never promotes ``source_verified`` or
execution authority.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .binance_depth_ingestor import BinanceDepthIngestor
from .binance_depth_session import (
    BinanceDepthReconnectPolicy,
    DepthSessionDecision,
)
from .binance_depth_soak import BinanceDepthSoakHarness, DepthFixtureCycle
from .binance_depth_transport import BinanceDepthTransportConfig
from .market_event_segments import MarketEventSegmentSet


FAULT_MATRIX_SCHEMA_VERSION = "BINANCE_DEPTH_FAULT_MATRIX_V1"


@dataclass(frozen=True)
class DepthFaultScenario:
    """One named fault scenario and its fail-closed expected outcome."""

    scenario_id: str
    description: str
    cycles: tuple[DepthFixtureCycle, ...]
    policy: BinanceDepthReconnectPolicy
    expected_decision: DepthSessionDecision
    expected_reason_code: str
    expected_attempts: int
    expected_reconnects: int
    expected_continuity: Mapping[str, int]
    expected_persistence_event_count: int


def _snapshot(symbol: str, last_update_id: int) -> Mapping[str, Any]:
    return {
        "lastUpdateId": last_update_id,
        "bids": [["65000", "2"]],
        "asks": [["65010", "3"]],
    }


def _event(symbol: str, first_update_id: int, final_update_id: int) -> Mapping[str, Any]:
    return {
        "e": "depthUpdate",
        "s": symbol,
        "U": first_update_id,
        "u": final_update_id,
        "b": [["65000", "1"]],
        "a": [],
    }


def _continuity(**overrides: int) -> dict[str, int]:
    values = {
        "completed_cycle_count": 0,
        "cycle_count": 0,
        "gap_event_count": 0,
        "persistence_failure_cycle_count": 0,
        "processed_event_count": 0,
        "reconnect_count": 0,
        "recovery_required_cycle_count": 0,
        "snapshot_rejected_cycle_count": 0,
        "snapshot_retry_cycle_count": 0,
        "source_failure_cycle_count": 0,
        "stopped_cycle_count": 0,
    }
    values.update(overrides)
    return values


def build_binance_depth_fault_matrix(symbol: str = "BTCUSDT") -> tuple[DepthFaultScenario, ...]:
    """Return the canonical offline matrix for one normalized symbol."""

    normalized_symbol = str(symbol).strip().upper()
    if not normalized_symbol:
        raise ValueError("symbol must be non-empty")

    clean = DepthFixtureCycle(
        _snapshot(normalized_symbol, 101),
        (_event(normalized_symbol, 101, 102),),
    )
    disconnected = DepthFixtureCycle(
        _snapshot(normalized_symbol, 101),
        (_event(normalized_symbol, 101, 102),),
        failure_reason="fixture disconnect",
    )
    second_cycle = DepthFixtureCycle(
        _snapshot(normalized_symbol, 102),
        (_event(normalized_symbol, 103, 104),),
    )
    gap_cycle = DepthFixtureCycle(
        _snapshot(normalized_symbol, 101),
        (
            _event(normalized_symbol, 101, 102),
            _event(normalized_symbol, 105, 106),
        ),
    )
    malformed_event_cycle = DepthFixtureCycle(
        _snapshot(normalized_symbol, 101),
        (
            _event(normalized_symbol, 101, 102),
            {"e": "depthUpdate", "s": normalized_symbol, "U": 103},
        ),
    )
    rejected_snapshot_cycle = DepthFixtureCycle(
        {"lastUpdateId": "not-an-integer", "bids": [], "asks": []},
    )

    return (
        DepthFaultScenario(
            scenario_id="clean_cycle",
            description="A contiguous snapshot plus one update completes without reconnect.",
            cycles=(clean,),
            policy=BinanceDepthReconnectPolicy(max_reconnects=0, backoff_initial_seconds=0),
            expected_decision=DepthSessionDecision.COMPLETED,
            expected_reason_code="SOURCE_CYCLE_COMPLETED",
            expected_attempts=1,
            expected_reconnects=0,
            expected_continuity=_continuity(
                cycle_count=1,
                completed_cycle_count=1,
                processed_event_count=1,
            ),
            expected_persistence_event_count=2,
        ),
        DepthFaultScenario(
            scenario_id="disconnect_reconnect",
            description="A source disconnect is retried once and the canonical chain continues.",
            cycles=(disconnected, second_cycle),
            policy=BinanceDepthReconnectPolicy(max_reconnects=1, backoff_initial_seconds=0),
            expected_decision=DepthSessionDecision.COMPLETED,
            expected_reason_code="SOURCE_CYCLE_COMPLETED",
            expected_attempts=2,
            expected_reconnects=1,
            expected_continuity=_continuity(
                cycle_count=2,
                completed_cycle_count=1,
                processed_event_count=2,
                reconnect_count=1,
                source_failure_cycle_count=1,
            ),
            expected_persistence_event_count=4,
        ),
        DepthFaultScenario(
            scenario_id="gap_terminal_without_retry",
            description="A sequence gap is terminal when recovery retry is not explicitly enabled.",
            cycles=(gap_cycle,),
            policy=BinanceDepthReconnectPolicy(max_reconnects=1, backoff_initial_seconds=0),
            expected_decision=DepthSessionDecision.RECOVERY_REQUIRED,
            expected_reason_code="INGESTOR_REQUIRES_RECOVERY",
            expected_attempts=1,
            expected_reconnects=0,
            expected_continuity=_continuity(
                cycle_count=1,
                gap_event_count=1,
                processed_event_count=2,
                recovery_required_cycle_count=1,
            ),
            expected_persistence_event_count=2,
        ),
        DepthFaultScenario(
            scenario_id="gap_recovered_with_opt_in",
            description="A sequence gap is recovered only with explicit bounded retry.",
            cycles=(gap_cycle, second_cycle),
            policy=BinanceDepthReconnectPolicy(
                max_reconnects=1,
                backoff_initial_seconds=0,
                retry_recovery=True,
            ),
            expected_decision=DepthSessionDecision.COMPLETED,
            expected_reason_code="SOURCE_CYCLE_COMPLETED",
            expected_attempts=2,
            expected_reconnects=1,
            expected_continuity=_continuity(
                cycle_count=2,
                completed_cycle_count=1,
                gap_event_count=1,
                processed_event_count=3,
                reconnect_count=1,
                recovery_required_cycle_count=1,
            ),
            expected_persistence_event_count=4,
        ),
        DepthFaultScenario(
            scenario_id="malformed_event_terminal",
            description="A malformed update enters recovery and is never converted into a fill or event.",
            cycles=(malformed_event_cycle,),
            policy=BinanceDepthReconnectPolicy(max_reconnects=1, backoff_initial_seconds=0),
            expected_decision=DepthSessionDecision.RECOVERY_REQUIRED,
            expected_reason_code="INGESTOR_REQUIRES_RECOVERY",
            expected_attempts=1,
            expected_reconnects=0,
            expected_continuity=_continuity(
                cycle_count=1,
                processed_event_count=2,
                recovery_required_cycle_count=1,
            ),
            expected_persistence_event_count=2,
        ),
        DepthFaultScenario(
            scenario_id="snapshot_rejected",
            description="An invalid snapshot is rejected before any canonical event is persisted.",
            cycles=(rejected_snapshot_cycle,),
            policy=BinanceDepthReconnectPolicy(max_reconnects=1, backoff_initial_seconds=0),
            expected_decision=DepthSessionDecision.SNAPSHOT_REJECTED,
            expected_reason_code="INVALID_DEPTH_SNAPSHOT:lastUpdateId must be a non-negative integer",
            expected_attempts=1,
            expected_reconnects=0,
            expected_continuity=_continuity(
                cycle_count=1,
                snapshot_rejected_cycle_count=1,
            ),
            expected_persistence_event_count=0,
        ),
        DepthFaultScenario(
            scenario_id="reconnect_budget_exhausted",
            description="A disconnect with no reconnect budget is an explicit exhausted observation.",
            cycles=(disconnected,),
            policy=BinanceDepthReconnectPolicy(max_reconnects=0, backoff_initial_seconds=0),
            expected_decision=DepthSessionDecision.EXHAUSTED,
            expected_reason_code="RECONNECT_BUDGET_EXHAUSTED",
            expected_attempts=1,
            expected_reconnects=0,
            expected_continuity=_continuity(
                cycle_count=1,
                processed_event_count=1,
                source_failure_cycle_count=1,
            ),
            expected_persistence_event_count=2,
        ),
    )


def _observed_case(
    scenario: DepthFaultScenario,
    *,
    run_root: Path,
    symbol: str,
) -> dict[str, Any]:
    sink = MarketEventSegmentSet(run_root / "segments", max_events_per_segment=2)
    ingestor = BinanceDepthIngestor(symbol, event_sink=sink)
    harness = BinanceDepthSoakHarness(
        ingestor,
        BinanceDepthTransportConfig(symbol, queue_size=2),
        scenario.cycles,
        policy=scenario.policy,
    )
    report = asyncio.run(harness.run())
    return {
        "scenario_id": scenario.scenario_id,
        "expected": {
            "decision": scenario.expected_decision.value,
            "reason_code": scenario.expected_reason_code,
            "attempts": scenario.expected_attempts,
            "reconnects": scenario.expected_reconnects,
            "continuity": dict(scenario.expected_continuity),
            "persistence_event_count": scenario.expected_persistence_event_count,
        },
        "observed": {
            "decision": report.session.decision.value,
            "reason_code": report.session.reason_code,
            "attempts": report.session.attempts,
            "reconnects": report.session.reconnects,
            "continuity": report.session.continuity_metrics(),
            "remaining_fixture_cycles": report.remaining_fixture_cycles,
            "chain": dict(report.chain_report),
            "persistence": dict(report.persistence_report or {}),
            "source_verified": report.source_verified,
        },
    }


def _case_errors(case: Mapping[str, Any]) -> list[str]:
    expected = case.get("expected")
    observed = case.get("observed")
    if not isinstance(expected, Mapping) or not isinstance(observed, Mapping):
        return ["case expected/observed objects are required"]
    errors: list[str] = []
    for key in ("decision", "reason_code", "attempts", "reconnects", "continuity"):
        if observed.get(key) != expected.get(key):
            errors.append(f"{key} mismatch")
    persistence = observed.get("persistence")
    if not isinstance(persistence, Mapping):
        errors.append("persistence report is missing")
    else:
        if persistence.get("valid") is not True:
            errors.append("persistence is not valid")
        if persistence.get("event_count") != expected.get("persistence_event_count"):
            errors.append("persistence event_count mismatch")
    chain = observed.get("chain")
    if not isinstance(chain, Mapping) or chain.get("valid") is not True:
        errors.append("canonical chain is not valid")
    elif chain.get("event_count") != expected.get("persistence_event_count"):
        errors.append("canonical chain event_count mismatch")
    if observed.get("remaining_fixture_cycles") != 0:
        errors.append("fixture budget was not fully consumed")
    if observed.get("source_verified") is not False:
        errors.append("source_verified must remain false")
    return errors


def run_binance_depth_fault_matrix(
    *,
    storage_root: str | Path,
    symbol: str = "BTCUSDT",
) -> dict[str, Any]:
    """Run every canonical fixture case in an isolated durable root."""

    normalized_symbol = str(symbol).strip().upper()
    if not normalized_symbol:
        raise ValueError("symbol must be non-empty")
    root = Path(storage_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    cases: list[dict[str, Any]] = []
    for scenario in build_binance_depth_fault_matrix(normalized_symbol):
        case_root = root / scenario.scenario_id
        case_root.mkdir()
        case = _observed_case(scenario, run_root=case_root, symbol=normalized_symbol)
        errors = _case_errors(case)
        case["description"] = scenario.description
        case["ok"] = not errors
        case["errors"] = errors
        cases.append(case)
    return {
        "schema_version": FAULT_MATRIX_SCHEMA_VERSION,
        "mode": "fixture",
        "environment": "offline",
        "symbol": normalized_symbol,
        "run_root": str(root),
        "case_count": len(cases),
        "cases": cases,
        "overall_ok": all(case["ok"] for case in cases),
        "source_verified": False,
        "execution_authority": False,
    }


def verify_binance_depth_fault_matrix(report: Mapping[str, Any]) -> tuple[bool, tuple[str, ...]]:
    """Verify a serialized matrix report without repairing or promoting it."""

    errors: list[str] = []
    if not isinstance(report, Mapping):
        return False, ("report must be an object",)
    if report.get("schema_version") != FAULT_MATRIX_SCHEMA_VERSION:
        errors.append("unsupported fault matrix schema")
    if report.get("mode") != "fixture" or report.get("environment") != "offline":
        errors.append("fault matrix must be offline fixture mode")
    if report.get("source_verified") is not False:
        errors.append("source_verified must remain false")
    if report.get("execution_authority") is not False:
        errors.append("execution_authority must remain false")
    cases = report.get("cases")
    if not isinstance(cases, list) or not cases:
        errors.append("cases must be a non-empty array")
    else:
        for index, case in enumerate(cases):
            case_errors = _case_errors(case) if isinstance(case, Mapping) else ["case must be an object"]
            if case_errors:
                errors.extend(f"case[{index}]: {error}" for error in case_errors)
            if isinstance(case, Mapping) and case.get("ok") is not True:
                errors.append(f"case[{index}]: case is not marked ok")
    if report.get("overall_ok") is not True:
        errors.append("overall_ok must be true")
    if not isinstance(cases, list) or report.get("case_count") != len(cases):
        errors.append("case_count mismatch")
    return not errors, tuple(errors)


__all__ = [
    "FAULT_MATRIX_SCHEMA_VERSION",
    "DepthFaultScenario",
    "build_binance_depth_fault_matrix",
    "run_binance_depth_fault_matrix",
    "verify_binance_depth_fault_matrix",
]
