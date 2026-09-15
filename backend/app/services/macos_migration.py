"""Safe, portable data migration bundles for moving Kuantra to macOS.

The migration format deliberately treats SQLite as the canonical user-data
source.  DuckDB is a rebuildable analytical projection and is therefore not
copied between machines.  Legacy encrypted credential rows are removed from
the migration snapshot; credentials must be re-entered into the destination
OS keychain.

The implementation is intentionally filesystem-only and cross-platform so a
Windows installation can create and verify a bundle before the destination
Mac is available.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import stat
import sqlite3
import tempfile
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterable

from app.core.input_limits import (
    MAX_ARCHIVE_BYTES,
    MAX_ARCHIVE_MEMBER_BYTES,
    MAX_ARCHIVE_MEMBERS,
    MAX_ARCHIVE_TOTAL_UNCOMPRESSED_BYTES,
)

BUNDLE_SCHEMA_VERSION = 1
BUNDLE_TYPE = "kuantra-macos-migration"
CURRENT_SQLITE_SCHEMA_VERSION = 7
LEGACY_SQLITE_SCHEMA_VERSION = 1
_SQLITE_RELATIVE_PATH = Path("data") / "kuantra_oltp.sqlite3"
_COLD_STORAGE_RELATIVE_ROOT = Path("data") / "cold_storage"
_SENSITIVE_SETTING_TOKENS = (
    "api_key",
    "api_secret",
    "apikey",
    "apisecret",
    "password",
    "passphrase",
    "private_key",
    "refresh_token",
    "secret",
    "token",
)


class MigrationBundleError(ValueError):
    """Raised when a migration bundle violates its safety contract."""


_LEGACY_TRADE_COLUMNS = frozenset(
    {"id", "symbol", "side", "entry_price", "qty", "entry_time", "status"}
)
_CURRENT_TRADE_COLUMNS = frozenset(
    {
        "id",
        "symbol",
        "side",
        "entry_price",
        "qty",
        "entry_time",
        "status",
        "commission",
        "created_at",
        "updated_at",
        "record_mode",
        "position_type",
        "execution_venue",
        "price_source",
        "price_source_symbol",
        "price_status",
        "price_observed_at",
        "price_origin",
        "leverage",
        "revision",
        "entry_time_source",
        "close_source",
        "tracking_started_at",
        "qty_unit",
    }
)
_LEDGER_COLUMNS = frozenset(
    {
        "event_id",
        "event_type",
        "account_id",
        "venue",
        "occurred_at_utc",
        "received_at_utc",
        "chain_date_utc",
        "chain_sequence",
        "schema_version",
        "adapter_version",
        "correlation_id",
        "idempotency_key",
        "request_fingerprint_sha256",
        "raw_payload_sha256",
        "normalized_payload_json",
        "provenance_json",
        "prev_hash",
        "event_hash",
    }
)
_PROJECTION_COLUMNS = frozenset(
    {
        "account_id",
        "venue",
        "trade_id",
        "symbol",
        "side",
        "entry_price",
        "qty",
        "status",
        "source_event_id",
        "source_event_hash",
        "snapshot_json",
    }
)
_KNOWN_ALEMBIC_REVISIONS = {
    "001_initial_baseline": LEGACY_SQLITE_SCHEMA_VERSION,
    "002_evidence_ledger": 2,
    "003_trade_projection": 3,
    "004_trade_quote_provenance": 4,
    "005_trade_position_type": 5,
    "006_trade_time_edit_sizing": 6,
    "007_trade_qty_unit": CURRENT_SQLITE_SCHEMA_VERSION,
}


def _table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    return {
        str(row[1])
        for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    }


def _inspect_sqlite_schema(conn: sqlite3.Connection) -> dict[str, Any]:
    """Classify the SQLite file without creating or changing any schema."""

    try:
        user_version = int(conn.execute("PRAGMA user_version").fetchone()[0])
    except (TypeError, ValueError, sqlite3.DatabaseError):
        user_version = 0

    revision: str | None = None
    if _table_exists(conn, "alembic_version"):
        rows = conn.execute("SELECT version_num FROM alembic_version").fetchall()
        if len(rows) != 1:
            return {
                "status": "unsupported",
                "reason": "SQLITE_SCHEMA_VERSION_MISSING_OR_AMBIGUOUS",
                "version": None,
                "alembic_revision": None,
                "sqlite_user_version": user_version,
            }
        revision = str(rows[0][0])
        if revision not in _KNOWN_ALEMBIC_REVISIONS:
            return {
                "status": "unsupported",
                "reason": "SQLITE_SCHEMA_VERSION_UNSUPPORTED",
                "version": None,
                "alembic_revision": revision,
                "sqlite_user_version": user_version,
            }

    if user_version > CURRENT_SQLITE_SCHEMA_VERSION:
        return {
            "status": "unsupported",
            "reason": "SQLITE_SCHEMA_VERSION_FUTURE",
            "version": user_version,
            "alembic_revision": revision,
            "sqlite_user_version": user_version,
        }

    trade_columns = _table_columns(conn, "trades") if _table_exists(conn, "trades") else set()
    missing_legacy = sorted(_LEGACY_TRADE_COLUMNS - trade_columns)
    if missing_legacy:
        return {
            "status": "unsupported",
            "reason": "SQLITE_SCHEMA_INCOMPATIBLE",
            "version": None,
            "alembic_revision": revision,
            "sqlite_user_version": user_version,
            "missing_trade_columns": missing_legacy,
        }

    ledger_columns = _table_columns(conn, "evidence_events") if _table_exists(conn, "evidence_events") else set()
    projection_columns = (
        _table_columns(conn, "evidence_trade_projections")
        if _table_exists(conn, "evidence_trade_projections")
        else set()
    )
    current_missing = sorted(
        (_CURRENT_TRADE_COLUMNS - trade_columns)
        | (_LEDGER_COLUMNS - ledger_columns)
        | (_PROJECTION_COLUMNS - projection_columns)
    )
    if not current_missing and _table_exists(conn, "evidence_events") and _table_exists(
        conn, "evidence_trade_projections"
    ):
        return {
            "status": "current",
            "reason": None,
            "version": CURRENT_SQLITE_SCHEMA_VERSION,
            "alembic_revision": revision,
            "sqlite_user_version": user_version,
        }

    # A baseline schema with the canonical trade identity can be upgraded by
    # the explicit staged upgrade below.  It is never silently upgraded by a
    # read-only bundle verifier.
    if revision in (None, "001_initial_baseline") and not ledger_columns and not projection_columns:
        return {
            "status": "legacy",
            "reason": "SQLITE_SCHEMA_UPGRADE_REQUIRED",
            "version": LEGACY_SQLITE_SCHEMA_VERSION,
            "alembic_revision": revision,
            "sqlite_user_version": user_version,
            "missing_current_columns": current_missing,
        }
    if (
        revision in (None, "002_evidence_ledger")
        and _LEDGER_COLUMNS.issubset(ledger_columns)
        and not projection_columns
    ):
        return {
            "status": "legacy",
            "reason": "SQLITE_SCHEMA_UPGRADE_REQUIRED",
            "version": 2,
            "alembic_revision": revision,
            "sqlite_user_version": user_version,
            "missing_current_columns": current_missing,
        }
    if (
        revision in (
            None,
            "003_trade_projection",
            "004_trade_quote_provenance",
            "005_trade_position_type",
            "006_trade_time_edit_sizing",
        )
        and user_version < CURRENT_SQLITE_SCHEMA_VERSION
        and set(current_missing).issubset({
            "record_mode", "execution_venue", "price_source", "price_source_symbol",
            "price_status", "price_observed_at", "price_origin", "position_type",
            "leverage", "revision", "entry_time_source", "close_source",
            "tracking_started_at", "qty_unit",
        })
        and _LEDGER_COLUMNS.issubset(ledger_columns)
        and _PROJECTION_COLUMNS.issubset(projection_columns)
    ):
        return {
            "status": "legacy",
            "reason": "SQLITE_SCHEMA_UPGRADE_REQUIRED",
            "version": _KNOWN_ALEMBIC_REVISIONS.get(revision, 4 if current_missing == ["position_type"] else 3),
            "alembic_revision": revision,
            "sqlite_user_version": user_version,
            "missing_current_columns": current_missing,
        }

    return {
        "status": "unsupported",
        "reason": "SQLITE_SCHEMA_INCOMPLETE",
        "version": None,
        "alembic_revision": revision,
        "sqlite_user_version": user_version,
        "missing_current_columns": current_missing,
    }


def _copy_sqlite_snapshot(source: Path, destination: Path) -> dict[str, Any]:
    """Copy a live SQLite database, including WAL state, without scrubbing it."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    source_conn = sqlite3.connect(str(source))
    target_conn = sqlite3.connect(str(destination))
    try:
        source_conn.execute("PRAGMA query_only = ON")
        source_conn.backup(target_conn)
        target_conn.commit()
        integrity = [row[0] for row in target_conn.execute("PRAGMA integrity_check").fetchall()]
        if integrity != ["ok"]:
            raise MigrationBundleError(f"SQLite snapshot failed integrity check: {integrity}")
        return {"integrity": "ok", "sha256": _sha256_file(destination)}
    finally:
        target_conn.close()
        source_conn.close()


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _is_sensitive_setting(key: str) -> bool:
    normalized = str(key).strip().lower().replace("-", "_")
    return any(token in normalized for token in _SENSITIVE_SETTING_TOKENS)


