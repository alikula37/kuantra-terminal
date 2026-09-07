"""Fail-closed aggregation for repeated Binance depth soak observations.

This module consumes persisted V2 soak reports only.  It does not run a
network probe, repair a report, or promote source truth.  Every input is first
checked by the single-report verifier; invalid observations remain visible in
the series and make the series invalid.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any, Mapping, Sequence

from .binance_depth_report import (
    DepthSoakReportVerdict,
    verify_depth_soak_report,
)


SOAK_SERIES_SCHEMA_VERSION = "BINANCE_DEPTH_SOAK_SERIES_V1"
VALID_SERIES_VERDICT = "VALID_TESTNET_SERIES_UNVERIFIED"
INVALID_SERIES_VERDICT = "INVALID_TESTNET_SERIES"
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")


def _report_digest(report: Mapping[str, Any]) -> str:
    encoded = json.dumps(report, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round(numerator / denominator, 12)


def _extract_metrics(report: Mapping[str, Any]) -> dict[str, int | float]:
    session = report["session"]
    continuity = session["continuity"]
    return {
        "elapsed_ms": float(report["elapsed_ms"]),
        "processed_event_count": int(continuity["processed_event_count"]),
        "gap_event_count": int(continuity["gap_event_count"]),
        "cycle_count": int(continuity["cycle_count"]),
        "reconnect_count": int(continuity["reconnect_count"]),
        "recovery_required_cycle_count": int(continuity["recovery_required_cycle_count"]),
        "source_failure_cycle_count": int(continuity["source_failure_cycle_count"]),
    }


def _aggregate(observations: Sequence[Mapping[str, Any]]) -> dict[str, int | float | None]:
    included = [observation for observation in observations if observation.get("included") is True]
    total_elapsed_ms = sum(float(observation["metrics"]["elapsed_ms"]) for observation in included)
    total_events = sum(int(observation["metrics"]["processed_event_count"]) for observation in included)
    total_gaps = sum(int(observation["metrics"]["gap_event_count"]) for observation in included)
    total_cycles = sum(int(observation["metrics"]["cycle_count"]) for observation in included)
    total_reconnects = sum(int(observation["metrics"]["reconnect_count"]) for observation in included)
    total_recovery_cycles = sum(
        int(observation["metrics"]["recovery_required_cycle_count"])
        for observation in included
    )
    total_source_failures = sum(
        int(observation["metrics"]["source_failure_cycle_count"])
        for observation in included
    )
    return {
        "total_elapsed_ms": round(total_elapsed_ms, 2),
        "total_processed_event_count": total_events,
        "total_gap_event_count": total_gaps,
        "total_cycle_count": total_cycles,
        "total_reconnect_count": total_reconnects,
        "total_recovery_required_cycle_count": total_recovery_cycles,
        "total_source_failure_cycle_count": total_source_failures,
        "gap_event_rate": _rate(total_gaps, total_events),
        "recovery_cycle_rate": _rate(total_recovery_cycles, total_cycles),
        "source_failure_cycle_rate": _rate(total_source_failures, total_cycles),
    }


def build_binance_depth_soak_series(
    reports: Sequence[Mapping[str, Any]],
    *,
    source_labels: Sequence[str] | None = None,
    expected_symbol: str | None = None,
    minimum_observations: int = 3,
) -> dict[str, Any]:
    """Build a strict testnet observation series from persisted reports."""

    if isinstance(reports, (str, bytes)) or not isinstance(reports, Sequence):
        raise ValueError("reports must be a sequence of report objects")
    if isinstance(minimum_observations, bool) or not isinstance(minimum_observations, int):
        raise ValueError("minimum_observations must be a positive integer")
    if minimum_observations <= 0:
        raise ValueError("minimum_observations must be a positive integer")
    normalized_expected_symbol = (
        str(expected_symbol).strip().upper() if expected_symbol is not None else None
    )
    if expected_symbol is not None and not normalized_expected_symbol:
        raise ValueError("expected_symbol must be non-empty when supplied")
    if source_labels is not None and len(source_labels) != len(reports):
        raise ValueError("source_labels length must match reports length")

    observations: list[dict[str, Any]] = []
    series_errors: list[str] = []
    included_symbols: set[str] = set()
    for index, report in enumerate(reports, start=1):
        label = str(source_labels[index - 1]) if source_labels is not None else f"observation-{index:03d}"
        if not isinstance(report, Mapping):
            observations.append(
                {
                    "observation_index": index,
                    "source": label,
                    "report_sha256": None,
                    "verification": {
                        "ok": False,
                        "verdict": "INVALID",
                        "errors": ["report must be an object"],
                        "warnings": [],
                    },
                    "included": False,
                    "metrics": None,
                    "errors": ["report must be an object"],
                }
            )
            continue

        verification = verify_depth_soak_report(
            report,
            expected_mode="testnet",
            require_durable=True,
        )
        observation: dict[str, Any] = {
            "observation_index": index,
            "source": label,
            "report_sha256": _report_digest(report),
            "verification": verification.as_dict(),
            "included": False,
            "metrics": None,
            "errors": list(verification.errors),
        }
        if verification.ok and verification.verdict is DepthSoakReportVerdict.VALID_TESTNET_OBSERVATION_UNVERIFIED:
            symbol = verification.symbol
            if normalized_expected_symbol is not None and symbol != normalized_expected_symbol:
                observation["errors"] = [
                    f"symbol does not match expected symbol {normalized_expected_symbol}"
                ]
                series_errors.append(f"observation {index}: symbol mismatch")
            else:
                included_symbols.add(symbol)
                observation["included"] = True
                observation["metrics"] = _extract_metrics(report)
        observations.append(observation)

    if len(included_symbols) > 1:
        series_errors.append("valid observations contain multiple symbols")
    symbol = normalized_expected_symbol or (next(iter(included_symbols)) if included_symbols else None)
    valid_count = sum(1 for observation in observations if observation["included"])
    invalid_count = len(observations) - valid_count
    if invalid_count:
        series_errors.append("one or more observations failed single-report verification")
    if valid_count < minimum_observations:
        series_errors.append(
            f"valid observation count {valid_count} is below minimum {minimum_observations}"
        )
    aggregate = _aggregate(observations)
    overall_ok = not series_errors
    return {
        "schema_version": SOAK_SERIES_SCHEMA_VERSION,
        "mode": "testnet_series",
        "environment": "testnet",
        "symbol": symbol,
        "minimum_observations": minimum_observations,
        "observation_count": len(observations),
        "valid_observation_count": valid_count,
        "invalid_observation_count": invalid_count,
        "observations": observations,
        "aggregate": aggregate,
        "series_errors": series_errors,
        "series_verdict": VALID_SERIES_VERDICT if overall_ok else INVALID_SERIES_VERDICT,
        "overall_ok": overall_ok,
        "source_verified": False,
        "execution_authority": False,
    }


def _same_number(actual: Any, expected: float | int | None) -> bool:
    if expected is None:
        return actual is None
    if isinstance(actual, bool) or not isinstance(actual, (int, float)):
        return False
    return math.isclose(float(actual), float(expected), rel_tol=0.0, abs_tol=1e-12)


def verify_binance_depth_soak_series(report: Mapping[str, Any]) -> tuple[bool, tuple[str, ...]]:
    """Verify series aggregates and inclusion decisions without repairing them."""

    errors: list[str] = []
    if not isinstance(report, Mapping):
        return False, ("series report must be an object",)
    if report.get("schema_version") != SOAK_SERIES_SCHEMA_VERSION:
        errors.append("unsupported soak series schema")
    if report.get("mode") != "testnet_series" or report.get("environment") != "testnet":
        errors.append("series must be testnet_series/testnet")
    if report.get("source_verified") is not False:
        errors.append("source_verified must remain false")
    if report.get("execution_authority") is not False:
        errors.append("execution_authority must remain false")
    minimum = report.get("minimum_observations")
    if isinstance(minimum, bool) or not isinstance(minimum, int) or minimum <= 0:
        errors.append("minimum_observations must be a positive integer")
        minimum = 1
    observations = report.get("observations")
    if not isinstance(observations, list):
        errors.append("observations must be an array")
        observations = []
    if report.get("observation_count") != len(observations):
        errors.append("observation_count mismatch")

    valid_count = 0
    derived_observations: list[dict[str, Any]] = []
    symbols: set[str] = set()
    for index, observation in enumerate(observations, start=1):
        if not isinstance(observation, Mapping):
            errors.append(f"observation[{index}] must be an object")
            continue
        verification = observation.get("verification")
        included = observation.get("included")
        metrics = observation.get("metrics")
        if not isinstance(verification, Mapping):
            errors.append(f"observation[{index}].verification must be an object")
            continue
        expected_digest = observation.get("report_sha256")
        if not isinstance(expected_digest, str) or not _HASH_RE.fullmatch(expected_digest):
            errors.append(f"observation[{index}].report_sha256 must be a SHA-256 digest")
        if included is True:
            valid_count += 1
            symbols.add(str(verification.get("symbol")))
            if verification.get("ok") is not True or verification.get("verdict") != DepthSoakReportVerdict.VALID_TESTNET_OBSERVATION_UNVERIFIED.value:
                errors.append(f"observation[{index}] included without valid testnet verdict")
            if not isinstance(metrics, Mapping):
                errors.append(f"observation[{index}].metrics must be an object")
            else:
                required = (
                    "elapsed_ms",
                    "processed_event_count",
                    "gap_event_count",
                    "cycle_count",
                    "reconnect_count",
                    "recovery_required_cycle_count",
                    "source_failure_cycle_count",
                )
                if any(field not in metrics for field in required):
                    errors.append(f"observation[{index}].metrics is incomplete")
                else:
                    derived_observations.append(observation)
        elif included is not False:
            errors.append(f"observation[{index}].included must be boolean")

    invalid_count = len(observations) - valid_count
    if report.get("valid_observation_count") != valid_count:
        errors.append("valid_observation_count mismatch")
    if report.get("invalid_observation_count") != invalid_count:
        errors.append("invalid_observation_count mismatch")
    expected_symbol = report.get("symbol")
    if expected_symbol is not None and symbols and symbols != {expected_symbol}:
        errors.append("series symbol does not match included observations")
    if len(symbols) > 1:
        errors.append("included observations contain multiple symbols")

    aggregate = report.get("aggregate")
    if not isinstance(aggregate, Mapping):
        errors.append("aggregate must be an object")
        aggregate = {}
    expected_aggregate = _aggregate(derived_observations)
    for field, expected in expected_aggregate.items():
        if field not in aggregate or not _same_number(aggregate.get(field), expected):
            errors.append(f"aggregate.{field} mismatch")

    series_errors = report.get("series_errors")
    if not isinstance(series_errors, list) or any(not isinstance(error, str) for error in series_errors):
        errors.append("series_errors must be an array of strings")
        series_errors = []
    expected_overall = valid_count >= minimum and invalid_count == 0 and not series_errors
    if report.get("overall_ok") is not expected_overall:
        errors.append("overall_ok mismatch")
    expected_verdict = VALID_SERIES_VERDICT if expected_overall else INVALID_SERIES_VERDICT
    if report.get("series_verdict") != expected_verdict:
        errors.append("series_verdict mismatch")
    return not errors, tuple(errors)


__all__ = [
    "SOAK_SERIES_SCHEMA_VERSION",
    "VALID_SERIES_VERDICT",
    "INVALID_SERIES_VERDICT",
    "build_binance_depth_soak_series",
    "verify_binance_depth_soak_series",
]
