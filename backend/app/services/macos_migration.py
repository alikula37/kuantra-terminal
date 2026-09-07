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
from typing import Any, Iterable


BUNDLE_SCHEMA_VERSION = 1
BUNDLE_TYPE = "kuantra-macos-migration"
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

    destination.parent.mkdir(parents=True, exist_ok=True)
    source_conn = sqlite3.connect(str(source))
    target_conn = sqlite3.connect(str(destination))
    deleted_legacy_credentials = 0
    deleted_credential_refs = 0
    deleted_sensitive_settings = 0
    try:
        source_conn.execute("PRAGMA query_only = ON")
        source_conn.backup(target_conn)
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
        source_conn.close()

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
            "projection_preflight": _projection_preflight(source_db),
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
        "migration_ready": bool(manifest["projection_preflight"].get("ready")),
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
        if _table_exists(conn, "evidence_events"):
            event_count = int(conn.execute("SELECT COUNT(*) FROM evidence_events").fetchone()[0])
        return {"valid": True, "integrity": "ok", "event_count": event_count}
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
        with zipfile.ZipFile(bundle, "r") as archive:
            names = archive.namelist()
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
            unexpected = sorted(set(names) - expected_names)
            if unexpected:
                errors.append(f"unlisted archive members: {unexpected}")
    except (OSError, zipfile.BadZipFile, MigrationBundleError) as exc:
        errors.append(str(exc))

    return {
        "valid": not errors,
        "migration_ready": bool(
            not errors and manifest and manifest.get("projection_preflight", {}).get("ready")
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


def restore_migration_bundle(
    bundle_path: str | Path,
    target_data_dir: str | Path,
    *,
    force: bool = False,
) -> dict[str, Any]:
    """Restore a verified bundle without deleting an existing target by default."""

    verification = verify_migration_bundle(bundle_path)
    if not verification["valid"]:
        raise MigrationBundleError("migration bundle verification failed: " + "; ".join(verification["errors"]))
    if not verification.get("migration_ready"):
        raise MigrationBundleError(
            "migration bundle is not ready: evidence projection coverage is incomplete; "
            "run the evidence backfill/projection rebuild on the source and recreate the bundle"
        )

    target = Path(target_data_dir).expanduser().resolve()
    existing_backup: Path | None = None
    if target.exists() and any(target.iterdir()):
        if not force:
            raise MigrationBundleError(
                f"target data directory is not empty: {target}; pass --force to move it aside safely"
            )
        existing_backup = _next_backup_path(target)
        shutil.move(str(target), str(existing_backup))
    target.mkdir(parents=True, exist_ok=True)

    restored: list[str] = []
    try:
        with zipfile.ZipFile(Path(bundle_path).expanduser().resolve(), "r") as archive:
            manifest = _read_manifest(archive)
            for item in manifest["files"]:
                relative = PurePosixPath(item["path"])
                if not _safe_bundle_member(relative.as_posix()) or relative.parts[0] != "data":
                    raise MigrationBundleError(f"invalid restore path: {relative}")
                destination = target.joinpath(*relative.parts[1:])
                destination.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(relative.as_posix(), "r") as source, destination.open("wb") as sink:
                    shutil.copyfileobj(source, sink)
                restored.append(str(destination))
    except Exception:
        # The previous target is recoverable if --force was used.  Leave the
        # partially restored target visible for forensics instead of deleting it.
        raise

    return {
        "valid": True,
        "migration_ready": bool(verification.get("migration_ready")),
        "target_data_dir": str(target),
        "restored_files": restored,
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
