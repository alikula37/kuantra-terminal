"""Append-only local registry and revocation state for attestation keys."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional

from app.db.repositories.evidence_ledger_repo import canonical_json

from .binance_depth_attestation import DepthSoakAttestation, verify_attestation
from .binance_depth_report_archive import DepthSoakArchiveError, DepthSoakArchiveRecord


KEY_REGISTRY_SCHEMA_VERSION = "BINANCE_DEPTH_ATTESTATION_KEY_REGISTRY_V1"
_ID_RE = re.compile(r"^[0-9a-f]{16}$")
_B64_RE = re.compile(r"^[A-Za-z0-9+/]+={0,2}$")


class DepthKeyRegistryError(ValueError):
    """Key registration/revocation or recovery failure."""


class OperatorKeyStatus(str):
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"


@dataclass(frozen=True)
class OperatorKeyRecord:
    schema_version: str
    key_id: str
    public_key_b64: str
    operator_label: str
    created_at: str
    status: str = OperatorKeyStatus.ACTIVE
    revoked_at: Optional[str] = None
    revocation_reason: Optional[str] = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "key_id": self.key_id,
            "public_key_b64": self.public_key_b64,
            "operator_label": self.operator_label,
            "created_at": self.created_at,
            "status": self.status,
            "revoked_at": self.revoked_at,
            "revocation_reason": self.revocation_reason,
        }


@dataclass(frozen=True)
class AttestationKeyAudit:
    key_id: str
    status: str
    signature_valid: bool
    operator_label: str
    errors: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "key_id": self.key_id,
            "status": self.status,
            "signature_valid": self.signature_valid,
            "operator_label": self.operator_label,
            "errors": list(self.errors),
        }


class BinanceDepthAttestationKeyRegistry:
    """Single-writer append-only registry; revoked keys cannot be reactivated."""

    def __init__(self, path: str | Path, *, strict: bool = True):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._records: dict[str, OperatorKeyRecord] = {}
        self._event_ids: set[str] = set()
        self._recovery_errors: list[str] = []
        self._load_existing()
        if strict and self._recovery_errors:
            raise DepthKeyRegistryError("; ".join(self._recovery_errors))

    @property
    def records(self) -> tuple[OperatorKeyRecord, ...]:
        return tuple(self._records.values())

    def get(self, identifier: str) -> OperatorKeyRecord:
        raw_identifier = str(identifier).strip()
        normalized = raw_identifier.lower()
        record = self._records.get(normalized)
        if record is None and not _ID_RE.fullmatch(normalized):
            # Base64 is case-sensitive; only the derived hex key id is lowered.
            key_id = key_id_for_public_key(raw_identifier)
            record = self._records.get(key_id)
        if record is None:
            raise DepthKeyRegistryError("operator key was not found")
        return record

    def register(
        self,
        public_key_b64: str,
        *,
        operator_label: str,
        recorded_at: Optional[str] = None,
    ) -> OperatorKeyRecord:
        public_raw = _decode_public_key(public_key_b64)
        label = _validate_label(operator_label)
        timestamp = _validate_timestamp(recorded_at or _now())
        key_id = hashlib.sha256(public_raw).hexdigest()[:16]
        existing = self._records.get(key_id)
        if existing is not None:
            if existing.public_key_b64 != public_key_b64 or existing.operator_label != label:
                raise DepthKeyRegistryError("key_id already exists with different key metadata")
            return existing
        event = self._event(
            event_type="REGISTER",
            key_id=key_id,
            public_key_b64=public_key_b64,
            operator_label=label,
            recorded_at=timestamp,
            revocation_reason=None,
        )
        self._append_event(event)
        record = OperatorKeyRecord(
            schema_version=KEY_REGISTRY_SCHEMA_VERSION,
            key_id=key_id,
            public_key_b64=public_key_b64,
            operator_label=label,
            created_at=timestamp,
        )
        self._records[key_id] = record
        self._event_ids.add(event["event_id"])
        return record

    def revoke(
        self,
        identifier: str,
        *,
        reason: str,
        revoked_at: Optional[str] = None,
    ) -> OperatorKeyRecord:
        record = self.get(identifier)
        if record.status == OperatorKeyStatus.REVOKED:
            return record
        timestamp = _validate_timestamp(revoked_at or _now())
        normalized_reason = _validate_reason(reason)
        event = self._event(
            event_type="REVOKE",
            key_id=record.key_id,
            public_key_b64=record.public_key_b64,
            operator_label=record.operator_label,
            recorded_at=timestamp,
            revocation_reason=normalized_reason,
        )
        self._append_event(event)
        revoked = replace(
            record,
            status=OperatorKeyStatus.REVOKED,
            revoked_at=timestamp,
            revocation_reason=normalized_reason,
        )
        self._records[record.key_id] = revoked
        self._event_ids.add(event["event_id"])
        return revoked

    def audit(
        self,
        record: DepthSoakArchiveRecord,
        attestation: DepthSoakAttestation,
    ) -> AttestationKeyAudit:
        key_id = key_id_for_public_key(attestation.public_key_b64)
        signature_valid = verify_attestation(record, attestation)
        registered = self._records.get(key_id)
        if registered is None:
            return AttestationKeyAudit(
                key_id=key_id,
                status="UNREGISTERED_KEY",
                signature_valid=signature_valid,
                operator_label=attestation.operator_label,
                errors=("public key is not registered",),
            )
        if registered.public_key_b64 != attestation.public_key_b64:
            return AttestationKeyAudit(
                key_id=key_id,
                status="KEY_METADATA_CONFLICT",
                signature_valid=False,
                operator_label=attestation.operator_label,
                errors=("registered public key does not match attestation",),
            )
        status = "REVOKED_KEY" if registered.status == OperatorKeyStatus.REVOKED else "ACTIVE_KEY"
        errors = () if signature_valid else ("attestation signature is invalid",)
        return AttestationKeyAudit(
            key_id=key_id,
            status=status,
            signature_valid=signature_valid,
            operator_label=registered.operator_label,
            errors=errors,
        )

    def recovery_report(self) -> dict[str, Any]:
        return {
            "valid": not self._recovery_errors,
            "path": str(self.path),
            "key_count": len(self._records),
            "event_count": len(self._event_ids),
            "errors": list(self._recovery_errors),
        }

    def _event(self, *, event_type: str, key_id: str, public_key_b64: str, operator_label: str, recorded_at: str, revocation_reason: Optional[str]) -> dict[str, Any]:
        stable = {
            "schema_version": KEY_REGISTRY_SCHEMA_VERSION,
            "event_type": event_type,
            "key_id": key_id,
            "public_key_b64": public_key_b64,
            "operator_label": operator_label,
            "recorded_at": recorded_at,
            "revocation_reason": revocation_reason,
        }
        event_id = hashlib.sha256(canonical_json(stable).encode("utf-8")).hexdigest()[:16]
        return {**stable, "event_id": event_id}

    def _append_event(self, event: Mapping[str, Any]) -> None:
        with self.path.open("ab") as handle:
            handle.write((canonical_json(dict(event)) + "\n").encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())

    def _load_existing(self) -> None:
        if not self.path.exists():
            return
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError) as exc:
            self._recovery_errors.append(f"registry read failed: {exc}")
            return
        for line_number, raw_line in enumerate(lines, start=1):
            try:
                event = json.loads(raw_line)
                self._apply_event(event)
            except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError, ValueError, DepthKeyRegistryError) as exc:
                self._recovery_errors.append(f"registry line {line_number}: {exc}")
                break

    def _apply_event(self, event: Any) -> None:
        if not isinstance(event, dict):
            raise DepthKeyRegistryError("registry event must be an object")
        required = {
            "schema_version",
            "event_id",
            "event_type",
            "key_id",
            "public_key_b64",
            "operator_label",
            "recorded_at",
            "revocation_reason",
        }
        if set(event) != required:
            raise DepthKeyRegistryError("registry event fields do not match schema")
        if event["schema_version"] != KEY_REGISTRY_SCHEMA_VERSION:
            raise DepthKeyRegistryError("unsupported registry schema")
        if event["event_id"] in self._event_ids:
            raise DepthKeyRegistryError("duplicate registry event_id")
        public_raw = _decode_public_key(event["public_key_b64"])
        key_id = hashlib.sha256(public_raw).hexdigest()[:16]
        if event["key_id"] != key_id or not _ID_RE.fullmatch(event["key_id"]):
            raise DepthKeyRegistryError("registry key_id does not match public key")
        _validate_label(event["operator_label"])
        _validate_timestamp(event["recorded_at"])
        stable = {key: event[key] for key in required if key != "event_id"}
        expected_event_id = hashlib.sha256(canonical_json(stable).encode("utf-8")).hexdigest()[:16]
        if event["event_id"] != expected_event_id:
            raise DepthKeyRegistryError("registry event_id does not match event content")
        current = self._records.get(key_id)
        if event["event_type"] == "REGISTER":
            if event["revocation_reason"] is not None or current is not None:
                raise DepthKeyRegistryError("invalid or duplicate REGISTER event")
            self._records[key_id] = OperatorKeyRecord(
                schema_version=KEY_REGISTRY_SCHEMA_VERSION,
                key_id=key_id,
                public_key_b64=event["public_key_b64"],
                operator_label=event["operator_label"],
                created_at=event["recorded_at"],
            )
        elif event["event_type"] == "REVOKE":
            if current is None or current.status == OperatorKeyStatus.REVOKED:
                raise DepthKeyRegistryError("invalid or duplicate REVOKE event")
            reason = _validate_reason(event["revocation_reason"])
            if current.operator_label != event["operator_label"] or current.public_key_b64 != event["public_key_b64"]:
                raise DepthKeyRegistryError("REVOKE metadata does not match REGISTER")
            self._records[key_id] = replace(
                current,
                status=OperatorKeyStatus.REVOKED,
                revoked_at=event["recorded_at"],
                revocation_reason=reason,
            )
        else:
            raise DepthKeyRegistryError("unsupported registry event_type")
        self._event_ids.add(event["event_id"])


def key_id_for_public_key(public_key_b64: str) -> str:
    return hashlib.sha256(_decode_public_key(public_key_b64)).hexdigest()[:16]


def _decode_public_key(value: Any) -> bytes:
    if not isinstance(value, str) or not _B64_RE.fullmatch(value):
        raise DepthKeyRegistryError("public_key_b64 must be base64 text")
    try:
        raw = base64.b64decode(value.encode("ascii"), validate=True)
    except (ValueError, UnicodeError) as exc:
        raise DepthKeyRegistryError("public_key_b64 is invalid") from exc
    if len(raw) != 32:
        raise DepthKeyRegistryError("public_key_b64 must encode 32 bytes")
    return raw


def _validate_label(label: Any) -> str:
    normalized = str(label).strip()
    if not normalized or len(normalized) > 128 or any(ord(char) < 32 for char in normalized):
        raise DepthKeyRegistryError("operator_label must be 1..128 printable characters")
    return normalized


def _validate_reason(reason: Any) -> str:
    normalized = str(reason).strip()
    if not normalized or len(normalized) > 256 or any(ord(char) < 32 for char in normalized):
        raise DepthKeyRegistryError("revocation_reason must be 1..256 printable characters")
    return normalized


def _validate_timestamp(value: Any) -> str:
    if not isinstance(value, str):
        raise DepthKeyRegistryError("timestamp must be ISO-8601 text")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DepthKeyRegistryError("timestamp must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise DepthKeyRegistryError("timestamp must include timezone")
    return value


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


__all__ = [
    "KEY_REGISTRY_SCHEMA_VERSION",
    "AttestationKeyAudit",
    "BinanceDepthAttestationKeyRegistry",
    "DepthKeyRegistryError",
    "OperatorKeyRecord",
    "OperatorKeyStatus",
    "key_id_for_public_key",
]
