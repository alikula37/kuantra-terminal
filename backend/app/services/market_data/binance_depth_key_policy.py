"""Local operator-key rotation and retention policy evaluation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .binance_depth_key_registry import (
    BinanceDepthAttestationKeyRegistry,
    OperatorKeyStatus,
)


KEY_POLICY_SCHEMA_VERSION = "BINANCE_DEPTH_ATTESTATION_KEY_POLICY_V1"
DEFAULT_MAX_ACTIVE_KEYS = 1
DEFAULT_MAX_ACTIVE_AGE_SECONDS = 90 * 24 * 60 * 60
DEFAULT_REVOKED_RETENTION_SECONDS = 365 * 24 * 60 * 60
DEFAULT_MAX_FUTURE_SKEW_SECONDS = 60.0


@dataclass(frozen=True)
class KeyRotationPolicyResult:
    """A point-in-time policy result; it does not mutate the registry."""

    schema_version: str
    evaluated_at: str
    valid: bool
    max_active_keys: int
    max_active_age_seconds: float
    revoked_retention_seconds: float
    active_key_ids: tuple[str, ...]
    revoked_key_ids: tuple[str, ...]
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "evaluated_at": self.evaluated_at,
            "valid": self.valid,
            "max_active_keys": self.max_active_keys,
            "max_active_age_seconds": self.max_active_age_seconds,
            "revoked_retention_seconds": self.revoked_retention_seconds,
            "active_key_ids": list(self.active_key_ids),
            "revoked_key_ids": list(self.revoked_key_ids),
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


def evaluate_key_rotation_policy(
    registry: BinanceDepthAttestationKeyRegistry,
    *,
    now: str | datetime | None = None,
    max_active_keys: int = DEFAULT_MAX_ACTIVE_KEYS,
    max_active_age_seconds: float = DEFAULT_MAX_ACTIVE_AGE_SECONDS,
    revoked_retention_seconds: float = DEFAULT_REVOKED_RETENTION_SECONDS,
    max_future_skew_seconds: float = DEFAULT_MAX_FUTURE_SKEW_SECONDS,
) -> KeyRotationPolicyResult:
    """Evaluate single-active-key, age and append-only retention obligations."""

    if isinstance(max_active_keys, bool) or not isinstance(max_active_keys, int) or max_active_keys < 1:
        raise ValueError("max_active_keys must be a positive integer")
    _validate_window(max_active_age_seconds, "max_active_age_seconds")
    _validate_window(revoked_retention_seconds, "revoked_retention_seconds")
    _validate_window(max_future_skew_seconds, "max_future_skew_seconds")

    evaluated_at = _coerce_timestamp(now) if now is not None else datetime.now(timezone.utc)
    active = [record for record in registry.records if record.status == OperatorKeyStatus.ACTIVE]
    revoked = [record for record in registry.records if record.status == OperatorKeyStatus.REVOKED]
    errors: list[str] = []
    warnings: list[str] = []
    recovery = registry.recovery_report()
    if recovery["valid"] is not True:
        errors.append("key registry recovery is not valid")
    if not active:
        errors.append("no active operator key is registered")
    if len(active) > max_active_keys:
        errors.append(f"active operator key count {len(active)} exceeds policy maximum {max_active_keys}")

    for record in active:
        created_at = _coerce_timestamp(record.created_at)
        age_seconds = (evaluated_at - created_at).total_seconds()
        if age_seconds < -max_future_skew_seconds:
            errors.append(f"active key {record.key_id} has a future created_at timestamp")
        elif age_seconds > max_active_age_seconds:
            errors.append(f"active key {record.key_id} exceeds maximum age")
        elif age_seconds < 0:
            warnings.append(f"active key {record.key_id} created_at is slightly ahead of local clock")

    for record in revoked:
        if record.revoked_at is None:
            errors.append(f"revoked key {record.key_id} has no revoked_at timestamp")
            continue
        revoked_at = _coerce_timestamp(record.revoked_at)
        age_seconds = (evaluated_at - revoked_at).total_seconds()
        if age_seconds < -max_future_skew_seconds:
            errors.append(f"revoked key {record.key_id} has a future revoked_at timestamp")
        elif age_seconds < 0:
            warnings.append(f"revoked key {record.key_id} revoked_at is slightly ahead of local clock")
        elif age_seconds < revoked_retention_seconds:
            warnings.append(
                f"revoked key {record.key_id} remains inside the configured retention window"
            )

    return KeyRotationPolicyResult(
        schema_version=KEY_POLICY_SCHEMA_VERSION,
        evaluated_at=_format_timestamp(evaluated_at),
        valid=not errors,
        max_active_keys=max_active_keys,
        max_active_age_seconds=max_active_age_seconds,
        revoked_retention_seconds=revoked_retention_seconds,
        active_key_ids=tuple(record.key_id for record in active),
        revoked_key_ids=tuple(record.key_id for record in revoked),
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


def _format_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


__all__ = [
    "DEFAULT_MAX_ACTIVE_AGE_SECONDS",
    "DEFAULT_MAX_ACTIVE_KEYS",
    "DEFAULT_MAX_FUTURE_SKEW_SECONDS",
    "DEFAULT_REVOKED_RETENTION_SECONDS",
    "KEY_POLICY_SCHEMA_VERSION",
    "KeyRotationPolicyResult",
    "evaluate_key_rotation_policy",
]
