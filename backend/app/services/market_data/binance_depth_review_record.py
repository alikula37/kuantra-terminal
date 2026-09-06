"""Signed, append-only operator review records for attested depth evidence."""

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
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from app.db.repositories.evidence_ledger_repo import canonical_json

from .binance_depth_attestation_gate import (
    ATTESTATION_GATE_SCHEMA_VERSION,
    DepthAttestationGateResult,
)
from .binance_depth_key_policy import KEY_POLICY_SCHEMA_VERSION, KeyRotationPolicyResult
from .binance_depth_key_registry import key_id_for_public_key
from .binance_depth_report_archive import BinanceDepthReportArchive, DepthSoakArchiveError


REVIEW_RECORD_SCHEMA_VERSION = "BINANCE_DEPTH_OPERATOR_REVIEW_V1"
_ID_RE = re.compile(r"^[0-9a-f]{16}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_REVIEW_NAME_RE = re.compile(r"^review-[0-9a-f]{16}\.json$")


class DepthReviewRecordError(ValueError):
    """Review record signing, validation or recovery failure."""


@dataclass(frozen=True)
class DepthOperatorReviewRecord:
    schema_version: str
    review_id: str
    report_id: str
    report_sha256: str
    attestation_id: str
    gate_result_sha256: str
    gate_decision: str
    gate_result: dict[str, Any]
    key_policy_sha256: str
    key_policy: dict[str, Any]
    reviewer_label: str
    reviewed_at: str
    retention_until: str
    key_id: str
    public_key_b64: str
    signature_b64: str
    source_verified: bool = False
    execution_authority: bool = False

    def signing_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "report_id": self.report_id,
            "report_sha256": self.report_sha256,
            "attestation_id": self.attestation_id,
            "gate_result_sha256": self.gate_result_sha256,
            "gate_decision": self.gate_decision,
            "gate_result": self.gate_result,
            "key_policy_sha256": self.key_policy_sha256,
            "key_policy": self.key_policy,
            "reviewer_label": self.reviewer_label,
            "reviewed_at": self.reviewed_at,
            "retention_until": self.retention_until,
            "key_id": self.key_id,
            "public_key_b64": self.public_key_b64,
            "source_verified": self.source_verified,
            "execution_authority": self.execution_authority,
        }

    def signing_bytes(self) -> bytes:
        return canonical_json(self.signing_payload()).encode("utf-8")

    def as_dict(self) -> dict[str, Any]:
        return {
            **self.signing_payload(),
            "review_id": self.review_id,
            "signature_b64": self.signature_b64,
        }

    @classmethod
    def from_dict(cls, payload: Any) -> "DepthOperatorReviewRecord":
        if not isinstance(payload, dict):
            raise DepthReviewRecordError("review record must be an object")
        required = {
            "schema_version",
            "review_id",
            "report_id",
            "report_sha256",
            "attestation_id",
            "gate_result_sha256",
            "gate_decision",
            "gate_result",
            "key_policy_sha256",
            "key_policy",
            "reviewer_label",
            "reviewed_at",
            "retention_until",
            "key_id",
            "public_key_b64",
            "signature_b64",
            "source_verified",
            "execution_authority",
        }
        missing = required.difference(payload)
        if missing:
            raise DepthReviewRecordError(f"review record missing: {', '.join(sorted(missing))}")
        unknown = set(payload).difference(required)
        if unknown:
            raise DepthReviewRecordError(f"review record has unknown fields: {', '.join(sorted(unknown))}")
        record = cls(**payload)
        _validate_record_shape(record)
        return record


