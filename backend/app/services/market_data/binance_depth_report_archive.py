"""Local-first append-only archive for verified Binance depth soak reports."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from app.db.repositories.evidence_ledger_repo import canonical_json

from .binance_depth_report import verify_depth_soak_report


ARCHIVE_SCHEMA_VERSION = "BINANCE_DEPTH_SOAK_ARCHIVE_V1"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_REPORT_NAME_RE = re.compile(r"^report-[0-9a-f]{64}\.json$")


class DepthSoakArchiveError(ValueError):
    """Archive or recovery failure; no unverified report is accepted."""


@dataclass(frozen=True)
class DepthSoakArchiveRecord:
    schema_version: str
    report_id: str
    report_sha256: str
    report_path: str
    mode: str
    environment: str
    symbol: str
    verdict: str
    archived_at: str
    source_verified: bool = False
    execution_authority: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "report_id": self.report_id,
            "report_sha256": self.report_sha256,
            "report_path": self.report_path,
            "mode": self.mode,
            "environment": self.environment,
            "symbol": self.symbol,
            "verdict": self.verdict,
            "archived_at": self.archived_at,
            "source_verified": self.source_verified,
            "execution_authority": self.execution_authority,
        }


class BinanceDepthReportArchive:
    """Single-writer report archive with hash-addressed JSON and JSONL manifest."""

    def __init__(self, root: str | Path, *, strict: bool = True):
        self.root = Path(root)
        self.reports_root = self.root / "reports"
        self.manifest_path = self.root / "manifest.jsonl"
        self.reports_root.mkdir(parents=True, exist_ok=True)
        self._records: list[DepthSoakArchiveRecord] = []
        self._by_sha256: dict[str, DepthSoakArchiveRecord] = {}
        self._recovery_errors: list[str] = []
        self._load_existing()
        if strict and self._recovery_errors:
            raise DepthSoakArchiveError("; ".join(self._recovery_errors))

    @property
    def records(self) -> tuple[DepthSoakArchiveRecord, ...]:
        return tuple(self._records)

    @property
    def record_count(self) -> int:
        return len(self._records)

    def get_record(self, identifier: str) -> DepthSoakArchiveRecord:
        """Resolve one archived report by full SHA-256 or short report id."""

        normalized = str(identifier).strip().lower()
        matches = [
            record
            for record in self._records
            if record.report_sha256 == normalized or record.report_id == normalized
        ]
        if len(matches) != 1:
            raise DepthSoakArchiveError("archived report identifier was not found or is ambiguous")
        return matches[0]

    def archive(self, report: Mapping[str, Any]) -> DepthSoakArchiveRecord:
        """Verify and append one report; identical hashes are idempotent."""

        verification = verify_depth_soak_report(report)
        if not verification.ok:
            raise DepthSoakArchiveError(
                "report verification failed: " + "; ".join(verification.errors)
            )
        report_bytes = (canonical_json(dict(report)) + "\n").encode("utf-8")
        report_sha256 = hashlib.sha256(report_bytes).hexdigest()
        existing = self._by_sha256.get(report_sha256)
        if existing is not None:
            self._assert_report_file(existing, report_bytes)
            return existing

        mode = str(report["mode"])
        environment = str(report["environment"])
        symbol = str(report["symbol"])
        report_path = self.reports_root / f"report-{report_sha256}.json"
        relative_path = report_path.relative_to(self.root).as_posix()
        record = DepthSoakArchiveRecord(
            schema_version=ARCHIVE_SCHEMA_VERSION,
            report_id=report_sha256[:16],
            report_sha256=report_sha256,
            report_path=relative_path,
            mode=mode,
            environment=environment,
            symbol=symbol,
            verdict=verification.verdict.value,
            archived_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        )
        self._write_new_report(report_path, report_bytes)
        self._append_manifest(record)
        self._records.append(record)
        self._by_sha256[report_sha256] = record
        return record

    def recovery_report(self) -> dict[str, Any]:
        return {
            "valid": not self._recovery_errors,
            "root": str(self.root),
            "manifest": str(self.manifest_path),
            "record_count": self.record_count,
            "report_count": len(list(self.reports_root.glob("report-*.json"))),
            "errors": list(self._recovery_errors),
        }

    def _load_existing(self) -> None:
        if not self.manifest_path.exists():
            report_files = list(self.reports_root.glob("report-*.json"))
            if report_files:
                self._recovery_errors.append("report files exist without manifest.jsonl")
            return
        try:
            raw_lines = self.manifest_path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError) as exc:
            self._recovery_errors.append(f"manifest read failed: {exc}")
            return
        referenced: set[str] = set()
        for line_number, raw_line in enumerate(raw_lines, start=1):
            try:
                record = self._decode_record(json.loads(raw_line))
                if record.report_sha256 in self._by_sha256:
                    raise DepthSoakArchiveError("duplicate report_sha256 in manifest")
                report_path = self._safe_report_path(record.report_path)
                report_bytes = report_path.read_bytes()
                if hashlib.sha256(report_bytes).hexdigest() != record.report_sha256:
                    raise DepthSoakArchiveError("report hash does not match manifest")
                report = json.loads(report_bytes.decode("utf-8"))
                verification = verify_depth_soak_report(report)
                if not verification.ok or verification.verdict.value != record.verdict:
                    raise DepthSoakArchiveError("archived report no longer passes verifier")
                if report.get("mode") != record.mode or report.get("symbol") != record.symbol:
                    raise DepthSoakArchiveError("manifest metadata does not match report")
                referenced.add(report_path.name)
                self._records.append(record)
                self._by_sha256[record.report_sha256] = record
            except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError, DepthSoakArchiveError) as exc:
                self._recovery_errors.append(f"manifest line {line_number}: {exc}")
                break
        actual = {path.name for path in self.reports_root.glob("report-*.json")}
        if actual != referenced:
            self._recovery_errors.append("report files and manifest references differ")

    def _decode_record(self, payload: Any) -> DepthSoakArchiveRecord:
        if not isinstance(payload, dict):
            raise DepthSoakArchiveError("manifest record must be an object")
        required = {
            "schema_version",
            "report_id",
            "report_sha256",
            "report_path",
            "mode",
            "environment",
            "symbol",
            "verdict",
            "archived_at",
            "source_verified",
            "execution_authority",
        }
        missing = required.difference(payload)
        if missing:
            raise DepthSoakArchiveError(f"manifest record missing: {', '.join(sorted(missing))}")
        sha256 = payload["report_sha256"]
        if not isinstance(sha256, str) or not _SHA256_RE.fullmatch(sha256):
            raise DepthSoakArchiveError("manifest report_sha256 is invalid")
        if payload["report_id"] != sha256[:16]:
            raise DepthSoakArchiveError("manifest report_id does not match report_sha256")
        if payload["schema_version"] != ARCHIVE_SCHEMA_VERSION:
            raise DepthSoakArchiveError("unsupported archive schema version")
        if payload["source_verified"] is not False or payload["execution_authority"] is not False:
            raise DepthSoakArchiveError("archive truth flags must remain false")
        return DepthSoakArchiveRecord(**payload)

    def _safe_report_path(self, relative_path: str) -> Path:
        if not isinstance(relative_path, str) or not relative_path.startswith("reports/"):
            raise DepthSoakArchiveError("report_path must stay under reports/")
        name = relative_path.removeprefix("reports/")
        if not _REPORT_NAME_RE.fullmatch(name):
            raise DepthSoakArchiveError("report_path has unsafe filename")
        path = self.reports_root / name
        if path.parent != self.reports_root:
            raise DepthSoakArchiveError("report_path escapes archive root")
        return path

    def _assert_report_file(self, record: DepthSoakArchiveRecord, report_bytes: bytes) -> None:
        path = self._safe_report_path(record.report_path)
        try:
            existing = path.read_bytes()
        except OSError as exc:
            raise DepthSoakArchiveError(f"idempotent report file missing: {exc}") from exc
        if existing != report_bytes:
            raise DepthSoakArchiveError("same report hash points to different bytes")

    @staticmethod
    def _write_new_report(path: Path, report_bytes: bytes) -> None:
        if path.exists():
            if path.read_bytes() != report_bytes:
                raise DepthSoakArchiveError("report path already contains different bytes")
            return
        fd, temporary_name = tempfile.mkstemp(prefix=".report-", suffix=".tmp", dir=path.parent)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(report_bytes)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if temporary.exists():
                temporary.unlink()

    def _append_manifest(self, record: DepthSoakArchiveRecord) -> None:
        line = (canonical_json(record.as_dict()) + "\n").encode("utf-8")
        with self.manifest_path.open("ab") as handle:
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())


__all__ = [
    "ARCHIVE_SCHEMA_VERSION",
    "BinanceDepthReportArchive",
    "DepthSoakArchiveError",
    "DepthSoakArchiveRecord",
]
