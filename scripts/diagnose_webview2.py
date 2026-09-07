"""Run a bounded, Kuantra-independent WebView2 controller probe on Windows.

The parent process owns the timeout and kills the GUI child after a report is
written. This is deliberate: a WebView2 controller that never becomes ready
can leave a native GUI loop alive even after the Python callback returns.

The probe does not start the Kuantra backend, does not load the Kuantra
frontend, and does not change production renderer flags. It records runtime,
interop, controller, JavaScript, environment, and DPI evidence in one JSON
report. The report and the temporary WebView2 user-data directory are kept for
forensics unless the caller removes them explicitly.
"""

from __future__ import annotations

import argparse
import ctypes
import importlib.metadata
import json
import logging
import os
import platform
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


RUNTIME_GUID = "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
MIN_RUNTIME = "86.0.622.0"
RELEVANT_ENVIRONMENT_KEYS = (
    "PYWEBVIEW_GUI",
    "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS",
    "WEBVIEW2_BROWSER_EXECUTABLE_FOLDER",
    "WEBVIEW2_USER_DATA_FOLDER",
    "QTWEBENGINE_CHROMIUM_FLAGS",
)
PROBE_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><title>Kuantra WebView2 Probe</title></head>
<body><main id="probe" data-ready="true">WebView2 controller probe</main></body></html>"""


class _ProbeApi:
    """Minimal js_api surface used to isolate pywebview API binding effects."""

    def ping(self) -> str:
        return "pong"


class _ProbeRuntime:
    pass


class _ProbePush:
    pass


def _version_at_least(version: str, minimum: str) -> bool:
    try:
        current = tuple(int(part) for part in str(version).split(".")[:4])
        required = tuple(int(part) for part in str(minimum).split(".")[:4])
    except (AttributeError, TypeError, ValueError):
        return False
    return current >= required


def _runtime_registry() -> list[dict[str, Any]]:
    """Return non-secret WebView2 Evergreen registration evidence."""
    if not sys.platform.startswith("win"):
        return []
    try:
        import winreg
    except ImportError:
        return []

    paths = (
        rf"SOFTWARE\Microsoft\EdgeUpdate\Clients\{RUNTIME_GUID}",
        rf"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{RUNTIME_GUID}",
    )
    hives = (("HKCU", winreg.HKEY_CURRENT_USER), ("HKLM", winreg.HKEY_LOCAL_MACHINE))
    views = (
        ("64", getattr(winreg, "KEY_WOW64_64KEY", 0)),
        ("32", getattr(winreg, "KEY_WOW64_32KEY", 0)),
        ("default", 0),
    )
    records: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for hive_name, hive in hives:
        for view_name, view in views:
            for registry_path in paths:
                try:
                    with winreg.OpenKey(hive, registry_path, 0, winreg.KEY_READ | view) as key:
                        values: dict[str, Any] = {}
                        for value_name in ("pv", "name"):
                            try:
                                value, _ = winreg.QueryValueEx(key, value_name)
                            except OSError:
                                continue
                            if isinstance(value, (str, int, float, bool)) or value is None:
                                values[value_name] = value
                        if not values:
                            continue
                        identity = (hive_name, view_name, registry_path, tuple(sorted(values.items())))
                        if identity in seen:
                            continue
                        seen.add(identity)
                        records.append(
                            {
                                "hive": hive_name,
                                "view": view_name,
                                "path": registry_path,
                                "values": values,
                            }
                        )
                except OSError:
                    continue
    return records


def _runtime_summary() -> dict[str, Any]:
    registrations = _runtime_registry()
    versions = [
        str(record["values"]["pv"])
        for record in registrations
        if "pv" in record.get("values", {})
    ]
    valid_versions = [version for version in versions if _version_at_least(version, MIN_RUNTIME)]
    return {
        "guid": RUNTIME_GUID,
        "minimum_version": MIN_RUNTIME,
        "registered": bool(registrations),
        "available": bool(valid_versions),
        "versions": sorted(set(versions)),
        "registrations": registrations,
    }


def _safe_environment() -> dict[str, str]:
    return {key: os.environ[key] for key in RELEVANT_ENVIRONMENT_KEYS if key in os.environ}


def _package_versions() -> dict[str, str | None]:
    versions: dict[str, str | None] = {}
    for distribution in ("pywebview", "pythonnet"):
        try:
            versions[distribution] = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            versions[distribution] = None
    return versions


def _dpi_summary() -> dict[str, Any]:
    if not sys.platform.startswith("win"):
        return {"available": False, "reason": "Windows-only diagnostic"}
    result: dict[str, Any] = {"available": True}
    try:
        user32 = ctypes.windll.user32
        result["system_dpi"] = int(user32.GetDpiForSystem())
    except (AttributeError, OSError, TypeError, ValueError) as exc:
        result["system_dpi_error"] = f"{type(exc).__name__}: {exc}"
    try:
        shcore = ctypes.windll.shcore
        awareness = ctypes.c_int()
        result["process_dpi_awareness_result"] = int(
            shcore.GetProcessDpiAwareness(None, ctypes.byref(awareness))
        )
        result["process_dpi_awareness"] = int(awareness.value)
    except (AttributeError, OSError, TypeError, ValueError) as exc:
        result["process_dpi_awareness_error"] = f"{type(exc).__name__}: {exc}"
    return result


def _base_report(user_data_dir: Path, scenario: str = "standalone") -> dict[str, Any]:
    windows = sys.getwindowsversion() if sys.platform.startswith("win") else None
    return {
        "schema_version": 1,
        "probe": "webview2-controller",
        "scenario": scenario,
        "started_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "platform": platform.system().lower(),
        "platform_release": platform.release(),
        "platform_version": platform.version(),
        "architecture": platform.machine(),
        "python": sys.version,
        "windows_version": (
            {
                "major": windows.major,
                "minor": windows.minor,
                "build": windows.build,
                "platform": windows.platform,
            }
            if windows
            else None
        ),
        "package_versions": _package_versions(),
        "environment": _safe_environment(),
        "dpi": _dpi_summary(),
        "runtime": _runtime_summary(),
        "renderer_expected": "edgechromium",
        "renderer_actual": None,
        "window_visible": True,
        "user_data_dir": str(user_data_dir),
        "controller_ready": False,
        "renderer_controller_ready": False,
        "js_roundtrip": False,
        "ok": False,
    }


def _write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


def _child_main(report_path: Path, user_data_dir: Path, timeout: float, scenario: str) -> int:
    report = _base_report(user_data_dir, scenario)
    report["child_pid"] = os.getpid()
    report["probe_timeout_seconds"] = timeout
    if not sys.platform.startswith("win"):
        report["reason"] = "WebView2 probe is applicable only on Windows"
        report["status"] = "not_applicable"
        _write_report(report_path, report)
        return 2

    started = time.monotonic()
    pywebview_log: list[str] = []

    class _CaptureHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            try:
                message = self.format(record)
            except Exception:
                message = record.getMessage()
            pywebview_log.append(message[-1000:])
            del pywebview_log[:-50]

    log_handler = _CaptureHandler()
    log_handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    pywebview_logger = logging.getLogger("pywebview")
    pywebview_logger.setLevel(logging.DEBUG)
    pywebview_logger.addHandler(log_handler)
    try:
        selected_renderer = "edgechromium"
        if scenario == "desktop-import":
            backend_dir = Path(__file__).resolve().parents[1] / "backend"
            sys.path.insert(0, str(backend_dir))
            import desktop_main

            desktop_main._configure_logging(False)
            selected_renderer = desktop_main._default_gui() or selected_renderer
            report["desktop_import"] = {"ok": True, "renderer": selected_renderer}
        if scenario == "kuantra-logging":
            backend_dir = Path(__file__).resolve().parents[1] / "backend"
            sys.path.insert(0, str(backend_dir))
            os.environ["KUANTRA_DATA_DIR"] = str(user_data_dir)
            from app.core.paths import DATA_DIR

            logs_dir = DATA_DIR / "logs"
            logs_dir.mkdir(parents=True, exist_ok=True)
            if sys.stdout is None or sys.stderr is None:
                diagnostic_log = open(logs_dir / "probe.log", "a", encoding="utf-8", buffering=1)
                sys.stdout = sys.stdout or diagnostic_log
                sys.stderr = sys.stderr or diagnostic_log
            import app.core.logging_config  # noqa: F401

            report["logging_import"] = {"ok": True, "log_dir": str(logs_dir)}
        import webview

        report["interop_import"] = {"ok": True, "error": None}
        window_kwargs: dict[str, Any] = {
            "html": PROBE_HTML,
            "width": 640,
            "height": 420,
            "resizable": False,
        }
        if scenario == "js-api":
            window_kwargs["js_api"] = _ProbeApi()
        elif scenario in {"kuantra-window", "kuantra-logging", "desktop-import", "kuantra-window-resizable"}:
            window_kwargs.update(
                {
                    "width": 1440,
                    "height": 900,
                    "min_size": (1024, 700),
                    "text_select": True,
                    "background_color": "#0b0e14",
                    "js_api": _ProbeApi(),
                }
            )
            if scenario == "kuantra-window-resizable":
                window_kwargs["resizable"] = True
        if scenario in {"frontend-file", "kuantra-bridge"}:
            frontend = Path(__file__).resolve().parents[1] / "frontend" / "dist" / "index.html"
            window_kwargs.pop("html", None)
            window_kwargs.update(
                {
                    "url": frontend.resolve().as_uri(),
                    "width": 1440,
                    "height": 900,
                    "min_size": (1024, 700),
                    "text_select": True,
                    "background_color": "#0b0e14",
                    "js_api": _ProbeApi(),
                }
            )
            report["frontend_path"] = str(frontend.resolve())
        if scenario == "kuantra-bridge":
            backend_dir = Path(__file__).resolve().parents[1] / "backend"
            sys.path.insert(0, str(backend_dir))
            from desktop.bridge import DesktopBridge

            window_kwargs["js_api"] = DesktopBridge(
                _ProbeRuntime(),
                _ProbePush(),
                index_url=window_kwargs["url"],
                windows_getter=lambda: [],
            )
        window = webview.create_window("Kuantra WebView2 Probe", **window_kwargs)

        def on_start() -> None:
            report["renderer_actual"] = getattr(webview, "renderer", None)
            report["event_states_at_callback"] = {
                name: bool(
                    getattr(getattr(window, "events", None), name, None)
                    and getattr(window.events, name).is_set()
                )
                for name in ("initialized", "shown", "loaded", "_pywebviewready")
            }
            ready_event = getattr(getattr(window, "events", None), "_pywebviewready", None)
            if ready_event is None:
                report["reason"] = "pywebview readiness event is unavailable"
                report["status"] = "failed"
                _write_report(report_path, report)
                return
            ready = bool(ready_event.wait(timeout))
            report["controller_ready"] = ready
            report["renderer_controller_ready"] = ready
            report["controller_ready_elapsed_ms"] = round((time.monotonic() - started) * 1000, 1)
            report["event_states"] = {
                name: bool(
                    getattr(getattr(window, "events", None), name, None)
                    and getattr(window.events, name).is_set()
                )
                for name in ("initialized", "shown", "loaded", "_pywebviewready")
            }
            report["native_type"] = type(getattr(window, "native", None)).__name__
            report["gui_type"] = type(getattr(window, "gui", None)).__name__
            if ready:
                try:
                    expression = (
                        "JSON.stringify({title: document.title, body: !!document.body})"
                        if scenario in {"frontend-file", "kuantra-bridge"}
                        else "JSON.stringify({title: document.title, ready: document.getElementById('probe').dataset.ready})"
                    )
                    result = window.evaluate_js(expression)
                    parsed = json.loads(result) if isinstance(result, str) else result
                    if scenario in {"frontend-file", "kuantra-bridge"}:
                        report["js_roundtrip"] = bool(
                            isinstance(parsed, dict)
                            and parsed.get("title") == "Kuantra Terminal"
                            and parsed.get("body") is True
                        )
                    else:
                        report["js_roundtrip"] = bool(
                            isinstance(parsed, dict)
                            and parsed.get("title") == "Kuantra WebView2 Probe"
                            and parsed.get("ready") == "true"
                        )
                    report["js_result"] = parsed
                except Exception as exc:  # noqa: BLE001 - native controller diagnostics
                    report["js_error"] = f"{type(exc).__name__}: {exc}"
            if report["controller_ready"] and report["js_roundtrip"]:
                report["ok"] = report["renderer_actual"] == "edgechromium"
                report["status"] = "ok" if report["ok"] else "failed"
                if not report["ok"]:
                    report["reason"] = "controller ready but initialized renderer is not edgechromium"
            else:
                report["reason"] = (
                    "WebView2 controller did not become ready"
                    if not report["controller_ready"]
                    else "WebView2 JavaScript roundtrip failed"
                )
                report["status"] = "failed"
            report["pywebview_log"] = pywebview_log[-50:]
            _write_report(report_path, report)
            if report["ok"]:
                try:
                    window.destroy()
                except Exception:
                    pass

        webview.start(
            on_start,
            private_mode=False,
            storage_path=str(user_data_dir),
            debug=False,
            gui=selected_renderer,
        )
        return 0 if report.get("ok") else 1
    except Exception as exc:  # noqa: BLE001 - native loader/controller diagnostics
        report["interop_import"] = {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
        report["reason"] = f"WebView2 probe failed before controller readiness: {type(exc).__name__}: {exc}"
        report["status"] = "failed"
        report["pywebview_log"] = pywebview_log[-50:]
        _write_report(report_path, report)
        return 1
    finally:
        report["pywebview_log"] = pywebview_log[-50:]
        _write_report(report_path, report)
        pywebview_logger.removeHandler(log_handler)


def _terminate(proc: subprocess.Popen[str]) -> str:
    if proc.poll() is not None:
        return "already-exited"
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
            proc.terminate()
    else:
        proc.terminate()
    try:
        proc.wait(timeout=5)
        return "terminated"
    except subprocess.TimeoutExpired:
        proc.kill()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
        return "killed"


def _terminate_webview2_for_user_data(user_data_dir: Path) -> None:
    """Stop detached WebView2 roots that retain the bounded probe profile."""
    try:
        import psutil
    except ImportError:
        return
    marker = str(user_data_dir.resolve()).lower()
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


def _load_report(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "status": "failed", "reason": f"invalid diagnostic report: {exc}"}
    return payload if isinstance(payload, dict) else {"ok": False, "status": "failed", "reason": "report is not an object"}


def _parent_main(args: argparse.Namespace) -> int:
    if not sys.platform.startswith("win"):
        report = _base_report(Path(args.user_data_dir or ""), args.scenario)
        report.update({"status": "not_applicable", "reason": "WebView2 probe is applicable only on Windows"})
        _write_report(Path(args.report), report)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 2

    report_path = Path(args.report).resolve()
    if report_path.exists():
        report_path.unlink()
    user_data_dir = (
        Path(args.user_data_dir).resolve()
        if args.user_data_dir
        else Path(tempfile.mkdtemp(prefix="kuantra-webview2-probe-"))
    )
    user_data_dir.mkdir(parents=True, exist_ok=True)
    child_command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--child",
        "--report",
        str(report_path),
        "--user-data-dir",
        str(user_data_dir),
        "--timeout",
        str(args.timeout),
        "--scenario",
        args.scenario,
    ]
    child_environment = os.environ.copy()
    probe_mode = "python"
    proc = subprocess.Popen(child_command, env=child_environment)
    deadline = time.monotonic() + args.timeout + args.grace_seconds
    termination_reason = None
    while proc.poll() is None:
        if report_path.exists():
            payload = _load_report(report_path)
            if payload.get("renderer_controller_ready") is False or payload.get("ok") is True:
                termination_reason = _terminate(proc)
                _terminate_webview2_for_user_data(user_data_dir)
                break
        if time.monotonic() >= deadline:
            termination_reason = _terminate(proc)
            _terminate_webview2_for_user_data(user_data_dir)
            break
        time.sleep(0.1)

    payload = _load_report(report_path) if report_path.exists() else {
        "ok": False,
        "status": "failed",
        "reason": "child exited without a diagnostic report",
    }
    payload["parent_pid"] = os.getpid()
    payload["child_returncode"] = proc.returncode
    payload["child_termination"] = termination_reason
    _terminate_webview2_for_user_data(user_data_dir)
    payload["hard_timeout_seconds"] = args.timeout + args.grace_seconds
    payload["probe_mode"] = probe_mode
    if termination_reason and termination_reason != "already-exited" and not payload.get("ok"):
        payload.setdefault("reason", "WebView2 probe child was terminated after report")
    _write_report(report_path, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload.get("ok") is True else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", default="dist/webview2-probe.json")
    parser.add_argument("--timeout", type=float, default=15.0, help="controller readiness timeout")
    parser.add_argument("--grace-seconds", type=float, default=10.0)
    parser.add_argument("--user-data-dir", default=None)
    parser.add_argument(
        "--scenario",
        choices=("standalone", "js-api", "kuantra-window", "kuantra-window-resizable", "frontend-file", "kuantra-bridge", "kuantra-logging", "desktop-import"),
        default="standalone",
        help="native host shape to probe; kuantra-window mirrors desktop window options",
    )
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.child:
        return _child_main(
            Path(args.report).resolve(),
            Path(args.user_data_dir).resolve(),
            args.timeout,
            args.scenario,
        )
    return _parent_main(args)


if __name__ == "__main__":
    raise SystemExit(main())
