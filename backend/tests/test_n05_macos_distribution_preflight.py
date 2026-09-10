"""N05 exact macOS signing/notarization preflight contract tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.run_n05_macos_distribution_preflight import (
    CommandResult,
    N05DistributionError,
    validate_n05_report,
    verify_mounted_distribution,
)


def _report(dmg: Path, executable: Path, *, architecture: str = "arm64") -> dict:
    digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    executable_sha = digest(executable)
    dmg_sha = digest(dmg)
    provenance = {
        "source_commit_sha": "a" * 40,
        "checkout_commit_sha": "a" * 40,
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
            "uv": "0.12.10",
            "pyinstaller": "6.22.2",
        },
        "os": "darwin",
        "os_version": "macOS-26.6.2-arm64",
        "architecture": architecture,
        "architecture_verified": True,
        "architecture_source": "executable",
        "executable_architectures": [architecture],
        "build_host_architecture": architecture,
        "build_host_translation": "native",
        "executable_path": "/private/temporary-mount/Kuantra Terminal.app/Contents/MacOS/Kuantra Terminal",
        "executable_sha256": executable_sha,
        "artifact_path": str(dmg.resolve()),
        "artifact_sha256": dmg_sha,
        "provenance_status": "COMPLETE",
    }
    return {
        "platform": "darwin",
        "architecture": architecture,
        "ok": True,
        "renderer_actual": "wkwebview",
        "renderer_controller_ready": True,
        "artifact_path": str(dmg.resolve()),
        "artifact_sha256": dmg_sha,
        "executable_sha256": executable_sha,
        "build_commit": "a" * 40,
        "build_provenance": provenance,
        "macos_dmg_smoke": {
            "status": "PASS",
            "mount_mode": "readonly",
            "executable_from_mount": True,
        },
    }


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path, dict]:
    app = tmp_path / "Kuantra Terminal.app"
    executable = app / "Contents" / "MacOS" / "Kuantra Terminal"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"synthetic executable")
    dmg = tmp_path / "Kuantra-Terminal-1.0.0-aarch64.dmg"
    dmg.write_bytes(b"synthetic dmg")
    report = _report(dmg, executable)
    return app, executable, dmg, report


def _runner(*, developer_id: bool, ticket: bool = True, unknown_entitlement: bool = False):
    authority = "Developer ID Application: Kuantra Test (TEAM123)" if developer_id else None
    flags = "0x10000(runtime)" if developer_id else "0x2(adhoc)"
    info = "\n".join(
        [
            "Identifier=com.kuantra.terminal",
            "Format=app bundle with Mach-O thin (arm64)",
            f"CodeDirectory v=20400 flags={flags} hashes=1+3 location=embedded",
            "Signature=adhoc" if not developer_id else "Signature=CMS",
            "TeamIdentifier=TEAM123" if developer_id else "TeamIdentifier=not set",
            *( [f"Authority={authority}"] if authority else [] ),
        ]
    )
    entitlement_xml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
        "<!DOCTYPE plist PUBLIC \"-//Apple//DTD PLIST 1.0//EN\" \"http://www.apple.com/DTDs/PropertyList-1.0.dtd\">"
        "<plist version=\"1.0\"><dict>"
        + ("<key>com.example.unapproved</key><true/>" if unknown_entitlement else "")
        + "</dict></plist>"
    )

    def run(command):
        if command[0] == "codesign" and command[1] == "-dv":
            return CommandResult(0, stderr=info)
        if command[0] == "codesign" and command[1] == "--verify":
            return CommandResult(0)
        if command[0] == "codesign" and command[1] == "-d":
            return CommandResult(0, stdout=entitlement_xml)
        if command[0] == "spctl":
            return CommandResult(0 if developer_id else 1, stderr="PRIVATE-GATEKEEPER-DIAGNOSTIC")
        if command[0] == "xcrun":
            return CommandResult(0 if ticket else 1, stderr="PRIVATE-TICKET-DIAGNOSTIC")
        raise AssertionError(command)

    return run


def test_ad_hoc_artifact_is_blocked_without_persisting_raw_signing_output(tmp_path: Path) -> None:
    app, executable, dmg, report = _fixture(tmp_path)
    result = verify_mounted_distribution(app, dmg, report, runner=_runner(developer_id=False))

    assert result["status"] == "BLOCKED"
    assert result["acceptance_status"] == "OWNER_REVIEW_REQUIRED"
    assert result["signing"]["identity_type"] == "AD_HOC"
    assert result["notarization"]["release_gate_pass"] is False
    assert result["commands"]["raw_output_recorded"] is False
    assert "PRIVATE" not in json.dumps(result)
    assert result["claims"]["production_ready"] is False


def test_developer_id_hardened_runtime_and_ticket_can_pass_n05(tmp_path: Path) -> None:
    app, executable, dmg, report = _fixture(tmp_path)
    result = verify_mounted_distribution(app, dmg, report, runner=_runner(developer_id=True))

    assert result["status"] == "PASS"
    assert result["acceptance_status"] == "N05_COMPLETE"
    assert result["signing"]["identity_type"] == "DEVELOPER_ID_APPLICATION"
    assert result["signing"]["hardened_runtime"] is True
    assert result["notarization"]["release_gate_pass"] is True
    assert result["claims"]["production_ready"] is False


def test_serialized_n05_pass_is_safe_to_bind_to_release_manifest(tmp_path: Path) -> None:
    app, executable, dmg, report = _fixture(tmp_path)
    result = verify_mounted_distribution(app, dmg, report, runner=_runner(developer_id=True))
    result["mount"] = {"mode": "readonly", "attached": True, "detached": True}

    validated = validate_n05_report(
        result,
        artifact_sha256=report["artifact_sha256"],
        source_commit_sha=report["build_commit"],
    )

    assert validated["status"] == "PASS"
    assert validated["commands"]["raw_output_recorded"] is False


def test_unapproved_entitlement_is_fail_closed(tmp_path: Path) -> None:
    app, executable, dmg, report = _fixture(tmp_path)
    result = verify_mounted_distribution(
        app,
        dmg,
        report,
        runner=_runner(developer_id=True, unknown_entitlement=True),
    )

    assert result["status"] == "BLOCKED"
    assert "unapproved_entitlements" in result["issues"]
    assert result["signing"]["unapproved_entitlement_keys"] == ["com.example.unapproved"]


def test_executable_provenance_mismatch_is_not_a_blocked_owner_gate(tmp_path: Path) -> None:
    app, executable, dmg, report = _fixture(tmp_path)
    report["build_provenance"]["executable_sha256"] = "e" * 64
    report["executable_sha256"] = "e" * 64

    with pytest.raises(N05DistributionError, match="executable SHA"):
        verify_mounted_distribution(app, dmg, report, runner=_runner(developer_id=True))


def test_app_symlink_cannot_escape_mount(tmp_path: Path) -> None:
    app, executable, dmg, report = _fixture(tmp_path)
    mount = tmp_path / "mount"
    mount.mkdir()
    escaped = tmp_path / "escaped.app"
    escaped.symlink_to(app, target_is_directory=True)

    with pytest.raises(N05DistributionError, match="escapes"):
        verify_mounted_distribution(escaped, dmg, report, runner=_runner(developer_id=True), mounted_root=mount)
