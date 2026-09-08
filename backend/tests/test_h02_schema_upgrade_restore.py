"""H02 schema upgrade, migration restore, and integrity contracts."""

from __future__ import annotations

import json
import hashlib
from pathlib import Path
import sqlite3
import stat
import zipfile

import pytest

from app.db.repositories.evidence_ledger_repo import EvidenceLedgerRepository
from app.db.repositories.evidence_projection_repo import EvidenceTradeProjectionRepository
from app.db.sqlite_driver import SQLiteDriver
from app.services import macos_migration
from app.services.macos_migration import (
    CURRENT_SQLITE_SCHEMA_VERSION,
    MigrationBundleError,
    create_migration_bundle,
    restore_migration_bundle,
    upgrade_sqlite_schema,
    verify_migration_bundle,
)
from app.services.trade_read_adapter import TradeReadAdapter


def _source_data(tmp_path: Path) -> Path:
    source = tmp_path / "source-data"
    source.mkdir()
    db_path = source / "kuantra_oltp.sqlite3"
    driver = SQLiteDriver(str(db_path))
    driver.record_trade_with_evidence(
        {
            "id": "H02-TRADE-1",
            "symbol": "H02USDT",
            "side": "BUY",
            "entry_price": 100.0,
            "qty": 1.0,
            "entry_time": "2026-09-08T10:00:00Z",
            "status": "OPEN",
            "pnl": 0.0,
            "commission": 0.1,
            "notes": "synthetic H02 fixture",
        },
        event_type="IntentRecorded",
        idempotency_key="h02:trade-1:intent",
        occurred_at="2026-09-08T10:00:00Z",
        provenance={"source": "h02-test"},
    )
    cold_storage = source / "cold_storage" / "2026" / "09"
    cold_storage.mkdir(parents=True)
    (cold_storage / "part-01.parquet").write_bytes(b"synthetic-segment-01")
    (cold_storage / "part-02.parquet").write_bytes(b"synthetic-segment-02")
    return source


def _pack(db_path: Path) -> dict:
    return TradeReadAdapter(
        legacy_driver=SQLiteDriver(str(db_path)),
        projection_repo=EvidenceTradeProjectionRepository(str(db_path)),
    ).get_evidence_pack("H02-TRADE-1")


