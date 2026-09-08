"""N01 exact source/build/artifact provenance contracts."""

import hashlib
import json
import re
from pathlib import Path

import pytest

from scripts.build_provenance import (
    ProvenanceError,
    collect_provenance,
    validate_provenance,
)


ROOT = Path(__file__).resolve().parents[2]
SHA1_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def test_collect_provenance_falls_back_to_checkout_and_binds_hashes(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_SHA", raising=False)
    monkeypatch.delenv("KUANTRA_BUILD_COMMIT", raising=False)
    executable = tmp_path / "Kuantra Terminal"
    artifact = tmp_path / "Kuantra-Terminal-test.dmg"
    executable.write_bytes(b"packaged executable")
    artifact.write_bytes(b"distributed artifact")

    provenance = collect_provenance(ROOT, executable=executable, artifact=artifact)

    assert SHA1_RE.fullmatch(provenance["source_commit_sha"])
    assert provenance["source_commit_sha"] == provenance["checkout_commit_sha"]
    assert provenance["source_commit_origin"] == "checkout"
    assert provenance["tracked_source_tree_status"] in {"clean", "dirty"}
    assert SHA256_RE.fullmatch(provenance["tracked_source_tree_sha256"])
    assert SHA256_RE.fullmatch(provenance["lock_hashes"]["backend_requirements_lock_sha256"])
    assert SHA256_RE.fullmatch(provenance["lock_hashes"]["frontend_package_lock_sha256"])
    assert provenance["toolchain"]["python"]
    assert provenance["toolchain"]["node"]
    assert provenance["toolchain"]["npm"]
    assert provenance["toolchain"]["uv"]
    assert provenance["toolchain"]["pyinstaller"]
    assert SHA256_RE.fullmatch(provenance["executable_sha256"])
    assert SHA256_RE.fullmatch(provenance["artifact_sha256"])
    assert provenance["provenance_status"] in {"COMPLETE", "DEVELOPER_DIRTY"}


def test_release_validator_rejects_dirty_or_incomplete_provenance():
    with pytest.raises(ProvenanceError, match="tracked source tree"):
        validate_provenance(
            {
                "source_commit_sha": "a" * 40,
                "checkout_commit_sha": "a" * 40,
                "source_commit_matches_checkout": True,
                "tracked_source_tree_status": "dirty",
                "tracked_source_tree_sha256": "b" * 64,
                "lock_hashes": {
                    "backend_requirements_lock_sha256": "c" * 64,
                    "frontend_package_lock_sha256": "d" * 64,
                },
                "toolchain": {
                    "python": "3.11",
                    "node": "20",
                    "npm": "10",
                    "uv": "0.1",
                    "pyinstaller": "6",
                },
                "os": "darwin",
                "architecture": "arm64",
                "executable_sha256": "e" * 64,
                "artifact_sha256": "f" * 64,
                "provenance_status": "DEVELOPER_DIRTY",
            },
            release_facing=True,
        )


def test_directory_artifact_hash_is_deterministic(tmp_path):
    executable = tmp_path / "app" / "Contents" / "MacOS" / "Kuantra Terminal"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"binary")
    (executable.parents[2] / "Info.plist").write_text("plist", encoding="utf-8")

    first = collect_provenance(ROOT, executable=executable, artifact=executable.parents[2])
    second = collect_provenance(ROOT, executable=executable, artifact=executable.parents[2])

    assert first["artifact_sha256"] == second["artifact_sha256"]
    assert first["executable_sha256"] == hashlib.sha256(b"binary").hexdigest()
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)

