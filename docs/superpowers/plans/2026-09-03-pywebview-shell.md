# pywebview Desktop Shell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Tauri shell + uvicorn HTTP link with a single-process pywebview desktop app whose React UI calls Python directly, packaged for macOS/Windows/Linux in CI.

**Architecture:** One Python process runs a pywebview window loading the built React app from `file://`; a `BackendRuntime` thread owns an asyncio loop and dispatches UI requests into the unchanged FastAPI app through in-process ASGI (httpx `ASGITransport`); live market data is pushed from Python into JS via `window.__kuantraPush`; a small optional uvicorn "integrations gateway" on 127.0.0.1:8765 serves only the Chrome extension WebSocket and the TradingView webhook.

**Tech Stack:** Python 3.11, pywebview 6.2, FastAPI/httpx, PyInstaller 6, React 18 + Vite 6 + `vite-plugin-singlefile`, vitest, NSIS, hdiutil, appimagetool, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-03-pywebview-shell-design.md`

## Global Constraints

- Python >= 3.11 for all backend/desktop code; `pywebview>=6.2`; `httpx>=0.27`; `uvicorn>=0.30`.
- Node 20+, Vite 6; no `@tauri-apps/*` package may remain anywhere.
- The frontend must not hardcode any host or port; `apiUrl()`/`apiBase()`/`wsUrl()` are the only URL sources.
- No HTTP/WebSocket socket between the UI and the backend. Only the integrations gateway listens, on `127.0.0.1` only.
- Product name `Kuantra Terminal`, bundle id `com.kuantra.terminal`, version from `backend/app/version.py` only.
- Release asset names: `Kuantra-Terminal-<ver>-aarch64.dmg`, `Kuantra-Terminal-<ver>-Setup.exe`, `Kuantra-Terminal-<ver>-x86_64.AppImage`, `MANIFEST.json`.
- Run commands from the repo root `/Users/revy/Desktop/projects/mali-kula/kuantra-terminal`. Python for local work: `/private/tmp/claude-501/-Users-revy-Desktop-projects-mali-kula-kuantra-terminal/70b2ede4-f655-4f6a-97c4-b0732cb90356/scratchpad/venv/bin/python` (3.11, has requirements + pyinstaller + pywebview). Call it `$PY` below.
- Tests: backend `$PY -m pytest backend/tests -q`; frontend `cd frontend && npm test`.
- Work on branch `feat/pywebview-shell`. Commit after every task with the trailer:
  `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>` and
  `Claude-Session: https://claude.ai/code/session_019FuZdnruVEFZtj2u4t62Y3`.
- i18n parity is enforced by `frontend/scripts/check-i18n.js`: any string changed in `en.json` must be changed in `tr.json` and `de.json`.

---

### Task 1: Version single source, user data dir, background helper

**Files:**
- Create: `backend/app/version.py`
- Modify: `backend/app/core/config.py`, `backend/app/__init__.py`, `backend/app/core/paths.py`, `backend/app/services/maintenance/log_sanitizer.py:71`, `backend/app/services/plugin_manager.py:75-81`, `backend/app/api/plugin_endpoints.py:115-135`
- Create: `backend/app/core/background.py`
- Test: `backend/tests/test_desktop_paths.py`, `backend/tests/test_background.py`

**Interfaces:**
- Produces: `app.version.__version__: str`; `app.core.paths.DATA_DIR: Path`, `resolve_data_dir() -> Path`, `is_frozen() -> bool`, `bundle_root() -> Path`, `USER_PLUGINS_DIR: Path`, `LOGS_DIR` stays in `logging_config`; `app.core.background.fire_and_forget(func, *args, **kwargs) -> asyncio.Future`; settings fields `gateway_enabled`, `gateway_host`, `gateway_port`.

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_desktop_paths.py
import importlib
import os
import sys
from pathlib import Path


def _reload_paths(monkeypatch, **env):
    for k in ("KUANTRA_DATA_DIR",):
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    import app.core.paths as paths
    return importlib.reload(paths)


def test_env_override_wins(monkeypatch, tmp_path):
    paths = _reload_paths(monkeypatch, KUANTRA_DATA_DIR=str(tmp_path / "custom"))
    assert paths.DATA_DIR == tmp_path / "custom"
    assert paths.DATA_DIR.is_dir()


def test_dev_mode_uses_backend_data(monkeypatch):
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    paths = _reload_paths(monkeypatch)
    assert paths.DATA_DIR == paths.BACKEND_ROOT / "data"


def test_frozen_mode_uses_user_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "AppData" / "Local"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / ".local" / "share"))
    paths = _reload_paths(monkeypatch)
    assert str(paths.DATA_DIR).startswith(str(tmp_path))
    assert paths.DATA_DIR.name in ("Kuantra Terminal", "kuantra-terminal")
    assert paths.USER_PLUGINS_DIR == paths.DATA_DIR / "plugins"


def test_version_single_source():
    from app.version import __version__
    from app.core.config import settings
    import app
    assert settings.version == __version__ == app.__version__
    assert settings.gateway_port == 8765
    assert settings.gateway_host == "127.0.0.1"
    assert settings.gateway_enabled is True


def teardown_module(module):
    # restore module state for the rest of the suite
    for k in ("KUANTRA_DATA_DIR",):
        os.environ.pop(k, None)
    import app.core.paths as paths
    importlib.reload(paths)
```

```python
# backend/tests/test_background.py
import asyncio
import pytest
from app.core.background import fire_and_forget


async def test_fire_and_forget_runs_coroutine():
    done = asyncio.Event()

    async def job(x):
        await asyncio.sleep(0)
        done.set()
        return x * 2

    fut = fire_and_forget(job, 21)
    assert await asyncio.wait_for(fut, 1) == 42
    assert done.is_set()


async def test_fire_and_forget_runs_sync_function_off_loop():
    import threading
    main = threading.get_ident()

    def job():
        return threading.get_ident()

    fut = fire_and_forget(job)
    assert await asyncio.wait_for(fut, 5) != main


async def test_fire_and_forget_swallows_and_logs_errors(caplog):
    async def boom():
        raise RuntimeError("nope")

    fut = fire_and_forget(boom)
    with pytest.raises(RuntimeError):
        await fut
    assert "nope" in caplog.text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `$PY -m pytest backend/tests/test_desktop_paths.py backend/tests/test_background.py -q`
Expected: FAIL (`ModuleNotFoundError: app.version`, `app.core.background`, missing `USER_PLUGINS_DIR`).

- [ ] **Step 3: Implement**

`backend/app/version.py`:
```python
"""Single source of truth for the product version. Everything else imports this."""
__version__ = "1.3.0"
```

`backend/app/__init__.py`:
```python
"""Kuantra Terminal Backend Application Package."""
from app.version import __version__  # noqa: F401
```

`backend/app/core/config.py` — replace `version: str = "1.3.0"` and add gateway fields:
```python
from pydantic import BaseModel, Field
import os
from dotenv import load_dotenv
from app.version import __version__

load_dotenv()


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


class AppSettings(BaseModel):
    app_name: str = "Kuantra Terminal Backend"
    version: str = __version__
    debug: bool = True
    host: str = "127.0.0.1"
    port: int = 8000
    # Integrations gateway: the only socket the desktop app opens (Chrome extension + TV webhooks).
    gateway_enabled: bool = Field(default_factory=lambda: _env_bool("KUANTRA_GATEWAY_ENABLED", True))
    gateway_host: str = Field(default_factory=lambda: os.getenv("KUANTRA_GATEWAY_HOST", "127.0.0.1"))
    gateway_port: int = Field(default_factory=lambda: int(os.getenv("KUANTRA_GATEWAY_PORT", "8765")))
    binance_ws_url: str = "wss://stream.binance.com:9443/ws"
    default_symbol: str = "BTCUSDT"
    ws_broadcast_interval_ms: int = 50
    sqlite_db_url: str = Field(default_factory=lambda: os.getenv("SQLITE_DB_URL", ""))
    duckdb_url: str = Field(default_factory=lambda: os.getenv("DUCKDB_URL", ""))


settings = AppSettings()
```

`backend/app/core/paths.py` (full replacement):
```python
"""
Filesystem locations.

Dev (running from a checkout): data lives in backend/data as before.
Frozen (PyInstaller desktop app): data lives in the per-user application data directory,
because the install location is read-only / replaced on update. KUANTRA_DATA_DIR overrides both.
"""
from pathlib import Path
import os
import sys

APP_NAME = "Kuantra Terminal"
APP_SLUG = "kuantra-terminal"

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def bundle_root() -> Path:
    """Directory holding bundled read-only resources (frontend, alembic) when frozen."""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return BACKEND_ROOT


def default_user_data_dir() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / APP_NAME
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / APP_SLUG


def resolve_data_dir() -> Path:
    env = os.environ.get("KUANTRA_DATA_DIR")
    if env:
        return Path(env).expanduser()
    if is_frozen():
        return default_user_data_dir()
    return BACKEND_ROOT / "data"


DATA_DIR = resolve_data_dir()
DATA_DIR.mkdir(parents=True, exist_ok=True)

USER_PLUGINS_DIR = DATA_DIR / "plugins"

SQLITE_DB_PATH = DATA_DIR / "kuantra_oltp.sqlite3"
DUCKDB_PATH = DATA_DIR / "kuantra_olap.duckdb"


def get_sqlite_path() -> str:
    return str(SQLITE_DB_PATH)


def get_duckdb_path() -> str:
    return str(DUCKDB_PATH)
```

`backend/app/services/maintenance/log_sanitizer.py:71` — replace `Path(os.getcwd()) / "logs"` with the real log dir:
```python
from app.core.logging_config import LOGS_DIR
...
        self.logs_dir = Path(logs_dir) if logs_dir else LOGS_DIR
```
(Put the import at module top; if it creates an import cycle, import inside `__init__`.)

`backend/app/services/plugin_manager.py:75-81` — bundled plugins stay next to the code (read-only when frozen); downloaded ones go to the user dir. Replace the constructor's directory block with:
```python
        from app.core.paths import USER_PLUGINS_DIR, is_frozen
        if plugins_dir:
            self.plugins_dir = Path(plugins_dir)
        else:
            backend_dir = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            self.plugins_dir = backend_dir / "plugins"
        # Downloaded .kmod plugins must never be written into the install directory.
        self.user_plugins_dir = Path(plugins_dir) if plugins_dir else USER_PLUGINS_DIR
        if not is_frozen():
            self.plugins_dir.mkdir(parents=True, exist_ok=True)
        self.user_plugins_dir.mkdir(parents=True, exist_ok=True)
```
Then in `discover_plugins()` scan both `self.plugins_dir` and `self.user_plugins_dir` (read the method; wherever it iterates `self.plugins_dir.iterdir()` iterate over `[self.plugins_dir, self.user_plugins_dir]`, skipping missing dirs, first wins on duplicate ids). In `backend/app/services/modstore_downloader.py:28` change `plugin_manager.plugins_dir` to `plugin_manager.user_plugins_dir`, and at `:128` do not reassign `plugin_manager.plugins_dir`.

`backend/app/core/background.py`:
```python
"""Run work after responding without Starlette BackgroundTasks.

Under the desktop shell every request is awaited in-process, so BackgroundTasks would delay
the response until the task finishes. fire_and_forget schedules the work on the running loop
(coroutines) or the default executor (sync callables) and returns a Future.
"""
import asyncio
import functools
import inspect
import logging

logger = logging.getLogger(__name__)


def fire_and_forget(func, *args, **kwargs) -> "asyncio.Future":
    loop = asyncio.get_running_loop()
    if inspect.iscoroutinefunction(func):
        fut = loop.create_task(func(*args, **kwargs))
    else:
        fut = loop.run_in_executor(None, functools.partial(func, *args, **kwargs))

    def _log(f):
        if not f.cancelled() and f.exception() is not None:
            logger.error("background task %s failed: %s", getattr(func, "__name__", func), f.exception())

    fut.add_done_callback(_log)
    return fut
```

`backend/app/api/plugin_endpoints.py` download endpoint — drop `BackgroundTasks`:
```python
@router.post("/download")
async def download_plugin_endpoint(req: DownloadPluginRequest):
    """Initiates an asynchronous download and dynamic mounting task for a remote .kmod plugin."""
    from app.services.modstore_downloader import modstore_downloader
    from app.core.background import fire_and_forget
    import uuid
    task_id = str(uuid.uuid4())[:8]
    fire_and_forget(
        modstore_downloader.download_and_install,
        plugin_id=req.plugin_id,
        download_url=req.download_url,
        expected_sha256=req.expected_sha256,
        task_id=task_id,
    )
    return {  # unchanged body
```
Remove the now-unused `BackgroundTasks` import.

- [ ] **Step 4: Run the full backend suite**

Run: `$PY -m pytest backend/tests -q`
Expected: new tests PASS; the pre-existing suite stays green (the persona/plugin tests use `plugin_manager.plugins_dir` — it still points at the bundled dir).

- [ ] **Step 5: Commit**

```bash
git checkout -b feat/pywebview-shell
git add backend/app/version.py backend/app/__init__.py backend/app/core backend/app/services backend/app/api/plugin_endpoints.py backend/tests/test_desktop_paths.py backend/tests/test_background.py docs/superpowers
git commit -m "refactor(backend): version single source, user data dir, fire_and_forget"
```

---

### Task 2: In-process backend runtime

**Files:**
- Create: `backend/desktop/__init__.py`, `backend/desktop/runtime.py`
- Test: `backend/tests/test_desktop_runtime.py`

**Interfaces:**
- Produces:
  ```python
  @dataclass
  class BridgeResponse: status: int; headers: dict[str, str]; content: bytes
  class BackendRuntime:
      def __init__(self, app_factory=None): ...
      app: FastAPI            # available after start()
      loop: asyncio.AbstractEventLoop
      def start(self, timeout: float = 60.0) -> None
      def stop(self, timeout: float = 15.0) -> None
      def run(self, coro, timeout: float | None = 30.0)   # run coroutine on the loop from any thread, return result
      def call(self, method, path, query="", headers=None, body: bytes|None=None,
               files=None, fields=None, timeout=120.0) -> BridgeResponse
      @property
      def is_running(self) -> bool
  ```
  `files` is `list[tuple[field, filename, bytes, content_type]]`, `fields` is `list[tuple[str, str]]`.

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_desktop_runtime.py
import json
import pytest
from desktop.runtime import BackendRuntime, BridgeResponse


@pytest.fixture(scope="module")
def runtime():
    rt = BackendRuntime()
    rt.start(timeout=60)
    yield rt
    rt.stop()


def test_health_roundtrip(runtime):
    resp = runtime.call("GET", "/health")
    assert isinstance(resp, BridgeResponse)
    assert resp.status == 200
    assert resp.headers["content-type"].startswith("application/json")
    assert json.loads(resp.content)["status"] == "online"


def test_query_string_and_json_body(runtime):
    resp = runtime.call("GET", "/api/v1/market-data/candles", query="symbol=BTCUSDT&timeframe=1m&limit=1")
    assert resp.status in (200, 502, 503)  # network-dependent endpoint; must not raise
    body = json.dumps({"symbol": "BTCUSDT", "side": "BUY", "order_type": "LIMIT", "qty": 1,
                       "price": 100.0, "stop_loss": 99.0, "take_profit": 102.0,
                       "exchange": "binance_futures", "mode": "PAPER"}).encode()
    resp = runtime.call("POST", "/api/v1/execution/order",
                        headers={"Content-Type": "application/json"}, body=body)
    assert resp.status in (200, 422)
    assert json.loads(resp.content)


def test_multipart_upload(runtime):
    csv = b"symbol,side,qty,price\nBTCUSDT,BUY,1,100\n"
    resp = runtime.call("POST", "/api/v1/journal/preview-csv",
                        files=[("file", "trades.csv", csv, "text/csv")])
    assert resp.status in (200, 400, 422)
    assert json.loads(resp.content)


def test_unknown_route_is_404_not_exception(runtime):
    resp = runtime.call("GET", "/api/v1/does-not-exist")
    assert resp.status == 404


def test_run_executes_on_loop(runtime):
    import asyncio

    async def probe():
        return asyncio.get_running_loop() is runtime.loop

    assert runtime.run(probe()) is True


def test_lifespan_started_binance_client(runtime):
    from app.websocket.binance_client import binance_client
    assert binance_client.is_running is True
```

- [ ] **Step 2: Run to verify failure**

Run: `$PY -m pytest backend/tests/test_desktop_runtime.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'desktop'`.

- [ ] **Step 3: Implement**

`backend/desktop/__init__.py`:
```python
"""Desktop shell: pywebview window + in-process backend runtime (no HTTP between UI and backend)."""
```

`backend/desktop/runtime.py`:
```python
"""
BackendRuntime: owns one asyncio loop in a daemon thread, runs the FastAPI lifespan, and
dispatches requests into the app in-process through httpx's ASGITransport. No socket.
"""
from __future__ import annotations

import asyncio
import logging
import threading
from dataclasses import dataclass, field
from typing import Callable, Iterable, Optional

import httpx

logger = logging.getLogger("desktop.runtime")

INTERNAL_BASE_URL = "http://kuantra.desktop"


@dataclass
class BridgeResponse:
    status: int
    headers: dict = field(default_factory=dict)
    content: bytes = b""


class BackendRuntime:
    def __init__(self, app_factory: Optional[Callable] = None):
        self._app_factory = app_factory
        self.app = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._ready = threading.Event()
        self._startup_error: Optional[BaseException] = None
        self._client: Optional[httpx.AsyncClient] = None
        self._lifespan_cm = None
        self._stopped = threading.Event()

    # ---- lifecycle -----------------------------------------------------------------------
    @property
    def is_running(self) -> bool:
        return self._ready.is_set() and self._startup_error is None and not self._stopped.is_set()

    def start(self, timeout: float = 60.0) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._thread_main, name="kuantra-backend-loop", daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout):
            raise RuntimeError("backend runtime did not start in time")
        if self._startup_error is not None:
            raise RuntimeError(f"backend runtime failed to start: {self._startup_error!r}") from self._startup_error
        logger.info("Backend runtime started (in-process ASGI, no socket).")

    def _thread_main(self) -> None:
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self._startup())
        except BaseException as exc:  # noqa: BLE001 - surfaced to start()
            self._startup_error = exc
            self._ready.set()
            return
        self._ready.set()
        try:
            self.loop.run_forever()
        finally:
            try:
                self.loop.run_until_complete(self._shutdown())
            finally:
                self.loop.close()
                self._stopped.set()

    async def _startup(self) -> None:
        if self._app_factory is None:
            from main import create_app
            from app.services.plugin_manager import plugin_manager
            self.app = create_app()
            plugin_manager.set_app(self.app)
        else:
            self.app = self._app_factory()
        transport = httpx.ASGITransport(app=self.app, raise_app_exceptions=False)
        self._client = httpx.AsyncClient(transport=transport, base_url=INTERNAL_BASE_URL, timeout=None)
        self._lifespan_cm = self.app.router.lifespan_context(self.app)
        await self._lifespan_cm.__aenter__()

    async def _shutdown(self) -> None:
        if self._lifespan_cm is not None:
            try:
                await self._lifespan_cm.__aexit__(None, None, None)
            except Exception as exc:  # noqa: BLE001
                logger.warning("lifespan shutdown error: %s", exc)
        if self._client is not None:
            await self._client.aclose()

    def stop(self, timeout: float = 15.0) -> None:
        if self.loop is None or self._stopped.is_set():
            return
        self.loop.call_soon_threadsafe(self.loop.stop)
        self._stopped.wait(timeout)

    # ---- dispatch --------------------------------------------------------------------------
    def run(self, coro, timeout: Optional[float] = 30.0):
        if self.loop is None:
            raise RuntimeError("runtime not started")
        fut = asyncio.run_coroutine_threadsafe(coro, self.loop)
        return fut.result(timeout)

    def call(
        self,
        method: str,
        path: str,
        query: str = "",
        headers: Optional[dict] = None,
        body: Optional[bytes] = None,
        files: Optional[Iterable[tuple]] = None,
        fields: Optional[Iterable[tuple]] = None,
        timeout: float = 120.0,
    ) -> BridgeResponse:
        return self.run(self._request(method, path, query, headers or {}, body, files, fields), timeout=timeout)

    async def _request(self, method, path, query, headers, body, files, fields) -> BridgeResponse:
        assert self._client is not None
        url = path if not query else f"{path}?{query}"
        kwargs = {"headers": {k: v for k, v in headers.items() if k.lower() != "content-length"}}
        if files or fields:
            kwargs["files"] = [(f[0], (f[1], f[2], f[3])) for f in (files or [])]
            kwargs["data"] = {k: v for k, v in (fields or [])}
            kwargs["headers"].pop("Content-Type", None)
            kwargs["headers"].pop("content-type", None)
        elif body is not None:
            kwargs["content"] = body
        resp = await self._client.request(method.upper(), url, **kwargs)
        return BridgeResponse(status=resp.status_code, headers=dict(resp.headers), content=resp.content)
```

- [ ] **Step 4: Run tests**

Run: `$PY -m pytest backend/tests/test_desktop_runtime.py -q`
Expected: PASS. If `test_lifespan_started_binance_client` fails because `create_app` in `backend/main.py` is fine but `binance_client.start()` raised, read the traceback; the lifespan must not be swallowed.

- [ ] **Step 5: Commit**

```bash
git add backend/desktop backend/tests/test_desktop_runtime.py
git commit -m "feat(desktop): in-process BackendRuntime over ASGI transport"
```

---

### Task 3: Push channel (server → UI events) and tv-sync fix

**Files:**
- Modify: `backend/app/websocket/connection_manager.py`, `backend/app/websocket/tv_sync.py:64-66`
- Create: `backend/desktop/push.py`
- Test: `backend/tests/test_desktop_push.py`

**Interfaces:**
- Produces: `ConnectionManager.attach(sink, channels: set[str] | None = None)`, `ConnectionManager.detach(sink)`; `desktop.push.PushChannel(flush_interval=0.05)` with `async send_text(text)`, `attach_windows(get_windows: Callable[[], list])`, `start()`, `stop()`, `pending() -> int`, `CHANNELS`.
- JS contract: `window.__kuantraPush(batch: object[])`.

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_desktop_push.py
import asyncio
import json
import time
import pytest
from app.websocket.connection_manager import ConnectionManager
from desktop.push import PushChannel


class FakeWindow:
    def __init__(self):
        self.scripts = []

    def run_js(self, script):
        self.scripts.append(script)


async def test_attach_receives_broadcasts_for_subscribed_channels():
    manager = ConnectionManager()
    win = FakeWindow()
    push = PushChannel(flush_interval=0.01)
    push.attach_windows(lambda: [win])
    push.start()
    manager.attach(push, PushChannel.CHANNELS)
    await manager.broadcast({"type": "TICK", "price": 1.0}, "market_ticks")
    await manager.broadcast({"type": "TV_SYNC_UPDATE", "symbol": "ETHUSDT"}, "tv_sync")
    await manager.broadcast({"type": "IGNORED"}, "not_a_channel")
    deadline = time.time() + 2
    while time.time() < deadline and len(win.scripts) < 1:
        await asyncio.sleep(0.01)
    push.stop()
    joined = "\n".join(win.scripts)
    assert "window.__kuantraPush" in joined
    types = []
    for s in win.scripts:
        payload = s[s.index("(") + 1: s.rindex(")")]
        types += [m["type"] for m in json.loads(payload)]
    assert types == ["TICK", "TV_SYNC_UPDATE"]
    manager.detach(push)
    assert push not in manager.active_connections


async def test_window_errors_do_not_break_channel():
    class Broken:
        def run_js(self, script):
            raise RuntimeError("window gone")

    push = PushChannel(flush_interval=0.01)
    push.attach_windows(lambda: [Broken()])
    push.start()
    await push.send_text(json.dumps({"type": "TICK"}))
    await asyncio.sleep(0.05)
    push.stop()
    assert push.pending() == 0


async def test_tv_sync_broadcast_reaches_tv_sync_channel():
    from app.websocket import connection_manager as cm
    from app.websocket.tv_sync import TradingViewSyncManager
    received = []

    class Sink:
        async def send_text(self, text):
            received.append(json.loads(text))

    sink = Sink()
    cm.ws_manager.attach(sink, {"tv_sync"})
    try:
        await TradingViewSyncManager().handle_extension_message({"symbol": "ethusdt", "timeframe": "5m", "exchange": "binance"})
    finally:
        cm.ws_manager.detach(sink)
    assert received and received[0]["type"] == "TV_SYNC_UPDATE" and received[0]["symbol"] == "ETHUSDT"
```

- [ ] **Step 2: Run to verify failure**

Run: `$PY -m pytest backend/tests/test_desktop_push.py -q`
Expected: FAIL (`attach` missing, `desktop.push` missing, tv_sync test fails on reversed args).

- [ ] **Step 3: Implement**

`backend/app/websocket/connection_manager.py` — add after `disconnect`:
```python
    def attach(self, sink, channels: Optional[Set[str]] = None) -> None:
        """Register a non-WebSocket sink (anything with `async send_text(str)`), e.g. the desktop push channel."""
        self.active_connections.add(sink)
        self.subscriptions[sink] = set(channels or {"market_ticks", "kline_updates", "open_positions", "system_metrics"})
        logger.info(f"Push sink attached. Total clients: {len(self.active_connections)}")

    def detach(self, sink) -> None:
        self.active_connections.discard(sink)
        self.subscriptions.pop(sink, None)
```
Change the type hints `Set[WebSocket]` / `Dict[WebSocket, ...]` to `Set[Any]` / `Dict[Any, Set[str]]`.

`backend/app/websocket/tv_sync.py:66` — fix argument order:
```python
        await ws_manager.broadcast(payload, "tv_sync")
```

`backend/desktop/push.py`:
```python
"""
PushChannel: a ConnectionManager sink that forwards broadcast messages to every pywebview
window as `window.__kuantraPush([...])`, batched every `flush_interval` seconds.
"""
from __future__ import annotations

import json
import logging
import queue
import threading
from typing import Callable, List

logger = logging.getLogger("desktop.push")


class PushChannel:
    CHANNELS = {"market_ticks", "kline_updates", "open_positions", "system_metrics", "tv_sync"}

    def __init__(self, flush_interval: float = 0.05, max_batch: int = 500):
        self._queue: "queue.Queue[str]" = queue.Queue()
        self._interval = flush_interval
        self._max_batch = max_batch
        self._get_windows: Callable[[], list] = lambda: []
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def attach_windows(self, get_windows: Callable[[], list]) -> None:
        self._get_windows = get_windows

    async def send_text(self, text: str) -> None:  # ConnectionManager sink protocol
        self._queue.put_nowait(text)

    def pending(self) -> int:
        return self._queue.qsize()

    def start(self) -> None:
        if self._thread is not None:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._flush_loop, name="kuantra-push", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None

    def _drain(self) -> List[str]:
        items: List[str] = []
        try:
            items.append(self._queue.get(timeout=self._interval))
            while len(items) < self._max_batch:
                items.append(self._queue.get_nowait())
        except queue.Empty:
            pass
        return items

    def _flush_loop(self) -> None:
        while not self._stop.is_set():
            items = self._drain()
            if not items:
                continue
            batch = "[" + ",".join(items) + "]"
            script = f"window.__kuantraPush && window.__kuantraPush({batch})"
            for win in list(self._get_windows()):
                try:
                    win.run_js(script)
                except Exception as exc:  # noqa: BLE001 - a closing window must not kill the stream
                    logger.debug("push to window failed: %s", exc)
```
Note: each queued item is already a JSON document (ConnectionManager passes `json.dumps(message)`), so joining with commas is valid JSON.

- [ ] **Step 4: Run tests**

Run: `$PY -m pytest backend/tests/test_desktop_push.py backend/tests -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/websocket backend/desktop/push.py backend/tests/test_desktop_push.py
git commit -m "feat(desktop): push channel sink for UI events; fix tv-sync broadcast args"
```

---

### Task 4: Integrations gateway (extension WS + TradingView webhook)

**Files:**
- Create: `backend/desktop/gateway.py`
- Modify: `backend/app/api/webhook_tv.py:105-115`, `backend/api/mobile_bridge.py:39` (path: `backend/app/api/mobile_bridge.py`), `backend/main.py` (share the tv-sync WS handler)
- Test: `backend/tests/test_desktop_gateway.py`

**Interfaces:**
- Produces: `desktop.gateway.build_gateway_app() -> FastAPI`; `IntegrationsGateway(runtime, host=None, port=None)` with `start() -> bool`, `stop()`, `url: str | None`, `enabled: bool`, `port: int`; `app.api.tv_sync_ws.tv_sync_websocket(websocket)` handler shared by dev server and gateway; `settings.gateway_url()` helper returning `http://host:port`.

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_desktop_gateway.py
import asyncio
import json
import socket
import pytest
import websockets
from desktop.runtime import BackendRuntime
from desktop.gateway import IntegrationsGateway


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def runtime():
    rt = BackendRuntime()
    rt.start(timeout=60)
    yield rt
    rt.stop()


def test_gateway_serves_tv_sync_and_webhook(runtime):
    port = _free_port()
    gw = IntegrationsGateway(runtime, host="127.0.0.1", port=port)
    assert gw.start() is True
    assert gw.url == f"http://127.0.0.1:{port}"
    try:
        async def talk():
            async with websockets.connect(f"ws://127.0.0.1:{port}/ws/tv-sync") as ws:
                first = json.loads(await asyncio.wait_for(ws.recv(), 5))
                assert first["type"] == "INITIAL_STATE"
                await ws.send(json.dumps({"symbol": "solusdt", "timeframe": "1h", "exchange": "binance"}))
                await asyncio.sleep(0.2)
        asyncio.run(talk())
        from app.websocket.tv_sync import tv_sync_manager
        assert tv_sync_manager.active_symbol == "SOLUSDT"
        import httpx
        r = httpx.get(f"{gw.url}/health", timeout=5)
        assert r.status_code == 200 and r.json()["gateway"] is True
        r = httpx.post(f"{gw.url}/api/v1/webhook/tradingview", content=b"{}", timeout=5)
        assert r.status_code in (200, 400, 401, 403, 422)
        # the gateway must not expose the rest of the API
        assert httpx.get(f"{gw.url}/api/v1/portfolio/summary", timeout=5).status_code == 404
    finally:
        gw.stop()


def test_gateway_disabled_when_port_busy(runtime):
    blocker = socket.socket()
    blocker.bind(("127.0.0.1", 0))
    blocker.listen(1)
    port = blocker.getsockname()[1]
    try:
        gw = IntegrationsGateway(runtime, host="127.0.0.1", port=port)
        assert gw.start() is False
        assert gw.enabled is False and gw.url is None
    finally:
        blocker.close()
```

- [ ] **Step 2: Run to verify failure**

Run: `$PY -m pytest backend/tests/test_desktop_gateway.py -q`
Expected: FAIL (`desktop.gateway` missing).

- [ ] **Step 3: Implement**

Create `backend/app/api/tv_sync_ws.py` (moved out of `main.py` so both servers share it):
```python
from fastapi import WebSocket, WebSocketDisconnect
from app.websocket.tv_sync import tv_sync_manager


async def tv_sync_websocket(websocket: WebSocket):
    await tv_sync_manager.connect_extension(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            await tv_sync_manager.handle_extension_message(data)
    except WebSocketDisconnect:
        tv_sync_manager.disconnect_extension(websocket)
    except Exception:
        tv_sync_manager.disconnect_extension(websocket)
```
In `backend/main.py` replace the inline `/ws/tv-sync` handler body with `app.add_api_websocket_route("/ws/tv-sync", tv_sync_websocket)` and import it.

`backend/desktop/gateway.py`:
```python
"""
IntegrationsGateway: the one socket the desktop app opens. It serves only what *other*
programs need to reach: the TradingView Chrome extension WebSocket and TradingView alert
webhooks. The UI never talks to it. Bound to loopback; disabled (not fatal) if the port is busy.
"""
from __future__ import annotations

import asyncio
import logging
import socket
from typing import Optional

import uvicorn
from fastapi import FastAPI

from app.api.webhook_tv import webhook_router
from app.api.tv_sync_ws import tv_sync_websocket
from app.core.config import settings
from app.version import __version__

logger = logging.getLogger("desktop.gateway")


def build_gateway_app() -> FastAPI:
    app = FastAPI(title="Kuantra Integrations Gateway", version=__version__, docs_url=None, redoc_url=None, openapi_url=None)
    app.include_router(webhook_router, prefix="/api/v1")
    app.add_api_websocket_route("/ws/tv-sync", tv_sync_websocket)

    @app.get("/health")
    async def health():
        return {"status": "online", "gateway": True, "version": __version__}

    return app


class IntegrationsGateway:
    def __init__(self, runtime, host: Optional[str] = None, port: Optional[int] = None):
        self._runtime = runtime
        self.host = host or settings.gateway_host
        self.port = port or settings.gateway_port
        self.enabled = False
        self.url: Optional[str] = None
        self._server: Optional[uvicorn.Server] = None
        self._task = None
        self._sock: Optional[socket.socket] = None

    def start(self) -> bool:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((self.host, self.port))
            sock.listen(128)
            sock.setblocking(False)
        except OSError as exc:
            sock.close()
            logger.warning("Integrations gateway disabled: cannot bind %s:%s (%s)", self.host, self.port, exc)
            self.enabled = False
            self.url = None
            return False
        self._sock = sock
        config = uvicorn.Config(build_gateway_app(), host=self.host, port=self.port, log_level="warning", lifespan="off")
        self._server = uvicorn.Server(config)

        async def _launch():
            self._task = asyncio.get_running_loop().create_task(self._server.serve(sockets=[sock]))
            for _ in range(100):
                if self._server.started:
                    return True
                if self._task.done():
                    return False
                await asyncio.sleep(0.05)
            return False

        ok = self._runtime.run(_launch(), timeout=10)
        self.enabled = bool(ok)
        self.url = f"http://{self.host}:{self.port}" if ok else None
        if ok:
            logger.info("Integrations gateway listening on %s (extension WS + TradingView webhook)", self.url)
        else:
            self._sock.close()
        return self.enabled

    def stop(self) -> None:
        if self._server is None:
            return
        self._server.should_exit = True

        async def _wait():
            if self._task is not None:
                try:
                    await asyncio.wait_for(self._task, 5)
                except Exception:  # noqa: BLE001
                    pass

        try:
            self._runtime.run(_wait(), timeout=8)
        except Exception:  # noqa: BLE001
            pass
        if self._sock is not None:
            self._sock.close()
        self.enabled = False
        self.url = None
```
Add to `AppSettings` in `config.py`:
```python
    def gateway_url(self) -> str:
        return f"http://{self.gateway_host}:{self.gateway_port}"
```
`backend/app/api/webhook_tv.py:111`: `"webhook_endpoint": f"{settings.gateway_url()}/api/v1/webhook/tradingview"` (import settings). `backend/app/api/mobile_bridge.py:39`: `"host_url": settings.gateway_url()`.

- [ ] **Step 4: Run tests**

Run: `$PY -m pytest backend/tests/test_desktop_gateway.py backend/tests -q`
Expected: PASS. If uvicorn complains about signal handlers from a non-main thread, upgrade uvicorn (`>=0.30`) in `backend/requirements.txt` and the venv.

- [ ] **Step 5: Commit**

```bash
git add backend/desktop/gateway.py backend/app/api backend/app/core/config.py backend/main.py backend/tests/test_desktop_gateway.py backend/requirements.txt
git commit -m "feat(desktop): loopback integrations gateway for extension WS and TV webhook"
```

---

### Task 5: DesktopBridge (window.pywebview.api)

**Files:**
- Create: `backend/desktop/bridge.py`, `backend/desktop/clipboard.py`
- Test: `backend/tests/test_desktop_bridge.py`

**Interfaces:**
- Produces `DesktopBridge(runtime, push, gateway, index_url, windows_getter=None, dialog_window_getter=None)` with the methods listed in the spec §3.2: `request`, `stream_open`, `open_popout`, `save_file`, `download`, `copy_text`, `open_external`, `get_app_info`. `desktop.clipboard.copy_text(text) -> bool`.

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_desktop_bridge.py
import base64
import json
import pytest
from desktop.runtime import BackendRuntime
from desktop.push import PushChannel
from desktop.bridge import DesktopBridge


class FakeDialogWindow:
    def __init__(self, path):
        self._path = path
        self.created = []

    def create_file_dialog(self, kind, save_filename="", **kw):
        return self._path


@pytest.fixture(scope="module")
def runtime():
    rt = BackendRuntime()
    rt.start(timeout=60)
    yield rt
    rt.stop()


@pytest.fixture
def bridge(runtime, tmp_path):
    push = PushChannel()
    dialog = FakeDialogWindow(str(tmp_path / "out.csv"))
    b = DesktopBridge(runtime, push, gateway=None, index_url="file:///tmp/index.html",
                      dialog_window_getter=lambda: dialog)
    return b


def test_request_json(bridge):
    r = bridge.request({"method": "GET", "path": "/health", "query": "", "headers": {}, "body": None, "files": [], "fields": []})
    assert r["status"] == 200
    assert json.loads(r["body"])["status"] == "online"
    assert r["body_b64"] is None
    assert "content-type" in r["headers"]


def test_request_multipart(bridge):
    csv = base64.b64encode(b"symbol,side,qty,price\nBTCUSDT,BUY,1,100\n").decode()
    r = bridge.request({"method": "POST", "path": "/api/v1/journal/preview-csv", "query": "", "headers": {},
                        "body": None, "files": [{"field": "file", "filename": "t.csv", "content_type": "text/csv", "data_b64": csv}], "fields": []})
    assert r["status"] in (200, 400, 422)


def test_request_binary_body_is_base64(bridge, tmp_path):
    r = bridge.request({"method": "GET", "path": "/api/v1/telemetry/export-logs", "query": "", "headers": {}, "body": None, "files": [], "fields": []})
    assert r["status"] in (200, 404, 500)
    if r["status"] == 200:
        assert r["body"] is None and r["body_b64"]


def test_stream_open_returns_snapshot_and_attaches(bridge, runtime):
    snap = bridge.stream_open()
    assert snap["type"] == "SNAPSHOT" and "last_price" in snap
    from app.websocket.connection_manager import ws_manager
    assert bridge.push in ws_manager.active_connections
    bridge.stream_open()  # idempotent
    assert list(ws_manager.active_connections).count(bridge.push) == 1


def test_save_file_text_and_base64(bridge, tmp_path):
    r = bridge.save_file({"filename": "a.csv", "content": "x,y\n1,2\n", "encoding": "text"})
    assert r["saved"] is True and open(r["path"]).read() == "x,y\n1,2\n"
    r = bridge.save_file({"filename": "b.bin", "content": base64.b64encode(b"\x00\x01").decode(), "encoding": "base64"})
    assert open(r["path"], "rb").read() == b"\x00\x01"


def test_download_uses_backend_and_dialog(bridge):
    r = bridge.download({"path": "/api/v1/journal/template-csv", "filename": "template.csv"})
    assert r["saved"] is True
    assert open(r["path"], "rb").read().strip() != b""


def test_open_external_rejects_non_http(bridge, monkeypatch):
    opened = []
    monkeypatch.setattr("webbrowser.open", lambda url: opened.append(url) or True)
    assert bridge.open_external("file:///etc/passwd") == {"ok": False}
    assert bridge.open_external("https://example.com") == {"ok": True}
    assert opened == ["https://example.com"]


def test_get_app_info(bridge):
    info = bridge.get_app_info()
    from app.version import __version__
    assert info["version"] == __version__ and info["gateway_url"] is None and "data_dir" in info
```

- [ ] **Step 2: Run to verify failure**

Run: `$PY -m pytest backend/tests/test_desktop_bridge.py -q` → FAIL (`desktop.bridge` missing).

- [ ] **Step 3: Implement**

`backend/desktop/clipboard.py`:
```python
"""Clipboard write without extra dependencies (navigator.clipboard is blocked on file://)."""
import shutil
import subprocess
import sys


def copy_text(text: str) -> bool:
    candidates = []
    if sys.platform == "darwin":
        candidates = [["pbcopy"]]
    elif sys.platform.startswith("win"):
        candidates = [["clip"]]
    else:
        candidates = [["wl-copy"], ["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"]]
    for cmd in candidates:
        if shutil.which(cmd[0]) is None:
            continue
        try:
            subprocess.run(cmd, input=text.encode("utf-8"), check=True, timeout=5)
            return True
        except Exception:  # noqa: BLE001
            continue
    return False
```

`backend/desktop/bridge.py`:
```python
"""
DesktopBridge is the object pywebview exposes as window.pywebview.api. Every public method is
synchronous (pywebview runs each call on its own thread) and takes/returns JSON-compatible data.
"""
from __future__ import annotations

import base64
import logging
import mimetypes
import re
import sys
import webbrowser
from pathlib import Path
from typing import Callable, Optional

from app.core.paths import DATA_DIR, is_frozen
from app.version import __version__
from desktop import clipboard
from desktop.push import PushChannel
from desktop.runtime import BackendRuntime

logger = logging.getLogger("desktop.bridge")

TEXT_TYPES = ("application/json", "text/", "application/xml", "application/javascript", "application/problem+json")


def _is_text(content_type: str) -> bool:
    ct = (content_type or "").lower()
    return any(ct.startswith(t) for t in TEXT_TYPES)


class DesktopBridge:
    def __init__(
        self,
        runtime: BackendRuntime,
        push: PushChannel,
        gateway=None,
        index_url: str = "",
        windows_getter: Optional[Callable[[], list]] = None,
        dialog_window_getter: Optional[Callable[[], object]] = None,
    ):
        self.runtime = runtime
        self.push = push
        self.gateway = gateway
        self.index_url = index_url
        self._windows = windows_getter or (lambda: [])
        self._dialog_window = dialog_window_getter
        self._stream_attached = False
        self._popouts: dict[str, object] = {}

    # ---- HTTP-shaped requests, no HTTP ---------------------------------------------------
    def request(self, req: dict) -> dict:
        files = [
            (f["field"], f.get("filename") or "upload", base64.b64decode(f["data_b64"]), f.get("content_type") or "application/octet-stream")
            for f in (req.get("files") or [])
        ]
        fields = [(k, v) for k, v in (req.get("fields") or [])]
        body = req.get("body")
        body_bytes = body.encode("utf-8") if isinstance(body, str) else None
        if req.get("body_b64"):
            body_bytes = base64.b64decode(req["body_b64"])
        resp = self.runtime.call(
            req.get("method", "GET"), req.get("path", "/"), req.get("query") or "",
            headers=req.get("headers") or {}, body=body_bytes, files=files or None, fields=fields or None,
        )
        content_type = resp.headers.get("content-type", "")
        if _is_text(content_type) or not resp.content:
            return {"status": resp.status, "headers": resp.headers, "body": resp.content.decode("utf-8", errors="replace"), "body_b64": None}
        return {"status": resp.status, "headers": resp.headers, "body": None, "body_b64": base64.b64encode(resp.content).decode("ascii")}

    # ---- live stream -----------------------------------------------------------------------
    def stream_open(self) -> dict:
        from app.websocket.binance_client import binance_client
        from app.websocket.connection_manager import ws_manager

        async def _attach():
            if not self._stream_attached:
                ws_manager.attach(self.push, PushChannel.CHANNELS)
                self._stream_attached = True
            return {
                "type": "SNAPSHOT",
                "symbol": binance_client.symbol,
                "last_price": binance_client.last_price,
                "open_positions": binance_client._recalculate_open_positions(binance_client.last_price),
            }

        return self.runtime.run(_attach())

    # ---- windows ---------------------------------------------------------------------------
    def open_popout(self, spec: dict) -> dict:
        import webview
        label = re.sub(r"[^a-z0-9]", "-", str(spec.get("label", "panel")).lower())
        existing = self._popouts.get(label)
        if existing is not None and existing in webview.windows:
            try:
                existing.restore()
            except Exception:  # noqa: BLE001
                pass
            return {"created": False, "label": label}
        query = str(spec.get("query", "")).lstrip("?")
        url = f"{self.index_url}?{query}" if query else self.index_url
        win = webview.create_window(
            spec.get("title", "Kuantra Terminal"), url=url, js_api=self,
            width=int(spec.get("width", 1024)), height=int(spec.get("height", 700)),
            min_size=(600, 400), text_select=True, background_color="#0b0e14",
        )
        self._popouts[label] = win
        return {"created": True, "label": label}

    # ---- files -----------------------------------------------------------------------------
    def _pick_save_path(self, filename: str) -> Optional[str]:
        import webview
        win = self._dialog_window() if self._dialog_window else (webview.active_window() or (webview.windows[0] if webview.windows else None))
        if win is None:
            return None
        result = win.create_file_dialog(webview.SAVE_DIALOG, save_filename=filename)
        if not result:
            return None
        return result[0] if isinstance(result, (list, tuple)) else str(result)

    def save_file(self, spec: dict) -> dict:
        filename = spec.get("filename") or "download"
        data = spec.get("content") or ""
        raw = base64.b64decode(data) if spec.get("encoding") == "base64" else str(data).encode("utf-8")
        path = self._pick_save_path(filename)
        if not path:
            return {"saved": False, "path": None}
        Path(path).write_bytes(raw)
        return {"saved": True, "path": path}

    def download(self, spec: dict) -> dict:
        resp = self.runtime.call("GET", spec["path"], spec.get("query") or "")
        if resp.status != 200:
            return {"saved": False, "path": None, "status": resp.status}
        filename = spec.get("filename")
        disposition = resp.headers.get("content-disposition", "")
        m = re.search(r'filename="?([^";]+)"?', disposition)
        if m:
            filename = m.group(1)
        if not filename:
            ext = mimetypes.guess_extension(resp.headers.get("content-type", "").split(";")[0]) or ""
            filename = f"kuantra-download{ext}"
        path = self._pick_save_path(filename)
        if not path:
            return {"saved": False, "path": None, "status": 200}
        Path(path).write_bytes(resp.content)
        return {"saved": True, "path": path, "status": 200}

    # ---- misc ------------------------------------------------------------------------------
    def copy_text(self, text: str) -> dict:
        return {"ok": clipboard.copy_text(str(text))}

    def open_external(self, url: str) -> dict:
        if not isinstance(url, str) or not re.match(r"^https?://", url):
            return {"ok": False}
        return {"ok": bool(webbrowser.open(url))}

    def get_app_info(self) -> dict:
        try:
            import webview
            gui = getattr(webview, "guilib", None)
            gui_name = getattr(gui, "renderer", None) or (gui.__name__.split(".")[-1] if gui else None)
        except Exception:  # noqa: BLE001
            gui_name = None
        return {
            "version": __version__,
            "platform": sys.platform,
            "gui": gui_name,
            "frozen": is_frozen(),
            "data_dir": str(DATA_DIR),
            "gateway_url": getattr(self.gateway, "url", None),
        }
```

- [ ] **Step 4: Run tests**

Run: `$PY -m pytest backend/tests/test_desktop_bridge.py backend/tests -q` → PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/desktop backend/tests/test_desktop_bridge.py
git commit -m "feat(desktop): DesktopBridge js_api (request, stream, files, popouts)"
```

---

### Task 6: Desktop entry point with smoke mode; dev server cleanup

**Files:**
- Create: `backend/desktop_main.py`, `backend/desktop/smoke.py`, `backend/requirements-desktop.txt`
- Modify: `backend/main.py` (strip handshake/parent-pid), delete `backend/app/core/parent_watcher.py`
- Test: `backend/tests/test_desktop_main.py`

**Interfaces:**
- CLI: `desktop_main.py [--smoke] [--smoke-report PATH] [--smoke-timeout SECONDS] [--debug] [--dev-url URL] [--gui {cocoa,edgechromium,qt,gtk}] [--frontend-dir DIR]`.
- Produces `desktop_main.resolve_frontend_index(frontend_dir=None) -> Path`, `desktop_main.build_app(args) -> AppContext` (runtime, push, gateway, bridge, index_url), `desktop.smoke.run_smoke(window, ctx, timeout) -> dict` (`{"ok": bool, "reason": str, "checks": {...}}`).

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_desktop_main.py
import json
import subprocess
import sys
from pathlib import Path
import pytest

BACKEND = Path(__file__).resolve().parents[1]


def test_resolve_frontend_index_dev(tmp_path):
    import desktop_main
    (tmp_path / "index.html").write_text("<html></html>")
    assert desktop_main.resolve_frontend_index(str(tmp_path)) == tmp_path / "index.html"
    with pytest.raises(FileNotFoundError):
        desktop_main.resolve_frontend_index(str(tmp_path / "nope"))


def test_cli_parser_defaults():
    import desktop_main
    args = desktop_main.parse_args([])
    assert args.smoke is False and args.dev_url is None and args.gui is None
    args = desktop_main.parse_args(["--smoke", "--smoke-report", "r.json", "--smoke-timeout", "5"])
    assert args.smoke and args.smoke_report == "r.json" and args.smoke_timeout == 5.0


def test_main_py_has_no_sidecar_handshake():
    src = (BACKEND / "main.py").read_text()
    assert "KUANTRA_BACKEND_PORT" not in src and "parent-pid" not in src
    assert not (BACKEND / "app" / "core" / "parent_watcher.py").exists()


@pytest.mark.skipif(sys.platform != "darwin", reason="GUI smoke runs on the macOS dev box; CI covers the others")
def test_smoke_mode_end_to_end(tmp_path):
    dist = BACKEND.parent / "frontend" / "dist" / "index.html"
    if not dist.exists():
        pytest.skip("frontend not built")
    report = tmp_path / "smoke.json"
    proc = subprocess.run([sys.executable, str(BACKEND / "desktop_main.py"), "--smoke", "--smoke-report", str(report), "--smoke-timeout", "60"],
                          cwd=str(BACKEND), capture_output=True, text=True, timeout=180,
                          env={**__import__("os").environ, "KUANTRA_DATA_DIR": str(tmp_path / "data"), "KUANTRA_GATEWAY_ENABLED": "0"})
    assert proc.returncode == 0, proc.stdout + proc.stderr
    data = json.loads(report.read_text())
    assert data["ok"] is True and data["checks"]["react_mounted"] and data["checks"]["bridge_roundtrip"]
```

- [ ] **Step 2: Run to verify failure** → `ModuleNotFoundError: desktop_main`.

- [ ] **Step 3: Implement**

`backend/requirements-desktop.txt`:
```
pywebview>=6.2
pyinstaller>=6.10
PyQt6>=6.7; sys_platform == "linux"
PyQt6-WebEngine>=6.7; sys_platform == "linux"
QtPy>=2.4; sys_platform == "linux"
```

`backend/main.py` — keep `create_app()`, `lifespan`, `/health`; replace the `/ws/tv-sync` block with the shared handler (Task 4); replace everything from `def find_available_port` through the end with:
```python
def main():
    """Development HTTP server. The desktop app does not use this; see desktop_main.py."""
    parser = argparse.ArgumentParser(description="Kuantra Terminal Backend (dev server)")
    parser.add_argument("--host", default=settings.host)
    parser.add_argument("--port", type=int, default=settings.port)
    args = parser.parse_args()
    print(f"[+] Kuantra dev backend on http://{args.host}:{args.port}", flush=True)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
```
Remove now-unused imports (`socket`, `asyncio` if unused). Delete `backend/app/core/parent_watcher.py`.

`backend/desktop/smoke.py`:
```python
"""Headless self-test used by CI: proves the packaged app can render the UI and reach Python."""
from __future__ import annotations

import json
import threading
import time


def _eval(window, script, timeout=5.0):
    """evaluate_js that also resolves promises via callback."""
    result = {}
    done = threading.Event()

    def cb(value):
        result["value"] = value
        done.set()

    window.evaluate_js(script, callback=cb)
    done.wait(timeout)
    return result.get("value")


def run_smoke(window, ctx, timeout: float = 90.0) -> dict:
    checks = {"react_mounted": False, "bridge_roundtrip": False, "health": False, "push_sink": False}
    deadline = time.time() + timeout
    reason = "timeout"
    while time.time() < deadline:
        try:
            n = window.evaluate_js("(function(){var r=document.getElementById('root');return r?r.children.length:0})()")
            text = window.evaluate_js("(function(){var r=document.getElementById('root');return r?r.innerText.slice(0,60):''})()") or ""
            checks["react_mounted"] = bool(n) and "LOADING KUANTRA" not in text.upper()
            if checks["react_mounted"]:
                info = _eval(window, "window.pywebview.api.get_app_info()")
                checks["bridge_roundtrip"] = isinstance(info, dict) and "version" in info
                checks["push_sink"] = bool(window.evaluate_js("typeof window.__kuantraPush === 'function'"))
                resp = ctx.runtime.call("GET", "/health")
                checks["health"] = resp.status == 200 and json.loads(resp.content).get("status") == "online"
            if all(checks.values()):
                return {"ok": True, "reason": "", "checks": checks}
        except Exception as exc:  # noqa: BLE001
            reason = f"{type(exc).__name__}: {exc}"
        time.sleep(0.5)
    return {"ok": False, "reason": reason, "checks": checks}
```

`backend/desktop_main.py`:
```python
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
    sys.exit(main())
```

- [ ] **Step 4: Build the frontend once with the current config and run tests**

Run: `cd frontend && npm run build && cd .. && $PY -m pytest backend/tests/test_desktop_main.py backend/tests -q`
Expected: PASS except `test_smoke_mode_end_to_end` may FAIL until Task 7 (frontend not yet bridge-aware: the `apiFetch` path is not present so React still mounts, `__kuantraPush` is missing → `push_sink` false). That is acceptable at this task; re-run after Task 8.

- [ ] **Step 5: Commit**

```bash
git add backend/desktop_main.py backend/desktop backend/main.py backend/requirements-desktop.txt backend/tests/test_desktop_main.py
git rm backend/app/core/parent_watcher.py
git commit -m "feat(desktop): pywebview entry point with smoke mode; dev server without sidecar handshake"
```

---

### Task 7: Frontend adapter — apiFetch, bridge readiness, build config, vitest

**Files:**
- Modify: `frontend/package.json`, `frontend/vite.config.ts`, `frontend/index.html`, `frontend/src/lib/backend.ts`, `frontend/src/main.tsx`, `frontend/tsconfig.json`
- Create: `frontend/src/lib/bridge.ts`, `frontend/vitest.config.ts`, `frontend/src/lib/__tests__/backend.test.ts`
- Codemod: every `fetch(` in `frontend/src` (except inside `lib/backend.ts`) → `apiFetch(`.

**Interfaces:**
- Produces (`lib/bridge.ts`): `type BridgeApi = { request(req: BridgeRequest): Promise<BridgeResponse>; stream_open(): Promise<StreamSnapshot>; open_popout(spec): Promise<{created:boolean,label:string}>; save_file(spec): Promise<{saved:boolean,path:string|null}>; download(spec): Promise<{saved:boolean,path:string|null}>; copy_text(t:string): Promise<{ok:boolean}>; open_external(url:string): Promise<{ok:boolean}>; get_app_info(): Promise<AppInfo> }`, `getBridge(): BridgeApi | null`, `isDesktop(): boolean`, `bridgeReady(timeoutMs?): Promise<BridgeApi | null>`.
- Produces (`lib/backend.ts`): `apiFetch(input: string, init?: RequestInit): Promise<Response>`, `apiUrl(path)`, `apiBase()`, `wsUrl(path)`, `DEFAULT_BASE`.

- [ ] **Step 1: Install tooling**

Run: `cd frontend && npm install -D vitest@^2 vite-plugin-singlefile@^2.3 && cd ..`
Add to `frontend/package.json` scripts: `"test": "vitest run"`, and change `"build"` to `"npm run check:i18n && tsc && vite build"` (unchanged) — tests run separately in CI.

`frontend/vitest.config.ts`:
```ts
import { defineConfig } from "vitest/config";
export default defineConfig({ test: { environment: "node", include: ["src/**/__tests__/**/*.test.ts"] } });
```
`frontend/tsconfig.json`: add `"src/**/__tests__/**"` to `exclude` (so `tsc` in the build ignores test files) and keep `include: ["src"]`.

- [ ] **Step 2: Write failing tests**

```ts
// frontend/src/lib/__tests__/backend.test.ts
import { beforeEach, describe, expect, it, vi } from "vitest";

