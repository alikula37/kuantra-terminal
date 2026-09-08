"""H04 red tests for bounded migration archive verification."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

from app.services import macos_migration
from app.services.macos_migration import verify_migration_bundle


def _minimal_archive(path: Path, *, member_name: str = "data/too-large.bin", payload: bytes = b"12345") -> None:
    manifest = {
        "bundle_type": macos_migration.BUNDLE_TYPE,
        "schema_version": macos_migration.BUNDLE_SCHEMA_VERSION,
        "files": [
            {
                "path": member_name,
                "size_bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        ],
    }
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest).encode("utf-8"))
        archive.writestr(member_name, payload)


def test_archive_member_size_limit_is_checked_before_payload_read(tmp_path, monkeypatch):
    bundle = tmp_path / "member-limit.zip"
    _minimal_archive(bundle)
    monkeypatch.setattr(macos_migration, "MAX_ARCHIVE_MEMBER_BYTES", 4, raising=False)

    result = verify_migration_bundle(bundle)

    assert result["valid"] is False
    assert any("archive member exceeds" in error for error in result["errors"])


def test_archive_total_uncompressed_limit_is_checked_before_payload_read(tmp_path, monkeypatch):
    bundle = tmp_path / "total-limit.zip"
    _minimal_archive(bundle)
    monkeypatch.setattr(macos_migration, "MAX_ARCHIVE_TOTAL_UNCOMPRESSED_BYTES", 4, raising=False)

    result = verify_migration_bundle(bundle)

    assert result["valid"] is False
    assert any("uncompressed archive size exceeds" in error for error in result["errors"])