def _snapshot_sqlite(source: Path, destination: Path) -> dict[str, Any]:
    """Create a compact SQLite snapshot and remove credential material.

    ``Connection.backup`` is used instead of copying the live ``.sqlite3``
    file, so an existing WAL is folded into the snapshot.  The destination is
    VACUUMed after scrubbing to avoid leaving deleted secret pages in its
    freelist.
    """

    _copy_sqlite_snapshot(source, destination)
    target_conn = sqlite3.connect(str(destination))
    deleted_legacy_credentials = 0
    deleted_credential_refs = 0
    deleted_sensitive_settings = 0
    try:
        target_conn.execute("PRAGMA secure_delete = ON")

        if _table_exists(target_conn, "exchange_credentials"):
            result = target_conn.execute("DELETE FROM exchange_credentials")
            deleted_legacy_credentials = max(result.rowcount, 0)

        # Keychain references are machine-local pointers.  Copying Windows
        # references to macOS would make the destination appear configured
        # while pointing at a non-existent keychain entry.
        if _table_exists(target_conn, "exchange_credential_refs"):
            result = target_conn.execute("DELETE FROM exchange_credential_refs")
            deleted_credential_refs = max(result.rowcount, 0)

        if _table_exists(target_conn, "user_settings"):
            keys = [
                str(row[0])
                for row in target_conn.execute("SELECT key FROM user_settings").fetchall()
                if _is_sensitive_setting(str(row[0]))
            ]
            for key in keys:
                target_conn.execute("DELETE FROM user_settings WHERE key = ?", (key,))
            deleted_sensitive_settings = len(keys)

        target_conn.commit()
        target_conn.execute("VACUUM")
        integrity = [row[0] for row in target_conn.execute("PRAGMA integrity_check").fetchall()]
        if integrity != ["ok"]:
            raise MigrationBundleError(f"sanitized SQLite snapshot failed integrity check: {integrity}")
    finally:
        target_conn.close()

    return {
        "integrity": "ok",
        "deleted_legacy_credential_rows": deleted_legacy_credentials,
        "deleted_keychain_reference_rows": deleted_credential_refs,
        "deleted_sensitive_setting_rows": deleted_sensitive_settings,
        "wal_sidecar_included": False,
    }