declare const globalThis: any;

function installBridge(impl: Partial<Record<string, any>>) {
  globalThis.window = globalThis;
  globalThis.pywebview = { api: impl };
}

beforeEach(() => {
  vi.resetModules();
  delete globalThis.pywebview;
  globalThis.window = globalThis;
  globalThis.location = { protocol: "http:", href: "http://localhost:5173/" };
});

describe("apiFetch in desktop mode", () => {
  it("serialises a JSON POST and rebuilds a Response", async () => {
    const request = vi.fn(async (req: any) => ({ status: 200, headers: { "content-type": "application/json" }, body: JSON.stringify({ echo: req }), body_b64: null }));
    installBridge({ request });
    const { apiFetch, apiUrl } = await import("../backend");
    const res = await apiFetch(apiUrl("/api/v1/x?a=1"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ k: 1 }) });
    expect(res.ok).toBe(true);
    const data = await res.json();
    expect(data.echo.method).toBe("POST");
    expect(data.echo.path).toBe("/api/v1/x");
    expect(data.echo.query).toBe("a=1");
    expect(data.echo.body).toBe(JSON.stringify({ k: 1 }));
    expect(request).toHaveBeenCalledTimes(1);
  });

  it("encodes FormData files as base64", async () => {
    const request = vi.fn(async (req: any) => ({ status: 200, headers: {}, body: JSON.stringify(req.files), body_b64: null }));
    installBridge({ request });
    const { apiFetch, apiUrl } = await import("../backend");
    const fd = new FormData();
    fd.append("file", new File(["a,b\n1,2"], "t.csv", { type: "text/csv" }));
    fd.append("note", "hello");
    const res = await apiFetch(apiUrl("/api/v1/journal/preview-csv"), { method: "POST", body: fd });
    const files = await res.json();
    expect(files[0].field).toBe("file");
    expect(files[0].filename).toBe("t.csv");
    expect(atob(files[0].data_b64)).toBe("a,b\n1,2");
    expect(request.mock.calls[0][0].fields).toEqual([["note", "hello"]]);
  });

  it("maps non-2xx to ok=false and decodes base64 bodies", async () => {
    installBridge({ request: async () => ({ status: 404, headers: {}, body: null, body_b64: btoa("nope") }) });
    const { apiFetch } = await import("../backend");
    const res = await apiFetch("/api/v1/missing");
    expect(res.ok).toBe(false);
    expect(res.status).toBe(404);
    expect(await res.text()).toBe("nope");
  });

  it("rejects with AbortError when the signal fires", async () => {
    installBridge({ request: () => new Promise(() => {}) });
    const { apiFetch } = await import("../backend");
    const c = new AbortController();
    const p = apiFetch("/slow", { signal: c.signal });
    c.abort();
    await expect(p).rejects.toMatchObject({ name: "AbortError" });
  });

  it("apiUrl/apiBase are path-only in desktop mode", async () => {
    installBridge({ request: async () => ({ status: 200, headers: {}, body: "{}", body_b64: null }) });
    const { apiUrl, apiBase } = await import("../backend");
    expect(apiUrl("/api/v1/x")).toBe("/api/v1/x");
    expect(apiBase()).toBe("");
  });
});