def create_operator_review_record(
    gate_result: DepthAttestationGateResult,
    private_key: Ed25519PrivateKey,
    *,
    policy_result: KeyRotationPolicyResult,
    reviewer_label: str,
    reviewed_at: str | None = None,
    retention_until: str,
) -> DepthOperatorReviewRecord:
    """Sign a review acknowledgement only for an eligible gate result."""

    if not isinstance(gate_result, DepthAttestationGateResult):
        raise DepthReviewRecordError("gate_result must be DepthAttestationGateResult")
    if gate_result.decision != "ELIGIBLE_FOR_REVIEW":
        raise DepthReviewRecordError("only ELIGIBLE_FOR_REVIEW can be recorded")
    if gate_result.source_verified is not False or gate_result.execution_authority is not False:
        raise DepthReviewRecordError("gate truth flags must remain false")
    if not isinstance(policy_result, KeyRotationPolicyResult):
        raise DepthReviewRecordError("policy_result must be KeyRotationPolicyResult")
    if policy_result.valid is not True:
        raise DepthReviewRecordError("key policy must be valid before recording review")
    if not isinstance(private_key, Ed25519PrivateKey):
        raise DepthReviewRecordError("private_key must be Ed25519PrivateKey")
    label = _validate_label(reviewer_label)
    reviewed_value = _format_timestamp(_coerce_timestamp(reviewed_at or _now()))
    retention_value = _format_timestamp(_coerce_timestamp(retention_until))
    if _coerce_timestamp(retention_value) <= _coerce_timestamp(reviewed_value):
        raise DepthReviewRecordError("retention_until must be after reviewed_at")
    gate_payload = gate_result.as_dict()
    gate_hash = hashlib.sha256(canonical_json(gate_payload).encode("utf-8")).hexdigest()
    policy_payload = policy_result.as_dict()
    policy_hash = hashlib.sha256(canonical_json(policy_payload).encode("utf-8")).hexdigest()
    public_key_b64 = _public_key_b64(private_key)
    draft = DepthOperatorReviewRecord(
        schema_version=REVIEW_RECORD_SCHEMA_VERSION,
        review_id="0" * 16,
        report_id=gate_result.report_id,
        report_sha256=gate_result.report_sha256,
        attestation_id=gate_result.attestation_id or "",
        gate_result_sha256=gate_hash,
        gate_decision=gate_result.decision,
        gate_result=gate_payload,
        key_policy_sha256=policy_hash,
        key_policy=policy_payload,
        reviewer_label=label,
        reviewed_at=reviewed_value,
        retention_until=retention_value,
        key_id=key_id_for_public_key(public_key_b64),
        public_key_b64=public_key_b64,
        signature_b64="",
    )
    review_id = hashlib.sha256(draft.signing_bytes()).hexdigest()[:16]
    signed = DepthOperatorReviewRecord(**{**draft.__dict__, "review_id": review_id})
    signature_b64 = base64.b64encode(private_key.sign(signed.signing_bytes())).decode("ascii")
    return DepthOperatorReviewRecord(**{**signed.__dict__, "signature_b64": signature_b64})


def verify_operator_review_record(record: DepthOperatorReviewRecord) -> bool:
    try:
        _validate_record_shape(record)
        gate_hash = hashlib.sha256(canonical_json(record.gate_result).encode("utf-8")).hexdigest()
        if gate_hash != record.gate_result_sha256:
            return False
        policy_hash = hashlib.sha256(canonical_json(record.key_policy).encode("utf-8")).hexdigest()
        if policy_hash != record.key_policy_sha256:
            return False
        expected_review_id = hashlib.sha256(record.signing_bytes()).hexdigest()[:16]
        if expected_review_id != record.review_id:
            return False
        public_raw = _b64decode(record.public_key_b64, expected_length=32, field="public_key_b64")
        signature = _b64decode(record.signature_b64, expected_length=64, field="signature_b64")
        Ed25519PublicKey.from_public_bytes(public_raw).verify(signature, record.signing_bytes())
        return True
    except (DepthReviewRecordError, InvalidSignature, ValueError, TypeError):
        return False


