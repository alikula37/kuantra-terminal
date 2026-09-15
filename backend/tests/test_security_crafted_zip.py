"""Crafted-ZIP regression coverage for the migration bundle boundaries.

Closes the security-review needs_validation item "Malicious migration zip with
falsified central-directory sizes": every test builds its own synthetic archive
under ``tmp_path`` (no real user data), exercises one attacker-controlled
inconsistency and asserts fail-closed behaviour plus restore atomicity.
"""

from __future__ import annotations

import stat
import struct
import zipfile
from pathlib import Path

import pytest

from app.db.sqlite_driver import SQLiteDriver
from app.services import macos_migration
from app.services.macos_migration import (
    BUNDLE_SCHEMA_VERSION,
    BUNDLE_TYPE,
    MigrationBundleError,
    create_migration_bundle,
    restore_migration_bundle,
    verify_migration_bundle,
)


def _source_data(tmp_path: Path) -> Path:
    source = tmp_path / "source-data"
    source.mkdir()
    driver = SQLiteDriver(str(source / "kuantra_oltp.sqlite3"))
    driver.record_trade_with_evidence(
        {
            "id": "ZIP-TRADE-1",
            "symbol": "ZIPUSDT",
            "side": "BUY",
            "entry_price": 100.0,
            "qty": 1.0,
            "entry_time": "2026-09-08T10:00:00Z",
            "status": "OPEN",
            "pnl": 0.0,
            "commission": 0.1,
            "notes": "synthetic crafted-zip fixture",
        },
        event_type="IntentRecorded",
        idempotency_key="zip:trade-1:intent",
        occurred_at="2026-09-08T10:00:00Z",
        provenance={"source": "crafted-zip-test"},
    )
    cold_storage = source / "cold_storage" / "2026" / "09"
    cold_storage.mkdir(parents=True)
    (cold_storage / "part-01.parquet").write_bytes(b"synthetic-segment-01")
    (cold_storage / "part-02.parquet").write_bytes(b"synthetic-segment-02")
    return source


def _valid_bundle(tmp_path: Path) -> Path:
    bundle = tmp_path / "valid.zip"
    created = create_migration_bundle(_source_data(tmp_path), bundle)
    assert created["migration_ready"] is True
    return bundle


def _patch_central_directory_size(bundle: Path, member: str, *, uncompressed: int | None = None, compressed: int | None = None) -> None:
    raw = bytearray(bundle.read_bytes())
    eocd = raw.rfind(b"\x50\x4b\x05\x06")
    assert eocd != -1, "archive has no end-of-central-directory record"
    cd_size, cd_offset = struct.unpack_from("<II", raw, eocd + 12)
    position = cd_offset
    end = cd_offset + cd_size
    while position < end:
        assert raw[position:position + 4] == b"\x50\x4b\x01\x02", "central directory signature mismatch"
        name_length, extra_length, comment_length = struct.unpack_from("<HHH", raw, position + 28)
        name = bytes(raw[position + 46:position + 46 + name_length]).decode("utf-8")
        if name == member:
            if compressed is not None:
                struct.pack_into("<I", raw, position + 20, compressed)
            if uncompressed is not None:
                struct.pack_into("<I", raw, position + 24, uncompressed)
            bundle.write_bytes(bytes(raw))
            return
        position += 46 + name_length + extra_length + comment_length
    raise AssertionError(f"member not found in central directory: {member}")


def _staging_leftovers(target_parent: Path, target_name: str) -> list[str]:
    return sorted(path.name for path in target_parent.glob(f".{target_name}.restore-*"))


# ---------------------------------------------------------------------------
# Central-directory size lies
# ---------------------------------------------------------------------------


def test_declared_member_size_above_cap_is_rejected(tmp_path, monkeypatch):
    bundle = _valid_bundle(tmp_path)
    _patch_central_directory_size(
        bundle, "data/cold_storage/2026/09/part-01.parquet",
        uncompressed=macos_migration.MAX_ARCHIVE_MEMBER_BYTES + 1,
    )
    result = verify_migration_bundle(bundle)
    assert result["valid"] is False
    assert any("safety limit" in error for error in result["errors"])


def test_declared_member_size_below_actual_is_rejected(tmp_path):
    bundle = _valid_bundle(tmp_path)
    _patch_central_directory_size(
        bundle, "data/cold_storage/2026/09/part-01.parquet", uncompressed=1,
    )
    result = verify_migration_bundle(bundle)
    assert result["valid"] is False
    assert any(
        "hash/size mismatch" in error or "Bad CRC-32" in error
        for error in result["errors"]
    )


def test_declared_total_size_above_cap_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(macos_migration, "MAX_ARCHIVE_TOTAL_UNCOMPRESSED_BYTES", 64)
    bundle = _valid_bundle(tmp_path)
    result = verify_migration_bundle(bundle)
    assert result["valid"] is False
    assert any("uncompressed archive size" in error for error in result["errors"])


def test_member_count_above_cap_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(macos_migration, "MAX_ARCHIVE_MEMBERS", 2)
    bundle = _valid_bundle(tmp_path)
    result = verify_migration_bundle(bundle)
    assert result["valid"] is False
    assert any("member count" in error for error in result["errors"])


def test_streamed_member_read_enforces_real_size(tmp_path):
    archive_path = tmp_path / "streamed.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("data/big.bin", b"\0" * 8192)
    with zipfile.ZipFile(archive_path, "r") as archive:
        with pytest.raises(MigrationBundleError, match="exceeds the safety limit"):
            macos_migration._read_member_bounded(archive, "data/big.bin", limit=1024)