describe("apiFetch in browser dev mode", () => {
  it("delegates to window.fetch with the default base", async () => {
    const fetchMock = vi.fn(async () => new Response("{}", { status: 200 }));
    globalThis.fetch = fetchMock;
    const { apiFetch, apiUrl, apiBase, wsUrl } = await import("../backend");
    expect(apiBase()).toBe("http://127.0.0.1:8000");
    expect(wsUrl("/api/v1/ws/stream")).toBe("ws://127.0.0.1:8000/api/v1/ws/stream");
    await apiFetch(apiUrl("/api/v1/x"));
    expect(fetchMock).toHaveBeenCalledWith("http://127.0.0.1:8000/api/v1/x", expect.anything());
  });
});
```

- [ ] **Step 3: Run to verify failure**

Run: `cd frontend && npm test` → FAIL (`apiFetch` not exported).

- [ ] **Step 4: Implement**

`frontend/src/lib/bridge.ts`:
```ts
/** Typed access to window.pywebview.api (the Python DesktopBridge). Null outside the desktop app. */
export interface BridgeFile { field: string; filename: string; content_type: string; data_b64: string; }
export interface BridgeRequest {
  method: string; path: string; query: string; headers: Record<string, string>;
  body: string | null; body_b64?: string | null; files: BridgeFile[]; fields: [string, string][];
}
export interface BridgeResponse { status: number; headers: Record<string, string>; body: string | null; body_b64: string | null; }
export interface StreamSnapshot { type: "SNAPSHOT"; symbol: string; last_price: number; open_positions: unknown[]; }
export interface AppInfo { version: string; platform: string; gui: string | null; frozen: boolean; data_dir: string; gateway_url: string | null; }
export interface BridgeApi {
  request(req: BridgeRequest): Promise<BridgeResponse>;
  stream_open(): Promise<StreamSnapshot>;
  open_popout(spec: { label: string; title: string; query: string; width: number; height: number }): Promise<{ created: boolean; label: string }>;
  save_file(spec: { filename: string; content: string; encoding: "text" | "base64"; mime?: string }): Promise<{ saved: boolean; path: string | null }>;
  download(spec: { path: string; query?: string; filename?: string }): Promise<{ saved: boolean; path: string | null; status?: number }>;
  copy_text(text: string): Promise<{ ok: boolean }>;
  open_external(url: string): Promise<{ ok: boolean }>;
  get_app_info(): Promise<AppInfo>;
}