class BinanceDepthOperatorReviewStore:
    """Single-writer append-only review store under an existing archive root."""

    def __init__(self, archive: BinanceDepthReportArchive, *, strict: bool = True):
        self.archive = archive
        self.root = archive.root
        self.reviews_root = self.root / "reviews"
        self.manifest_path = self.root / "reviews.jsonl"
        self.reviews_root.mkdir(parents=True, exist_ok=True)
        self._records: list[DepthOperatorReviewRecord] = []
        self._by_id: dict[str, DepthOperatorReviewRecord] = {}
        self._recovery_errors: list[str] = []
        self._load_existing()
        if strict and self._recovery_errors:
            raise DepthReviewRecordError("; ".join(self._recovery_errors))

    @property
    def reviews(self) -> tuple[DepthOperatorReviewRecord, ...]:
        return tuple(self._records)

    def append(self, record: DepthOperatorReviewRecord) -> DepthOperatorReviewRecord:
        try:
            archive_record = self.archive.get_record(record.report_sha256)
        except DepthSoakArchiveError as exc:
            raise DepthReviewRecordError(str(exc)) from exc
        if archive_record.report_id != record.report_id:
            raise DepthReviewRecordError("review report_id does not match archive")
        if not verify_operator_review_record(record):
            raise DepthReviewRecordError("review record signature or gate snapshot is invalid")
        existing = self._by_id.get(record.review_id)
        if existing is not None:
            if existing.as_dict() != record.as_dict():
                raise DepthReviewRecordError("review_id was reused with different content")
            return existing
        path = self.reviews_root / f"review-{record.review_id}.json"
        relative_path = path.relative_to(self.root).as_posix()
        self._write_new_file(path, (canonical_json(record.as_dict()) + "\n").encode("utf-8"))
        manifest_payload = {"review_path": relative_path, **record.as_dict()}
        with self.manifest_path.open("ab") as handle:
            handle.write((canonical_json(manifest_payload) + "\n").encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
        self._records.append(record)
        self._by_id[record.review_id] = record
        return record

    def recovery_report(self) -> dict[str, Any]:
        return {
            "valid": not self._recovery_errors,
            "root": str(self.root),
            "manifest": str(self.manifest_path),
            "review_count": len(self._records),
            "errors": list(self._recovery_errors),
        }

    def _load_existing(self) -> None:
        if not self.manifest_path.exists():
            if list(self.reviews_root.glob("review-*.json")):
                self._recovery_errors.append("review files exist without reviews.jsonl")
            return
        try:
            lines = self.manifest_path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError) as exc:
            self._recovery_errors.append(f"review manifest read failed: {exc}")
            return
        referenced: set[str] = set()
        for line_number, raw_line in enumerate(lines, start=1):
            try:
                payload = json.loads(raw_line)
                if not isinstance(payload, dict):
                    raise DepthReviewRecordError("review manifest entry must be an object")
                relative_path = payload.pop("review_path")
                record = DepthOperatorReviewRecord.from_dict(payload)
                if record.review_id in self._by_id:
                    raise DepthReviewRecordError("duplicate review_id")
                path = self._safe_path(relative_path)
                file_record = DepthOperatorReviewRecord.from_dict(json.loads(path.read_text(encoding="utf-8")))
                if file_record.as_dict() != record.as_dict():
                    raise DepthReviewRecordError("manifest and review file differ")
                archive_record = self.archive.get_record(record.report_sha256)
                if archive_record.report_id != record.report_id or not verify_operator_review_record(record):
                    raise DepthReviewRecordError("review record is invalid against archive/signature")
                referenced.add(path.name)
                self._records.append(record)
                self._by_id[record.review_id] = record
            except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError, ValueError, DepthReviewRecordError) as exc:
                self._recovery_errors.append(f"review manifest line {line_number}: {exc}")
                break
        actual = {path.name for path in self.reviews_root.glob("review-*.json")}
        if actual != referenced:
            self._recovery_errors.append("review files and manifest references differ")

    def _safe_path(self, relative_path: str) -> Path:
        if not isinstance(relative_path, str) or not relative_path.startswith("reviews/"):
            raise DepthReviewRecordError("review_path must stay under reviews/")
        name = relative_path.removeprefix("reviews/")
        if not _REVIEW_NAME_RE.fullmatch(name):
            raise DepthReviewRecordError("review_path has unsafe filename")
        return self.reviews_root / name

    @staticmethod
    def _write_new_file(path: Path, payload: bytes) -> None:
        if path.exists():
            if path.read_bytes() != payload:
                raise DepthReviewRecordError("review path already contains different bytes")
            return
        fd, temporary_name = tempfile.mkstemp(prefix=".review-", suffix=".tmp", dir=path.parent)
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


