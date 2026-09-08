"""Cross-platform migration bundle contracts for the Windows -> macOS move."""

from __future__ import annotations

import json
import sqlite3
import zipfile
from pathlib import Path

import pytest

from app.db.sqlite_driver import SQLiteDriver
from app.services.macos_migration import (
    MigrationBundleError,
    create_migration_bundle,
    restore_migration_bundle,
    verify_migration_bundle,
)


def _source_data(tmp_path: Path) -> Path:
    source = tmp_path / "source-data"
    source.mkdir()
    database = source / "kuantra_oltp.sqlite3"
    driver = SQLiteDriver(str(database))
    driver.record_trade_with_evidence(
        {
            "id": "trade-1",
            "symbol": "BTCUSDT",
            "side": "BUY",
            "entry_price": 100.0,
            "qty": 1.0,
            "entry_time": "2026-09-08T10:00:00Z",
            "status": "OPEN",
            "pnl": 0.0,
            "commission": 0.1,
            "notes": "synthetic migration fixture",
        },
        event_type="IntentRecorded",
        idempotency_key="migration:trade-1:intent",
        occurred_at="2026-09-08T10:00:00Z",
        provenance={"source": "migration-test"},
    )
    with sqlite3.connect(database) as conn:
        conn.executescript(
            """
            INSERT INTO exchange_credentials (
                exchange_id, name, api_key_encrypted, api_secret_encrypted,
                passphrase_encrypted, is_testnet, is_active, created_at, updated_at
            ) VALUES (
                'binance_futures', 'Binance Futures', 'encrypted-key',
                'encrypted-secret', NULL, 1, 1,
                '2026-09-08T10:00:00Z', '2026-09-08T10:00:00Z'
            );
            INSERT INTO exchange_credential_refs (
                exchange_id, name, api_key_ref, api_secret_ref, passphrase_ref,
                permission_scope, is_testnet, is_active, created_at, updated_at
            ) VALUES (
                'binance_futures', 'Binance Futures',
                'exchange/binance_futures/api_key',
                'exchange/binance_futures/api_secret', NULL, 'READ_ONLY', 1, 1,
                '2026-09-08T10:00:00Z', '2026-09-08T10:00:00Z'
            );
            INSERT INTO user_settings (key, value, updated_at)
            VALUES ('user_initial_balance', '10000', '2026-09-08T10:00:00Z');
            INSERT INTO user_settings (key, value, updated_at)
            VALUES ('BINANCE_API_KEY', 'must-be-removed', '2026-09-08T10:00:00Z');
            """
        )
    cold_storage = source / "cold_storage" / "2026" / "09"
    cold_storage.mkdir(parents=True)
    (cold_storage / "ticks.parquet").write_bytes(b"parquet-placeholder")
    (source / "logs").mkdir()
    (source / "logs" / "backend.log").write_text("token=do-not-copy", encoding="utf-8")
    (source / "kuantra_olap.duckdb").write_bytes(b"projection-placeholder")
    return source


def test_create_sanitizes_credentials_and_excludes_projection(tmp_path):
    source = _source_data(tmp_path)
    bundle = tmp_path / "migration.zip"

    result = create_migration_bundle(source, bundle)
    assert result["valid"] is True
    assert result["migration_ready"] is True
    assert result["manifest"]["projection_policy"] == "duckdb_excluded_rebuild_from_sqlite"
    assert result["manifest"]["sqlite"]["deleted_legacy_credential_rows"] == 1
    assert result["manifest"]["sqlite"]["deleted_sensitive_setting_rows"] == 1

    with zipfile.ZipFile(bundle) as archive:
        names = set(archive.namelist())
        assert "manifest.json" in names
        assert "data/kuantra_oltp.sqlite3" in names
        assert "data/cold_storage/2026/09/ticks.parquet" in names
        assert "data/kuantra_olap.duckdb" not in names
        assert "data/logs/backend.log" not in names
        assert "data/kuantra_oltp.sqlite3-wal" not in names
        payload = archive.read("data/kuantra_oltp.sqlite3")
        assert b"encrypted-secret" not in payload
        assert b"must-be-removed" not in payload
        assert b"exchange/binance_futures/api_key" not in payload
        assert result["manifest"]["sqlite"]["deleted_keychain_reference_rows"] == 1

    # The source database must remain untouched.
    with sqlite3.connect(source / "kuantra_oltp.sqlite3") as conn:
        assert conn.execute("SELECT COUNT(*) FROM exchange_credentials").fetchone()[0] == 1


def test_verify_detects_tamper_and_restore_requires_safe_target(tmp_path):
    source = _source_data(tmp_path)
    bundle = tmp_path / "migration.zip"
    create_migration_bundle(source, bundle)
    assert verify_migration_bundle(bundle)["valid"] is True
    assert verify_migration_bundle(bundle)["migration_ready"] is True

    tampered = tmp_path / "tampered.zip"
    with zipfile.ZipFile(bundle) as source_zip, zipfile.ZipFile(tampered, "w") as target_zip:
        for info in source_zip.infolist():
            payload = source_zip.read(info.filename)
            if info.filename.endswith("ticks.parquet"):
                payload += b"tamper"
            target_zip.writestr(info, payload)
    tampered_result = verify_migration_bundle(tampered)
    assert tampered_result["valid"] is False
    assert any("hash/size mismatch" in error for error in tampered_result["errors"])

    target = tmp_path / "target"
    target.mkdir()
    (target / "existing.txt").write_text("keep until explicit force", encoding="utf-8")
    with pytest.raises(MigrationBundleError, match="not empty"):
        restore_migration_bundle(bundle, target)

    restored = restore_migration_bundle(bundle, target, force=True)
    assert restored["valid"] is True
    assert restored["duckdb_rebuild_required"] is True
    assert restored["credentials_reenter_required"] is True
    assert Path(restored["previous_target_backup"]).is_dir()
    assert (target / "kuantra_oltp.sqlite3").is_file()
    assert (target / "cold_storage" / "2026" / "09" / "ticks.parquet").is_file()
    assert not (target / "kuantra_olap.duckdb").exists()


def test_restore_rejects_incomplete_evidence_projection(tmp_path):
    source = _source_data(tmp_path)
    with sqlite3.connect(source / "kuantra_oltp.sqlite3") as conn:
        conn.execute("DELETE FROM evidence_trade_projections")
        conn.commit()

    bundle = tmp_path / "incomplete.zip"
    result = create_migration_bundle(source, bundle)
    assert result["valid"] is True
    assert result["migration_ready"] is False
    with pytest.raises(MigrationBundleError, match="not ready"):
        restore_migration_bundle(bundle, tmp_path / "target")


def test_cli_manifest_is_json_and_versioned(tmp_path):
    source = _source_data(tmp_path)
    bundle = tmp_path / "migration.zip"
    create_migration_bundle(source, bundle)
    with zipfile.ZipFile(bundle) as archive:
        manifest = json.loads(archive.read("manifest.json"))
    assert manifest["bundle_type"] == "kuantra-macos-migration"
    assert manifest["schema_version"] == 1
    assert manifest["credential_policy"] == "os_keychain_not_exported"