function host(): any {
  return typeof window !== "undefined" ? (window as any) : (globalThis as any);
}

export function getBridge(): BridgeApi | null {
  const api = host().pywebview?.api;
  return api && typeof api.request === "function" ? (api as BridgeApi) : null;
}

export function isDesktop(): boolean {
  return getBridge() !== null;
}

/** Expected to run inside pywebview when served from file:// (or when pywebview is already injected). */
export function expectsDesktop(): boolean {
  const loc = host().location;
  return !!getBridge() || (!!loc && loc.protocol === "file:");
}

/** Resolve once pywebview has injected its API (it fires `pywebviewready`), or null after the timeout. */
export function bridgeReady(timeoutMs = expectsDesktop() ? 30000 : 0): Promise<BridgeApi | null> {
  const existing = getBridge();
  if (existing || timeoutMs <= 0) return Promise.resolve(existing);
  return new Promise((resolve) => {
    const timer = setTimeout(() => { cleanup(); resolve(getBridge()); }, timeoutMs);
    const onReady = () => { cleanup(); resolve(getBridge()); };
    const cleanup = () => { clearTimeout(timer); host().removeEventListener?.("pywebviewready", onReady); };
    host().addEventListener?.("pywebviewready", onReady);
  });
}
```

`frontend/src/lib/backend.ts` (full replacement):
```ts
/**
 * Single source of truth for how the UI reaches the backend.
 *
 * Desktop (pywebview): no HTTP at all. apiFetch() serialises the request and calls
 * window.pywebview.api.request(); the reply is rebuilt into a real Response.
 * Browser dev (vite + `python backend/main.py`): plain fetch against DEFAULT_BASE.
 */
