"""Fail-closed review gate for attested Binance depth observations."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .binance_depth_attestation import BinanceDepthAttestationStore
from .binance_depth_key_registry import BinanceDepthAttestationKeyRegistry
from .binance_depth_report_archive import BinanceDepthReportArchive


ATTESTATION_GATE_SCHEMA_VERSION = "BINANCE_DEPTH_ATTESTATION_GATE_V1"
DEFAULT_MAX_AGE_SECONDS = 24 * 60 * 60
DEFAULT_MAX_FUTURE_SKEW_SECONDS = 60.0


@dataclass(frozen=True)
class DepthAttestationGateResult:
    """A review eligibility result, never an execution or source-truth grant."""

    schema_version: str
    report_id: str
    report_sha256: str
    decision: str
    report_verdict: str
    attestation_id: str | None
    key_id: str | None
    key_status: str | None
    operator_label: str | None
    signature_valid: bool
    freshness_valid: bool
    age_seconds: float | None
    max_age_seconds: float
    source_verified: bool = False
    execution_authority: bool = False
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "report_id": self.report_id,
            "report_sha256": self.report_sha256,
            "decision": self.decision,
            "report_verdict": self.report_verdict,
            "attestation_id": self.attestation_id,
            "key_id": self.key_id,
            "key_status": self.key_status,
            "operator_label": self.operator_label,
            "signature_valid": self.signature_valid,
            "freshness_valid": self.freshness_valid,
            "age_seconds": self.age_seconds,
            "max_age_seconds": self.max_age_seconds,
            "source_verified": self.source_verified,
            "execution_authority": self.execution_authority,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


def evaluate_binance_depth_attestation_gate(
    archive: BinanceDepthReportArchive,
    attestation_store: BinanceDepthAttestationStore,
    key_registry: BinanceDepthAttestationKeyRegistry,
    report_identifier: str,
    *,
    attestation_id: str | None = None,
    now: str | datetime | None = None,
    max_age_seconds: float = DEFAULT_MAX_AGE_SECONDS,
    max_future_skew_seconds: float = DEFAULT_MAX_FUTURE_SKEW_SECONDS,
    require_testnet: bool = True,
) -> DepthAttestationGateResult:
    """Evaluate whether one attested observation is eligible for human review.

    The gate is deliberately narrower than a production truth gate: it requires
    a valid archive, an active registered operator key, a valid signature and a
    fresh timestamp. It never changes the report's ``source_verified`` or
    ``execution_authority`` flags.
    """

    _validate_window(max_age_seconds, "max_age_seconds")
    _validate_window(max_future_skew_seconds, "max_future_skew_seconds")
    record = archive.get_record(report_identifier)
    warnings = [
        "eligible_for_review is not source verification",
        "eligible_for_review does not authorize order submission",
    ]
    errors: list[str] = []
    if record.source_verified is not False:
        errors.append("archive source_verified must remain false")
    if record.execution_authority is not False:
        errors.append("archive execution_authority must remain false")
    if require_testnet and record.verdict != "VALID_TESTNET_OBSERVATION_UNVERIFIED":
        errors.append("report verdict is not a valid testnet observation")

    matches = [
        item
        for item in attestation_store.attestations
        if item.report_sha256 == record.report_sha256
        and (attestation_id is None or item.attestation_id == attestation_id)
    ]
    if not matches:
        errors.append("no attestation exists for the archived report")
        return _result(
            record,
            decision="REJECTED",
            attestation=None,
            key_status=None,
            key_id=None,
            operator_label=None,
            signature_valid=False,
            freshness_valid=False,
            age_seconds=None,
            max_age_seconds=max_age_seconds,
            errors=errors,
            warnings=warnings,
        )
    if len(matches) > 1:
        errors.append("multiple attestations match; provide an explicit attestation_id")
        return _result(
            record,
            decision="REJECTED",
            attestation=None,
            key_status=None,
            key_id=None,
            operator_label=None,
            signature_valid=False,
            freshness_valid=False,
            age_seconds=None,
            max_age_seconds=max_age_seconds,
            errors=errors,
            warnings=warnings,
        )

    attestation = matches[0]
    audit = key_registry.audit(record, attestation)
    if not audit.signature_valid:
        errors.append("attestation signature is invalid")
    if audit.status != "ACTIVE_KEY":
        errors.append(f"attestation key status is {audit.status}")
    if attestation.source_verified is not False:
        errors.append("attestation source_verified must remain false")
    if attestation.execution_authority is not False:
        errors.append("attestation execution_authority must remain false")

    now_value = _coerce_timestamp(now) if now is not None else datetime.now(timezone.utc)
    attested_at = _coerce_timestamp(attestation.attested_at)
    age_seconds = (now_value - attested_at).total_seconds()
    freshness_valid = 0 <= age_seconds <= max_age_seconds
    if age_seconds < -max_future_skew_seconds:
        errors.append("attestation timestamp is too far in the future")
        freshness_valid = False
    elif age_seconds < 0:
        warnings.append("attestation timestamp is slightly ahead of local clock")
        freshness_valid = True
    elif age_seconds > max_age_seconds:
        errors.append("attestation is older than the configured freshness window")
    if not freshness_valid and age_seconds >= 0 and age_seconds <= max_age_seconds:
        errors.append("attestation freshness check failed")

    decision = "ELIGIBLE_FOR_REVIEW" if not errors and freshness_valid else "REJECTED"
    return _result(
        record,
        decision=decision,
        attestation=attestation,
        key_status=audit.status,
        key_id=audit.key_id,
        operator_label=audit.operator_label,
        signature_valid=audit.signature_valid,
        freshness_valid=freshness_valid,
        age_seconds=age_seconds,
        max_age_seconds=max_age_seconds,
        errors=errors,
        warnings=warnings,
    )


def _result(
    record: Any,
    *,
    decision: str,
    attestation: Any,
    key_status: str | None,
    key_id: str | None,
    operator_label: str | None,
    signature_valid: bool,
    freshness_valid: bool,
    age_seconds: float | None,
    max_age_seconds: float,
    errors: list[str],
    warnings: list[str],
) -> DepthAttestationGateResult:
    return DepthAttestationGateResult(
        schema_version=ATTESTATION_GATE_SCHEMA_VERSION,
        report_id=record.report_id,
        report_sha256=record.report_sha256,
        decision=decision,
        report_verdict=record.verdict,
        attestation_id=attestation.attestation_id if attestation is not None else None,
        key_id=key_id,
        key_status=key_status,
        operator_label=operator_label,
        signature_valid=signature_valid,
        freshness_valid=freshness_valid,
        age_seconds=age_seconds,
        max_age_seconds=max_age_seconds,
        source_verified=False,
        execution_authority=False,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )


def _validate_window(value: float, field: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a finite non-negative number")
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{field} must be a finite non-negative number")


def _coerce_timestamp(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("timestamp must be ISO-8601") from exc
    else:
        raise ValueError("timestamp must be ISO-8601")
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return parsed.astimezone(timezone.utc)


__all__ = [
    "ATTESTATION_GATE_SCHEMA_VERSION",
    "DEFAULT_MAX_AGE_SECONDS",
    "DEFAULT_MAX_FUTURE_SKEW_SECONDS",
    "DepthAttestationGateResult",
    "evaluate_binance_depth_attestation_gate",
]