# ---------------------------------------------------------------------------
# Manifest boundary
# ---------------------------------------------------------------------------


def test_oversized_manifest_is_bounded_before_parsing(tmp_path, monkeypatch):
    monkeypatch.setattr(macos_migration, "MAX_ARCHIVE_MANIFEST_BYTES", 2048)
    archive_path = tmp_path / "manifest-bomb.zip"
    payload = b'{"bundle_type":"kuantra.macos.migration","pad":"' + b"x" * 8192 + b'"}'
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", payload)
    result = verify_migration_bundle(archive_path)
    assert result["valid"] is False
    assert any("manifest.json" in error and "safety limit" in error for error in result["errors"])


def test_corrupt_central_directory_fails_closed(tmp_path):
    bundle = _valid_bundle(tmp_path)
    corrupt = tmp_path / "corrupt.zip"
    corrupt.write_bytes(bundle.read_bytes()[:-32])
    result = verify_migration_bundle(corrupt)
    assert result["valid"] is False
    assert result["errors"]
    target = tmp_path / "corrupt-target"
    with pytest.raises(MigrationBundleError, match="verification failed"):
        restore_migration_bundle(corrupt, target)
    assert not target.exists()


# ---------------------------------------------------------------------------
# Member-name / entry-shape inconsistencies
# ---------------------------------------------------------------------------


def _minimal_manifest_archive(tmp_path: Path, member: str, data: bytes, *, symlink: bool = False) -> Path:
    archive_path = tmp_path / "crafted-names.zip"
    manifest = {
        "bundle_type": BUNDLE_TYPE,
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "files": [{"path": member, "size_bytes": len(data), "sha256": "0" * 64}],
    }
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", __import__("json").dumps(manifest))
        if symlink:
            info = zipfile.ZipInfo(member)
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(info, "target")
        else:
            archive.writestr(member, data)
    return archive_path


def test_path_traversal_member_is_rejected(tmp_path):
    archive = _minimal_manifest_archive(tmp_path, "../escape.bin", b"escape")
    result = verify_migration_bundle(archive)
    assert result["valid"] is False
    assert any("unsafe" in error for error in result["errors"])


def test_symlink_member_is_rejected(tmp_path):
    archive = _minimal_manifest_archive(tmp_path, "data/link.bin", b"", symlink=True)
    result = verify_migration_bundle(archive)
    assert result["valid"] is False
    assert any("symlink" in error for error in result["errors"])


def test_unlisted_member_is_rejected(tmp_path):
    archive_path = tmp_path / "unlisted.zip"
    manifest = {"bundle_type": BUNDLE_TYPE, "schema_version": BUNDLE_SCHEMA_VERSION, "files": []}
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", __import__("json").dumps(manifest))
        archive.writestr("data/extra.bin", b"extra")
    result = verify_migration_bundle(archive_path)
    assert result["valid"] is False
    assert any("unlisted archive members" in error for error in result["errors"])


def test_duplicate_member_names_are_rejected(tmp_path):
    archive_path = tmp_path / "duplicate.zip"
    manifest = {"bundle_type": BUNDLE_TYPE, "schema_version": BUNDLE_SCHEMA_VERSION, "files": []}
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", __import__("json").dumps(manifest))
        archive.writestr("data/dup.bin", b"one")
        archive.writestr("data/dup.bin", b"two")
    result = verify_migration_bundle(archive_path)
    assert result["valid"] is False
    assert any("duplicate archive members" in error for error in result["errors"])


# ---------------------------------------------------------------------------
# Restore atomicity under crafted input
# ---------------------------------------------------------------------------


def test_failed_verification_never_touches_target(tmp_path):
    bundle = _valid_bundle(tmp_path)
    _patch_central_directory_size(
        bundle, "data/cold_storage/2026/09/part-02.parquet",
        uncompressed=macos_migration.MAX_ARCHIVE_MEMBER_BYTES + 1,
    )
    target = tmp_path / "restore-target"
    with pytest.raises(MigrationBundleError, match="verification failed"):
        restore_migration_bundle(bundle, target)
    assert not target.exists()
    assert _staging_leftovers(tmp_path, "restore-target") == []


def test_interrupted_restore_leaves_no_partial_target(tmp_path, monkeypatch):
    bundle = _valid_bundle(tmp_path)
    calls = {"count": 0}
    real_copyfileobj = macos_migration.shutil.copyfileobj

    def interrupted(source, destination, *args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 2:
            raise OSError("synthetic crafted-zip interruption")
        return real_copyfileobj(source, destination, *args, **kwargs)

    monkeypatch.setattr(macos_migration.shutil, "copyfileobj", interrupted)
    target = tmp_path / "interrupted-target"
    with pytest.raises(OSError, match="synthetic crafted-zip interruption"):
        restore_migration_bundle(bundle, target)
    assert not target.exists()
    assert _staging_leftovers(tmp_path, "interrupted-target") == []


def test_valid_bundle_still_round_trips_after_bounds(tmp_path):
    bundle = _valid_bundle(tmp_path)
    result = verify_migration_bundle(bundle)
    assert result["valid"] is True
    target = tmp_path / "valid-target"
    restored = restore_migration_bundle(bundle, target)
    assert restored["valid"] is True
    assert (target / "kuantra_oltp.sqlite3").is_file()
