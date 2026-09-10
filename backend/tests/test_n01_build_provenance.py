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
from scripts.macos_architecture import detect_executable_architecture


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
    assert provenance["provenance_status"] in {"COMPLETE", "DEVELOPER_DIRTY", "INCOMPLETE"}


def test_executable_architecture_detection_prefers_lipo_and_rejects_universal2(tmp_path):
    executable = tmp_path / "Kuantra Terminal"
    executable.write_bytes(b"synthetic Mach-O")

    def lipo_runner(command):
        assert command[:2] == ("lipo", "-archs")
        return 0, "x86_64\n", ""

    detected = detect_executable_architecture(executable, runner=lipo_runner)
    assert detected == {
        "architecture": "x86_64",
        "architectures": ["x86_64"],
        "verified": True,
        "source": "lipo",
    }

    def universal_runner(command):
        if command[0] == "lipo":
            return 0, "arm64 x86_64\n", ""
        return 1, "", ""

    universal = detect_executable_architecture(executable, runner=universal_runner)
    assert universal["architecture"] == "universal2"
    assert universal["verified"] is False


def test_file_architecture_fallback_ignores_architecture_tokens_in_path(tmp_path):
    executable = tmp_path / "arm64-fixture" / "opaque-binary"
    executable.parent.mkdir()
    executable.write_bytes(b"not a Mach-O binary")

    def file_runner(command):
        if command[0] == "lipo":
            return 1, "", "not an object file"
        return 0, f"{executable}: data\n", ""

    undetected = detect_executable_architecture(executable, runner=file_runner)
    assert undetected["architecture"] is None
    assert undetected["verified"] is False

    def mach_o_runner(command):
        if command[0] == "lipo":
            return 1, "", "not an object file"
        return 0, f"{executable}: Mach-O 64-bit executable x86_64\n", ""

    detected = detect_executable_architecture(executable, runner=mach_o_runner)
    assert detected["architecture"] == "x86_64"
    assert detected["verified"] is True
    assert detected["source"] == "file"


def test_release_provenance_requires_verified_native_architecture():
    with pytest.raises(ProvenanceError, match="verified executable architecture"):
        validate_provenance(
            {
                "source_commit_sha": "a" * 40,
                "checkout_commit_sha": "a" * 40,
                "source_commit_matches_checkout": True,
                "tracked_source_tree_status": "clean",
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
                "architecture": "x86_64",
                "architecture_verified": False,
                "architecture_source": "host_fallback",
                "executable_sha256": "e" * 64,
                "artifact_sha256": "f" * 64,
                "provenance_status": "COMPLETE",
            },
            release_facing=True,
        )


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
