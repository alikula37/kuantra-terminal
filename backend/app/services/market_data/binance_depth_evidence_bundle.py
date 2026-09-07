"""Deterministic backup/restore bundle for local Binance depth evidence."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from app.db.repositories.evidence_ledger_repo import canonical_json

from .binance_depth_attestation import BinanceDepthAttestationStore
from .binance_depth_key_registry import BinanceDepthAttestationKeyRegistry
from .binance_depth_report_archive import BinanceDepthReportArchive
from .binance_depth_review_record import BinanceDepthOperatorReviewStore


EVIDENCE_BUNDLE_SCHEMA_VERSION = "BINANCE_DEPTH_EVIDENCE_BUNDLE_V1"
BUNDLE_MANIFEST_NAME = "bundle-manifest.json"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_TIMESTAMP_RE = re.compile(r"Z$|[+-][0-9]{2}:[0-9]{2}$")
_PRIVATE_MARKERS = (
    b"private_key_b64",
    b"BEGIN PRIVATE KEY",
    b"BEGIN OPENSSH PRIVATE KEY",
)


class DepthEvidenceBundleError(ValueError):
    """Bundle creation, verification or restore failure."""


@dataclass(frozen=True)
class EvidenceBundleFile:
    path: str
    sha256: str
    size: int

    def as_dict(self) -> dict[str, Any]:
        return {"path": self.path, "sha256": self.sha256, "size": self.size}


@dataclass(frozen=True)
class DepthEvidenceBundleManifest:
    schema_version: str
    bundle_id: str
    created_at: str
    file_count: int
    files: tuple[EvidenceBundleFile, ...]
    registry_path: str | None
    contains_private_keys: bool = False
    source_verified: bool = False
    execution_authority: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "bundle_id": self.bundle_id,
            "created_at": self.created_at,
            "file_count": self.file_count,
            "files": [entry.as_dict() for entry in self.files],
            "registry_path": self.registry_path,
            "contains_private_keys": self.contains_private_keys,
            "source_verified": self.source_verified,
            "execution_authority": self.execution_authority,
        }


@dataclass(frozen=True)
class DepthEvidenceBundleVerification:
    valid: bool
    bundle_id: str | None
    file_count: int
    registry_path: str | None
    errors: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "bundle_id": self.bundle_id,
            "file_count": self.file_count,
            "registry_path": self.registry_path,
            "errors": list(self.errors),
        }


def create_evidence_bundle(
    archive_root: str | Path,
    output_path: str | Path,
    *,
    registry_path: str | Path | None = None,
    created_at: str | None = None,
) -> DepthEvidenceBundleManifest:
    """Create a deterministic zip bundle without private key material."""

    root = Path(archive_root)
    output = Path(output_path)
    if not root.is_dir():
        raise DepthEvidenceBundleError("archive_root must be an existing directory")
    timestamp = _format_timestamp(_coerce_timestamp(created_at or _now()))
    archive = BinanceDepthReportArchive(root)
    BinanceDepthAttestationStore(archive)
    BinanceDepthOperatorReviewStore(archive)
    registry_relative: str | None = None
    paths: list[tuple[str, Path]] = []
    for relative in ("manifest.jsonl", "attestations.jsonl", "reviews.jsonl"):
        candidate = root / relative
        if candidate.is_file():
            paths.append((relative, candidate))
    for directory in ("reports", "attestations", "reviews"):
        directory_path = root / directory
        if directory_path.is_dir():
            for candidate in sorted(directory_path.rglob("*")):
                if candidate.is_file() and not candidate.is_symlink():
                    paths.append((candidate.relative_to(root).as_posix(), candidate))
                elif candidate.is_symlink():
                    raise DepthEvidenceBundleError("symlinks are not allowed in evidence roots")
    if registry_path is not None:
        registry = Path(registry_path)
        if not registry.is_file():
            raise DepthEvidenceBundleError("registry_path must be an existing file")
        BinanceDepthAttestationKeyRegistry(registry)
        try:
            registry_relative = registry.relative_to(root).as_posix()
            paths.append((registry_relative, registry))
        except ValueError:
            registry_relative = f"registry/{registry.name}"
            paths.append((registry_relative, registry))
    entries = _build_entries(paths)
    bundle_id = _bundle_id(timestamp, entries, registry_relative)
    manifest = DepthEvidenceBundleManifest(
        schema_version=EVIDENCE_BUNDLE_SCHEMA_VERSION,
        bundle_id=bundle_id,
        created_at=timestamp,
        file_count=len(entries),
        files=tuple(entries),
        registry_path=registry_relative,
    )
    _write_bundle(output, manifest, paths)
    return manifest


def verify_evidence_bundle(bundle_path: str | Path) -> DepthEvidenceBundleVerification:
    """Verify zip safety, manifest hash, and absence of private key markers."""

    errors: list[str] = []
    bundle_id: str | None = None
    registry_path: str | None = None
    file_count = 0
    try:
        with zipfile.ZipFile(bundle_path, "r") as archive:
            names = archive.namelist()
            if len(names) != len(set(names)):
                raise DepthEvidenceBundleError("bundle contains duplicate paths")
            _validate_zip_names(names)
            if BUNDLE_MANIFEST_NAME not in names:
                raise DepthEvidenceBundleError("bundle-manifest.json is missing")
            manifest = _decode_manifest(archive.read(BUNDLE_MANIFEST_NAME))
            bundle_id = manifest.bundle_id
            registry_path = manifest.registry_path
            file_count = manifest.file_count
            expected = {entry.path: entry for entry in manifest.files}
            actual = {name for name in names if name != BUNDLE_MANIFEST_NAME}
            if actual != set(expected):
                raise DepthEvidenceBundleError("manifest file list differs from bundle entries")
            if manifest.contains_private_keys is not False:
                raise DepthEvidenceBundleError("bundle manifest permits private keys")
            for name, entry in expected.items():
                payload = archive.read(name)
                if _contains_private_key_marker(payload):
                    raise DepthEvidenceBundleError(f"private key marker found in {name}")
                if len(payload) != entry.size:
                    raise DepthEvidenceBundleError(f"size mismatch for {name}")
                if hashlib.sha256(payload).hexdigest() != entry.sha256:
                    raise DepthEvidenceBundleError(f"SHA-256 mismatch for {name}")
            expected_id = _bundle_id(manifest.created_at, manifest.files, manifest.registry_path)
            if expected_id != manifest.bundle_id:
                raise DepthEvidenceBundleError("bundle_id does not match manifest content")
    except (OSError, UnicodeError, zipfile.BadZipFile, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        errors.append(str(exc))
    return DepthEvidenceBundleVerification(
        valid=not errors,
        bundle_id=bundle_id,
        file_count=file_count,
        registry_path=registry_path,
        errors=tuple(errors),
    )


def restore_evidence_bundle(
    bundle_path: str | Path,
    target_root: str | Path,
) -> DepthEvidenceBundleVerification:
    """Restore into a new/empty directory and reopen all local stores strictly."""

    verification = verify_evidence_bundle(bundle_path)
    if not verification.valid:
        raise DepthEvidenceBundleError("bundle verification failed: " + "; ".join(verification.errors))
    target = Path(target_root)
    if target.exists() and any(target.iterdir()):
        raise DepthEvidenceBundleError("target_root must be empty or not exist")
    target.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(bundle_path, "r") as archive:
            for name in archive.namelist():
                if name == BUNDLE_MANIFEST_NAME:
                    continue
                destination = target / Path(name)
                destination.parent.mkdir(parents=True, exist_ok=True)
                with destination.open("wb") as handle:
                    handle.write(archive.read(name))
                    handle.flush()
                    os.fsync(handle.fileno())
        restored_archive = BinanceDepthReportArchive(target)
        BinanceDepthAttestationStore(restored_archive)
        BinanceDepthOperatorReviewStore(restored_archive)
        if verification.registry_path is not None:
            BinanceDepthAttestationKeyRegistry(target / Path(verification.registry_path))
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise DepthEvidenceBundleError(f"restored bundle failed strict recovery: {exc}") from exc
    return verification


def _build_entries(paths: Iterable[tuple[str, Path]]) -> list[EvidenceBundleFile]:
    by_name: dict[str, EvidenceBundleFile] = {}
    for relative, path in paths:
        _validate_relative_name(relative)
        if relative in by_name:
            raise DepthEvidenceBundleError(f"duplicate bundle path: {relative}")
        payload = path.read_bytes()
        if _contains_private_key_marker(payload):
            raise DepthEvidenceBundleError(f"private key marker found in {relative}")
        by_name[relative] = EvidenceBundleFile(
            path=relative,
            sha256=hashlib.sha256(payload).hexdigest(),
            size=len(payload),
        )
    return [by_name[name] for name in sorted(by_name)]


def _write_bundle(output: Path, manifest: DepthEvidenceBundleManifest, paths: list[tuple[str, Path]]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    payloads = {relative: path.read_bytes() for relative, path in paths}
    fd, temporary_name = tempfile.mkstemp(prefix=".evidence-bundle-", suffix=".zip", dir=output.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as raw:
            with zipfile.ZipFile(raw, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
                _write_zip_entry(archive, BUNDLE_MANIFEST_NAME, canonical_json(manifest.as_dict()).encode("utf-8") + b"\n")
                for relative in sorted(payloads):
                    _write_zip_entry(archive, relative, payloads[relative])
            raw.flush()
            os.fsync(raw.fileno())
        if output.exists():
            if output.read_bytes() != temporary.read_bytes():
                raise DepthEvidenceBundleError("output bundle already exists with different bytes")
            temporary.unlink()
        else:
            os.replace(temporary, output)
    finally:
        if temporary.exists():
            temporary.unlink()


def _write_zip_entry(archive: zipfile.ZipFile, name: str, payload: bytes) -> None:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 0
    info.external_attr = 0o600 << 16
    archive.writestr(info, payload)


def _decode_manifest(payload: bytes) -> DepthEvidenceBundleManifest:
    raw = json.loads(payload.decode("utf-8"))
    if not isinstance(raw, dict):
        raise DepthEvidenceBundleError("bundle manifest must be an object")
    required = {
        "schema_version",
        "bundle_id",
        "created_at",
        "file_count",
        "files",
        "registry_path",
        "contains_private_keys",
        "source_verified",
        "execution_authority",
    }
    if set(raw) != required:
        raise DepthEvidenceBundleError("bundle manifest fields do not match schema")
    if raw["schema_version"] != EVIDENCE_BUNDLE_SCHEMA_VERSION:
        raise DepthEvidenceBundleError("unsupported evidence bundle schema")
    if not isinstance(raw["bundle_id"], str) or not _SHA256_RE.fullmatch(raw["bundle_id"]):
        raise DepthEvidenceBundleError("bundle_id is invalid")
    _coerce_timestamp(raw["created_at"])
    if isinstance(raw["file_count"], bool) or not isinstance(raw["file_count"], int) or raw["file_count"] < 0:
        raise DepthEvidenceBundleError("file_count is invalid")
    if not isinstance(raw["files"], list):
        raise DepthEvidenceBundleError("files must be an array")
    entries: list[EvidenceBundleFile] = []
    for item in raw["files"]:
        if not isinstance(item, dict) or set(item) != {"path", "sha256", "size"}:
            raise DepthEvidenceBundleError("bundle file entry is invalid")
        _validate_relative_name(item["path"])
        if not isinstance(item["sha256"], str) or not _SHA256_RE.fullmatch(item["sha256"]):
            raise DepthEvidenceBundleError("bundle file SHA-256 is invalid")
        if isinstance(item["size"], bool) or not isinstance(item["size"], int) or item["size"] < 0:
            raise DepthEvidenceBundleError("bundle file size is invalid")
        entries.append(EvidenceBundleFile(item["path"], item["sha256"], item["size"]))
    if len(entries) != raw["file_count"] or len({entry.path for entry in entries}) != len(entries):
        raise DepthEvidenceBundleError("bundle file_count or paths are inconsistent")
    registry_path = raw["registry_path"]
    if registry_path is not None:
        _validate_relative_name(registry_path)
        if registry_path not in {entry.path for entry in entries}:
            raise DepthEvidenceBundleError("registry_path is not present in bundle files")
    if raw["contains_private_keys"] is not False:
        raise DepthEvidenceBundleError("contains_private_keys must remain false")
    if raw["source_verified"] is not False or raw["execution_authority"] is not False:
        raise DepthEvidenceBundleError("bundle truth flags must remain false")
    return DepthEvidenceBundleManifest(
        schema_version=raw["schema_version"],
        bundle_id=raw["bundle_id"],
        created_at=raw["created_at"],
        file_count=raw["file_count"],
        files=tuple(entries),
        registry_path=registry_path,
        contains_private_keys=False,
        source_verified=False,
        execution_authority=False,
    )


def _bundle_id(created_at: str, entries: Iterable[EvidenceBundleFile], registry_path: str | None) -> str:
    stable = {
        "schema_version": EVIDENCE_BUNDLE_SCHEMA_VERSION,
        "created_at": created_at,
        "registry_path": registry_path,
        "files": [entry.as_dict() for entry in entries],
    }
    return hashlib.sha256(canonical_json(stable).encode("utf-8")).hexdigest()


def _validate_zip_names(names: Iterable[str]) -> None:
    for name in names:
        if name == BUNDLE_MANIFEST_NAME:
            continue
        _validate_relative_name(name)


def _validate_relative_name(value: Any) -> None:
    if not isinstance(value, str) or not value or "\\" in value:
        raise DepthEvidenceBundleError("bundle path must be relative POSIX text")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise DepthEvidenceBundleError("bundle path escapes root")


def _contains_private_key_marker(payload: bytes) -> bool:
    return any(marker in payload for marker in _PRIVATE_MARKERS)


def _coerce_timestamp(value: str) -> datetime:
    if not isinstance(value, str) or not _TIMESTAMP_RE.search(value):
        raise DepthEvidenceBundleError("timestamp must be timezone-aware ISO-8601")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DepthEvidenceBundleError("timestamp must be timezone-aware ISO-8601") from exc
    if parsed.tzinfo is None:
        raise DepthEvidenceBundleError("timestamp must include timezone")
    return parsed.astimezone(timezone.utc)


def _format_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


__all__ = [
    "BUNDLE_MANIFEST_NAME",
    "EVIDENCE_BUNDLE_SCHEMA_VERSION",
    "DepthEvidenceBundleError",
    "DepthEvidenceBundleManifest",
    "DepthEvidenceBundleVerification",
    "EvidenceBundleFile",
    "create_evidence_bundle",
    "restore_evidence_bundle",
    "verify_evidence_bundle",
]