import { getBridge, type BridgeFile } from "./bridge";

export const DEFAULT_BASE = "http://127.0.0.1:8000";

export function apiBase(): string {
  return getBridge() ? "" : DEFAULT_BASE;
}

export function apiUrl(path: string): string {
  return `${apiBase()}${path}`;
}

export function wsUrl(path: string): string {
  return `${DEFAULT_BASE.replace(/^http/, "ws")}${path}`;
}

function splitUrl(input: string): { path: string; query: string } {
  let s = input;
  if (s.startsWith(DEFAULT_BASE)) s = s.slice(DEFAULT_BASE.length);
  const m = /^https?:\/\/[^/]+(\/.*)?$/.exec(s);
  if (m) s = m[1] || "/";
  const q = s.indexOf("?");
  return q === -1 ? { path: s, query: "" } : { path: s.slice(0, q), query: s.slice(q + 1) };
}

function normalizeHeaders(h: HeadersInit | undefined): Record<string, string> {
  const out: Record<string, string> = {};
  if (!h) return out;
  if (typeof Headers !== "undefined" && h instanceof Headers) h.forEach((v, k) => (out[k] = v));
  else if (Array.isArray(h)) h.forEach(([k, v]) => (out[k] = v));
  else Object.entries(h).forEach(([k, v]) => (out[k] = String(v)));
  return out;
}