def _projection_preflight(source: Path) -> dict[str, Any]:
    """Inspect exact legacy/projection coverage without mutating the source DB."""

    conn = sqlite3.connect(str(source))
    try:
        has_trades = _table_exists(conn, "trades")
        has_projection = _table_exists(conn, "evidence_trade_projections")
        has_events = _table_exists(conn, "evidence_events")
        trade_columns = _table_columns(conn, "trades") if has_trades else set()
        if has_trades and not _LEGACY_TRADE_COLUMNS.issubset(trade_columns):
            return {
                "ready": False,
                "reason": "TRADES_SCHEMA_INCOMPLETE",
                "trade_count": 0,
                "projected_count": 0,
                "missing_count": 0,
                "extra_count": 0,
                "duplicate_count": 0,
                "evidence_event_count": 0,
            }
        trade_count = int(conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]) if has_trades else 0
        event_count = int(conn.execute("SELECT COUNT(*) FROM evidence_events").fetchone()[0]) if has_events else 0
        if not has_trades:
            return {
                "ready": False,
                "reason": "TRADES_TABLE_MISSING",
                "trade_count": 0,
                "projected_count": 0,
                "missing_count": 0,
                "extra_count": 0,
                "duplicate_count": 0,
                "evidence_event_count": event_count,
            }
        if not has_projection:
            return {
                "ready": trade_count == 0,
                "reason": "PROJECTION_TABLE_MISSING" if trade_count else None,
                "trade_count": trade_count,
                "projected_count": 0,
                "missing_count": trade_count,
                "extra_count": 0,
                "duplicate_count": 0,
                "evidence_event_count": event_count,
            }
        projection_columns = _table_columns(conn, "evidence_trade_projections")
        if not _PROJECTION_COLUMNS.issubset(projection_columns):
            return {
                "ready": False,
                "reason": "PROJECTION_SCHEMA_INCOMPLETE",
                "trade_count": trade_count,
                "projected_count": 0,
                "missing_count": trade_count,
                "extra_count": 0,
                "duplicate_count": 0,
                "evidence_event_count": event_count,
            }

        scope = ("local-journal", "legacy")
        projected_count = int(conn.execute(
            """SELECT COUNT(DISTINCT trade_id)
               FROM evidence_trade_projections
               WHERE account_id = ? AND venue IN (?, ?)""",
            ("local-journal", *scope),
        ).fetchone()[0])
        duplicate_count = int(conn.execute(
            """SELECT COUNT(*) - COUNT(DISTINCT trade_id)
               FROM evidence_trade_projections
               WHERE account_id = ? AND venue IN (?, ?)""",
            ("local-journal", *scope),
        ).fetchone()[0])
        missing_count = int(conn.execute(
            """SELECT COUNT(*)
               FROM trades AS t
               WHERE NOT EXISTS (
                   SELECT 1 FROM evidence_trade_projections AS p
                   WHERE p.account_id = ? AND p.venue IN (?, ?) AND p.trade_id = t.id
               )""",
            ("local-journal", *scope),
        ).fetchone()[0])
        extra_count = int(conn.execute(
            """SELECT COUNT(DISTINCT p.trade_id)
               FROM evidence_trade_projections AS p
               WHERE p.account_id = ? AND p.venue IN (?, ?)
                 AND NOT EXISTS (SELECT 1 FROM trades AS t WHERE t.id = p.trade_id)""",
            ("local-journal", *scope),
        ).fetchone()[0])
        ready = not any((missing_count, extra_count, duplicate_count)) and projected_count == trade_count
        return {
            "ready": ready,
            "reason": None if ready else "PROJECTION_COVERAGE_INCOMPLETE",
            "trade_count": trade_count,
            "projected_count": projected_count,
            "missing_count": missing_count,
            "extra_count": extra_count,
            "duplicate_count": duplicate_count,
            "evidence_event_count": event_count,
            "account_id": "local-journal",
            "venues": list(scope),
        }
    finally:
        conn.close()


def _iter_cold_storage_files(source_root: Path) -> Iterable[tuple[Path, Path]]:
    cold_root = source_root / "cold_storage"
    if not cold_root.is_dir():
        return
    for path in sorted(cold_root.rglob("*")):
        if path.is_symlink():
            raise MigrationBundleError(f"cold storage symlink is not allowed: {path}")
        if not path.is_file():
            continue
        if path.suffix.lower() != ".parquet":
            continue
        relative = _COLD_STORAGE_RELATIVE_ROOT / path.relative_to(cold_root)
        yield path, relative


def _safe_bundle_member(name: str) -> bool:
    path = PurePosixPath(name)
    return bool(name) and not path.is_absolute() and ".." not in path.parts and not name.endswith("/")


