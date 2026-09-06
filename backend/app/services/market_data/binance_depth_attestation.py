"""Optional Ed25519 operator attestation for archived depth soak evidence."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from app.db.repositories.evidence_ledger_repo import canonical_json

from .binance_depth_report_archive import (
    BinanceDepthReportArchive,
    DepthSoakArchiveError,
    DepthSoakArchiveRecord,
)


ATTESTATION_SCHEMA_VERSION = "BINANCE_DEPTH_SOAK_ATTESTATION_V1"
KEY_BUNDLE_SCHEMA_VERSION = "BINANCE_DEPTH_ATTESTATION_KEY_V1"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ID_RE = re.compile(r"^[0-9a-f]{16}$")
_ATTESTATION_NAME_RE = re.compile(r"^attestation-[0-9a-f]{16}\.json$")


class DepthSoakAttestationError(ValueError):
    """Attestation, key or store validation failure."""


@dataclass(frozen=True)
class DepthSoakAttestation:
    schema_version: str
    attestation_id: str
    report_id: str
    report_sha256: str
    mode: str
    environment: str
    symbol: str
    verdict: str
    operator_label: str
    attested_at: str
    public_key_b64: str
    signature_b64: str
    source_verified: bool = False
    execution_authority: bool = False

    def signing_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "report_id": self.report_id,
            "report_sha256": self.report_sha256,
            "mode": self.mode,
            "environment": self.environment,
            "symbol": self.symbol,
            "verdict": self.verdict,
            "operator_label": self.operator_label,
            "attested_at": self.attested_at,
            "public_key_b64": self.public_key_b64,
            "source_verified": self.source_verified,
            "execution_authority": self.execution_authority,
            "execution_authority": self.execution_authority,
        }

    def signing_bytes(self) -> bytes:
        return canonical_json(self.signing_payload()).encode("utf-8")

    def as_dict(self) -> dict[str, Any]:
        return {
            **self.signing_payload(),
            "attestation_id": self.attestation_id,
            "signature_b64": self.signature_b64,
        }

    @classmethod
    def from_dict(cls, payload: Any) -> "DepthSoakAttestation":
        if not isinstance(payload, dict):
            raise DepthSoakAttestationError("attestation must be an object")
        required = {
            "schema_version",
            "attestation_id",
            "report_id",
            "report_sha256",
            "mode",
            "environment",
            "symbol",
            "verdict",
            "operator_label",
            "attested_at",
            "public_key_b64",
            "signature_b64",
            "source_verified",
            "execution_authority",
        }
        missing = required.difference(payload)
        if missing:
            raise DepthSoakAttestationError(f"attestation missing: {', '.join(sorted(missing))}")
        unknown = set(payload).difference(required)
        if unknown:
            raise DepthSoakAttestationError(f"attestation has unknown fields: {', '.join(sorted(unknown))}")
        attestation = cls(**payload)
        _validate_attestation_shape(attestation)
        return attestation


def generate_operator_key_bundle() -> dict[str, str]:
    """Generate a raw Ed25519 key bundle for explicit local operator use."""

    private_key = Ed25519PrivateKey.generate()
    private_raw = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_raw = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return {
        "schema_version": KEY_BUNDLE_SCHEMA_VERSION,
        "private_key_b64": _b64encode(private_raw),
        "public_key_b64": _b64encode(public_raw),
    }


def private_key_from_bundle(payload: Mapping[str, Any]) -> Ed25519PrivateKey:
    if payload.get("schema_version") != KEY_BUNDLE_SCHEMA_VERSION:
        raise DepthSoakAttestationError("unsupported key bundle schema")
    raw = _b64decode(payload.get("private_key_b64"), expected_length=32, field="private_key_b64")
    return Ed25519PrivateKey.from_private_bytes(raw)


def attest_archive_record(
    record: DepthSoakArchiveRecord,
    private_key: Ed25519PrivateKey,
    *,
    operator_label: str,
    attested_at: str | None = None,
) -> DepthSoakAttestation:
    """Sign only archive metadata; never sign or promote execution authority."""

    if not isinstance(private_key, Ed25519PrivateKey):
        raise DepthSoakAttestationError("private_key must be Ed25519PrivateKey")
    label = str(operator_label).strip()
    if not label or len(label) > 128 or any(ord(char) < 32 for char in label):
        raise DepthSoakAttestationError("operator_label must be 1..128 printable characters")
    timestamp = attested_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    public_key_b64 = _b64encode(
        private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
    )
    draft = DepthSoakAttestation(
        schema_version=ATTESTATION_SCHEMA_VERSION,
        attestation_id="0" * 16,
        report_id=record.report_id,
        report_sha256=record.report_sha256,
        mode=record.mode,
        environment=record.environment,
        symbol=record.symbol,
        verdict=record.verdict,
        operator_label=label,
        attested_at=timestamp,
        public_key_b64=public_key_b64,
        signature_b64="",
        source_verified=False,
        execution_authority=False,
    )
    attestation_id = hashlib.sha256(draft.signing_bytes()).hexdigest()[:16]
    signed = DepthSoakAttestation(
        **{**draft.__dict__, "attestation_id": attestation_id}
    )
    signature_b64 = _b64encode(private_key.sign(signed.signing_bytes()))
    return DepthSoakAttestation(**{**signed.__dict__, "signature_b64": signature_b64})


def verify_attestation(record: DepthSoakArchiveRecord, attestation: DepthSoakAttestation) -> bool:
    try:
        _validate_attestation_shape(attestation)
        if (
            attestation.report_id != record.report_id
            or attestation.report_sha256 != record.report_sha256
            or attestation.mode != record.mode
            or attestation.environment != record.environment
            or attestation.symbol != record.symbol
            or attestation.verdict != record.verdict
            or record.source_verified is not False
            or record.execution_authority is not False
        ):
            return False
        expected_id = hashlib.sha256(attestation.signing_bytes()).hexdigest()[:16]
        if expected_id != attestation.attestation_id:
            return False
        public_raw = _b64decode(attestation.public_key_b64, expected_length=32, field="public_key_b64")
        signature = _b64decode(attestation.signature_b64, expected_length=64, field="signature_b64")
        Ed25519PublicKey.from_public_bytes(public_raw).verify(signature, attestation.signing_bytes())
        return True
    except (DepthSoakAttestationError, InvalidSignature, ValueError, TypeError):
        return False


class BinanceDepthAttestationStore:
    """Store signed attestations next to an already verified report archive."""

    def __init__(self, archive: BinanceDepthReportArchive, *, strict: bool = True):
        self.archive = archive
        self.root = archive.root
        self.attestations_root = self.root / "attestations"
        self.manifest_path = self.root / "attestations.jsonl"
        self.attestations_root.mkdir(parents=True, exist_ok=True)
        self._attestations: list[DepthSoakAttestation] = []
        self._by_id: dict[str, DepthSoakAttestation] = {}
        self._recovery_errors: list[str] = []
        self._load_existing()
        if strict and self._recovery_errors:
            raise DepthSoakAttestationError("; ".join(self._recovery_errors))

    @property
    def attestations(self) -> tuple[DepthSoakAttestation, ...]:
        return tuple(self._attestations)

    def append(self, attestation: DepthSoakAttestation) -> DepthSoakAttestation:
        record = self.archive.get_record(attestation.report_sha256)
        if not verify_attestation(record, attestation):
            raise DepthSoakAttestationError("attestation does not verify against archived report")
        existing = self._by_id.get(attestation.attestation_id)
        if existing is not None:
            if existing.as_dict() != attestation.as_dict():
                raise DepthSoakAttestationError("attestation id was reused with different content")
            return existing
        path = self.attestations_root / f"attestation-{attestation.attestation_id}.json"
        relative_path = path.relative_to(self.root).as_posix()
        self._write_new_file(path, (canonical_json(attestation.as_dict()) + "\n").encode("utf-8"))
        manifest_payload = {"attestation_path": relative_path, **attestation.as_dict()}
        line = (canonical_json(manifest_payload) + "\n").encode("utf-8")
        with self.manifest_path.open("ab") as handle:
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())
        self._attestations.append(attestation)
        self._by_id[attestation.attestation_id] = attestation
        return attestation

    def recovery_report(self) -> dict[str, Any]:
        return {
            "valid": not self._recovery_errors,
            "root": str(self.root),
            "manifest": str(self.manifest_path),
            "attestation_count": len(self._attestations),
            "errors": list(self._recovery_errors),
        }

    def _load_existing(self) -> None:
        if not self.manifest_path.exists():
            if list(self.attestations_root.glob("attestation-*.json")):
                self._recovery_errors.append("attestation files exist without attestations.jsonl")
            return
        try:
            lines = self.manifest_path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError) as exc:
            self._recovery_errors.append(f"attestation manifest read failed: {exc}")
            return
        referenced: set[str] = set()
        for line_number, raw_line in enumerate(lines, start=1):
            try:
                payload = json.loads(raw_line)
                if not isinstance(payload, dict):
                    raise DepthSoakAttestationError("manifest entry must be an object")
                relative_path = payload.pop("attestation_path")
                attestation = DepthSoakAttestation.from_dict(payload)
                if attestation.attestation_id in self._by_id:
                    raise DepthSoakAttestationError("duplicate attestation_id")
                path = self._safe_path(relative_path)
                file_payload = json.loads(path.read_text(encoding="utf-8"))
                file_attestation = DepthSoakAttestation.from_dict(file_payload)
                if file_attestation.as_dict() != attestation.as_dict():
                    raise DepthSoakAttestationError("manifest and attestation file differ")
                record = self.archive.get_record(attestation.report_sha256)
                if not verify_attestation(record, attestation):
                    raise DepthSoakAttestationError("attestation signature is invalid")
                referenced.add(path.name)
                self._attestations.append(attestation)
                self._by_id[attestation.attestation_id] = attestation
            except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError, ValueError, DepthSoakAttestationError) as exc:
                self._recovery_errors.append(f"attestation manifest line {line_number}: {exc}")
                break
        actual = {path.name for path in self.attestations_root.glob("attestation-*.json")}
        if actual != referenced:
            self._recovery_errors.append("attestation files and manifest references differ")

    def _safe_path(self, relative_path: str) -> Path:
        if not isinstance(relative_path, str) or not relative_path.startswith("attestations/"):
            raise DepthSoakAttestationError("attestation_path must stay under attestations/")
        name = relative_path.removeprefix("attestations/")
        if not _ATTESTATION_NAME_RE.fullmatch(name):
            raise DepthSoakAttestationError("attestation_path has unsafe filename")
        return self.attestations_root / name

    @staticmethod
    def _write_new_file(path: Path, payload: bytes) -> None:
        if path.exists():
            if path.read_bytes() != payload:
                raise DepthSoakAttestationError("attestation path already contains different bytes")
            return
        fd, temporary_name = tempfile.mkstemp(prefix=".attestation-", suffix=".tmp", dir=path.parent)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if temporary.exists():
                temporary.unlink()


def _validate_attestation_shape(attestation: DepthSoakAttestation) -> None:
    if attestation.schema_version != ATTESTATION_SCHEMA_VERSION:
        raise DepthSoakAttestationError("unsupported attestation schema")
    if not _ID_RE.fullmatch(attestation.attestation_id):
        raise DepthSoakAttestationError("attestation_id is invalid")
    if not _ID_RE.fullmatch(attestation.report_id):
        raise DepthSoakAttestationError("report_id is invalid")
    if not _SHA256_RE.fullmatch(attestation.report_sha256):
        raise DepthSoakAttestationError("report_sha256 is invalid")
    if not attestation.operator_label or len(attestation.operator_label) > 128:
        raise DepthSoakAttestationError("operator_label is invalid")
    if any(ord(char) < 32 for char in attestation.operator_label):
        raise DepthSoakAttestationError("operator_label contains control characters")
    if attestation.source_verified is not False or attestation.execution_authority is not False:
        raise DepthSoakAttestationError("attestation truth flags must remain false")
    try:
        datetime.fromisoformat(attestation.attested_at.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise DepthSoakAttestationError("attested_at must be ISO-8601") from exc


def _b64encode(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def _b64decode(value: Any, *, expected_length: int, field: str) -> bytes:
    if not isinstance(value, str):
        raise DepthSoakAttestationError(f"{field} must be base64 text")
    try:
        decoded = base64.b64decode(value.encode("ascii"), validate=True)
    except (ValueError, UnicodeError) as exc:
        raise DepthSoakAttestationError(f"{field} is not valid base64") from exc
    if len(decoded) != expected_length:
        raise DepthSoakAttestationError(f"{field} has invalid length")
    return decoded


__all__ = [
    "ATTESTATION_SCHEMA_VERSION",
    "KEY_BUNDLE_SCHEMA_VERSION",
    "BinanceDepthAttestationStore",
    "DepthSoakAttestation",
    "DepthSoakAttestationError",
    "attest_archive_record",
    "generate_operator_key_bundle",
    "private_key_from_bundle",
    "verify_attestation",
]