async function blobToBase64(blob: Blob): Promise<string> {
  const bytes = new Uint8Array(await blob.arrayBuffer());
  let bin = "";
  for (let i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(bin);
}

function base64ToBytes(b64: string): Uint8Array {
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

function abortError(): Error {
  const e = new Error("The operation was aborted.");
  e.name = "AbortError";
  return e;
}

function raceAbort<T>(p: Promise<T>, signal: AbortSignal): Promise<T> {
  if (signal.aborted) return Promise.reject(abortError());
  return new Promise<T>((resolve, reject) => {
    const onAbort = () => reject(abortError());
    signal.addEventListener("abort", onAbort, { once: true });
    p.then((v) => { signal.removeEventListener("abort", onAbort); resolve(v); },
           (e) => { signal.removeEventListener("abort", onAbort); reject(e); });
  });
}

const NULL_BODY_STATUS = new Set([101, 204, 205, 304]);

export async function apiFetch(input: string, init: RequestInit = {}): Promise<Response> {
  const api = getBridge();
  if (!api) return fetch(input, init);

  const { path, query } = splitUrl(input);
  const method = (init.method || "GET").toUpperCase();
  const headers = normalizeHeaders(init.headers);
  let body: string | null = null;
  const files: BridgeFile[] = [];
  const fields: [string, string][] = [];

  if (typeof FormData !== "undefined" && init.body instanceof FormData) {
    for (const [k, v] of (init.body as any).entries() as Iterable<[string, FormDataEntryValue]>) {
      if (typeof v === "string") fields.push([k, v]);
      else files.push({ field: k, filename: (v as File).name || "upload", content_type: v.type || "application/octet-stream", data_b64: await blobToBase64(v) });
    }
  } else if (typeof init.body === "string") {
    body = init.body;
  } else if (init.body instanceof Blob) {
    files.push({ field: "file", filename: "upload", content_type: init.body.type || "application/octet-stream", data_b64: await blobToBase64(init.body) });
  } else if (init.body != null) {
    body = String(init.body);
  }

  const call = api.request({ method, path, query, headers, body, files, fields });
  const result = init.signal ? await raceAbort(call, init.signal) : await call;

  const status = result.status >= 200 && result.status <= 599 ? result.status : 500;
  const payload: BodyInit | null = NULL_BODY_STATUS.has(status) ? null : result.body_b64 != null ? base64ToBytes(result.body_b64) : result.body ?? "";
  return new Response(payload, { status, headers: result.headers });
}
```

`frontend/src/main.tsx`:
```tsx
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";
import { ThemeProvider } from "./context/ThemeContext";
import { I18nProvider } from "./context/I18nContext";
import { PluginRegistryProvider } from "./context/PluginRegistryContext";
import { bridgeReady } from "./lib/bridge";
import { installPushSink } from "./lib/push";

// Inside the desktop app the Python bridge is injected right after load; wait for it so the
// first requests never fall back to the browser path. In a plain browser this resolves at once.
bridgeReady().finally(() => {
  installPushSink();
  ReactDOM.createRoot(document.getElementById("root")!).render(
    <ThemeProvider>
      <I18nProvider>
        <PluginRegistryProvider>
          <App />
        </PluginRegistryProvider>
      </I18nProvider>
    </ThemeProvider>
  );
});
```
(`installPushSink` is created in Task 8; create `frontend/src/lib/push.ts` there. For this task's build to pass, create it now with the Task 8 content.)

`frontend/vite.config.ts`:
```ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { viteSingleFile } from "vite-plugin-singlefile";

// base "./" + single-file output: the desktop app loads index.html over file:// with no server
// and no module chunks to fetch.
export default defineConfig({
  base: "./",
  plugins: [react(), viteSingleFile()],
  clearScreen: false,
  build: { outDir: "dist", emptyOutDir: true },
  server: { port: 5173, strictPort: true },
});
```

`frontend/index.html`: change the placeholder text to `LOADING KUANTRA TERMINAL...` (the smoke test keys on this).

Codemod (run from `frontend/`):
```bash
python3 - <<'EOF'
import re, os
for dp, _, fns in os.walk("src"):
    for fn in fns:
        p = os.path.join(dp, fn)
        if not fn.endswith((".ts", ".tsx")) or p.endswith("lib/backend.ts") or "__tests__" in p:
            continue
        s = open(p).read()
        if not re.search(r"(?<![\w.])fetch\(", s):
            continue
        s2 = re.sub(r"(?<![\w.])fetch\(", "apiFetch(", s)
        rel = os.path.relpath("src/lib/backend", dp).replace(os.sep, "/")
        rel = rel if rel.startswith(".") else "./" + rel
        m = re.search(r'import \{([^}]*)\} from "' + re.escape(rel) + r'";', s2)
        if m:
            names = [n.strip() for n in m.group(1).split(",") if n.strip()]
            if "apiFetch" not in names:
                names.append("apiFetch")
            s2 = s2.replace(m.group(0), 'import { ' + ", ".join(sorted(names)) + ' } from "' + rel + '";')
        else:
            lines = s2.split("\n")
            last = max(i for i, l in enumerate(lines[:200]) if re.match(r'^(import\b.*|\} from .*);?\s*$', l))
            lines.insert(last + 1, f'import {{ apiFetch }} from "{rel}";')
            s2 = "\n".join(lines)
        open(p, "w").write(s2)
        print("codemod", p)
EOF
grep -rnE "(?<![\w.])fetch\(" src --include=*.ts --include=*.tsx | grep -v "lib/backend.ts" || echo "no raw fetch left"
```
(If `grep -P` is unavailable, use `grep -rn "fetch(" src | grep -v "apiFetch(" | grep -v lib/backend.ts`.)

- [ ] **Step 5: Verify**

Run: `cd frontend && npm test && npx tsc --noEmit && npm run build && ls -la dist && cd ..`
Expected: tests PASS; `dist/` contains a single `index.html` (plus maybe `favicon`), no `assets/` JS chunks. `grep -c "<script" dist/index.html` ≥ 1 and `grep -c 'src="./assets' dist/index.html` = 0.

- [ ] **Step 6: Commit**

```bash
git add frontend
git commit -m "feat(frontend): apiFetch bridge adapter, single-file file:// build, vitest"
```

---

### Task 8: Frontend push stream, popouts, downloads, clipboard, strings

**Files:**
- Create: `frontend/src/lib/push.ts`, `frontend/src/lib/desktop.ts`, `frontend/src/lib/__tests__/push.test.ts`, `frontend/src/lib/__tests__/desktop.test.ts`
- Modify: `frontend/src/hooks/useWebSocket.ts`, `frontend/src/hooks/usePopoutWindow.ts`, `frontend/src/components/modals/CsvImportModal.tsx:155-157`, `frontend/src/hooks/useTelemetry.ts:57-59`, `frontend/src/components/PivotGrid.tsx:96-101`, `frontend/src/components/studio/ReverseSkillStudio.tsx:117-121`, `frontend/src/App.tsx:175`, `frontend/src/locales/{en,tr,de}.json:117`

**Interfaces:**
- `lib/push.ts`: `installPushSink(): void`, `subscribePush(handler: (msg: any) => void): () => void`, `openStream(): Promise<StreamSnapshot | null>` (calls `stream_open`).
- `lib/desktop.ts`: `saveTextFile(filename, text, mime="text/csv"): Promise<boolean>`, `downloadFromBackend(path, filename?): Promise<boolean>`, `copyText(text): Promise<boolean>`, `openPopout(label, title, width, height): Promise<boolean>`.

- [ ] **Step 1: Write failing tests**

```ts
// frontend/src/lib/__tests__/push.test.ts
import { beforeEach, expect, it, vi } from "vitest";
declare const globalThis: any;
beforeEach(() => { vi.resetModules(); globalThis.window = globalThis; delete globalThis.__kuantraPush; delete globalThis.pywebview; });

it("dispatches batched messages (objects or JSON strings) to subscribers", async () => {
  const { installPushSink, subscribePush } = await import("../push");
  installPushSink();
  const got: any[] = [];
  const off = subscribePush((m) => got.push(m));
  globalThis.__kuantraPush([{ type: "TICK", price: 1 }, JSON.stringify({ type: "CANDLE_UPDATE" }), "not json"]);
  expect(got.map((m) => m.type)).toEqual(["TICK", "CANDLE_UPDATE"]);
  off();
  globalThis.__kuantraPush([{ type: "TICK" }]);
  expect(got).toHaveLength(2);
});

it("openStream returns the snapshot from the bridge and null in the browser", async () => {
  const { openStream } = await import("../push");
  expect(await openStream()).toBeNull();
  globalThis.pywebview = { api: { request: async () => ({}), stream_open: async () => ({ type: "SNAPSHOT", symbol: "BTCUSDT", last_price: 1, open_positions: [] }) } };
  expect((await openStream())?.symbol).toBe("BTCUSDT");
});
```

```ts
// frontend/src/lib/__tests__/desktop.test.ts
import { beforeEach, expect, it, vi } from "vitest";
declare const globalThis: any;
beforeEach(() => { vi.resetModules(); globalThis.window = globalThis; delete globalThis.pywebview; });

it("saveTextFile uses the bridge when present", async () => {
  const save_file = vi.fn(async () => ({ saved: true, path: "/tmp/x.csv" }));
  globalThis.pywebview = { api: { request: async () => ({}), save_file } };
  const { saveTextFile } = await import("../desktop");
  expect(await saveTextFile("x.csv", "a,b")).toBe(true);
  expect(save_file).toHaveBeenCalledWith({ filename: "x.csv", content: "a,b", encoding: "text", mime: "text/csv" });
});

it("downloadFromBackend falls back to window.open in the browser", async () => {
  const open = vi.fn();
  globalThis.open = open;
  const { downloadFromBackend } = await import("../desktop");
  expect(await downloadFromBackend("/api/v1/journal/template-csv", "t.csv")).toBe(true);
  expect(open).toHaveBeenCalledWith("http://127.0.0.1:8000/api/v1/journal/template-csv", "_blank");
});

it("copyText prefers the bridge, then navigator.clipboard", async () => {
  const copy_text = vi.fn(async () => ({ ok: true }));
  globalThis.pywebview = { api: { request: async () => ({}), copy_text } };
  const { copyText } = await import("../desktop");
  expect(await copyText("hi")).toBe(true);
  delete globalThis.pywebview;
  vi.resetModules();
  globalThis.navigator = { clipboard: { writeText: vi.fn(async () => undefined) } };
  const mod = await import("../desktop");
  expect(await mod.copyText("hi")).toBe(true);
});
```

- [ ] **Step 2: Run to verify failure** → `cd frontend && npm test` FAIL (modules missing).

- [ ] **Step 3: Implement**

`frontend/src/lib/push.ts`:
```ts
import { getBridge, type StreamSnapshot } from "./bridge";

type Handler = (msg: any) => void;
const handlers = new Set<Handler>();

function host(): any { return typeof window !== "undefined" ? (window as any) : (globalThis as any); }

/** Called by Python as window.__kuantraPush([...]) — each item is a message object or its JSON text. */
export function installPushSink(): void {
  host().__kuantraPush = (batch: unknown) => {
    const items = Array.isArray(batch) ? batch : [batch];
    for (const raw of items) {
      let msg = raw;
      if (typeof raw === "string") {
        try { msg = JSON.parse(raw); } catch { continue; }
      }
      handlers.forEach((h) => { try { h(msg); } catch (e) { console.error("push handler failed", e); } });
    }
  };
}

export function subscribePush(handler: Handler): () => void {
  handlers.add(handler);
  return () => { handlers.delete(handler); };
}

export async function openStream(): Promise<StreamSnapshot | null> {
  const api = getBridge();
  if (!api) return null;
  return api.stream_open();
}
```

`frontend/src/lib/desktop.ts`:
```ts
import { getBridge } from "./bridge";
import { apiUrl } from "./backend";

function host(): any { return typeof window !== "undefined" ? (window as any) : (globalThis as any); }

export async function saveTextFile(filename: string, text: string, mime = "text/csv"): Promise<boolean> {
  const api = getBridge();
  if (api) return (await api.save_file({ filename, content: text, encoding: "text", mime })).saved;
  const blob = new Blob([text], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  return true;
}

export async function downloadFromBackend(path: string, filename?: string): Promise<boolean> {
  const api = getBridge();
  if (api) return (await api.download({ path, filename })).saved;
  host().open(apiUrl(path), "_blank");
  return true;
}

export async function copyText(text: string): Promise<boolean> {
  const api = getBridge();
  if (api) {
    const r = await api.copy_text(text);
    if (r.ok) return true;
  }
  try {
    const nav = host().navigator;
    if (nav?.clipboard?.writeText) { await nav.clipboard.writeText(text); return true; }
  } catch { /* fall through */ }
  return false;
}

export async function openPopout(label: string, title: string, width: number, height: number): Promise<boolean> {
  const api = getBridge();
  const query = `popout=${encodeURIComponent(label)}`;
  if (api) return (await api.open_popout({ label, title, query, width, height })).created || true;
  const url = new URL(host().location.href);
  url.search = `?${query}`;
  host().open(url.toString(), `win-${label.toLowerCase().replace(/[^a-z0-9]/g, "-")}`, `width=${width},height=${height},menubar=no,status=no,toolbar=no`);
  return true;
}
```

`frontend/src/hooks/usePopoutWindow.ts` (full replacement):
```ts
import { useCallback } from "react";
import { openPopout } from "../lib/desktop";

export const usePopoutWindow = () => {
  const popout = useCallback(
    async (panelId: string, title: string = "Kuantra Sub-Window", width: number = 1024, height: number = 700) => {
      try {
        await openPopout(panelId, `Kuantra Terminal - ${title}`, width, height);
      } catch (e) {
        console.warn("pop-out failed:", e);
      }
    },
    []
  );
  return { popout };
};
```
(Keep whatever the file exports today — check the tail of the current file and preserve the return shape.)

`frontend/src/hooks/useWebSocket.ts` — add the desktop path at the top of `connect` (keep the existing WebSocket code as the browser fallback):
```ts
import { getBridge } from "../lib/bridge";
import { openStream, subscribePush } from "../lib/push";
...
  const unsubscribeRef = useRef<(() => void) | null>(null);

  const handleMessage = useCallback((message: any) => {
    if (message.type === "TICK") {
      updateTick(message.price, message.latency_ms || 12, message.timestamp || Date.now(), message.volume);
      if (message.open_positions) updatePositionPnl(message.open_positions);
    } else if (message.type === "CANDLE_UPDATE") {
      updateCandle(message.data);
    } else if (message.type === "SNAPSHOT") {
      if (message.last_price) updateTick(message.last_price, 12, Date.now());
      if (message.open_positions) updatePositionPnl(message.open_positions);
    }
  }, [updateTick, updateCandle, updatePositionPnl]);

  const connect = useCallback(() => {
    if (getBridge()) {
      if (unsubscribeRef.current) return;
      unsubscribeRef.current = subscribePush(handleMessage);
      openStream().then((snap) => { if (snap) handleMessage(snap); setConnectionStatus(true); })
                  .catch(() => setConnectionStatus(false));
      return;
    }
    // ...existing WebSocket code, with the inline TICK/CANDLE/SNAPSHOT branch replaced by handleMessage(message)
  }, [handleMessage, setConnectionStatus]);
```
and in the cleanup effect add `if (unsubscribeRef.current) { unsubscribeRef.current(); unsubscribeRef.current = null; }`.

Call-site edits:
- `CsvImportModal.tsx` `handleDownloadTemplate`: `downloadFromBackend("/api/v1/journal/template-csv", "kuantra_trade_template.csv");`
- `useTelemetry.ts` `exportRedactedLogs`: `downloadFromBackend("/api/v1/telemetry/export-logs", "kuantra_diagnostics_redacted.zip");`
- `PivotGrid.tsx:96-101`: replace the Blob/anchor block with `saveTextFile(\`kuantra_pivot_${Date.now()}.csv\`, csvRows.join("\n"));`
- `ReverseSkillStudio.tsx` `copyToClipboard`: `copyText(text).then((ok) => { if (ok) { setIsCopied(true); setTimeout(() => setIsCopied(false), 2000); } });`
- `App.tsx:175`: `Multi-Screen Sync Active`.
- Locales line 117: en `"Encrypted Local Vault"`, tr `"Şifreli Yerel Kasa"`, de `"Verschlüsselter lokaler Tresor"`. Search all three locales for `Tauri`, `C++ sidecar`, `Sidecar` and reword to "desktop core"/"masaüstü çekirdeği"/"Desktop-Kern" keeping key parity.

- [ ] **Step 4: Verify**

Run: `cd frontend && npm test && npm run build && cd .. && $PY -m pytest backend/tests/test_desktop_main.py -q`
Expected: frontend tests PASS, build OK, and now `test_smoke_mode_end_to_end` PASSES on macOS (React mounts over file://, bridge roundtrip, `__kuantraPush` installed).

- [ ] **Step 5: Manual check on macOS**

Run: `cd backend && $PY desktop_main.py --debug` — open the trade ticket, submit a PAPER order with the screenshot values, confirm the risk-rejection reason is shown (not "did not match the expected pattern"); export a CSV from Pivot grid (native save dialog appears); open a pop-out; confirm ticks update the header price. Close the window; the process must exit.

- [ ] **Step 6: Commit**

```bash
git add frontend
git commit -m "feat(frontend): push stream, native pop-outs, downloads and clipboard via bridge"
```

---

### Task 9: PyInstaller spec, build script, macOS DMG packaging + local verification

**Files:**
- Create: `packaging/kuantra.spec`, `packaging/icons/` (copy `icon.icns`, `icon.ico`, `icon.png`, `128x128.png`, `128x128@2x.png` from `src-tauri/icons/`), `scripts/build_desktop.py`, `scripts/package_macos.sh`, `scripts/smoke_desktop.py`
- Test: `backend/tests/test_packaging_spec.py`

**Interfaces:**
- `python scripts/build_desktop.py [--skip-frontend]` → builds frontend (unless skipped), runs PyInstaller with the spec, prints the output path. Output: macOS `dist/Kuantra Terminal.app`; Windows `dist/Kuantra Terminal/Kuantra Terminal.exe`; Linux `dist/kuantra-terminal/kuantra-terminal`.
- `python scripts/smoke_desktop.py [--report PATH]` → finds the built executable for the host OS, runs `--smoke --smoke-report`, exits with its code.
- `bash scripts/package_macos.sh` → `dist/Kuantra-Terminal-<ver>-<arch>.dmg`.

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_packaging_spec.py
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]


def test_spec_and_scripts_exist():
    assert (ROOT / "packaging" / "kuantra.spec").is_file()
    for f in ("icon.icns", "icon.ico", "icon.png"):
        assert (ROOT / "packaging" / "icons" / f).is_file()
    for f in ("build_desktop.py", "smoke_desktop.py", "package_macos.sh", "package_windows.sh", "package_linux.sh"):
        assert (ROOT / "scripts" / f).is_file(), f


def test_spec_bundles_frontend_alembic_and_app_data():
    spec = (ROOT / "packaging" / "kuantra.spec").read_text()
    for needle in ('"frontend"', "alembic.ini", '"alembic"', "collect_data_files(\"app\"", "console=False", "com.kuantra.terminal", "NSHighResolutionCapable"):
        assert needle in spec, needle
    for forbidden in ("numpy", "pandas", "scipy", "duckdb", "unittest"):
        assert f'"{forbidden}"' not in spec.split("excludes")[1].split("]")[0], forbidden
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implement**

`packaging/kuantra.spec`:
```python
# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Kuantra Terminal desktop app (pywebview shell). Run via scripts/build_desktop.py."""
import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
BACKEND = os.path.join(ROOT, "backend")
sys.path.insert(0, BACKEND)
from app.version import __version__  # noqa: E402

IS_MAC = sys.platform == "darwin"
IS_WIN = sys.platform.startswith("win")
IS_LINUX = sys.platform.startswith("linux")
APP_NAME = "Kuantra Terminal"
EXE_NAME = APP_NAME if (IS_MAC or IS_WIN) else "kuantra-terminal"
ICON = os.path.join(ROOT, "packaging", "icons", "icon.icns" if IS_MAC else "icon.ico" if IS_WIN else "icon.png")

datas = [
    (os.path.join(ROOT, "frontend", "dist"), "frontend"),
    (os.path.join(BACKEND, "alembic.ini"), "."),
    (os.path.join(BACKEND, "alembic"), "alembic"),
]
datas += collect_data_files("app", includes=["**/*.json", "**/*.yaml", "**/*.yml", "**/*.sql", "**/*.md", "**/*.txt"])

hiddenimports = []
for pkg in ["app", "starlette", "fastapi", "uvicorn", "pydantic", "cryptography", "webview", "httpx", "anyio", "alembic", "sqlalchemy.dialects.sqlite"]:
    hiddenimports += collect_submodules(pkg)

excludes = ["torch", "bleak", "web3", "quickfix", "PIL", "matplotlib", "tkinter", "pytest", "test",
            "alembic.testing", "setuptools", "pkg_resources", "ccxt.pro", "aiohttp.test_utils"]
if not IS_WIN:
    excludes.append("winloop")
if not IS_LINUX:
    excludes += ["PyQt6", "PyQt5", "PySide6", "PySide2", "qtpy"]

a = Analysis(
    [os.path.join(BACKEND, "desktop_main.py")],
    pathex=[BACKEND],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name=EXE_NAME,
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon=ICON,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name=EXE_NAME)

if IS_MAC:
    app = BUNDLE(
        coll,
        name=f"{APP_NAME}.app",
        icon=ICON,
        bundle_identifier="com.kuantra.terminal",
        version=__version__,
        info_plist={
            "CFBundleName": APP_NAME,
            "CFBundleDisplayName": APP_NAME,
            "CFBundleShortVersionString": __version__,
            "CFBundleVersion": __version__,
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "11.0",
            "NSRequiresAquaSystemAppearance": False,
            "LSApplicationCategoryType": "public.app-category.finance",
        },
    )
```

`scripts/build_desktop.py`:
```python
"""Build the desktop app with PyInstaller (all platforms). Usage: python scripts/build_desktop.py [--skip-frontend]"""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.version import __version__  # noqa: E402


def output_path() -> Path:
    if sys.platform == "darwin":
        return ROOT / "dist" / "Kuantra Terminal.app"
    if sys.platform.startswith("win"):
        return ROOT / "dist" / "Kuantra Terminal" / "Kuantra Terminal.exe"
    return ROOT / "dist" / "kuantra-terminal" / "kuantra-terminal"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-frontend", action="store_true")
    args = ap.parse_args()
    if not args.skip_frontend:
        npm = "npm.cmd" if sys.platform.startswith("win") else "npm"
        subprocess.run([npm, "--prefix", str(ROOT / "frontend"), "run", "build"], check=True)
    if not (ROOT / "frontend" / "dist" / "index.html").is_file():
        print("frontend/dist/index.html missing", file=sys.stderr)
        return 1
    for d in ("build", "dist"):
        shutil.rmtree(ROOT / d, ignore_errors=True)
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
           "--distpath", str(ROOT / "dist"), "--workpath", str(ROOT / "build"), str(ROOT / "packaging" / "kuantra.spec")]
    print("[*] ", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, cwd=str(ROOT))
    out = output_path()
    if not out.exists():
        print(f"expected output missing: {out}", file=sys.stderr)
        return 1
    print(f"[+] built {out} (version {__version__})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

`scripts/smoke_desktop.py`:
```python
"""Run the packaged app's headless self-test. Exit code = smoke result."""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def executable() -> Path:
    if sys.platform == "darwin":
        return ROOT / "dist" / "Kuantra Terminal.app" / "Contents" / "MacOS" / "Kuantra Terminal"
    if sys.platform.startswith("win"):
        return ROOT / "dist" / "Kuantra Terminal" / "Kuantra Terminal.exe"
    return ROOT / "dist" / "kuantra-terminal" / "kuantra-terminal"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", default=str(ROOT / "dist" / "smoke.json"))
    ap.add_argument("--timeout", type=float, default=120)
    args = ap.parse_args()
    exe = executable()
    env = {**os.environ, "KUANTRA_DATA_DIR": str(ROOT / "dist" / "smoke-data"), "KUANTRA_GATEWAY_ENABLED": "0"}
    proc = subprocess.run([str(exe), "--smoke", "--smoke-report", args.report, "--smoke-timeout", str(args.timeout)],
                          env=env, timeout=args.timeout + 60)
    report = Path(args.report)
    print(report.read_text() if report.exists() else "no smoke report written")
    ok = proc.returncode == 0 and report.exists() and json.loads(report.read_text()).get("ok") is True
    print("SMOKE", "OK" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
```

`scripts/package_macos.sh`:
```bash
#!/usr/bin/env bash
# Ad-hoc sign the .app and wrap it in a DMG: dist/Kuantra-Terminal-<ver>-<arch>.dmg
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$(python3 -c "import sys; sys.path.insert(0,'$ROOT/backend'); from app.version import __version__; print(__version__)")"
ARCH="$(uname -m)"; [ "$ARCH" = "arm64" ] && ARCH="aarch64"
APP="$ROOT/dist/Kuantra Terminal.app"
OUT="$ROOT/dist/Kuantra-Terminal-${VERSION}-${ARCH}.dmg"
STAGE="$ROOT/dist/dmg-stage"
[ -d "$APP" ] || { echo "missing $APP (run scripts/build_desktop.py first)"; exit 1; }
codesign --force --deep --sign - "$APP"
rm -rf "$STAGE" "$OUT"; mkdir -p "$STAGE"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
hdiutil create -volname "Kuantra Terminal" -srcfolder "$STAGE" -ov -format UDZO "$OUT"
rm -rf "$STAGE"
echo "[+] $OUT ($(du -h "$OUT" | cut -f1))"
```

Copy icons: `mkdir -p packaging/icons && cp src-tauri/icons/{icon.icns,icon.ico,icon.png,128x128.png,128x128@2x.png} packaging/icons/`.

Add to `.gitignore`: `dist/` already covers `dist`; add `build/` (exists), `*.spec` under backend stays; add `dist/smoke-data/`.

- [ ] **Step 4: Build and smoke on macOS**

Run:
```bash
$PY -m pip install -r backend/requirements-desktop.txt
$PY scripts/build_desktop.py
$PY scripts/smoke_desktop.py
bash scripts/package_macos.sh
$PY -m pytest backend/tests/test_packaging_spec.py -q
```
Expected: `SMOKE OK`, DMG created. Then open the app from `dist/` by double-click (Finder launch has CWD `/`), confirm the dashboard loads and data lands in `~/Library/Application Support/Kuantra Terminal`. If the frozen app fails on missing modules, add them to `hiddenimports` and rebuild; record the fix in the spec comment.

- [ ] **Step 5: Commit**

```bash
git add packaging scripts/build_desktop.py scripts/smoke_desktop.py scripts/package_macos.sh backend/tests/test_packaging_spec.py .gitignore
git commit -m "build: PyInstaller spec, build/smoke scripts, macOS DMG packaging"
```

---

### Task 10: Windows NSIS installer and Linux AppImage packaging

**Files:**
- Create: `packaging/windows/installer.nsi`, `scripts/package_windows.sh`, `packaging/linux/kuantra-terminal.desktop`, `packaging/linux/AppRun`, `scripts/package_linux.sh`
- Test: `backend/tests/test_packaging_installers.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_packaging_installers.py
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]


def test_nsis_script_contract():
    nsi = (ROOT / "packaging" / "windows" / "installer.nsi").read_text()
    for needle in ("RequestExecutionLevel user", "$LOCALAPPDATA\\Programs", 'taskkill /F /T /IM "Kuantra Terminal.exe"',
                   "F3017226-FE2A-4295-8BDF-00C3A9A7E4C5", "MicrosoftEdgeWebview2Setup.exe", "Section \"Uninstall\"", "${VERSION}"):
        assert needle in nsi, needle


def test_linux_desktop_and_apprun():
    desk = (ROOT / "packaging" / "linux" / "kuantra-terminal.desktop").read_text()
    assert "Exec=kuantra-terminal" in desk and "Icon=kuantra-terminal" in desk and "Categories=" in desk
    apprun = (ROOT / "packaging" / "linux" / "AppRun").read_text()
    assert "PYWEBVIEW_GUI" in apprun and 'exec "$HERE/usr/bin/kuantra-terminal"' in apprun
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implement**

`packaging/windows/installer.nsi`:
```nsis
; Kuantra Terminal per-user installer. Build: makensis -DVERSION=x.y.z -DSRCDIR=<dist\Kuantra Terminal> -DOUTFILE=<path> -DICON=<icon.ico> installer.nsi
!include "MUI2.nsh"
!include "LogicLib.nsh"

!define APP_NAME "Kuantra Terminal"
!define EXE_NAME "Kuantra Terminal.exe"
!define PUBLISHER "Kuantra Quantitative Engineering"
!define UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\KuantraTerminal"
!define WEBVIEW2_KEY "Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"

Name "${APP_NAME}"
OutFile "${OUTFILE}"
Unicode True
RequestExecutionLevel user
InstallDir "$LOCALAPPDATA\Programs\${APP_NAME}"
InstallDirRegKey HKCU "Software\${APP_NAME}" "InstallDir"
SetCompressor /SOLID lzma

!define MUI_ICON "${ICON}"
!define MUI_UNICON "${ICON}"
!define MUI_FINISHPAGE_RUN "$INSTDIR\${EXE_NAME}"
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

Function KillRunning
  nsExec::ExecToLog 'taskkill /F /T /IM "${EXE_NAME}"'
  Pop $0
FunctionEnd

Function un.KillRunning
  nsExec::ExecToLog 'taskkill /F /T /IM "${EXE_NAME}"'
  Pop $0
FunctionEnd

Function EnsureWebView2
  ReadRegStr $0 HKCU "${WEBVIEW2_KEY}" "pv"
  ${If} $0 == ""
    ReadRegStr $0 HKLM "${WEBVIEW2_KEY}" "pv"
  ${EndIf}
  ${If} $0 == ""
    ReadRegStr $0 HKLM "SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}" "pv"
  ${EndIf}
  ${If} $0 == ""
    DetailPrint "Installing Microsoft Edge WebView2 Runtime..."
    nsExec::ExecToLog 'powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest -Uri https://go.microsoft.com/fwlink/p/?LinkId=2124703 -OutFile \"$TEMP\MicrosoftEdgeWebview2Setup.exe\""'
    Pop $0
    ExecWait '"$TEMP\MicrosoftEdgeWebview2Setup.exe" /silent /install' $0
    Delete "$TEMP\MicrosoftEdgeWebview2Setup.exe"
  ${EndIf}
FunctionEnd

Section "Install"
  Call KillRunning
  SetOutPath "$INSTDIR"
  RMDir /r "$INSTDIR\_internal"
  File /r "${SRCDIR}\*.*"
  Call EnsureWebView2
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  CreateDirectory "$SMPROGRAMS\${APP_NAME}"
  CreateShortcut "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" "$INSTDIR\${EXE_NAME}"
  CreateShortcut "$DESKTOP\${APP_NAME}.lnk" "$INSTDIR\${EXE_NAME}"
  WriteRegStr HKCU "Software\${APP_NAME}" "InstallDir" "$INSTDIR"
  WriteRegStr HKCU "${UNINST_KEY}" "DisplayName" "${APP_NAME}"
  WriteRegStr HKCU "${UNINST_KEY}" "DisplayVersion" "${VERSION}"
  WriteRegStr HKCU "${UNINST_KEY}" "Publisher" "${PUBLISHER}"
  WriteRegStr HKCU "${UNINST_KEY}" "DisplayIcon" "$INSTDIR\${EXE_NAME}"
  WriteRegStr HKCU "${UNINST_KEY}" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegStr HKCU "${UNINST_KEY}" "InstallLocation" "$INSTDIR"
  WriteRegDWORD HKCU "${UNINST_KEY}" "NoModify" 1
  WriteRegDWORD HKCU "${UNINST_KEY}" "NoRepair" 1
SectionEnd

Section "Uninstall"
  Call un.KillRunning
  Delete "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk"
  RMDir "$SMPROGRAMS\${APP_NAME}"
  Delete "$DESKTOP\${APP_NAME}.lnk"
  RMDir /r "$INSTDIR"
  DeleteRegKey HKCU "${UNINST_KEY}"
  DeleteRegKey HKCU "Software\${APP_NAME}"
SectionEnd
```

`scripts/package_windows.sh` (run under Git Bash / GitHub `shell: bash`):
```bash
#!/usr/bin/env bash
# Build dist/Kuantra-Terminal-<ver>-Setup.exe with NSIS. Requires makensis on PATH (choco install nsis).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$(python -c "import sys; sys.path.insert(0,'$ROOT/backend'); from app.version import __version__; print(__version__)")"
SRC="$ROOT/dist/Kuantra Terminal"
OUT="$ROOT/dist/Kuantra-Terminal-${VERSION}-Setup.exe"
[ -f "$SRC/Kuantra Terminal.exe" ] || { echo "missing $SRC (run scripts/build_desktop.py first)"; exit 1; }
w() { if command -v cygpath >/dev/null 2>&1; then cygpath -w "$1"; else echo "$1"; fi; }
makensis -V2 "-DVERSION=${VERSION}" "-DSRCDIR=$(w "$SRC")" "-DOUTFILE=$(w "$OUT")" "-DICON=$(w "$ROOT/packaging/icons/icon.ico")" "$(w "$ROOT/packaging/windows/installer.nsi")"
echo "[+] $OUT"
```

`packaging/linux/kuantra-terminal.desktop`:
```ini
[Desktop Entry]
Type=Application
Name=Kuantra Terminal
Comment=Institutional quant trading terminal
Exec=kuantra-terminal
Icon=kuantra-terminal
Terminal=false
Categories=Office;Finance;
StartupWMClass=kuantra-terminal
```

`packaging/linux/AppRun`:
```bash
#!/bin/bash
HERE="$(dirname "$(readlink -f "$0")")"
export PYWEBVIEW_GUI="${PYWEBVIEW_GUI:-qt}"
export QTWEBENGINE_CHROMIUM_FLAGS="${QTWEBENGINE_CHROMIUM_FLAGS:---disable-gpu-sandbox}"
exec "$HERE/usr/bin/kuantra-terminal" "$@"
```

`scripts/package_linux.sh`:
```bash
#!/usr/bin/env bash
# Build dist/Kuantra-Terminal-<ver>-x86_64.AppImage from dist/kuantra-terminal/ using appimagetool.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$(python3 -c "import sys; sys.path.insert(0,'$ROOT/backend'); from app.version import __version__; print(__version__)")"
SRC="$ROOT/dist/kuantra-terminal"
APPDIR="$ROOT/dist/AppDir"
OUT="$ROOT/dist/Kuantra-Terminal-${VERSION}-x86_64.AppImage"
TOOL="${APPIMAGETOOL:-$ROOT/build/appimagetool}"
[ -x "$SRC/kuantra-terminal" ] || { echo "missing $SRC (run scripts/build_desktop.py first)"; exit 1; }
if [ ! -x "$TOOL" ]; then
  mkdir -p "$(dirname "$TOOL")"
  curl -fsSL -o "$TOOL" https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage
  chmod +x "$TOOL"
fi
rm -rf "$APPDIR" "$OUT"
mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/share/applications" "$APPDIR/usr/share/icons/hicolor/256x256/apps"
cp -r "$SRC"/. "$APPDIR/usr/bin/"
cp "$ROOT/packaging/linux/AppRun" "$APPDIR/AppRun"; chmod +x "$APPDIR/AppRun"
cp "$ROOT/packaging/linux/kuantra-terminal.desktop" "$APPDIR/kuantra-terminal.desktop"
cp "$ROOT/packaging/linux/kuantra-terminal.desktop" "$APPDIR/usr/share/applications/"
cp "$ROOT/packaging/icons/128x128@2x.png" "$APPDIR/kuantra-terminal.png"
cp "$ROOT/packaging/icons/128x128@2x.png" "$APPDIR/usr/share/icons/hicolor/256x256/apps/kuantra-terminal.png"
APPIMAGE_EXTRACT_AND_RUN=1 ARCH=x86_64 "$TOOL" --no-appstream "$APPDIR" "$OUT"
rm -rf "$APPDIR"
echo "[+] $OUT ($(du -h "$OUT" | cut -f1))"
```
`chmod +x scripts/*.sh packaging/linux/AppRun`.

- [ ] **Step 4: Run tests** → `$PY -m pytest backend/tests/test_packaging_installers.py -q` PASS. Optional local syntax check: `brew install makensis` is not required; CI validates.

- [ ] **Step 5: Commit**

```bash
git add packaging scripts/package_windows.sh scripts/package_linux.sh backend/tests/test_packaging_installers.py
git commit -m "build: NSIS installer and AppImage packaging"
```

---

### Task 11: CI and release workflows, manifest, verify script, workflow tests

**Files:**
- Rewrite: `.github/workflows/ci.yml`, `.github/workflows/release.yml`, `scripts/generate_release_manifest.py`, `scripts/verify_packaging.py`
- Modify tests: `backend/tests/test_ci_cd_workflows.py`, `backend/tests/test_release_manifest.py`, `backend/tests/test_phase18_documentation_packaging.py`, `backend/tests/test_phase9_health_updater.py`, `backend/tests/test_phase10_onboarding_build.py`, `backend/tests/test_phase15_final_release.py`, `backend/tests/test_sidecar_build.py` (delete), `backend/tests/test_live_uat.py` + `scripts/run_live_uat.py`

- [ ] **Step 1: Read each listed test, then rewrite the assertions to the new contract** (concrete replacements):
  - `test_ci_cd_workflows.py`: delete the `build_sidecar` import and Nuitka/rust assertions. Assert `ci.yml` has jobs `test-and-build` with matrix `[windows-latest, macos-latest, ubuntu-22.04]`, steps named `Run backend tests`, `Frontend tests and build`, `Build desktop app`, `Smoke test desktop app`, and no `rust-toolchain`. Assert `release.yml` triggers on `tags: ['v*']`, has jobs `build-and-package` and `publish-release`, and references `scripts/package_macos.sh`, `scripts/package_windows.sh`, `scripts/package_linux.sh`, `softprops/action-gh-release`.
  - `test_release_manifest.py`: version assertions read `from app.version import __version__`; manifest `version == __version__`; remove any `tauri.conf.json` read.
  - `test_phase18_documentation_packaging.py`: each `docs/BUILD_*.md` must contain `pywebview` and `PyInstaller`, and must not contain `Nuitka` or `Tauri`.
  - `test_phase9_health_updater.py`: drop the `tauri.conf.json` updater block assertions (keep `/health` checks).
  - `test_phase10_onboarding_build.py`: version check from `app.version`.
  - `test_phase15_final_release.py`: replace `tauri.conf.json` assertions with: `packaging/kuantra.spec` contains `APP_NAME = "Kuantra Terminal"` and `com.kuantra.terminal`.
  - Delete `backend/tests/test_sidecar_build.py` and `backend/build_sidecar.py`, `backend/kuantra-backend-x86_64-pc-windows-msvc.spec`.
  - `scripts/run_live_uat.py`: remove the `KUANTRA_BACKEND_PORT` handshake section; keep `TestClient` checks. Update `test_live_uat.py` accordingly.

- [ ] **Step 2: Rewrite `scripts/generate_release_manifest.py`**: read `dist/` (argument `--dist`, default `dist`), only files matching `Kuantra-Terminal-*`, version from `app.version`, `release_tag` from `--tag` (default `v{version}`), remove `create_synthetic_binaries`; `--dry-run` writes a manifest with zero artifacts instead of fabricating files. Write `MANIFEST.json` into the dist dir. Keep the field names `filename, platform, arch, size_bytes, sha256`.

- [ ] **Step 3: Rewrite `scripts/verify_packaging.py`**: required dirs `backend frontend packaging scripts docs`; required files `packaging/kuantra.spec`, `packaging/windows/installer.nsi`, `packaging/linux/AppRun`, `backend/desktop_main.py`, `frontend/vite.config.ts`; keep the locale parity check and docs check.

- [ ] **Step 4: Write the workflows**

`.github/workflows/ci.yml`:
```yaml
name: Kuantra Terminal CI

on:
  push:
    branches: [ main, 'feat/**' ]
  pull_request:
    branches: [ main ]

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

permissions:
  contents: read

jobs:
  test-and-build:
    name: Test & Build (${{ matrix.os }})
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: false
      matrix:
        os: [ windows-latest, macos-latest, ubuntu-22.04 ]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip
          cache-dependency-path: |
            backend/requirements.txt
            backend/requirements-desktop.txt
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: npm
          cache-dependency-path: frontend/package-lock.json
      - name: Install Linux desktop dependencies
        if: runner.os == 'Linux'
        run: |
          sudo apt-get update
          sudo apt-get install -y xvfb libfuse2 libxcb-cursor0 libxkbcommon-x11-0 libxcb-icccm4 libxcb-image0 \
            libxcb-keysyms1 libxcb-render-util0 libxcb-shape0 libxcb-xinerama0 libnss3 libasound2 libgl1 libegl1 \
            libxdamage1 libxcomposite1 libxrandr2 libxtst6 libdbus-1-3 wl-clipboard xclip
      - name: Install Python dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r backend/requirements.txt -r backend/requirements-desktop.txt
      - name: Run backend tests
        run: python -m pytest backend/tests -q --tb=short
      - name: Frontend tests and build
        working-directory: frontend
        run: |
          npm ci
          npm test
          npm run build
      - name: Build desktop app
        run: python scripts/build_desktop.py --skip-frontend
      - name: Smoke test desktop app
        shell: bash
        env:
          QTWEBENGINE_CHROMIUM_FLAGS: "--no-sandbox --disable-gpu"
        run: |
          if [ "$RUNNER_OS" = "Linux" ]; then xvfb-run -a python scripts/smoke_desktop.py; else python scripts/smoke_desktop.py; fi
      - name: Upload smoke report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: smoke-${{ matrix.os }}
          path: dist/smoke.json
          if-no-files-found: ignore
```

`.github/workflows/release.yml`:
```yaml
name: Kuantra Terminal Release

on:
  push:
    tags: [ 'v*' ]

permissions:
  contents: write

jobs:
  build-and-package:
    name: Package (${{ matrix.os }})
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: false
      matrix:
        include:
          - os: windows-latest
            package: bash scripts/package_windows.sh
          - os: macos-latest
            package: bash scripts/package_macos.sh
          - os: ubuntu-22.04
            package: bash scripts/package_linux.sh
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: npm
          cache-dependency-path: frontend/package-lock.json
      - name: Install Linux desktop dependencies
        if: runner.os == 'Linux'
        run: |
          sudo apt-get update
          sudo apt-get install -y xvfb libfuse2 libxcb-cursor0 libxkbcommon-x11-0 libxcb-icccm4 libxcb-image0 \
            libxcb-keysyms1 libxcb-render-util0 libxcb-shape0 libxcb-xinerama0 libnss3 libasound2 libgl1 libegl1 \
            libxdamage1 libxcomposite1 libxrandr2 libxtst6 libdbus-1-3
      - name: Install NSIS
        if: runner.os == 'Windows'
        run: choco install nsis -y --no-progress
      - name: Install Python dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r backend/requirements.txt -r backend/requirements-desktop.txt
      - name: Build frontend
        working-directory: frontend
        run: |
          npm ci
          npm run build
      - name: Build desktop app
        run: python scripts/build_desktop.py --skip-frontend
      - name: Smoke test desktop app
        shell: bash
        env:
          QTWEBENGINE_CHROMIUM_FLAGS: "--no-sandbox --disable-gpu"
        run: |
          if [ "$RUNNER_OS" = "Linux" ]; then xvfb-run -a python scripts/smoke_desktop.py; else python scripts/smoke_desktop.py; fi
      - name: Package
        shell: bash
        run: ${{ matrix.package }}
      - uses: actions/upload-artifact@v4
        with:
          name: release-${{ matrix.os }}
          path: dist/Kuantra-Terminal-*
          if-no-files-found: error

  publish-release:
    name: Publish GitHub Release
    needs: build-and-package
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/download-artifact@v4
        with:
          path: dist
          merge-multiple: true
      - name: Build MANIFEST.json
        run: python scripts/generate_release_manifest.py --dist dist --tag "${GITHUB_REF_NAME}"
      - uses: softprops/action-gh-release@v2
        with:
          tag_name: ${{ github.ref_name }}
          name: Kuantra Terminal ${{ github.ref_name }}
          body_path: RELEASE_NOTES.md
          files: |
            dist/Kuantra-Terminal-*
            dist/MANIFEST.json
```
Delete `.github/workflows/cleanup-release-assets.yml` (it pruned Tauri-named assets that no longer exist).

- [ ] **Step 5: Run the whole backend suite** → `$PY -m pytest backend/tests -q` PASS (0 failures; skips allowed).

- [ ] **Step 6: Commit**

```bash
git add .github scripts backend/tests
git rm backend/tests/test_sidecar_build.py backend/build_sidecar.py backend/kuantra-backend-x86_64-pc-windows-msvc.spec .github/workflows/cleanup-release-assets.yml
git commit -m "ci: pywebview build, smoke and release pipelines; drop Tauri/Nuitka contracts"
```

---

### Task 12: Remove Tauri, update extension, docs, repo metadata

**Files:**
- Delete: `src-tauri/` (entire directory), `scripts/build_sidecar.sh`, root `package-lock.json` Tauri entries
- Modify: root `package.json`, `.gitignore`, `browser-extension/background.js`, `browser-extension/popup.html`, `browser-extension/popup.js`, `browser-extension/manifest.json`, `README.md`, `ARCHITECTURE.md`, `CONTRIBUTING.md`, `RELEASE_NOTES.md`, `global.md`, `.cursorrules`, `docs/BUILD_MACOS.md`, `docs/BUILD_WINDOWS.md`, `docs/BUILD_LINUX.md`, `frontend/src/components/updater/UpdateNotifier.tsx` (text only), `.claude/docs/` (leave)

- [ ] **Step 1: Root `package.json`** — scripts: `dev`, `check:i18n`, `build`, `test` (`npm --prefix frontend test`), `desktop` (`python backend/desktop_main.py --dev-url http://localhost:5173`), `desktop:build` (`python scripts/build_desktop.py`); remove `tauri` script, keyword and devDependency; run `npm install` at root to regenerate `package-lock.json` (it becomes nearly empty). `.gitignore`: replace the `# Rust / Tauri` block with `# Desktop build outputs\ndist/\nbuild/\n` (keep others), drop `backend/*.spec` line if no longer needed.

- [ ] **Step 2: Browser extension** — `background.js`: read port from `chrome.storage.local` (`bridgePort`, default `8765`), build `ws://127.0.0.1:${port}/ws/tv-sync`, reconnect as before; on `chrome.storage.onChanged` for `bridgePort` reconnect. `popup.html`: replace the static `8000` with an `<input id="port" type="number" min="1024" max="65535">` and a Save button; `popup.js` loads/saves `bridgePort`. Update header comment. `manifest.json` version → `1.3.0`, description mentions "Kuantra Terminal desktop app".

- [ ] **Step 3: Docs** — rewrite the three `docs/BUILD_*.md` with: prerequisites (Python 3.11, Node 20; Windows: NSIS; Linux: apt list from ci.yml), `pip install -r backend/requirements.txt -r backend/requirements-desktop.txt`, `python scripts/build_desktop.py`, `python scripts/smoke_desktop.py`, then the platform `package_*.sh`, output filenames, data directory location, first-launch note (macOS Gatekeeper scan), gateway port 8765 note, dev workflow (`npm run dev` + `python backend/main.py`, or `npm run desktop`). Each must mention `pywebview` and `PyInstaller` and not mention Nuitka/Tauri. `ARCHITECTURE.md` §1: replace the process diagram with the spec §3 diagram and remove the parent-watcher section. `README.md`: badge/diagram/prereqs lines, drop the `<30 MB` claims, title version `v1.3.0`. `RELEASE_NOTES.md`: add a top section "Desktop shell: Tauri → pywebview" listing user-visible changes (single process, no local port, data dir move, extension port 8765, first-launch note). `global.md`/`.cursorrules:26-27`: replace the installer-size rule with "installers must kill running `Kuantra Terminal` processes on install/uninstall (NSIS does)". `CONTRIBUTING.md`: dev workflow section.

- [ ] **Step 4: Delete Tauri** — `git rm -r src-tauri scripts/build_sidecar.sh`; `grep -rni "tauri\|nuitka\|sidecar" --exclude-dir=node_modules --exclude-dir=.git --exclude-dir=dist --exclude-dir=build --exclude-dir=docs/superpowers .` must return only `RELEASE_NOTES.md` history lines and the `.claude/` folder. Fix every other hit (frontend UI strings included; keep locale parity).

- [ ] **Step 5: Verify** — `$PY scripts/verify_packaging.py && $PY -m pytest backend/tests -q && cd frontend && npm test && npm run build && cd .. && $PY scripts/build_desktop.py --skip-frontend && $PY scripts/smoke_desktop.py`.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "chore: remove Tauri shell; extension port setting; docs for pywebview packaging"
```

---

### Task 13: Cross-platform verification (Linux in Docker, Windows/Linux/macOS in CI)

**Files:**
- Create: `packaging/linux/Dockerfile.smoke` (ubuntu:22.04 image that installs the ci.yml apt list + Python 3.11 + Node 20, copies the repo, runs build + xvfb smoke + package_linux)

- [ ] **Step 1: Docker smoke (OrbStack is available locally)**

```dockerfile
# packaging/linux/Dockerfile.smoke — reproduces the Linux CI job locally
FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y software-properties-common curl git xvfb libfuse2 \
    libxcb-cursor0 libxkbcommon-x11-0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-render-util0 \
    libxcb-shape0 libxcb-xinerama0 libnss3 libasound2 libgl1 libegl1 libxdamage1 libxcomposite1 libxrandr2 \
    libxtst6 libdbus-1-3 file && add-apt-repository -y ppa:deadsnakes/ppa && apt-get update && \
    apt-get install -y python3.11 python3.11-venv python3.11-dev && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && apt-get install -y nodejs
WORKDIR /src
COPY . .
RUN python3.11 -m venv /venv && /venv/bin/pip install -U pip && \
    /venv/bin/pip install -r backend/requirements.txt -r backend/requirements-desktop.txt
RUN cd frontend && npm ci && npm run build
RUN /venv/bin/python scripts/build_desktop.py --skip-frontend
ENV QTWEBENGINE_CHROMIUM_FLAGS="--no-sandbox --disable-gpu"
RUN xvfb-run -a /venv/bin/python scripts/smoke_desktop.py && bash scripts/package_linux.sh && ls -la dist
```
Run: `docker build --platform linux/amd64 -f packaging/linux/Dockerfile.smoke -t kuantra-linux-smoke .` (from repo root; add a `.dockerignore` with `node_modules`, `dist`, `build`, `.git`, `backend/data`, `**/__pycache__`). Expected: image builds, `SMOKE OK`, AppImage listed. Fix whatever breaks (missing Qt libs → add to apt lists in both the Dockerfile and the workflows; missing hidden imports → spec).

- [ ] **Step 2: Push the branch and watch CI**

```bash
git push -u origin feat/pywebview-shell
gh run watch --exit-status $(gh run list --branch feat/pywebview-shell --workflow "Kuantra Terminal CI" --limit 1 --json databaseId -q '.[0].databaseId')
```
Expected: all three matrix jobs green. On failure download `smoke-<os>` artifacts and job logs (`gh run view <id> --log-failed`), fix, commit, push, repeat. Windows-specific things to expect: `pythonnet` needs the .NET runtime present on the runner (it is); if `--windowed` smoke exits non-zero with no report, temporarily set `console=True` in the spec for a diagnostic run.

- [ ] **Step 3: Tag a release candidate to exercise release.yml**

`git tag v1.3.0-rc1 && git push origin v1.3.0-rc1`; watch "Kuantra Terminal Release"; confirm the pre-release contains the three assets and `MANIFEST.json`. Delete the rc release/tag afterwards if the user prefers (`gh release delete v1.3.0-rc1 --yes && git push --delete origin v1.3.0-rc1`).

- [ ] **Step 4: Final commit and summary**

Update `docs/superpowers/plans/2026-09-03-pywebview-shell.md` checkboxes, commit. Report to the user: what changed, how to build locally per OS, data directory move, extension port, first-launch note, and the branch/CI status.
