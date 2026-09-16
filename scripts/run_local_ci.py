"""Run Kuantra's reproducible local merge gate.

GitHub Actions is an optional remote evidence source. This command is the canonical
merge gate when remote Actions are unavailable or disabled. It deliberately runs the
same product-truth, backend, frontend, freeze and packaged smoke boundaries in one
ordered process and writes a provenance report to ``dist/local-ci-report.json``.

Usage (from the repository root)::

    python scripts/run_local_ci.py

For a locked environment, invoke the command through uv, for example::

    uv run --offline --no-project --with-requirements backend/requirements.lock \
        python scripts/run_local_ci.py

The gate is fail-closed. A packaged smoke report can be green while the supported
platform renderer silently falls back to another renderer; the preflight check rejects
that condition instead of treating it as a passing desktop build.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from build_provenance import ProvenanceError, validate_report
from macos_architecture import canonical_architecture, native_host_matches


ROOT = Path(__file__).resolve().parents[1]
REPORT_DEFAULT = ROOT / "dist" / "local-ci-report.json"
REQUIRED_SMOKE_CHECKS = {
    "react_mounted",
    "bridge_roundtrip",
    "health",
    "push_sink",
    "plugin_boundary",
    "journal_export",
}
QT_FAILURE_MARKERS = (
    "Frozen Qt runtime preflight failed",
    "QT cannot be loaded",
)
QT_READY_MARKER = "Frozen Qt runtime bindings ready"
WEBVIEW2_FAILURE_MARKER = "Frozen WebView2 renderer preflight failed"
WEBVIEW2_READY_MARKER = "Frozen WebView2 renderer bindings ready"
RENDERER_INIT_MARKER = "Frozen renderer initialized:"
RENDERER_READY_MARKER = "Frozen renderer controller ready:"


def _python_command(*args: str) -> list[str]:
    return [sys.executable, *args]


def _npm_command() -> str:
    candidate = "npm.cmd" if os.name == "nt" else "npm"
    return shutil.which(candidate) or candidate


def _run_step(
    name: str,
    command: list[str],
    env: dict[str, str],
    timeout: float,
) -> dict[str, Any]:
    started = time.monotonic()
    print(f"\n[local-ci] {name}: {' '.join(command)}", flush=True)
    result: dict[str, Any] = {
        "name": name,
        "command": command,
        "status": "FAIL",
        "returncode": None,
        "duration_seconds": None,
    }
    try:
        completed = subprocess.run(
            command,
            cwd=str(ROOT),
            env=env,
            check=False,
            timeout=timeout,
        )
        result["returncode"] = completed.returncode
        result["status"] = "PASS" if completed.returncode == 0 else "FAIL"
    except subprocess.TimeoutExpired:
        result["status"] = "TIMEOUT"
        print(f"[local-ci] {name}: timeout after {timeout:g}s", file=sys.stderr, flush=True)
    except OSError as exc:
        result["status"] = "ERROR"
        result["error"] = str(exc)
        print(f"[local-ci] {name}: {exc}", file=sys.stderr, flush=True)
    result["duration_seconds"] = round(time.monotonic() - started, 3)
    print(f"[local-ci] {name}: {result['status']}", flush=True)
    return result


def _read_desktop_logs(data_dir: Path) -> str:
    chunks: list[str] = []
    for path in sorted(data_dir.rglob("*.log")):
        try:
            chunks.append(path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
    return "\n".join(chunks)


def _desktop_preflight(data_dir: Path) -> tuple[str, dict[str, Any]]:
    """Validate the renderer actually loaded by the frozen desktop process."""
    if sys.platform == "darwin":
        return "PASS", {"required": False, "reason": "macOS uses native WKWebView"}

    logs = _read_desktop_logs(data_dir)
    renderer = "edgechromium" if sys.platform.startswith("win") else "qt"
    failure_markers = QT_FAILURE_MARKERS if renderer == "qt" else (WEBVIEW2_FAILURE_MARKER,)
    ready_marker = QT_READY_MARKER if renderer == "qt" else WEBVIEW2_READY_MARKER
    failures = [marker for marker in failure_markers if marker in logs]
    if failures:
        return "FAIL", {
            "required": True,
            "renderer": renderer,
            "failure_markers": failures,
            "reason": f"supported {renderer} renderer failed to load; fallback is not merge-safe",
        }
    if ready_marker not in logs:
        return "FAIL", {
            "required": True,
            "renderer": renderer,
            "reason": f"no frozen {renderer} preflight success marker was recorded",
        }
    initialized = [line for line in logs.splitlines() if RENDERER_INIT_MARKER in line]
    expected_init = f"{RENDERER_INIT_MARKER} {renderer}"
    if not any(expected_init in line for line in initialized):
        return "FAIL", {
            "required": True,
            "renderer": renderer,
            "reason": f"frozen renderer identity was not attested as {renderer}",
            "initialization_lines": initialized[-5:],
        }
    ready_lines = [line for line in logs.splitlines() if RENDERER_READY_MARKER in line]
    expected_ready = f"{RENDERER_READY_MARKER} {renderer}"
    if not any(expected_ready in line for line in ready_lines):
        return "FAIL", {
            "required": True,
            "renderer": renderer,
            "reason": f"frozen renderer controller did not become ready as {renderer}",
            "ready_lines": ready_lines[-5:],
        }
    return "PASS", {
        "required": True,
        "renderer": renderer,
        "ready": True,
        "initialized": expected_init,
        "controller_ready": expected_ready,
    }


def _validate_smoke_report(path: Path) -> tuple[str, dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return "FAIL", {"reason": f"smoke report unavailable or invalid: {exc}"}
    checks = payload.get("checks")
    missing = sorted(REQUIRED_SMOKE_CHECKS - set(checks or {}))
    failed = sorted(name for name in REQUIRED_SMOKE_CHECKS if (checks or {}).get(name) is not True)
    if payload.get("ok") is not True or missing or failed:
        return "FAIL", {"reason": "required packaged smoke checks did not pass", "missing": missing, "failed": failed}
    expected_renderer = "edgechromium" if sys.platform.startswith("win") else "qt" if sys.platform.startswith("linux") else None
    renderer_expected = payload.get("renderer_expected")
    renderer_actual = payload.get("renderer_actual")
    if expected_renderer and (
        renderer_expected != expected_renderer
        or renderer_actual != expected_renderer
        or payload.get("renderer_controller_ready") is not True
    ):
        return "FAIL", {
            "reason": "packaged smoke did not attest the supported renderer",
            "renderer_expected": renderer_expected,
            "renderer_actual": renderer_actual,
            "renderer_controller_ready": payload.get("renderer_controller_ready"),
        }
    return "PASS", {
        "version": payload.get("version"),
        "checks": {name: checks[name] for name in sorted(REQUIRED_SMOKE_CHECKS)},
        "executable_sha256": payload.get("executable_sha256"),
        "truth_matrix": payload.get("truth_matrix"),
        "renderer_expected": renderer_expected,
        "renderer_actual": renderer_actual,
        "renderer_controller_ready": payload.get("renderer_controller_ready"),
    }


def _validate_smoke_provenance(
    path: Path,
    *,
    expected_architecture: str | None = None,
) -> tuple[str, dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        provenance = validate_report(payload, release_facing=False)
    except (OSError, json.JSONDecodeError, ProvenanceError) as exc:
        return "FAIL", {"reason": f"smoke provenance is incomplete: {exc}"}
    details = {
        "provenance_status": provenance.get("provenance_status"),
        "source_commit_sha": provenance.get("source_commit_sha"),
        "tracked_source_tree_status": provenance.get("tracked_source_tree_status"),
        "tracked_source_tree_sha256": provenance.get("tracked_source_tree_sha256"),
        "lock_hashes": provenance.get("lock_hashes"),
        "toolchain": provenance.get("toolchain"),
        "architecture": provenance.get("architecture"),
        "architecture_verified": provenance.get("architecture_verified"),
        "architecture_source": provenance.get("architecture_source"),
        "executable_sha256": provenance.get("executable_sha256"),
        "artifact_sha256": provenance.get("artifact_sha256"),
    }
    if expected_architecture is not None:
        observed_architecture = canonical_architecture(str(provenance.get("architecture") or ""))
        host_architecture = canonical_architecture(str(provenance.get("build_host_architecture") or ""))
        host_translation = provenance.get("build_host_translation")
        if (
            observed_architecture != expected_architecture
            or host_architecture != expected_architecture
            or host_translation != "native"
        ):
            return "FAIL", {
                **details,
                "reason": "expected native host/executable architecture was not proven",
                "expected_architecture": expected_architecture,
                "observed_architecture": observed_architecture,
                "build_host_architecture": host_architecture,
                "build_host_translation": host_translation,
            }
    return "PASS", details


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Kuantra local merge gate")
    parser.add_argument("--report", type=Path, default=REPORT_DEFAULT)
    parser.add_argument("--smoke-timeout", type=float, default=90.0)
    parser.add_argument("--keep-data", action="store_true", help="keep isolated test/smoke data directories")
    parser.add_argument(
        "--expected-architecture",
        default=None,
        help="on macOS, require a native arm64 or x86_64 host and matching executable",
    )
    args = parser.parse_args(argv)

    expected_architecture = None
    if args.expected_architecture is not None:
        expected_architecture = canonical_architecture(args.expected_architecture)
        if expected_architecture is None:
            parser.error(f"unsupported expected architecture: {args.expected_architecture}")
        if sys.platform != "darwin":
            parser.error("--expected-architecture is only valid for macOS local CI")
        native_ok, native_reason = native_host_matches(expected_architecture)
        if not native_ok:
            parser.error(f"native local-CI host check failed: {native_reason}")

    report_path = args.report if args.report.is_absolute() else ROOT / args.report
    report_path = report_path.resolve()
    test_data = Path(tempfile.mkdtemp(prefix="kuantra-local-ci-tests-"))
    smoke_data = Path(tempfile.mkdtemp(prefix="kuantra-local-ci-smoke-"))
    smoke_report = ROOT / "dist" / "local-ci-smoke.json"
    env = os.environ.copy()
    env.update(
        {
            "KUANTRA_DATA_DIR": str(test_data),
            "PYTHONUNBUFFERED": "1",
        }
    )

    started = time.monotonic()
    steps: list[dict[str, Any]] = []
    steps.append(_run_step("diff-check", ["git", "diff", "--check"], env, 60))
    steps.append(_run_step("compileall", _python_command("-m", "compileall", "-q", "backend"), env, 180))
    steps.append(_run_step("release-truth", _python_command("scripts/check_release_truth.py"), env, 120))
    steps.append(_run_step("packaging-integrity", _python_command("scripts/verify_packaging.py"), env, 120))
    steps.append(
        _run_step(
            "supply-chain-audit",
            _python_command(
                "scripts/supply_chain_audit.py",
                "--report",
                str(ROOT / "dist" / "h05-supply-chain-report.json"),
            ),
            env,
            180,
        )
    )
    steps.append(_run_step("backend-tests", _python_command("-m", "pytest", "backend/tests", "-q", "--tb=short"), env, 900))

    npm = _npm_command()
    steps.append(_run_step("frontend-tests", [npm, "--prefix", str(ROOT / "frontend"), "test"], env, 600))
    steps.append(_run_step("frontend-build", [npm, "--prefix", str(ROOT / "frontend"), "run", "build"], env, 600))

    build_command = _python_command("scripts/build_desktop.py", "--skip-frontend")
    if expected_architecture is not None:
        build_command.extend(["--expected-architecture", expected_architecture])
    build_step = _run_step("desktop-build", build_command, env, 1200)
    steps.append(build_step)

    if build_step["status"] == "PASS":
        smoke_env = env.copy()
        smoke_env["KUANTRA_DATA_DIR"] = str(smoke_data)
        smoke_env["KUANTRA_GATEWAY_ENABLED"] = "0"
        smoke_command = _python_command(
            "scripts/smoke_desktop.py",
            "--report",
            str(smoke_report),
            "--data-dir",
            str(smoke_data),
            "--timeout",
            str(args.smoke_timeout),
        )
        if expected_architecture is not None:
            smoke_command.extend(["--expected-architecture", expected_architecture])
        smoke_step = _run_step(
            "desktop-smoke",
            smoke_command,
            smoke_env,
            args.smoke_timeout + 90,
        )
        steps.append(smoke_step)
        smoke_status, smoke_details = _validate_smoke_report(smoke_report)
        if smoke_step["status"] != "PASS":
            smoke_status = "FAIL"
            smoke_details = {
                **smoke_details,
                "reason": "packaged smoke process did not exit successfully",
                "process_status": smoke_step["status"],
            }
        steps.append({
            "name": "desktop-smoke-contract",
            "status": smoke_status,
            "returncode": 0 if smoke_status == "PASS" else 1,
            "duration_seconds": 0,
            "details": smoke_details,
        })
        renderer_status, renderer_details = _desktop_preflight(smoke_data)
        steps.append({
            "name": "desktop-renderer-preflight",
            "status": renderer_status,
            "returncode": 0 if renderer_status == "PASS" else 1,
            "duration_seconds": 0,
            "details": renderer_details,
        })
        provenance_status, provenance_details = _validate_smoke_provenance(
            smoke_report,
            expected_architecture=expected_architecture,
        )
        steps.append({
            "name": "provenance-contract",
            "status": provenance_status,
            "returncode": 0 if provenance_status == "PASS" else 1,
            "duration_seconds": 0,
            "details": provenance_details,
        })
    else:
        steps.append({
            "name": "desktop-smoke",
            "status": "BLOCKED",
            "returncode": None,
            "duration_seconds": 0,
            "details": {"reason": "desktop build failed"},
        })

    failed = [step["name"] for step in steps if step["status"] not in {"PASS"}]
    smoke_provenance: dict[str, Any] = {}
    if smoke_report.is_file():
        try:
            smoke_payload = json.loads(smoke_report.read_text(encoding="utf-8"))
            if isinstance(smoke_payload, dict) and isinstance(smoke_payload.get("build_provenance"), dict):
                smoke_provenance = smoke_payload["build_provenance"]
        except (OSError, json.JSONDecodeError):
            smoke_provenance = {}
    report = {
        "local_ci_schema_version": 1,
        "policy": "KDG-002@1.1.0",
        "started_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "duration_seconds": round(time.monotonic() - started, 3),
        "product_version": _product_version(),
        "platform": platform.system().lower(),
        "expected_architecture": expected_architecture,
        "architecture": smoke_provenance.get("architecture", platform.machine()),
        "build_host_architecture": smoke_provenance.get("build_host_architecture", platform.machine()),
        "python": sys.version.split()[0],
        "test_data_dir": str(test_data),
        "smoke_data_dir": str(smoke_data),
        "provenance_status": smoke_provenance.get("provenance_status", "INCOMPLETE"),
        "build_provenance": smoke_provenance,
        "merge_ready": not failed,
        "failed_steps": failed,
        "steps": steps,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\n[local-ci] report: {report_path}")
    print("[local-ci] " + ("MERGE READY" if not failed else "MERGE BLOCKED: " + ", ".join(failed)))

    if not args.keep_data and not failed:
        shutil.rmtree(test_data, ignore_errors=True)
        shutil.rmtree(smoke_data, ignore_errors=True)
    return 0 if not failed else 1


def _product_version() -> str:
    version_path = ROOT / "backend" / "app" / "version.py"
    for line in version_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("__version__"):
            return line.split("=", 1)[1].strip().strip("\"'")
    return "UNKNOWN"


if __name__ == "__main__":
    raise SystemExit(main())