def _manifest_file_entry(path: Path, relative: Path) -> dict[str, Any]:
    return {
        "path": relative.as_posix(),
        "size_bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def create_migration_bundle(
    source_data_dir: str | Path,
    output_bundle: str | Path,
    *,
    force: bool = False,
) -> dict[str, Any]:
    """Create a credential-safe, hash-addressed migration ZIP."""

    source_root = Path(source_data_dir).expanduser().resolve()
    output_path = Path(output_bundle).expanduser().resolve()
    source_db = source_root / "kuantra_oltp.sqlite3"
    if not source_root.is_dir():
        raise MigrationBundleError(f"source data directory does not exist: {source_root}")
    if not source_db.is_file():
        raise MigrationBundleError(f"canonical SQLite database is missing: {source_db}")
    try:
        output_path.relative_to(source_root)
    except ValueError:
        pass
    else:
        raise MigrationBundleError("output bundle must be outside the source data directory")
    if output_path.exists() and not force:
        raise MigrationBundleError(f"output bundle already exists: {output_path}; pass --force to replace it")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="kuantra-macos-migration-") as temp_dir:
        staging = Path(temp_dir)
        staged_db = staging / _SQLITE_RELATIVE_PATH
        sqlite_meta = _snapshot_sqlite(source_db, staged_db)
        sqlite_preflight = _verify_sqlite_snapshot(staged_db)
        projection_preflight = _projection_preflight(source_db)
        staged_files: list[tuple[Path, Path]] = [(staged_db, _SQLITE_RELATIVE_PATH)]

        for source_file, relative in _iter_cold_storage_files(source_root):
            staged_file = staging / relative
            staged_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_file, staged_file)
            staged_files.append((staged_file, relative))

        manifest: dict[str, Any] = {
            "bundle_type": BUNDLE_TYPE,
            "schema_version": BUNDLE_SCHEMA_VERSION,
            "created_at_utc": _utc_now(),
            "source_platform": platform.system().lower(),
            "source_architecture": platform.machine(),
            "credential_policy": "os_keychain_not_exported",
            "projection_policy": "duckdb_excluded_rebuild_from_sqlite",
            "projection_preflight": projection_preflight,
            "sqlite_preflight": sqlite_preflight,
            "sqlite": sqlite_meta,
            "files": [_manifest_file_entry(path, relative) for path, relative in staged_files],
            "excluded": [
                "kuantra_olap.duckdb and DuckDB WAL sidecars (rebuildable projection)",
                "SQLite WAL/SHM sidecars (folded into the sanitized SQLite snapshot)",
                "logs and telemetry queues (may contain sensitive operational data)",
                "plugins and models (executable/experimental content is not migration data)",
                "legacy encrypted credential values (removed from the snapshot)",
            ],
        }
        manifest_path = staging / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        temp_output = output_path.with_name(f".{output_path.name}.tmp-{os.getpid()}")
        try:
            with zipfile.ZipFile(temp_output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
                archive.write(manifest_path, "manifest.json")
                for path, relative in staged_files:
                    archive.write(path, relative.as_posix())
            if output_path.exists():
                output_path.unlink()
            os.replace(temp_output, output_path)
        finally:
            if temp_output.exists():
                temp_output.unlink()

    return {
        "valid": True,
        "bundle_path": str(output_path),
        "bundle_sha256": _sha256_file(output_path),
        "migration_ready": bool(
            manifest["projection_preflight"].get("ready")
            and manifest["sqlite_preflight"].get("valid")
        ),
        "manifest": manifest,
    }


def _read_manifest(archive: zipfile.ZipFile) -> dict[str, Any]:
    try:
        raw = archive.read("manifest.json")
        manifest = json.loads(raw.decode("utf-8"))
    except (KeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MigrationBundleError(f"manifest.json is missing or invalid: {exc}") from exc
    if not isinstance(manifest, dict):
        raise MigrationBundleError("manifest.json must contain an object")
    if manifest.get("bundle_type") != BUNDLE_TYPE:
        raise MigrationBundleError("unsupported migration bundle type")
    if manifest.get("schema_version") != BUNDLE_SCHEMA_VERSION:
        raise MigrationBundleError("unsupported migration bundle schema version")
    return manifest


def _verify_sqlite_snapshot(path: Path) -> dict[str, Any]:
    conn = sqlite3.connect(str(path))
    try:
        integrity = [row[0] for row in conn.execute("PRAGMA integrity_check").fetchall()]
        if integrity != ["ok"]:
            return {"valid": False, "reason": "SQLITE_INTEGRITY_FAILED", "integrity": integrity}
        schema = _inspect_sqlite_schema(conn)
        if schema.get("status") != "current":
            return {
                "valid": False,
                "reason": str(schema.get("reason") or "SQLITE_SCHEMA_UNSUPPORTED"),
                "integrity": "ok",
                "schema": schema,
            }
        legacy_rows = 0
        if _table_exists(conn, "exchange_credentials"):
            legacy_rows = int(conn.execute("SELECT COUNT(*) FROM exchange_credentials").fetchone()[0])
        keychain_refs = 0
        if _table_exists(conn, "exchange_credential_refs"):
            keychain_refs = int(conn.execute("SELECT COUNT(*) FROM exchange_credential_refs").fetchone()[0])
        sensitive_settings = []
        if _table_exists(conn, "user_settings"):
            sensitive_settings = [
                str(row[0])
                for row in conn.execute("SELECT key FROM user_settings").fetchall()
                if _is_sensitive_setting(str(row[0]))
            ]
        if legacy_rows or keychain_refs or sensitive_settings:
            return {
                "valid": False,
                "reason": "CREDENTIAL_MATERIAL_REMAINS",
                "legacy_credential_rows": legacy_rows,
                "keychain_reference_rows": keychain_refs,
                "sensitive_setting_keys": sensitive_settings,
            }
        event_count = 0
        if not _table_exists(conn, "evidence_events"):
            return {
                "valid": False,
                "reason": "EVIDENCE_LEDGER_TABLE_MISSING",
                "integrity": "ok",
                "schema": schema,
            }
        event_count = int(conn.execute("SELECT COUNT(*) FROM evidence_events").fetchone()[0])

        # Inspect the snapshot without running the application's bootstrap
        # schema initializer. Verification must not turn an incomplete or future
        # snapshot into a different database before deciding whether it is safe.
        from app.db.repositories.evidence_ledger_repo import EvidenceLedgerRepository

        ledger = EvidenceLedgerRepository(str(path), initialize_schema=False)
        chain = ledger.verify_chain()
        if not chain["valid"]:
            return {
                "valid": False,
                "reason": "EVIDENCE_CHAIN_INVALID",
                "integrity": "ok",
                "event_count": event_count,
                "ledger_integrity": chain,
                "schema": schema,
            }
        return {
            "valid": True,
            "integrity": "ok",
            "event_count": event_count,
            "ledger_integrity": chain,
            "schema": schema,
        }
    except (sqlite3.DatabaseError, OSError, ValueError) as exc:
        return {
            "valid": False,
            "reason": "SQLITE_SCHEMA_OR_READ_ERROR",
            "error": str(exc),
        }
    finally:
        conn.close()


def verify_migration_bundle(bundle_path: str | Path) -> dict[str, Any]:
    """Verify manifest, member hashes, archive safety and credential boundary."""

    bundle = Path(bundle_path).expanduser().resolve()
    errors: list[str] = []
    manifest: dict[str, Any] | None = None
    files_checked = 0
    sqlite_result: dict[str, Any] | None = None
    try:
        if not bundle.is_file():
            raise MigrationBundleError(f"migration bundle does not exist: {bundle}")
        if bundle.stat().st_size > MAX_ARCHIVE_BYTES:
            raise MigrationBundleError(
                f"archive size exceeds the safety limit of {MAX_ARCHIVE_BYTES} bytes"
            )
        with zipfile.ZipFile(bundle, "r") as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            resource_errors = []
            if len(infos) > MAX_ARCHIVE_MEMBERS:
                resource_errors.append(
                    f"archive member count exceeds the safety limit of {MAX_ARCHIVE_MEMBERS}"
                )
            total_uncompressed = 0
            for info in infos:
                if info.file_size < 0 or info.file_size > MAX_ARCHIVE_MEMBER_BYTES:
                    resource_errors.append(
                        f"archive member exceeds the safety limit of {MAX_ARCHIVE_MEMBER_BYTES}: {info.filename}"
                    )
                total_uncompressed += max(info.file_size, 0)
            if total_uncompressed > MAX_ARCHIVE_TOTAL_UNCOMPRESSED_BYTES:
                resource_errors.append(
                    "uncompressed archive size exceeds the safety limit of "
                    f"{MAX_ARCHIVE_TOTAL_UNCOMPRESSED_BYTES} bytes"
                )
            if resource_errors:
                errors.extend(resource_errors)
                raise MigrationBundleError("archive resource limits exceeded")
            if len(names) != len(set(names)):
                errors.append("duplicate archive members are not allowed")
            unsafe = [name for name in names if not _safe_bundle_member(name)]
            if unsafe:
                errors.append(f"unsafe archive members: {unsafe}")
            manifest = _read_manifest(archive)
            expected_files = manifest.get("files")
            if not isinstance(expected_files, list) or not expected_files:
                errors.append("manifest files list is empty")
                expected_files = []
            manifest_paths = [
                item.get("path")
                for item in expected_files
                if isinstance(item, dict) and isinstance(item.get("path"), str)
            ]
            if len(manifest_paths) != len(set(manifest_paths)):
                errors.append("manifest contains duplicate file paths")
            expected_names = {"manifest.json"}
            with tempfile.TemporaryDirectory(prefix="kuantra-macos-verify-") as temp_dir:
                temp_root = Path(temp_dir)
                for item in expected_files:
                    if not isinstance(item, dict) or not isinstance(item.get("path"), str):
                        errors.append("manifest contains an invalid file entry")
                        continue
                    name = item["path"]
                    expected_names.add(name)
                    if not _safe_bundle_member(name):
                        errors.append(f"unsafe manifest path: {name}")
                        continue
                    try:
                        info = archive.getinfo(name)
                        payload = archive.read(name)
                    except KeyError:
                        errors.append(f"manifest file is missing from archive: {name}")
                        continue
                    digest = hashlib.sha256(payload).hexdigest()
                    if digest != item.get("sha256") or len(payload) != item.get("size_bytes"):
                        errors.append(f"hash/size mismatch: {name}")
                    if info.is_dir():
                        errors.append(f"manifest member is a directory: {name}")
                    if ((info.external_attr >> 16) & 0o170000) == stat.S_IFLNK:
                        errors.append(f"manifest member is a symlink: {name}")
                    files_checked += 1
                    if name == _SQLITE_RELATIVE_PATH.as_posix():
                        extracted = temp_root / "kuantra_oltp.sqlite3"
                        extracted.write_bytes(payload)
                        sqlite_result = _verify_sqlite_snapshot(extracted)
                        if not sqlite_result.get("valid"):
                            errors.append(str(sqlite_result.get("reason", "invalid SQLite snapshot")))
                        else:
                            projection = _projection_preflight(extracted)
                            sqlite_result["projection_preflight"] = projection
            if sqlite_result is None:
                errors.append("canonical SQLite snapshot is missing from archive")
            unexpected = sorted(set(names) - expected_names)
            if unexpected:
                errors.append(f"unlisted archive members: {unexpected}")
    except (OSError, zipfile.BadZipFile, MigrationBundleError) as exc:
        errors.append(str(exc))

    return {
        "valid": not errors,
        "migration_ready": bool(
            not errors
            and sqlite_result
            and sqlite_result.get("valid")
            and sqlite_result.get("projection_preflight", {}).get("ready")
        ),
        "bundle_path": str(bundle),
        "bundle_sha256": _sha256_file(bundle) if bundle.is_file() else None,
        "files_checked": files_checked,
        "sqlite": sqlite_result,
        "manifest": manifest,
        "errors": errors,
    }


def _next_backup_path(target: Path) -> Path:
    stamp = time.strftime("%Y%m%d_%H%M%S", time.gmtime())
    candidate = target.with_name(f"{target.name}.pre-migration-{stamp}")
    counter = 1
    while candidate.exists():
        candidate = target.with_name(f"{target.name}.pre-migration-{stamp}-{counter}")
        counter += 1
    return candidate


def _next_upgrade_backup_path(target: Path) -> Path:
    stamp = time.strftime("%Y%m%d_%H%M%S", time.gmtime())
    candidate = target.with_name(f"{target.name}.pre-upgrade-{stamp}")
    counter = 1
    while candidate.exists():
        candidate = target.with_name(f"{target.name}.pre-upgrade-{stamp}-{counter}")
        counter += 1
    return candidate


def _sqlite_sidecar_paths(path: Path) -> tuple[Path, ...]:
    return tuple(path.with_name(path.name + suffix) for suffix in ("-wal", "-shm", "-journal"))


def _checkpoint_and_remove_sqlite_sidecars(path: Path) -> None:
    """Fold WAL state into a disposable staged DB before file promotion."""

    conn = sqlite3.connect(str(path))
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        conn.close()
    for sidecar in _sqlite_sidecar_paths(path):
        if sidecar.exists():
            sidecar.unlink()


def _move_sqlite_with_sidecars(source: Path, destination: Path) -> tuple[Path, ...]:
    """Move a SQLite file and its sidecars as one recoverable file set."""

    moved: list[tuple[Path, Path]] = []
    try:
        os.replace(source, destination)
        moved.append((destination, source))
        for sidecar in _sqlite_sidecar_paths(source):
            if sidecar.exists():
                destination_sidecar = destination.with_name(destination.name + sidecar.name[len(source.name):])
                os.replace(sidecar, destination_sidecar)
                moved.append((destination_sidecar, sidecar))
    except Exception:
        for moved_path, original_path in reversed(moved):
            if moved_path.exists():
                os.replace(moved_path, original_path)
        raise
    return tuple(moved_path for moved_path, _ in moved)


def _verify_upgrade_database(path: Path) -> dict[str, Any]:
    """Verify a current database while preserving credential rows."""

    conn = sqlite3.connect(str(path))
    try:
        integrity = [row[0] for row in conn.execute("PRAGMA integrity_check").fetchall()]
        schema = _inspect_sqlite_schema(conn)
    finally:
        conn.close()
    if integrity != ["ok"]:
        return {"valid": False, "reason": "SQLITE_INTEGRITY_FAILED", "integrity": integrity, "schema": schema}
    if schema.get("status") != "current":
        return {
            "valid": False,
            "reason": str(schema.get("reason") or "SQLITE_SCHEMA_UNSUPPORTED"),
            "integrity": "ok",
            "schema": schema,
        }

    from app.db.repositories.evidence_ledger_repo import EvidenceLedgerRepository

    ledger = EvidenceLedgerRepository(str(path), initialize_schema=False)
    chain = ledger.verify_chain()
    if not chain["valid"]:
        return {
            "valid": False,
            "reason": "EVIDENCE_CHAIN_INVALID",
            "integrity": "ok",
            "schema": schema,
            "ledger_integrity": chain,
        }
    projection = _projection_preflight(path)
    return {
        "valid": bool(projection.get("ready")),
        "reason": None if projection.get("ready") else str(projection.get("reason")),
        "integrity": "ok",
        "schema": schema,
        "ledger_integrity": chain,
        "projection_preflight": projection,
    }


def upgrade_sqlite_schema(
    db_path: str | Path,
    *,
    failure_injector: Callable[[str, Path], None] | None = None,
) -> dict[str, Any]:
    """Upgrade a supported legacy SQLite file through a staged atomic swap.

    The optional injector is a test-only failure boundary.  It is deliberately
    phase-labelled so tests can prove that a failed upgrade leaves the original
    database and its WAL sidecars untouched.
    """

    raw_target = Path(db_path).expanduser()
    if raw_target.is_symlink():
        raise MigrationBundleError(f"SQLite upgrade target cannot be a symlink: {raw_target}")
    target = raw_target.resolve()
    if not target.is_file():
        raise MigrationBundleError(f"SQLite upgrade target must be a regular file: {target}")

    try:
        source_conn = sqlite3.connect(str(target))
        try:
            source_integrity = [
                row[0] for row in source_conn.execute("PRAGMA integrity_check").fetchall()
            ]
            source_schema = _inspect_sqlite_schema(source_conn)
        finally:
            source_conn.close()
    except sqlite3.DatabaseError as exc:
        raise MigrationBundleError("SQLite preflight validation failed") from exc
    if source_integrity != ["ok"]:
        raise MigrationBundleError(f"SQLite preflight integrity failed: {source_integrity}")
    if source_schema.get("status") == "current":
        validation = _verify_upgrade_database(target)
        if not validation["valid"]:
            raise MigrationBundleError(
                "current SQLite database failed canonical validation: "
                + str(validation.get("reason"))
            )
        return {
            "valid": True,
            "status": "CURRENT",
            "changed": False,
            "target": str(target),
            "schema_before": source_schema,
            "schema_after": source_schema,
            "validation": validation,
        }
    if source_schema.get("status") != "legacy":
        raise MigrationBundleError(
            "SQLite schema upgrade is unsupported: "
            + str(source_schema.get("reason") or "unknown")
        )

    target.parent.mkdir(parents=True, exist_ok=True)
    work_dir = Path(tempfile.mkdtemp(prefix=f".{target.name}.upgrade-", dir=str(target.parent)))
    backup_snapshot = work_dir / "pre-upgrade.sqlite3"
    staged = work_dir / "staged.sqlite3"
    promoted_backup: Path | None = None
    try:
        _copy_sqlite_snapshot(target, backup_snapshot)
        try:
            backup_preflight_conn = sqlite3.connect(str(backup_snapshot))
            try:
                backup_schema = _inspect_sqlite_schema(backup_preflight_conn)
                backup_integrity = [
                    row[0]
                    for row in backup_preflight_conn.execute("PRAGMA integrity_check").fetchall()
                ]
            finally:
                backup_preflight_conn.close()
        except sqlite3.DatabaseError as exc:
            raise MigrationBundleError("pre-upgrade backup failed SQLite validation") from exc
        if backup_integrity != ["ok"] or backup_schema.get("status") != "legacy":
            raise MigrationBundleError("pre-upgrade backup failed schema/integrity verification")
        if failure_injector is not None:
            failure_injector("after_backup", backup_snapshot)

        _copy_sqlite_snapshot(backup_snapshot, staged)
        from app.db.sqlite_driver import SQLiteDriver

        SQLiteDriver(str(staged))
        staged_conn = sqlite3.connect(str(staged))
        try:
            if _table_exists(staged_conn, "alembic_version"):
                staged_conn.execute(
                    "UPDATE alembic_version SET version_num = ?",
                    ("007_trade_qty_unit",),
                )
            staged_conn.commit()
        finally:
            staged_conn.close()
        if failure_injector is not None:
            failure_injector("after_schema_upgrade", staged)

        from app.db.repositories.evidence_ledger_repo import EvidenceLedgerRepository
        from app.db.repositories.evidence_projection_repo import EvidenceTradeProjectionRepository

        ledger = EvidenceLedgerRepository(str(staged))
        backfill = ledger.backfill_legacy_trades(dry_run=False)
        if backfill.get("errors"):
            raise MigrationBundleError(
                "legacy evidence backfill failed: " + json.dumps(backfill["errors"], sort_keys=True)
            )
        if failure_injector is not None:
            failure_injector("after_backfill", staged)

        projection = EvidenceTradeProjectionRepository(str(staged))
        projection_rebuild = projection.rebuild(account_id=None, dry_run=False)
        if failure_injector is not None:
            failure_injector("after_projection_rebuild", staged)

        validation = _verify_upgrade_database(staged)
        if not validation["valid"]:
            raise MigrationBundleError(
                "staged SQLite database failed canonical validation: "
                + str(validation.get("reason"))
            )
        _checkpoint_and_remove_sqlite_sidecars(staged)
        if failure_injector is not None:
            failure_injector("before_promote", staged)

        promoted_backup = _next_upgrade_backup_path(target)
        _move_sqlite_with_sidecars(target, promoted_backup)
        try:
            os.replace(staged, target)
        except Exception:
            if promoted_backup.exists() and not target.exists():
                _move_sqlite_with_sidecars(promoted_backup, target)
            raise
    finally:
        if work_dir.exists():
            shutil.rmtree(work_dir, ignore_errors=True)

    schema_after_conn = sqlite3.connect(str(target))
    try:
        schema_after = _inspect_sqlite_schema(schema_after_conn)
    finally:
        schema_after_conn.close()
    return {
        "valid": True,
        "status": "UPGRADED",
        "changed": True,
        "target": str(target),
        "schema_before": source_schema,
        "schema_after": schema_after,
        "backup_path": str(promoted_backup) if promoted_backup else None,
        "backup_sha256": _sha256_file(promoted_backup) if promoted_backup else None,
        "backfill": backfill,
        "projection_rebuild": projection_rebuild,
        "validation": validation,
    }


def restore_migration_bundle(
    bundle_path: str | Path,
    target_data_dir: str | Path,
    *,
    force: bool = False,
) -> dict[str, Any]:
    """Restore a verified bundle through a staged, atomic directory promotion."""

    verification = verify_migration_bundle(bundle_path)
    if not verification["valid"]:
        raise MigrationBundleError("migration bundle verification failed: " + "; ".join(verification["errors"]))
    if not verification.get("migration_ready"):
        raise MigrationBundleError(
            "migration bundle is not ready: evidence projection coverage is incomplete; "
            "run the evidence backfill/projection rebuild on the source and recreate the bundle"
        )

    raw_target = Path(target_data_dir).expanduser()
    if raw_target.is_symlink():
        raise MigrationBundleError(f"target data directory cannot be a symlink: {raw_target}")
    target = raw_target.resolve()
    if target.exists() and not target.is_dir():
        raise MigrationBundleError(f"target data path is not a directory: {target}")
    if target.exists() and any(target.iterdir()) and not force:
        raise MigrationBundleError(
            f"target data directory is not empty: {target}; pass --force to move it aside safely"
        )

    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{target.name}.restore-", dir=str(target.parent)))
    existing_backup: Path | None = None
    restored_relative: list[PurePosixPath] = []
    try:
        with zipfile.ZipFile(Path(bundle_path).expanduser().resolve(), "r") as archive:
            manifest = _read_manifest(archive)
            for item in manifest["files"]:
                relative = PurePosixPath(item["path"])
                if not _safe_bundle_member(relative.as_posix()) or relative.parts[0] != "data":
                    raise MigrationBundleError(f"invalid restore path: {relative}")
                info = archive.getinfo(relative.as_posix())
                if info.is_dir() or ((info.external_attr >> 16) & 0o170000) == stat.S_IFLNK:
                    raise MigrationBundleError(f"archive member is not a regular file: {relative}")
                destination = staging.joinpath(*relative.parts[1:])
                destination.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(relative.as_posix(), "r") as source, destination.open("wb") as sink:
                    shutil.copyfileobj(source, sink)
                if destination.stat().st_size != item.get("size_bytes"):
                    raise MigrationBundleError(f"restored size mismatch: {relative}")
                if _sha256_file(destination) != item.get("sha256"):
                    raise MigrationBundleError(f"restored hash mismatch: {relative}")
                restored_relative.append(relative)

        staged_db = staging / "kuantra_oltp.sqlite3"
        staged_sqlite = _verify_sqlite_snapshot(staged_db)
        if not staged_sqlite.get("valid"):
            raise MigrationBundleError(
                "staged SQLite verification failed: "
                + str(staged_sqlite.get("reason", "unknown"))
            )
        staged_projection = _projection_preflight(staged_db)
        if not staged_projection.get("ready"):
            raise MigrationBundleError(
                "staged projection preflight failed: "
                + str(staged_projection.get("reason", "unknown"))
            )

        # Move the old target aside only after every archive member has been
        # extracted and verified. If promotion fails, restore that path and keep
        # the user's pre-restore directory recoverable.
        if target.exists():
            existing_backup = _next_backup_path(target)
            os.replace(target, existing_backup)
        try:
            os.replace(staging, target)
        except Exception:
            if existing_backup is not None and not target.exists():
                os.replace(existing_backup, target)
            raise
    except Exception:
        # A failed extraction never writes into the target. The staging directory
        # is disposable and is removed below; a forced target remains in place
        # until the final atomic promotion.
        raise
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)

    return {
        "valid": True,
        "migration_ready": bool(verification.get("migration_ready")),
        "target_data_dir": str(target),
        "restored_files": [str(target.joinpath(*relative.parts[1:])) for relative in restored_relative],
        "previous_target_backup": str(existing_backup) if existing_backup else None,
        "duckdb_rebuild_required": True,
        "credentials_reenter_required": True,
        "bundle_sha256": verification["bundle_sha256"],
    }


def rebuild_duckdb_projection(target_data_dir: str | Path) -> dict[str, Any]:
    """Rebuild DuckDB from a restored canonical SQLite database.

    The environment override is installed before importing the hydrator so its
    module-level singleton, if initialized, points at the same destination.
    Coverage remains an explicit fail-closed gate: an incomplete evidence
    projection must not be presented as a successful restore.
    """

    target = Path(target_data_dir).expanduser().resolve()
    sqlite_path = target / "kuantra_oltp.sqlite3"
    duckdb_path = target / "kuantra_olap.duckdb"
    if not sqlite_path.is_file():
        raise MigrationBundleError(f"restored SQLite database is missing: {sqlite_path}")

    previous_data_dir = os.environ.get("KUANTRA_DATA_DIR")
    os.environ["KUANTRA_DATA_DIR"] = str(target)
    try:
        try:
            from app.db.duckdb_hydrator import DuckDBHydrator
        except ImportError as exc:
            raise MigrationBundleError(
                "DuckDB dependencies are unavailable; install the locked backend environment before rebuilding"
            ) from exc

        result = DuckDBHydrator(
            duckdb_path=str(duckdb_path),
            sqlite_path=str(sqlite_path),
        ).hydrate_from_sqlite(force_rebuild=True)
    finally:
        if previous_data_dir is None:
            os.environ.pop("KUANTRA_DATA_DIR", None)
        else:
            os.environ["KUANTRA_DATA_DIR"] = previous_data_dir

    if result.get("status") != "HYDRATED":
        raise MigrationBundleError(
            "DuckDB projection rebuild did not pass evidence coverage: "
            + json.dumps(result, sort_keys=True, default=str)
        )
    return {
        "valid": True,
        "target_data_dir": str(target),
        "duckdb_path": str(duckdb_path),
        "duckdb_exists": duckdb_path.is_file(),
        "hydration": result,
    }