def _legacy_database(tmp_path: Path) -> Path:
    database = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE trades (
                id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                entry_price REAL NOT NULL,
                exit_price REAL,
                qty REAL NOT NULL,
                stop_loss REAL,
                take_profit REAL,
                pnl REAL,
                r_multiple REAL,
                mae REAL,
                mfe REAL,
                exit_efficiency REAL,
                status TEXT NOT NULL,
                entry_time TEXT NOT NULL,
                exit_time TEXT,
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE user_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL);
            INSERT INTO alembic_version VALUES ('001_initial_baseline');
            INSERT INTO trades (
                id, symbol, side, entry_price, qty, status, entry_time, notes
            ) VALUES (
                'legacy-trade-1', 'BTCUSDT', 'BUY', 100.0, 1.0, 'OPEN',
                '2026-09-08T10:00:00Z', 'synthetic legacy fixture'
            );
            """
        )
    return database


def _rewrite_bundle_with_sqlite_payload(
    source_bundle: Path,
    target_bundle: Path,
    mutate_sqlite,
) -> None:
    entries: dict[str, tuple[zipfile.ZipInfo, bytes]] = {}
    with zipfile.ZipFile(source_bundle, "r") as archive:
        for info in archive.infolist():
            payload = archive.read(info.filename)
            if info.filename == "data/kuantra_oltp.sqlite3":
                mutated_path = target_bundle.with_suffix(".mutated.sqlite3")
                mutated_path.write_bytes(payload)
                with sqlite3.connect(mutated_path) as connection:
                    mutate_sqlite(connection)
                    connection.commit()
                    connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                payload = mutated_path.read_bytes()
            entries[info.filename] = (info, payload)

    manifest = json.loads(entries["manifest.json"][1].decode("utf-8"))
    for item in manifest["files"]:
        if item["path"] == "data/kuantra_oltp.sqlite3":
            item["size_bytes"] = len(entries[item["path"]][1])
            item["sha256"] = hashlib.sha256(
                entries[item["path"]][1]
            ).hexdigest()
    entries["manifest.json"] = (
        entries["manifest.json"][0],
        (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )
    with zipfile.ZipFile(target_bundle, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, (info, payload) in entries.items():
            archive.writestr(info, payload)


def test_corrupt_ledger_chain_is_rejected_even_when_sqlite_integrity_passes(tmp_path):
    source = _source_data(tmp_path)
    bundle = tmp_path / "valid.zip"
    create_migration_bundle(source, bundle)
    tampered = tmp_path / "chain-tampered.zip"

    def mutate(connection: sqlite3.Connection):
        connection.execute("DROP TRIGGER evidence_events_no_update")
        connection.execute(
            "UPDATE evidence_events SET normalized_payload_json = ? WHERE chain_sequence = 1",
            ('{"trade":{"id":"H02-TRADE-1","symbol":"H02USDT","side":"BUY",'
             '"entry_price":101.0,"qty":1.0,"entry_time":"2026-09-08T10:00:00Z",'
             '"status":"OPEN","pnl":0.0,"commission":0.1}}',),
        )

    _rewrite_bundle_with_sqlite_payload(bundle, tampered, mutate)
    result = verify_migration_bundle(tampered)

    assert result["valid"] is False
    assert any("EVIDENCE_CHAIN_INVALID" in error for error in result["errors"])


def test_interrupted_restore_never_promotes_partial_target(tmp_path, monkeypatch):
    source = _source_data(tmp_path)
    bundle = tmp_path / "valid.zip"
    create_migration_bundle(source, bundle)
    target = tmp_path / "target"
    calls = {"count": 0}
    original_copyfileobj = macos_migration.shutil.copyfileobj

    def fail_after_first(source_file, destination_file, *args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 2:
            raise OSError("synthetic interrupted restore")
        return original_copyfileobj(source_file, destination_file, *args, **kwargs)

    monkeypatch.setattr(macos_migration.shutil, "copyfileobj", fail_after_first)
    with pytest.raises(OSError, match="interrupted restore"):
        restore_migration_bundle(bundle, target)

    assert not target.exists()


def test_restore_round_trip_preserves_canonical_pack_and_lineage(tmp_path):
    source = _source_data(tmp_path)
    source_db = source / "kuantra_oltp.sqlite3"
    before = _pack(source_db)
    bundle = tmp_path / "valid.zip"
    created = create_migration_bundle(source, bundle)
    assert created["migration_ready"] is True

    target = tmp_path / "target"
    restored = restore_migration_bundle(bundle, target)
    assert restored["valid"] is True
    target_db = target / "kuantra_oltp.sqlite3"
    after = _pack(target_db)

    assert after == before
    assert EvidenceLedgerRepository(str(target_db)).verify_chain()["valid"] is True
    assert EvidenceTradeProjectionRepository(str(target_db)).rebuild(dry_run=True)[
        "ledger_valid"
    ] is True


def test_missing_bundle_segment_and_future_schema_are_rejected_without_restore(tmp_path):
    source = _source_data(tmp_path)
    bundle = tmp_path / "valid.zip"
    create_migration_bundle(source, bundle)

    missing = tmp_path / "missing.zip"
    with zipfile.ZipFile(bundle, "r") as source_zip, zipfile.ZipFile(
        missing, "w", compression=zipfile.ZIP_DEFLATED
    ) as target_zip:
        for info in source_zip.infolist():
            if info.filename.endswith("part-02.parquet"):
                continue
            target_zip.writestr(info, source_zip.read(info.filename))

    missing_result = verify_migration_bundle(missing)
    assert missing_result["valid"] is False
    assert any("missing from archive" in error for error in missing_result["errors"])
    with pytest.raises(MigrationBundleError, match="verification failed"):
        restore_migration_bundle(missing, tmp_path / "missing-target")

    future = tmp_path / "future.zip"
    with zipfile.ZipFile(bundle, "r") as source_zip:
        entries = {info.filename: source_zip.read(info.filename) for info in source_zip.infolist()}
    manifest = json.loads(entries["manifest.json"].decode("utf-8"))
    manifest["schema_version"] = 999
    entries["manifest.json"] = (json.dumps(manifest, sort_keys=True) + "\n").encode("utf-8")
    with zipfile.ZipFile(future, "w", compression=zipfile.ZIP_DEFLATED) as target_zip:
        for name, payload in entries.items():
            target_zip.writestr(name, payload)

    future_result = verify_migration_bundle(future)
    assert future_result["valid"] is False
    assert any("unsupported migration bundle schema version" in error for error in future_result["errors"])


def test_sqlite_future_version_checksum_and_archive_escape_fail_closed(tmp_path):
    source = _source_data(tmp_path)
    bundle = tmp_path / "valid.zip"
    create_migration_bundle(source, bundle)

    future_sqlite = tmp_path / "future-sqlite.zip"

    def mark_future(connection: sqlite3.Connection):
        connection.execute("PRAGMA user_version = 999")

    _rewrite_bundle_with_sqlite_payload(bundle, future_sqlite, mark_future)
    future_result = verify_migration_bundle(future_sqlite)
    assert future_result["valid"] is False
    assert any("SQLITE_SCHEMA_VERSION_FUTURE" in error for error in future_result["errors"])

    checksum = tmp_path / "checksum.zip"
    with zipfile.ZipFile(bundle, "r") as source_zip, zipfile.ZipFile(
        checksum, "w", compression=zipfile.ZIP_DEFLATED
    ) as target_zip:
        for info in source_zip.infolist():
            payload = source_zip.read(info.filename)
            if info.filename == "data/kuantra_oltp.sqlite3":
                payload = payload[:-1] + bytes([payload[-1] ^ 0x01])
            target_zip.writestr(info, payload)
    checksum_result = verify_migration_bundle(checksum)
    assert checksum_result["valid"] is False
    assert any("hash/size mismatch" in error for error in checksum_result["errors"])
    with pytest.raises(MigrationBundleError, match="verification failed"):
        restore_migration_bundle(checksum, tmp_path / "checksum-target")

    traversal = tmp_path / "traversal.zip"
    with zipfile.ZipFile(bundle, "r") as source_zip:
        entries = [(info, source_zip.read(info.filename)) for info in source_zip.infolist()]
    manifest = json.loads(next(payload for info, payload in entries if info.filename == "manifest.json"))
    escape_payload = b"outside"
    manifest["files"].append(
        {
            "path": "data/../outside.txt",
            "size_bytes": len(escape_payload),
            "sha256": hashlib.sha256(escape_payload).hexdigest(),
        }
    )
    with zipfile.ZipFile(traversal, "w", compression=zipfile.ZIP_DEFLATED) as target_zip:
        for info, payload in entries:
            if info.filename == "manifest.json":
                payload = (json.dumps(manifest, sort_keys=True) + "\n").encode("utf-8")
            target_zip.writestr(info, payload)
        target_zip.writestr("data/../outside.txt", escape_payload)
    traversal_result = verify_migration_bundle(traversal)
    assert traversal_result["valid"] is False
    assert any("unsafe manifest path" in error for error in traversal_result["errors"])

    symlink = tmp_path / "symlink.zip"
    symlink_info = zipfile.ZipInfo("data/cold_storage/link.parquet")
    symlink_info.create_system = 3
    symlink_info.external_attr = (stat.S_IFLNK | 0o777) << 16
    symlink_payload = b"cold-storage-target"
    manifest["files"][-1] = {
        "path": symlink_info.filename,
        "size_bytes": len(symlink_payload),
        "sha256": hashlib.sha256(symlink_payload).hexdigest(),
    }
    with zipfile.ZipFile(symlink, "w", compression=zipfile.ZIP_DEFLATED) as target_zip:
        for info, payload in entries:
            if info.filename == "manifest.json":
                payload = (json.dumps(manifest, sort_keys=True) + "\n").encode("utf-8")
            target_zip.writestr(info, payload)
        target_zip.writestr(symlink_info, symlink_payload)
    symlink_result = verify_migration_bundle(symlink)
    assert symlink_result["valid"] is False
    assert any("symlink" in error for error in symlink_result["errors"])


def test_supported_legacy_schema_upgrade_is_atomic_and_idempotent(tmp_path):
    database = _legacy_database(tmp_path)
    before = database.read_bytes()

    upgraded = upgrade_sqlite_schema(database)

    assert upgraded["valid"] is True
    assert upgraded["status"] == "UPGRADED"
    assert upgraded["schema_before"]["version"] == 1
    assert upgraded["schema_after"]["version"] == CURRENT_SQLITE_SCHEMA_VERSION
    assert upgraded["validation"]["valid"] is True
    assert upgraded["backfill"]["appended"] == 1
    assert Path(upgraded["backup_path"]).is_file()
    assert hashlib.sha256(Path(upgraded["backup_path"]).read_bytes()).hexdigest() == upgraded[
        "backup_sha256"
    ]

    with sqlite3.connect(database) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(trades)")}
        assert {"commission", "updated_at"}.issubset(columns)
        assert connection.execute("SELECT COUNT(*) FROM evidence_events").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM evidence_trade_projections").fetchone()[0] == 1

    repeated = upgrade_sqlite_schema(database)
    assert repeated["status"] == "CURRENT"
    assert repeated["changed"] is False
    assert database.read_bytes() != before


def test_interrupted_schema_upgrade_keeps_original_legacy_database(tmp_path):
    database = _legacy_database(tmp_path)
    original = database.read_bytes()

    def fail(phase: str, _path: Path) -> None:
        if phase == "after_schema_upgrade":
            raise OSError("synthetic interrupted schema upgrade")

    with pytest.raises(OSError, match="interrupted schema upgrade"):
        upgrade_sqlite_schema(database, failure_injector=fail)

    assert database.read_bytes() == original
    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'evidence_events'"
        ).fetchone() is None
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone()[0] == (
            "001_initial_baseline"
        )


def test_corrupt_upgrade_backup_fails_closed_without_touching_target(tmp_path, monkeypatch):
    database = _legacy_database(tmp_path)
    original = database.read_bytes()
    original_copy = macos_migration._copy_sqlite_snapshot

    def corrupt(source: Path, destination: Path):
        result = original_copy(source, destination)
        if destination.name == "pre-upgrade.sqlite3":
            destination.write_bytes(b"not-a-sqlite-database")
        return result

    monkeypatch.setattr(macos_migration, "_copy_sqlite_snapshot", corrupt)
    with pytest.raises(MigrationBundleError, match="backup"):
        upgrade_sqlite_schema(database)

    assert database.read_bytes() == original
