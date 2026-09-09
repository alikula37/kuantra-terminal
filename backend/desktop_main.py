"""
Kuantra Terminal desktop entry point (pywebview shell).

Single process: pywebview window + in-process FastAPI backend. No HTTP between UI and backend.
"""
from __future__ import annotations

import argparse
import json
import logging
import multiprocessing
import os
import sys
import threading
from dataclasses import dataclass
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# This process-only diagnostic must dispatch before app.core.paths creates or
# tightens the normal user data directory. It never enters the GUI lifecycle.
if __name__ == "__main__" and "--h07-benchmark" in sys.argv[1:]:
    from desktop.h07_worker import main as h07_main
    raise SystemExit(h07_main(sys.argv[1:]))

# The G0-G2 diagnostic must dispatch before app.core.paths initializes the
# normal user-data boundary or the desktop/WebView lifecycle.
if __name__ == "__main__" and "--g0-g2-audit" in sys.argv[1:]:
    from desktop.g0_g2_worker import main as g0_g2_main
    raise SystemExit(g0_g2_main(sys.argv[1:]))

# The N03 install-lifecycle diagnostic is also process-only.  It must run
# before the normal user-data path or WebView lifecycle and only accepts an
# explicitly empty synthetic data directory from its launcher.
if __name__ == "__main__" and "--n03-audit" in sys.argv[1:]:
    from desktop.n03_worker import main as n03_main
    raise SystemExit(n03_main(sys.argv[1:]))

from app.core.paths import DATA_DIR, PROJECT_ROOT, bundle_root, is_frozen  # noqa: E402

APP_TITLE = "Kuantra Terminal"
WINDOW = {"width": 1440, "height": 900, "min_size": (1024, 700)}


@dataclass
class AppContext:
    runtime: object
    push: object
    gateway: object
    bridge: object
    index_url: str


def parse_args(argv=None):
    p = argparse.ArgumentParser(prog="kuantra-terminal")
    p.add_argument("--smoke", action="store_true", help="headless self-test, exit 0 on success")
    p.add_argument("--h07-ui-fixture", type=Path, help="synthetic fixture for native smoke measurement")
    p.add_argument(
        "--h07-ui-fixture-size",
        type=int,
        choices=(1_000, 10_000, 100_000),
        default=100_000,
        help="declared synthetic fixture size for native H07 measurement",
    )
    p.add_argument("--smoke-report", default=None, help="write smoke result JSON here")
    p.add_argument("--smoke-timeout", type=float, default=90.0)
    p.add_argument("--debug", action="store_true", help="enable webview devtools")
    p.add_argument("--dev-url", default=None, help="load a Vite dev server URL instead of the bundled frontend")
    p.add_argument("--gui", default=None, choices=["cocoa", "edgechromium", "qt", "gtk"])
    p.add_argument("--frontend-dir", default=None, help="directory containing index.html (dev only)")
    args = p.parse_args(argv)
    if args.h07_ui_fixture is not None and (
        not args.smoke or os.environ.get("KUANTRA_MARKET_DATA_ENABLED", "").lower() != "false"
        or not os.environ.get("KUANTRA_DATA_DIR")
    ):
        p.error("H07 UI measurement requires --smoke, explicit data directory and disabled market data")
    return args


def resolve_frontend_index(frontend_dir: str | None = None) -> Path:
    if frontend_dir:
        candidate = Path(frontend_dir) / "index.html"
    elif is_frozen():
        candidate = bundle_root() / "frontend" / "index.html"
    else:
        candidate = PROJECT_ROOT / "frontend" / "dist" / "index.html"
    if not candidate.is_file():
        raise FileNotFoundError(f"frontend not found at {candidate}; run `npm --prefix frontend run build`")
    return candidate


