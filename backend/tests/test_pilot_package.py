"""Fail-closed trusted macOS pilot package contracts."""

import hashlib
import json
from pathlib import Path

import pytest

from scripts.prepare_pilot_package import (
    INSTRUCTIONS_NAME,
    MANIFEST_NAME,
    MissingPilotEvidence,
    PilotPackageError,
    prepare_arm64_pilot_package,
    prepare_pilot_package,
)
from scripts.release_truth import DEFAULT_MATRIX_PATH, canonical_matrix_digest, load_matrix


ROOT = Path(__file__).resolve().parents[2]
VERSION = "1.1.3"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _chain(tmp_path: Path, architecture: str, *, commit: str = "a" * 40):
    dmg = tmp_path / f"Kuantra-Terminal-{VERSION}-{architecture}.dmg"
    smoke = tmp_path / f"input-smoke-{architecture}.json"
    n05 = tmp_path / f"input-n05-{architecture}.json"
    executable = tmp_path / f"mounted-{architecture}-executable"
    executable.write_bytes(f"{architecture} executable".encode())
    dmg.write_bytes(f"{architecture} DMG".encode())
    executable_sha = _sha256(executable)
    dmg_sha = _sha256(dmg)
    provenance = {
        "source_commit_sha": commit,
        "checkout_commit_sha": commit,
        "source_commit_origin": "checkout",
        "source_commit_matches_checkout": True,
        "tracked_source_tree_status": "clean",
        "tracked_source_tree_sha256": "b" * 64,
        "lock_hashes": {
            "backend_requirements_lock_sha256": "c" * 64,
            "frontend_package_lock_sha256": "d" * 64,
        },
        "toolchain": {
            "python": "3.11.16",
            "node": "v20.20.2",
            "npm": "10.8.2",
            "uv": "uv 0.12.10",
            "pyinstaller": "6.22.2",
        },
        "os": "darwin",
        "os_version": "macOS-15.0",
        "architecture": architecture,
        "architecture_verified": True,
        "architecture_source": "executable",
        "architecture_detection_tool": "lipo",
        "executable_architectures": [architecture],
        "build_host_architecture": architecture,
        "build_host_translation": "native",
        "executable_sha256": executable_sha,
        "artifact_sha256": dmg_sha,
        "provenance_status": "COMPLETE",
    }
    truth = load_matrix(DEFAULT_MATRIX_PATH)
    smoke.write_text(
        json.dumps(
            {
                "ok": True,
                "version": VERSION,
                "version_expected": VERSION,
                "platform": "darwin",
                "architecture": architecture,
                "architecture_verified": True,
                "renderer_actual": "wkwebview",
                "renderer_controller_ready": True,
                "build_commit": commit,
                "executable_sha256": executable_sha,
                "artifact_sha256": dmg_sha,
                "build_provenance": provenance,
                "truth_matrix": {
                    "document_id": truth["document_id"],
                    "version": truth["version"],
                    "product_version": truth["product"]["version"],
                    "sha256": canonical_matrix_digest(truth),
                },
                "macos_dmg_smoke": {
                    "status": "PASS",
                    "dmg_image_integrity": "PASS",
                    "mount_mode": "readonly",
                    "executable_from_mount": True,
                    "renderer": "wkwebview",
                    "architecture": architecture,
                    "executable_sha256": executable_sha,
                    "artifact_sha256": dmg_sha,
                    "mount_detached": True,
                },
            }
        ),
        encoding="utf-8",
    )
    n05.write_text(
        json.dumps(
            {
                "schema_version": "N05.macos-distribution.v1",
                "status": "BLOCKED",
                "acceptance_status": "OWNER_REVIEW_REQUIRED",
                "platform": {"os": "darwin", "os_version": "macOS-15.0", "architecture": architecture},
                "source": {
                    "commit_sha": commit,
                    "tracked_tree_status": "clean",
                    "provenance_status": "COMPLETE",
                },
                "artifacts": {
                    "dmg_sha256": dmg_sha,
                    "dmg_size_bytes": dmg.stat().st_size,
                    "app_tree_sha256": "e" * 64,
                    "executable_sha256": executable_sha,
                },
                "signing": {
                    "codesign_verify": "PASS",
                    "identity_type": "AD_HOC",
                    "unapproved_entitlement_keys": [],
                },
                "notarization": {
                    "gatekeeper_assessment": "FAIL",
                    "dmg_ticket_validation": "FAIL",
                    "release_gate_pass": False,
                },
                "mount": {"mode": "readonly", "attached": True, "detached": True},
                "commands": {"raw_output_recorded": False},
                "claims": {
                    "production_ready": False,
                    "commercial_support": False,
                    "signing": False,
                    "notarized": False,
                    "live_execution": False,
                },
                "contract": {
                    "user_data_read": False,
                    "credentials_read": False,
                    "signing_secret_read": False,
                    "application_network_used": False,
                    "live_execution": False,
                },
            }
        ),
        encoding="utf-8",
    )
    return {"dmg": dmg, "smoke_report": smoke, "n05_report": n05}