def _validate_record_shape(record: DepthOperatorReviewRecord) -> None:
    if record.schema_version != REVIEW_RECORD_SCHEMA_VERSION:
        raise DepthReviewRecordError("unsupported review record schema")
    if not _ID_RE.fullmatch(record.review_id):
        raise DepthReviewRecordError("review_id is invalid")
    if not _ID_RE.fullmatch(record.report_id):
        raise DepthReviewRecordError("report_id is invalid")
    if not _SHA256_RE.fullmatch(record.report_sha256):
        raise DepthReviewRecordError("report_sha256 is invalid")
    if not _ID_RE.fullmatch(record.attestation_id):
        raise DepthReviewRecordError("attestation_id is invalid")
    if not _SHA256_RE.fullmatch(record.gate_result_sha256):
        raise DepthReviewRecordError("gate_result_sha256 is invalid")
    if not _SHA256_RE.fullmatch(record.key_policy_sha256):
        raise DepthReviewRecordError("key_policy_sha256 is invalid")
    if record.gate_decision != "ELIGIBLE_FOR_REVIEW":
        raise DepthReviewRecordError("gate_decision must be ELIGIBLE_FOR_REVIEW")
    if not isinstance(record.gate_result, dict):
        raise DepthReviewRecordError("gate_result must be an object")
    expected_gate_fields = set(DepthAttestationGateResult.__dataclass_fields__)
    if set(record.gate_result) != expected_gate_fields:
        raise DepthReviewRecordError("gate_result fields do not match gate schema")
    if record.gate_result.get("schema_version") != ATTESTATION_GATE_SCHEMA_VERSION:
        raise DepthReviewRecordError("gate_result schema is unsupported")
    if record.gate_result.get("decision") != "ELIGIBLE_FOR_REVIEW":
        raise DepthReviewRecordError("gate_result decision is not eligible")
    if record.gate_result.get("report_id") != record.report_id:
        raise DepthReviewRecordError("gate_result report_id does not match review")
    if record.gate_result.get("report_sha256") != record.report_sha256:
        raise DepthReviewRecordError("gate_result report_sha256 does not match review")
    if record.gate_result.get("attestation_id") != record.attestation_id:
        raise DepthReviewRecordError("gate_result attestation_id does not match review")
    if record.gate_result.get("signature_valid") is not True:
        raise DepthReviewRecordError("gate_result signature_valid must be true")
    if record.gate_result.get("freshness_valid") is not True:
        raise DepthReviewRecordError("gate_result freshness_valid must be true")
    if record.gate_result.get("key_status") != "ACTIVE_KEY":
        raise DepthReviewRecordError("gate_result key_status must be ACTIVE_KEY")
    if record.gate_result.get("report_verdict") != "VALID_TESTNET_OBSERVATION_UNVERIFIED":
        raise DepthReviewRecordError("gate_result report_verdict must be a testnet observation")
    if record.gate_result.get("source_verified") is not False:
        raise DepthReviewRecordError("gate_result source_verified must remain false")
    if record.gate_result.get("execution_authority") is not False:
        raise DepthReviewRecordError("gate_result execution_authority must remain false")
    if record.gate_result.get("errors") != []:
        raise DepthReviewRecordError("gate_result errors must be empty")
    if not isinstance(record.key_policy, dict):
        raise DepthReviewRecordError("key_policy must be an object")
    expected_policy_fields = set(KeyRotationPolicyResult.__dataclass_fields__)
    if set(record.key_policy) != expected_policy_fields:
        raise DepthReviewRecordError("key_policy fields do not match policy schema")
    if record.key_policy.get("schema_version") != KEY_POLICY_SCHEMA_VERSION:
        raise DepthReviewRecordError("key_policy schema is unsupported")
    if record.key_policy.get("valid") is not True:
        raise DepthReviewRecordError("key_policy valid must be true")
    if record.key_policy.get("errors") != []:
        raise DepthReviewRecordError("key_policy errors must be empty")
    if record.source_verified is not False or record.execution_authority is not False:
        raise DepthReviewRecordError("review truth flags must remain false")
    _validate_label(record.reviewer_label)
    reviewed_at = _coerce_timestamp(record.reviewed_at)
    retention_until = _coerce_timestamp(record.retention_until)
    if retention_until <= reviewed_at:
        raise DepthReviewRecordError("retention_until must be after reviewed_at")
    if not _ID_RE.fullmatch(record.key_id):
        raise DepthReviewRecordError("key_id is invalid")
    if key_id_for_public_key(record.public_key_b64) != record.key_id:
        raise DepthReviewRecordError("key_id does not match public key")
    _b64decode(record.public_key_b64, expected_length=32, field="public_key_b64")
    _b64decode(record.signature_b64, expected_length=64, field="signature_b64")


def _validate_label(value: Any) -> str:
    normalized = str(value).strip()
    if not normalized or len(normalized) > 128 or any(ord(char) < 32 for char in normalized):
        raise DepthReviewRecordError("reviewer_label must be 1..128 printable characters")
    return normalized


def _coerce_timestamp(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise DepthReviewRecordError("timestamp must be ISO-8601") from exc
    else:
        raise DepthReviewRecordError("timestamp must be ISO-8601")
    if parsed.tzinfo is None:
        raise DepthReviewRecordError("timestamp must include timezone")
    return parsed.astimezone(timezone.utc)


def _format_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _public_key_b64(private_key: Ed25519PrivateKey) -> str:
    return base64.b64encode(
        private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
    ).decode("ascii")


def _b64decode(value: Any, *, expected_length: int, field: str) -> bytes:
    if not isinstance(value, str):
        raise DepthReviewRecordError(f"{field} must be base64 text")
    try:
        decoded = base64.b64decode(value.encode("ascii"), validate=True)
    except (ValueError, UnicodeError) as exc:
        raise DepthReviewRecordError(f"{field} is invalid") from exc
    if len(decoded) != expected_length:
        raise DepthReviewRecordError(f"{field} must encode {expected_length} bytes")
    return decoded


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


__all__ = [
    "REVIEW_RECORD_SCHEMA_VERSION",
    "BinanceDepthOperatorReviewStore",
    "DepthOperatorReviewRecord",
    "DepthReviewRecordError",
    "create_operator_review_record",
    "verify_operator_review_record",
]