def _configure_logging(debug: bool) -> None:
    # Order matters. app.core.logging_config installs a StreamHandler bound to sys.stdout *at
    # import time*, so a windowed exe (where stdout is None) has to get a real stream first or
    # every console log line raises. basicConfig cannot fix that afterwards either: importing
    # logging_config already attached handlers to the root logger, which makes basicConfig a
    # no-op, so the level is set explicitly instead.
    if sys.stdout is None or sys.stderr is None:  # windowed exe on Windows
        logs_dir = DATA_DIR / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        log = open(logs_dir / "kuantra_desktop.log", "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stdout or log
        sys.stderr = sys.stderr or log
    import app.core.logging_config  # noqa: F401  - sets up console + rotating file handlers
    logging.getLogger().setLevel(logging.DEBUG if debug else logging.INFO)


def build_app(args) -> AppContext:
    import webview
    from desktop.bridge import DesktopBridge
    from desktop.gateway import IntegrationsGateway
    from desktop.push import PushChannel
    from desktop.runtime import BackendRuntime
    from app.core.config import settings

    runtime = BackendRuntime()
    runtime.start()
    push = PushChannel()
    push.attach_windows(lambda: list(webview.windows))
    push.start()
    gateway = None
    if settings.gateway_enabled:
        gateway = IntegrationsGateway(runtime)
        gateway.start()
    index_url = args.dev_url or resolve_frontend_index(args.frontend_dir).as_uri()
    bridge = DesktopBridge(runtime, push, gateway=gateway, index_url=index_url, windows_getter=lambda: list(webview.windows))
    return AppContext(runtime=runtime, push=push, gateway=gateway, bridge=bridge, index_url=index_url)


_shutdown_done = threading.Event()


def shutdown(ctx: AppContext) -> None:
    """Stop the shell's own resources exactly once.

    Called both from the last window's `closed` event and again after `webview.start()` returns,
    whichever happens first. Timeouts are short because the first call runs on the GUI thread and
    a slow shutdown there looks like a frozen window.
    """
    if _shutdown_done.is_set():
        return
    _shutdown_done.set()
    for step in (
        lambda: ctx.push.stop(),
        lambda: ctx.gateway and ctx.gateway.stop(timeout=3.0),
        lambda: ctx.bridge._close(),
        lambda: ctx.runtime.stop(timeout=5.0),
    ):
        try:
            step()
        except Exception as exc:  # noqa: BLE001
            logging.getLogger("desktop").warning("shutdown step failed: %s", exc)


def _default_gui() -> str | None:
    # macOS uses its native WKWebView. Windows uses the Evergreen WebView2 runtime: the Qt
    # WebEngine wheel is available only to source/diagnostic builds; its Chromium child-process
    # sandbox can be rejected by hardened Windows builds and it is not shipped in the production
    # Windows payload. Linux continues to use the self-contained Qt WebEngine wheel.
    if sys.platform == "darwin":
        return os.environ.get("PYWEBVIEW_GUI")
    if sys.platform.startswith("win"):
        return os.environ.get("PYWEBVIEW_GUI", "edgechromium")
    return os.environ.get("PYWEBVIEW_GUI", "qt")


def _preflight_renderer(renderer: str | None, log: logging.Logger) -> None:
    """Fail closed when the selected frozen renderer cannot load its native bindings.

    pywebview can silently fall back to another backend after a Qt import failure. That makes a
    green UI smoke test meaningless: it proves a window rendered, not that the renderer shipped
    and supported by this build did. Development runs keep pywebview's normal discovery behavior.
    """
    if not is_frozen() or renderer is None:
        return

    if sys.platform.startswith("win") and renderer != "edgechromium":
        log.error("Frozen Windows renderer is unsupported: %s", renderer)
        raise RuntimeError("frozen Windows builds require the edgechromium renderer")

    if renderer == "edgechromium":
        if sys.platform.startswith("win") and not _webview2_runtime_available():
            log.error("Frozen WebView2 renderer preflight failed: Evergreen Runtime is unavailable")
            raise RuntimeError("frozen WebView2 runtime is not installed")
        try:
            # This validates that pythonnet and the WebView2 interop assemblies are present in the
            # frozen payload. Runtime availability is then proven by packaged smoke, which creates
            # the actual controller rather than trusting a registry probe.
            import webview.platforms.edgechromium  # noqa: F401
        except Exception as exc:  # noqa: BLE001 - native loader failures are opaque
            log.error("Frozen WebView2 renderer preflight failed: %s", exc)
            raise RuntimeError("frozen WebView2 renderer could not be loaded") from exc
        log.info("Frozen WebView2 renderer bindings ready")
        return

    if renderer != "qt":
        return

    try:
        from PyQt6.QtCore import QT_VERSION_STR, qVersion
        qt_version = qVersion() or QT_VERSION_STR
    except Exception as exc:  # noqa: BLE001 - native loader failures are opaque
        log.error("Frozen Qt runtime preflight failed: %s", exc)
        raise RuntimeError("frozen Qt runtime could not be loaded") from exc
    log.info("Frozen Qt runtime bindings ready (Qt %s)", qt_version)


def _version_at_least(version: str, minimum: str) -> bool:
    """Compare dotted WebView2 versions without importing packaging at startup."""
    try:
        current_parts = tuple(int(part) for part in version.split(".")[:4])
        minimum_parts = tuple(int(part) for part in minimum.split(".")[:4])
    except (AttributeError, TypeError, ValueError):
        return False
    return current_parts >= minimum_parts


def _webview2_runtime_available() -> bool:
    """Return whether an Evergreen WebView2 runtime is registered for this user/machine."""
    if not sys.platform.startswith("win"):
        return True

    try:
        import winreg
    except ImportError:
        return False

    runtime_guid = "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
    registry_paths = (
        rf"SOFTWARE\Microsoft\EdgeUpdate\Clients\{runtime_guid}",
        rf"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{runtime_guid}",
    )
    for view in (getattr(winreg, "KEY_WOW64_64KEY", 0), getattr(winreg, "KEY_WOW64_32KEY", 0), 0):
        access = winreg.KEY_READ | view
        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            for registry_path in registry_paths:
                try:
                    with winreg.OpenKey(hive, registry_path, 0, access) as key:
                        version, _ = winreg.QueryValueEx(key, "pv")
                    if _version_at_least(str(version), "86.0.622.0"):
                        return True
                except OSError:
                    continue
    return False


def _window_hidden_for_smoke(smoke: bool, renderer: str | None) -> bool:
    """Qt/GTK smoke can stay hidden; WebView2 needs a visible WinForms controller."""
    return smoke and renderer != "edgechromium"


def main(argv=None) -> int:
    args = parse_args(argv)
    _configure_logging(args.debug)
    log = logging.getLogger("desktop")
    renderer = args.gui or _default_gui()
    _preflight_renderer(renderer, log)
    import webview

    ctx = build_app(args)
    exit_code = {"code": 0}

    window = webview.create_window(
        APP_TITLE, url=ctx.index_url, js_api=ctx.bridge, width=WINDOW["width"], height=WINDOW["height"],
        min_size=WINDOW["min_size"], text_select=True, background_color="#0b0e14",
        # WebView2 does not complete controller initialization for a hidden WinForms host on
        # some Windows builds. A visible smoke window is still closed immediately after checks.
        hidden=_window_hidden_for_smoke(args.smoke, renderer) and args.h07_ui_fixture is None,
    )

    def on_start():
        actual_renderer = None
        try:
            actual_renderer = getattr(webview, "renderer", None)
        except Exception:  # noqa: BLE001 - renderer identity is diagnostic only
            pass
        if is_frozen() and renderer and actual_renderer != renderer:
            reason = f"renderer mismatch: expected {renderer}, initialized {actual_renderer or 'unknown'}"
            log.error("Frozen renderer initialization failed: %s", reason)
            exit_code["code"] = 1
            if args.smoke:
                result = {
                    "ok": False,
                    "reason": reason,
                    "checks": {
                        "react_mounted": False,
                        "bridge_roundtrip": False,
                        "health": False,
                        "push_sink": False,
                        "plugin_boundary": False,
                    },
                }
                result["version"] = ctx.bridge.get_app_info()["version"]
                result["renderer_expected"] = renderer
                result["renderer_actual"] = actual_renderer
                result["renderer_controller_ready"] = False
                if args.smoke_report:
                    Path(args.smoke_report).write_text(json.dumps(result, indent=2))
            window.destroy()
            return
        log.info("Frozen renderer initialized: %s", actual_renderer or renderer or "auto")
        if not args.smoke:
            return
        from desktop.smoke import run_smoke
        result = run_smoke(window, ctx, timeout=args.smoke_timeout)
        if result["ok"] and args.h07_ui_fixture is not None:
            from desktop.smoke import measure_h07_ui
            try:
                result["h07_ui"] = measure_h07_ui(
                    window, args.h07_ui_fixture, size=args.h07_ui_fixture_size,
                )
            except Exception as exc:
                result["h07_ui"] = {"status": "FAILED", "reason": str(exc)}
            result["ok"] = result["h07_ui"]["status"] == "MEASURED"
        result["version"] = ctx.bridge.get_app_info()["version"]
        result["renderer_expected"] = renderer
        result["renderer_actual"] = actual_renderer
        result["renderer_controller_ready"] = bool(result["ok"])
        if result["ok"]:
            log.info("Frozen renderer controller ready: %s", actual_renderer or renderer or "auto")
        else:
            log.error("Frozen renderer controller failed: %s", result.get("reason", "unknown"))
        if args.smoke_report:
            Path(args.smoke_report).write_text(json.dumps(result, indent=2))
        print(("SMOKE_OK " if result["ok"] else "SMOKE_FAIL ") + json.dumps(result), flush=True)
        exit_code["code"] = 0 if result["ok"] else 1
        window.destroy()

    def on_closed():
        if not webview.windows:  # last window closed
            shutdown(ctx)

    window.events.closed += on_closed
    log.info("Starting %s (frozen=%s, data=%s, gateway=%s)", APP_TITLE, is_frozen(), DATA_DIR, getattr(ctx.gateway, "url", None))
    webview.start(on_start, private_mode=False, storage_path=str(DATA_DIR / "webview"), debug=args.debug, gui=renderer)
    shutdown(ctx)
    return exit_code["code"]


if __name__ == "__main__":
    multiprocessing.freeze_support()
    _code = main()
    # pywebview answers a js_api call by evaluating JS back into the window. A call still in
    # flight when the last window closes parks its (non-daemon) worker thread forever, so the
    # interpreter would hang joining it at exit. Our own shutdown has already completed above,
    # so leave immediately rather than letting a dead GUI loop keep the process alive.
    try:
        sys.stdout.flush()
        sys.stderr.flush()
    except Exception:  # noqa: BLE001
        pass
    logging.shutdown()
    os._exit(_code)