def test_pilot_package_requires_both_native_architectures(tmp_path):
    instructions = tmp_path / "instructions.md"
    instructions.write_text("trusted pilot instructions", encoding="utf-8")
    output = tmp_path / "pilot"

    with pytest.raises(MissingPilotEvidence, match="x86_64"):
        prepare_pilot_package(
            output=output,
            artifacts={"arm64": _chain(tmp_path, "arm64")},
            instructions=instructions,
        )
    assert not output.exists()


def test_pilot_package_binds_two_architectures_and_generates_checksums(tmp_path):
    instructions = tmp_path / "instructions.md"
    instructions.write_text("trusted pilot instructions", encoding="utf-8")
    chains = {
        architecture: _chain(tmp_path, architecture)
        for architecture in ("arm64", "x86_64")
    }

    manifest = prepare_pilot_package(
        output=tmp_path / "pilot",
        artifacts=chains,
        instructions=instructions,
    )

    output = tmp_path / "pilot"
    assert manifest["distribution"]["artifact_status"] == "AD_HOC_TRUSTED_PILOT_ONLY"
    assert manifest["distribution"]["download_integrity"] == {
        "sha256sums_required": True,
        "hdiutil_verify_required": True,
        "github_immutable_release_recommended": True,
    }
    assert manifest["claims"]["production_ready"] is False
    assert manifest["distribution"]["github_release_replaces_apple_notarization"] is False
    assert {item["architecture"] for item in manifest["artifacts"]} == {"arm64", "x86_64"}
    assert (output / MANIFEST_NAME).is_file()
    assert (output / INSTRUCTIONS_NAME).read_text(encoding="utf-8") == "trusted pilot instructions"

    checksums = {}
    for line in (output / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        digest, filename = line.split("  ", 1)
        checksums[filename] = digest
    assert set(checksums) == set(manifest["included_files"]) - {"SHA256SUMS"}
    for filename, digest in checksums.items():
        assert _sha256(output / filename) == digest


def test_arm64_pilot_package_is_explicitly_m_series_only(tmp_path):
    instructions = tmp_path / "instructions.md"
    instructions.write_text("M-series pilot instructions", encoding="utf-8")
    chain = _chain(tmp_path, "arm64")

    manifest = prepare_arm64_pilot_package(
        output=tmp_path / "pilot-arm64",
        artifacts={"arm64": chain},
        instructions=instructions,
        pilot_tag="pilot-v1.1.0",
    )

    output = tmp_path / "pilot-arm64"
    assert manifest["package_type"] == "TRUSTED_MACOS_PILOT_ARM64"
    assert manifest["pilot_scope"] == "APPLE_SILICON_M_SERIES_ONLY"
    assert manifest["distribution"]["artifact_status"] == "AD_HOC_TRUSTED_PILOT_ONLY_ARM64"
    assert manifest["distribution"]["release_channel"] == "PRIVATE_PRERELEASE_PILOT"
    assert manifest["distribution"]["pilot_tag"] == "pilot-v1.1.0"
    assert manifest["distribution"]["architectures"] == ["arm64"]
    assert manifest["distribution"]["dual_architecture_complete"] is False
    assert manifest["distribution"]["intel_artifact_included"] is False
    assert manifest["access_boundary"]["hardware_scope"] == "Apple Silicon M-series only (native arm64)"
    assert manifest["access_boundary"]["intel_support_claim"] is False
    assert {item["architecture"] for item in manifest["artifacts"]} == {"arm64"}
    assert (output / "Kuantra-Terminal-1.1.3-arm64.dmg").is_file()
    assert (output / INSTRUCTIONS_NAME).read_text(encoding="utf-8") == "M-series pilot instructions"


def test_pilot_package_rejects_canonical_product_tag(tmp_path):
    instructions = tmp_path / "instructions.md"
    instructions.write_text("M-series pilot instructions", encoding="utf-8")

    with pytest.raises(PilotPackageError, match="canonical product release tag"):
        prepare_arm64_pilot_package(
            output=tmp_path / "pilot-arm64",
            artifacts={"arm64": _chain(tmp_path, "arm64")},
            instructions=instructions,
            pilot_tag="v1.1.3",
        )


def test_pilot_package_rejects_cross_architecture_source_mix(tmp_path):
    instructions = tmp_path / "instructions.md"
    instructions.write_text("trusted pilot instructions", encoding="utf-8")
    chains = {
        "arm64": _chain(tmp_path, "arm64", commit="a" * 40),
        "x86_64": _chain(tmp_path, "x86_64", commit="f" * 40),
    }

    with pytest.raises(PilotPackageError, match="one exact source"):
        prepare_pilot_package(
            output=tmp_path / "pilot",
            artifacts=chains,
            instructions=instructions,
        )


def test_pilot_package_rejects_changed_dmg_after_smoke(tmp_path):
    instructions = tmp_path / "instructions.md"
    instructions.write_text("trusted pilot instructions", encoding="utf-8")
    chains = {
        architecture: _chain(tmp_path, architecture)
        for architecture in ("arm64", "x86_64")
    }
    chains["x86_64"]["dmg"].write_bytes(b"changed after smoke")

    with pytest.raises(PilotPackageError, match="artifact SHA"):
        prepare_pilot_package(
            output=tmp_path / "pilot",
            artifacts=chains,
            instructions=instructions,
        )
