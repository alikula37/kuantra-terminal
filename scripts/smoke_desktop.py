"""Run the packaged app's headless self-test. Exit code = smoke result.

Usage: python scripts/smoke_desktop.py [--report PATH] [--timeout SECONDS]
"""
import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.version import __version__  # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))
from release_truth import DEFAULT_MATRIX_PATH, canonical_matrix_digest, load_matrix  # noqa: E402


def executable() -> Path:
    if sys.platform == "darwin":
        return ROOT / "dist" / "Kuantra Terminal.app" / "Contents" / "MacOS" / "Kuantra Terminal"
    if sys.platform.startswith("win"):
        return ROOT / "dist" / "Kuantra Terminal" / "Kuantra Terminal.exe"
    return ROOT / "dist" / "kuantra-terminal" / "kuantra-terminal"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def enrich_report(report: dict, executable_path: Path, artifact_path: Path | None) -> dict:
    """Attach reproducible provenance to a successful or failed smoke report."""
    matrix = load_matrix(DEFAULT_MATRIX_PATH)
    product = matrix["product"]
    report["smoke_schema_version"] = 2
    report["version_expected"] = __version__
    report["platform"] = platform.system().lower()
    report["architecture"] = platform.machine()
    report["executable_path"] = str(executable_path.resolve())
    report["executable_sha256"] = sha256(executable_path) if executable_path.is_file() else None
    report["artifact_path"] = str(artifact_path.resolve()) if artifact_path else None
    report["artifact_sha256"] = sha256(artifact_path) if artifact_path and artifact_path.is_file() else None
    report["build_commit"] = os.environ.get("GITHUB_SHA") or os.environ.get("KUANTRA_BUILD_COMMIT", "UNKNOWN")
    report["truth_matrix"] = {
        "document_id": matrix["document_id"],
        "version": matrix["version"],
        "product_version": product["version"],
        "sha256": canonical_matrix_digest(matrix),
    }
    report["recorded_at_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", default=str(ROOT / "dist" / "smoke.json"))
    ap.add_argument("--timeout", type=float, default=120)
    ap.add_argument("--executable", default=None, help="explicit packaged executable or AppImage")
    ap.add_argument("--artifact", default=None, help="installer/DMG/AppImage represented by this smoke")
    ap.add_argument("--appimage", action="store_true", help="run the executable through AppImage extraction")
    ap.add_argument("--data-dir", default=None, help="isolated writable data directory for the smoke run")
    args = ap.parse_args()

    exe = Path(args.executable).resolve() if args.executable else executable()
    if not exe.exists():
        print(f"built executable missing: {exe} (run scripts/build_desktop.py first)", file=sys.stderr)
        return 1

    artifact = Path(args.artifact).resolve() if args.artifact else None
    data_dir = Path(args.data_dir).resolve() if args.data_dir else ROOT / "dist" / "smoke-data"
    env = {**os.environ,
           "KUANTRA_DATA_DIR": str(data_dir),
           "KUANTRA_GATEWAY_ENABLED": "0"}
    if args.appimage:
        env["APPIMAGE_EXTRACT_AND_RUN"] = "1"
    hard_timeout = args.timeout + 60
    try:
        proc = subprocess.run(
            [str(exe), "--smoke", "--smoke-report", args.report, "--smoke-timeout", str(args.timeout)],
            env=env, timeout=hard_timeout,
        )
    except subprocess.TimeoutExpired:
        print(f"SMOKE FAIL (timeout after {hard_timeout:g} s)")
        return 1
    report = Path(args.report)
    if report.exists():
        try:
            payload = json.loads(report.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                payload = {"ok": False, "reason": "smoke report is not a JSON object"}
        except (OSError, json.JSONDecodeError) as exc:
            payload = {"ok": False, "reason": f"invalid smoke report: {exc}"}
    else:
        payload = {"ok": False, "reason": "no smoke report written"}
    payload = enrich_report(payload, exe, artifact)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    required_checks = {"react_mounted", "bridge_roundtrip", "health", "push_sink", "plugin_boundary"}
    checks = payload.get("checks", {})
    ok = (
        proc.returncode == 0
        and payload.get("ok") is True
        and payload.get("version") == __version__
        and payload.get("truth_matrix", {}).get("product_version") == __version__
        and required_checks.issubset(checks)
        and all(checks.get(name) is True for name in required_checks)
    )
    print("SMOKE " + ("OK" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
