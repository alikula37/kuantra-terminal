"""Smoke the executable selected from a read-only mounted macOS DMG."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from build_provenance import ProvenanceError, validate_report  # noqa: E402


class DmgSmokeError(ValueError):
    """Raised when the final mounted-DMG smoke boundary is not proven."""


def _sha256_file(path: Path) -> str:
    if not path.is_file():
        raise DmgSmokeError(f"missing file for hash: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_macos_dmg_report(
    report: Mapping[str, Any],
    *,
    dmg: Path,
    executable: Path,
) -> dict[str, str]:
    """Validate report identity against the exact mounted executable and DMG."""

    try:
        validate_report(report, release_facing=True)
    except ProvenanceError as exc:
        raise DmgSmokeError(f"release provenance is incomplete: {exc}") from exc

    if report.get("renderer_actual") != "wkwebview":
        raise DmgSmokeError("mounted macOS smoke did not use wkwebview")
    if report.get("renderer_controller_ready") is not True:
        raise DmgSmokeError("mounted macOS WKWebView controller is not ready")
    executable = executable.resolve()
    dmg = dmg.resolve()
    if "Contents" not in executable.parts or "MacOS" not in executable.parts:
        raise DmgSmokeError("mounted executable is not inside an app Contents/MacOS path")
    if Path(str(report.get("executable_path") or "")).resolve() != executable:
        raise DmgSmokeError("report executable path does not match mounted executable")
    if Path(str(report.get("artifact_path") or "")).resolve() != dmg:
        raise DmgSmokeError("report artifact path does not match DMG")
    executable_sha = _sha256_file(executable)
    artifact_sha = _sha256_file(dmg)
    if report.get("executable_sha256") != executable_sha:
        raise DmgSmokeError("mounted executable SHA does not match report")
    if report.get("artifact_sha256") != artifact_sha:
        raise DmgSmokeError("artifact SHA does not match report")
    provenance = report.get("build_provenance")
    if not isinstance(provenance, Mapping):
        raise DmgSmokeError("build provenance is missing")
    if provenance.get("executable_sha256") != executable_sha:
        raise DmgSmokeError("provenance executable SHA does not match mounted executable")
    if provenance.get("artifact_sha256") != artifact_sha:
        raise DmgSmokeError("provenance artifact SHA does not match DMG")
    return {
        "renderer": "wkwebview",
        "executable_sha256": executable_sha,
        "artifact_sha256": artifact_sha,
    }


def _read_report(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DmgSmokeError(f"smoke report is missing or invalid: {exc}") from exc
    if not isinstance(payload, dict):
        raise DmgSmokeError("smoke report must be a JSON object")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Smoke the final executable from a mounted macOS DMG")
    parser.add_argument("--dmg", type=Path, required=True)
    parser.add_argument("--report", type=Path, default=ROOT / "dist" / "macos-dmg-smoke.json")
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--timeout", type=float, default=90.0)
    args = parser.parse_args(argv)
    if sys.platform != "darwin":
        print("[dmg-smoke] FAIL: exact DMG smoke requires macOS", file=sys.stderr)
        return 1

    dmg = args.dmg.resolve()
    report_path = args.report.resolve()
    if not dmg.is_file():
        print(f"[dmg-smoke] FAIL: missing DMG: {dmg}", file=sys.stderr)
        return 1
    mountpoint = Path(tempfile.mkdtemp(prefix="kuantra-dmg-smoke-"))
    generated_data_dir = args.data_dir is None
    data_dir = args.data_dir.resolve() if args.data_dir else Path(tempfile.mkdtemp(prefix="kuantra-dmg-data-"))
    attached = False
    detached = False
    payload: dict[str, Any] | None = None
    error: Exception | None = None
    try:
        attached_result = subprocess.run(
            ["hdiutil", "attach", "-nobrowse", "-readonly", "-mountpoint", str(mountpoint), str(dmg)],
            check=False,
            capture_output=True,
            text=True,
        )
        if attached_result.returncode != 0:
            raise DmgSmokeError(
                f"read-only DMG attach failed: {attached_result.stderr.strip() or attached_result.stdout.strip()}"
            )
        attached = True
        executable = mountpoint / "Kuantra Terminal.app" / "Contents" / "MacOS" / "Kuantra Terminal"
        if not executable.is_file():
            raise DmgSmokeError(f"mounted DMG executable missing: {executable}")
        report_path.parent.mkdir(parents=True, exist_ok=True)
        env = {**os.environ, "KUANTRA_DATA_DIR": str(data_dir), "KUANTRA_GATEWAY_ENABLED": "0"}
        smoke = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "smoke_desktop.py"),
                "--executable", str(executable),
                "--artifact", str(dmg),
                "--report", str(report_path),
                "--data-dir", str(data_dir),
                "--timeout", str(args.timeout),
            ],
            cwd=str(ROOT),
            env=env,
            check=False,
        )
        payload = _read_report(report_path)
        if smoke.returncode != 0:
            raise DmgSmokeError("mounted DMG desktop smoke process failed")
        identity = validate_macos_dmg_report(payload, dmg=dmg, executable=executable)
        payload["macos_dmg_smoke"] = {
            "status": "PASS",
            "mount_mode": "readonly",
            "executable_from_mount": True,
            "renderer": identity["renderer"],
            "executable_sha256": identity["executable_sha256"],
            "artifact_sha256": identity["artifact_sha256"],
        }
    except Exception as exc:  # noqa: BLE001 - convert mount/smoke failures to one gate result
        error = exc
    finally:
        if attached:
            detached_result = subprocess.run(
                ["hdiutil", "detach", str(mountpoint), "-force"],
                check=False,
                capture_output=True,
                text=True,
            )
            detached = detached_result.returncode == 0
        shutil.rmtree(mountpoint, ignore_errors=True)
        if generated_data_dir:
            shutil.rmtree(data_dir, ignore_errors=True)

    if payload is not None:
        payload.setdefault("macos_dmg_smoke", {})
        payload["macos_dmg_smoke"]["mount_detached"] = detached
        if error is not None:
            payload["macos_dmg_smoke"]["status"] = "FAIL"
            payload["macos_dmg_smoke"]["reason"] = str(error)
        report_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    if error is not None:
        print(f"[dmg-smoke] FAIL: {error}", file=sys.stderr)
        return 1
    if not detached:
        print("[dmg-smoke] FAIL: DMG detach was not confirmed", file=sys.stderr)
        return 1
    print(f"[dmg-smoke] PASS: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

