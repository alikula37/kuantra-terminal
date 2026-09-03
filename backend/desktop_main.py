"""
Kuantra Terminal desktop entry point (pywebview shell).

Single process: pywebview window + in-process FastAPI backend. No HTTP between UI and backend.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

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
    p.add_argument("--smoke-report", default=None, help="write smoke result JSON here")
    p.add_argument("--smoke-timeout", type=float, default=90.0)
    p.add_argument("--debug", action="store_true", help="enable webview devtools")
    p.add_argument("--dev-url", default=None, help="load a Vite dev server URL instead of the bundled frontend")
    p.add_argument("--gui", default=None, choices=["cocoa", "edgechromium", "qt", "gtk"])
    p.add_argument("--frontend-dir", default=None, help="directory containing index.html (dev only)")
    return p.parse_args(argv)


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
    from app.core.logging_config import LOGS_DIR  # sets up rotating file handler on import
    if sys.stdout is None or sys.stderr is None:  # windowed exe on Windows
        log = open(LOGS_DIR / "kuantra_desktop.log", "a", encoding="utf-8")
        sys.stdout = sys.stdout or log
        sys.stderr = sys.stderr or log
    logging.basicConfig(level=logging.DEBUG if debug else logging.INFO, stream=sys.stdout,
                        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


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


def shutdown(ctx: AppContext) -> None:
    for step in (lambda: ctx.push.stop(), lambda: ctx.gateway and ctx.gateway.stop(), lambda: ctx.runtime.stop()):
        try:
            step()
        except Exception as exc:  # noqa: BLE001
            logging.getLogger("desktop").warning("shutdown step failed: %s", exc)


def _default_gui() -> str | None:
    if sys.platform.startswith("linux"):
        return os.environ.get("PYWEBVIEW_GUI", "qt")
    return os.environ.get("PYWEBVIEW_GUI")


def main(argv=None) -> int:
    args = parse_args(argv)
    _configure_logging(args.debug)
    log = logging.getLogger("desktop")
    import webview

    ctx = build_app(args)
    exit_code = {"code": 0}

    window = webview.create_window(
        APP_TITLE, url=ctx.index_url, js_api=ctx.bridge, width=WINDOW["width"], height=WINDOW["height"],
        min_size=WINDOW["min_size"], text_select=True, background_color="#0b0e14", hidden=args.smoke,
    )

    def on_start():
        if not args.smoke:
            return
        from desktop.smoke import run_smoke
        result = run_smoke(window, ctx, timeout=args.smoke_timeout)
        result["version"] = ctx.bridge.get_app_info()["version"]
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
    webview.start(on_start, private_mode=False, storage_path=str(DATA_DIR / "webview"), debug=args.debug, gui=args.gui or _default_gui())
    shutdown(ctx)
    return exit_code["code"]


if __name__ == "__main__":
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
