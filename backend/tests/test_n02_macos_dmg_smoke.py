"""N02 exact mounted-DMG and WKWebView smoke contracts."""

from pathlib import Path

import pytest

from scripts.build_provenance import collect_provenance
from scripts.macos_architecture import host_architecture
from scripts.smoke_macos_dmg import DmgSmokeError, validate_macos_dmg_report


ROOT = Path(__file__).resolve().parents[2]


def _report(tmp_path):
    executable = tmp_path / "mounted" / "Kuantra Terminal.app" / "Contents" / "MacOS" / "Kuantra Terminal"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"mounted executable")
    dmg = tmp_path / "Kuantra-Terminal-test.dmg"
    dmg.write_bytes(b"dmg artifact")
    provenance = dict(collect_provenance(ROOT, executable=executable, artifact=dmg))
    architecture = host_architecture() or "x86_64"
    provenance["tracked_source_tree_status"] = "clean"
    provenance["provenance_status"] = "COMPLETE"
    provenance["source_commit_matches_checkout"] = True
    provenance["architecture"] = architecture
    provenance["architecture_verified"] = True
    provenance["architecture_source"] = "executable"
    provenance["executable_architectures"] = [architecture]
    return (
        {
            "build_commit": provenance["source_commit_sha"],
            "architecture": architecture,
            "executable_sha256": provenance["executable_sha256"],
            "artifact_sha256": provenance["artifact_sha256"],
            "executable_path": str(executable.resolve()),
            "artifact_path": str(dmg.resolve()),
            "build_provenance": provenance,
            "renderer_actual": "wkwebview",
            "renderer_controller_ready": True,
        },
        dmg,
        executable,
    )


def test_macos_dmg_validator_requires_mounted_wkwebview_identity(tmp_path):
    report, dmg, executable = _report(tmp_path)

    assert validate_macos_dmg_report(report, dmg=dmg, executable=executable)["renderer"] == "wkwebview"

    report["renderer_actual"] = "qt"
    with pytest.raises(DmgSmokeError, match="wkwebview"):
        validate_macos_dmg_report(report, dmg=dmg, executable=executable)


def test_macos_dmg_validator_rejects_path_or_hash_mismatch(tmp_path):
    report, dmg, executable = _report(tmp_path)
    report["artifact_sha256"] = "0" * 64
    with pytest.raises(DmgSmokeError, match="artifact_sha256"):
        validate_macos_dmg_report(report, dmg=dmg, executable=executable)


def test_macos_dmg_script_contains_readonly_mount_explicit_executable_and_detach():
    script = (ROOT / "scripts" / "smoke_macos_dmg.py").read_text(encoding="utf-8")
    for needle in (
        "hdiutil",
        "verify",
        "-readonly",
        "-mountpoint",
        "hdiutil",
        "detach",
        "Contents",
        "MacOS",
        "--artifact",
        "wkwebview",
    ):
        assert needle in script
