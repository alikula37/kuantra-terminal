"""Run the packaged app's renderer smoke self-test. Exit code = smoke result.

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
from build_provenance import (  # noqa: E402
    collect_provenance,
    default_artifact_for_executable,
)
from macos_architecture import canonical_architecture, detect_executable_architecture  # noqa: E402
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
    artifact = artifact_path or default_artifact_for_executable(executable_path)
    provenance = collect_provenance(
        ROOT,
        executable=executable_path,
        artifact=artifact,
    )
    report["smoke_schema_version"] = 2
    report["version_expected"] = __version__
    report["platform"] = platform.system().lower()
    report["architecture"] = provenance["architecture"]
    report["architecture_verified"] = provenance["architecture_verified"]
    report["build_host_architecture"] = provenance["build_host_architecture"]
    report["executable_path"] = provenance["executable_path"]
    report["executable_sha256"] = provenance["executable_sha256"]
    report["artifact_path"] = provenance["artifact_path"]
    report["artifact_sha256"] = provenance["artifact_sha256"]
    report["build_commit"] = provenance["source_commit_sha"] or "UNKNOWN"
    report["provenance_status"] = provenance["provenance_status"]
    report["build_provenance"] = provenance
    report["truth_matrix"] = {
        "document_id": matrix["document_id"],
        "version": matrix["version"],
        "product_version": product["version"],
        "sha256": canonical_matrix_digest(matrix),
    }
    report["recorded_at_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return report


def terminate_webview2_for_data_dir(data_dir: Path) -> None:
    """Stop WebView2 roots that detached after a controller initialization failure."""
    try:
        import psutil
    except ImportError:
        return
    marker = str(data_dir.resolve()).lower()
    for _ in range(3):
        targets = []
        for process in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                name = (process.info.get("name") or "").lower()
                command_line = " ".join(process.info.get("cmdline") or []).lower()
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                continue
            if name == "msedgewebview2.exe" and marker in command_line:
                targets.append(process)
        if not targets:
            return
        for process in targets:
            try:
                process.kill()
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                pass
        gone, _ = psutil.wait_procs(targets, timeout=2)
        if len(gone) == len(targets):
            return


def terminate_process_tree(proc: subprocess.Popen, data_dir: Path | None = None) -> None:
    """Stop the packaged process and any WebView2 descendants it owns."""
    if proc.poll() is not None:
        return
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired):
            pass
    else:
        proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)
    if data_dir is not None:
        terminate_webview2_for_data_dir(data_dir)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", default=str(ROOT / "dist" / "smoke.json"))
    ap.add_argument("--timeout", type=float, default=120)
    ap.add_argument("--executable", default=None, help="explicit packaged executable or AppImage")
    ap.add_argument("--artifact", default=None, help="installer/DMG/AppImage represented by this smoke")
    ap.add_argument("--appimage", action="store_true", help="run the executable through AppImage extraction")
    ap.add_argument("--data-dir", default=None, help="isolated writable data directory for the smoke run")
    ap.add_argument(
        "--expected-architecture",
        default=None,
        help="require the explicit executable to be one native arm64 or x86_64 binary",
    )
    args = ap.parse_args()

    exe = Path(args.executable).resolve() if args.executable else executable()
    if not exe.exists():
        print(f"built executable missing: {exe} (run scripts/build_desktop.py first)", file=sys.stderr)
        return 1

    if args.expected_architecture is not None:
        expected_architecture = canonical_architecture(args.expected_architecture)
        if expected_architecture is None:
            print(
                f"unsupported expected architecture: {args.expected_architecture}",
                file=sys.stderr,
            )
            return 1
        detected = detect_executable_architecture(exe)
        if detected.get("verified") is not True:
            print(
                f"executable architecture is not independently verified: {detected}",
                file=sys.stderr,
            )
            return 1
        if detected.get("architecture") != expected_architecture:
            print(
                "executable architecture mismatch: "
                f"expected {expected_architecture}, got {detected.get('architecture')}",
                file=sys.stderr,
            )
            return 1

    artifact = Path(args.artifact).resolve() if args.artifact else None
    report = Path(args.report).resolve()
    report.parent.mkdir(parents=True, exist_ok=True)
    if report.exists():
        report.unlink()
    data_dir = Path(args.data_dir).resolve() if args.data_dir else ROOT / "dist" / "smoke-data"
    env = {**os.environ,
           "KUANTRA_DATA_DIR": str(data_dir),
           "KUANTRA_GATEWAY_ENABLED": "0"}
    if args.appimage:
        env["APPIMAGE_EXTRACT_AND_RUN"] = "1"
    hard_timeout = args.timeout + 15
    proc = subprocess.Popen(
        [str(exe), "--smoke", "--smoke-report", args.report, "--smoke-timeout", str(args.timeout)],
        env=env,
    )
    deadline = time.monotonic() + hard_timeout
    terminated_for_renderer_failure = False
    terminated_after_success = False
    while proc.poll() is None:
        if report.exists():
            try:
                early_payload = json.loads(report.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                early_payload = {}
            if early_payload.get("renderer_controller_ready") is False:
                terminated_for_renderer_failure = True
                terminate_process_tree(proc, data_dir)
                break
            if early_payload.get("renderer_controller_ready") is True and early_payload.get("ok") is True:
                # A successful report is authoritative. The desktop shell may keep a native GUI
                # or network worker alive after window.destroy(), so do not leave the local gate
                # blocked on process shutdown.
                terminated_after_success = True
                terminate_process_tree(proc, data_dir)
                break
        if time.monotonic() >= deadline:
            terminate_process_tree(proc, data_dir)
            print(f"SMOKE FAIL (timeout after {hard_timeout:g} s)")
            return 1
        time.sleep(0.25)
    if terminated_for_renderer_failure:
        print("SMOKE FAIL (renderer controller did not become ready)")
    terminate_webview2_for_data_dir(data_dir)
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
    process_ok = proc.returncode == 0 or terminated_after_success
    ok = (
        process_ok
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
