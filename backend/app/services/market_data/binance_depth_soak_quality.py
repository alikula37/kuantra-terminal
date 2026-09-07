"""Quality/promotion gate for a validated Binance depth soak series.

The gate is intentionally narrower than source verification.  It answers only
whether a series satisfies explicit observation-quality thresholds for human
review.  It never authorizes orders and never changes truth flags.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any, Mapping

from .binance_depth_soak_series import (
    VALID_SERIES_VERDICT,
    verify_binance_depth_soak_series,
)


SERIES_QUALITY_GATE_SCHEMA_VERSION = "BINANCE_DEPTH_SOAK_SERIES_QUALITY_GATE_V1"
DEFAULT_MINIMUM_OBSERVATIONS = 3
DEFAULT_MINIMUM_ELAPSED_MS_PER_OBSERVATION = 300_000.0
DEFAULT_MINIMUM_PROCESSED_EVENTS_PER_OBSERVATION = 100
DEFAULT_MAX_GAP_EVENT_RATE = 0.0
DEFAULT_MAX_RECOVERY_CYCLE_RATE = 0.0
DEFAULT_MAX_SOURCE_FAILURE_CYCLE_RATE = 0.0
DEFAULT_MAX_INVALID_OBSERVATION_RATE = 0.0


def _digest(series: Mapping[str, Any]) -> str:
    encoded = json.dumps(series, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _validate_rate(value: float, field: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a finite rate between 0 and 1")
    if not math.isfinite(value) or value < 0 or value > 1:
        raise ValueError(f"{field} must be a finite rate between 0 and 1")


@dataclass(frozen=True)
class DepthSoakSeriesQualityPolicy:
    """Explicit thresholds for review eligibility of a testnet series."""

    minimum_observations: int = DEFAULT_MINIMUM_OBSERVATIONS
    minimum_elapsed_ms_per_observation: float = DEFAULT_MINIMUM_ELAPSED_MS_PER_OBSERVATION
    minimum_processed_events_per_observation: int = DEFAULT_MINIMUM_PROCESSED_EVENTS_PER_OBSERVATION
    max_gap_event_rate: float = DEFAULT_MAX_GAP_EVENT_RATE
    max_recovery_cycle_rate: float = DEFAULT_MAX_RECOVERY_CYCLE_RATE
    max_source_failure_cycle_rate: float = DEFAULT_MAX_SOURCE_FAILURE_CYCLE_RATE
    max_invalid_observation_rate: float = DEFAULT_MAX_INVALID_OBSERVATION_RATE

    def __post_init__(self) -> None:
        if (
            isinstance(self.minimum_observations, bool)
            or not isinstance(self.minimum_observations, int)
            or self.minimum_observations <= 0
        ):
            raise ValueError("minimum_observations must be a positive integer")
        if (
            isinstance(self.minimum_elapsed_ms_per_observation, bool)
            or not isinstance(self.minimum_elapsed_ms_per_observation, (int, float))
            or not math.isfinite(self.minimum_elapsed_ms_per_observation)
            or self.minimum_elapsed_ms_per_observation < 0
        ):
            raise ValueError("minimum_elapsed_ms_per_observation must be finite and non-negative")
        if (
            isinstance(self.minimum_processed_events_per_observation, bool)
            or not isinstance(self.minimum_processed_events_per_observation, int)
            or self.minimum_processed_events_per_observation < 0
        ):
            raise ValueError("minimum_processed_events_per_observation must be non-negative")
        for field in (
            "max_gap_event_rate",
            "max_recovery_cycle_rate",
            "max_source_failure_cycle_rate",
            "max_invalid_observation_rate",
        ):
            _validate_rate(getattr(self, field), field)

    def as_dict(self) -> dict[str, int | float]:
        return {
            "minimum_observations": self.minimum_observations,
            "minimum_elapsed_ms_per_observation": self.minimum_elapsed_ms_per_observation,
            "minimum_processed_events_per_observation": self.minimum_processed_events_per_observation,
            "max_gap_event_rate": self.max_gap_event_rate,
            "max_recovery_cycle_rate": self.max_recovery_cycle_rate,
            "max_source_failure_cycle_rate": self.max_source_failure_cycle_rate,
            "max_invalid_observation_rate": self.max_invalid_observation_rate,
        }


@dataclass(frozen=True)
class DepthSoakSeriesQualityGateResult:
    """Review eligibility result, never a market-truth or execution grant."""

    schema_version: str
    decision: str
    series_sha256: str
    series_verdict: str | None
    policy: DepthSoakSeriesQualityPolicy
    observation_count: int
    valid_observation_count: int
    invalid_observation_count: int
    aggregate: Mapping[str, Any]
    source_verified: bool = False
    execution_authority: bool = False
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "decision": self.decision,
            "series_sha256": self.series_sha256,
            "series_verdict": self.series_verdict,
            "policy": self.policy.as_dict(),
            "observation_count": self.observation_count,
            "valid_observation_count": self.valid_observation_count,
            "invalid_observation_count": self.invalid_observation_count,
            "aggregate": dict(self.aggregate),
            "source_verified": self.source_verified,
            "execution_authority": self.execution_authority,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


def evaluate_binance_depth_soak_series_quality(
    series: Mapping[str, Any],
    *,
    policy: DepthSoakSeriesQualityPolicy | None = None,
) -> DepthSoakSeriesQualityGateResult:
    """Evaluate explicit quality thresholds on one validated series report."""

    selected_policy = policy or DepthSoakSeriesQualityPolicy()
    structural_ok, structural_errors = verify_binance_depth_soak_series(series)
    errors = list(structural_errors)
    warnings = [
        "series quality eligibility is not source verification",
        "series quality eligibility does not authorize order submission",
    ]
    observations = series.get("observations", []) if isinstance(series, Mapping) else []
    if not isinstance(observations, list):
        observations = []
    aggregate = series.get("aggregate", {}) if isinstance(series, Mapping) else {}
    if not isinstance(aggregate, Mapping):
        aggregate = {}
    observation_count = int(series.get("observation_count", len(observations))) if isinstance(series, Mapping) and isinstance(series.get("observation_count", len(observations)), int) else len(observations)
    valid_count = int(series.get("valid_observation_count", 0)) if isinstance(series, Mapping) and isinstance(series.get("valid_observation_count", 0), int) else 0
    invalid_count = int(series.get("invalid_observation_count", 0)) if isinstance(series, Mapping) and isinstance(series.get("invalid_observation_count", 0), int) else 0
    series_verdict = series.get("series_verdict") if isinstance(series, Mapping) else None

    if structural_ok:
        if series_verdict != VALID_SERIES_VERDICT or series.get("overall_ok") is not True:
            errors.append("series is not a valid unverified testnet series")
        if valid_count < selected_policy.minimum_observations:
            errors.append(
                f"valid observation count {valid_count} is below policy minimum {selected_policy.minimum_observations}"
            )
        invalid_rate = invalid_count / observation_count if observation_count else 0.0
        if invalid_rate > selected_policy.max_invalid_observation_rate:
            errors.append(
                f"invalid observation rate {invalid_rate:.12f} exceeds policy maximum {selected_policy.max_invalid_observation_rate:.12f}"
            )
        for index, observation in enumerate(observations, start=1):
            if not isinstance(observation, Mapping) or observation.get("included") is not True:
                continue
            metrics = observation.get("metrics")
            if not isinstance(metrics, Mapping):
                errors.append(f"observation {index} metrics are missing")
                continue
            elapsed_ms = metrics.get("elapsed_ms")
            processed = metrics.get("processed_event_count")
            if not isinstance(elapsed_ms, (int, float)) or elapsed_ms < selected_policy.minimum_elapsed_ms_per_observation:
                errors.append(
                    f"observation {index} elapsed_ms is below policy minimum {selected_policy.minimum_elapsed_ms_per_observation}"
                )
            if not isinstance(processed, int) or processed < selected_policy.minimum_processed_events_per_observation:
                errors.append(
                    f"observation {index} processed events are below policy minimum {selected_policy.minimum_processed_events_per_observation}"
                )
        for field, maximum in (
            ("gap_event_rate", selected_policy.max_gap_event_rate),
            ("recovery_cycle_rate", selected_policy.max_recovery_cycle_rate),
            ("source_failure_cycle_rate", selected_policy.max_source_failure_cycle_rate),
        ):
            value = aggregate.get(field)
            numeric_value = 0.0 if value is None else value
            if not isinstance(numeric_value, (int, float)) or not math.isfinite(numeric_value):
                errors.append(f"aggregate.{field} is not a finite rate")
            elif numeric_value > maximum:
                errors.append(
                    f"aggregate.{field} {numeric_value:.12f} exceeds policy maximum {maximum:.12f}"
                )
    decision = "ELIGIBLE_FOR_REVIEW" if not errors else "REJECTED"
    return DepthSoakSeriesQualityGateResult(
        schema_version=SERIES_QUALITY_GATE_SCHEMA_VERSION,
        decision=decision,
        series_sha256=_digest(series) if isinstance(series, Mapping) else "0" * 64,
        series_verdict=series_verdict if isinstance(series_verdict, str) else None,
        policy=selected_policy,
        observation_count=observation_count,
        valid_observation_count=valid_count,
        invalid_observation_count=invalid_count,
        aggregate=aggregate,
        source_verified=False,
        execution_authority=False,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )


__all__ = [
    "SERIES_QUALITY_GATE_SCHEMA_VERSION",
    "DEFAULT_MINIMUM_OBSERVATIONS",
    "DEFAULT_MINIMUM_ELAPSED_MS_PER_OBSERVATION",
    "DEFAULT_MINIMUM_PROCESSED_EVENTS_PER_OBSERVATION",
    "DEFAULT_MAX_GAP_EVENT_RATE",
    "DEFAULT_MAX_RECOVERY_CYCLE_RATE",
    "DEFAULT_MAX_SOURCE_FAILURE_CYCLE_RATE",
    "DEFAULT_MAX_INVALID_OBSERVATION_RATE",
    "DepthSoakSeriesQualityPolicy",
    "DepthSoakSeriesQualityGateResult",
    "evaluate_binance_depth_soak_series_quality",
]
