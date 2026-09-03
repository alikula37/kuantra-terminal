# Kuantra Terminal: pywebview Desktop Shell — Design

Date: 2026-09-03
Status: approved (user decision: replace Tauri with pywebview across the whole project)

## 1. Goal

Replace the Tauri (Rust) desktop shell and the uvicorn HTTP server that sits between the
React frontend and the Python backend with a single-process Python desktop application built on
pywebview. The frontend calls Python directly through `window.pywebview.api`; there is no HTTP
socket between the UI and the backend. The result must build and run on macOS, Windows and
Linux from GitHub Actions and be fit for production distribution (DMG, NSIS installer, AppImage).

## 2. Non-goals

- Rewriting the 141 FastAPI endpoints as plain Python functions. They are kept as-is and
  dispatched in-process through ASGI (no network). Rewriting them is a separate project.
- Code signing / notarization (no identities exist today). Ad-hoc signing on macOS only.
- Auto-update. The old Tauri updater was never functional (placeholder key, no `latest.json`).
  The in-UI "updater" component is a static banner and stays a static banner.

## 3. Architecture

```
┌────────────────────────────── one OS process ──────────────────────────────┐
│  backend/desktop_main.py                                                   │
│  ┌──────────────┐   js_api (thread per call)   ┌────────────────────────┐  │
│  │ pywebview    │ ─────────────────────────────▶│ DesktopBridge          │  │
│  │ window(s)    │ ◀────── run_js push batches ──│  request()  stream_open│  │
│  │ file://…/    │                               │  save_file() download()│  │
│  │ index.html   │                               │  open_popout() …       │  │
│  └──────────────┘                               └───────────┬────────────┘  │
│                                                             │ run_coroutine_threadsafe
│  ┌──────────────────────────────────────────────────────────▼─────────────┐ │
│  │ BackendRuntime: dedicated asyncio loop thread                          │ │
│  │   FastAPI app (create_app())  ◀── httpx.ASGITransport (in-process)     │ │
│  │   lifespan: binance_client.start()/stop()                              │ │
│  │   ws_manager.broadcast() ──▶ PushChannel sink ──▶ JS window.__kuantraPush│ │
│  │   IntegrationsGateway (optional uvicorn on 127.0.0.1:8765)             │ │
│  │      /ws/tv-sync  (Chrome extension)   /api/v1/webhook/tradingview     │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────────┘
```

### 3.1 Frontend loading

- The Vite build is emitted with `base: "./"` and bundled into a single `index.html`
  (`vite-plugin-singlefile`) so no module chunk is fetched over `file://`. Verified on macOS
  WKWebView (prototype 2026-09-03): React mounts, `localStorage` works, origin is stable
  (`file://`), no port is involved. pywebview enables file-URL access on all three engines
  (`allowFileAccessFromFileURLs`, `--allow-file-access-from-files`, `LocalContentCanAccessFileUrls`).
- pywebview `private_mode=False` with `storage_path=<DATA_DIR>/webview` so `localStorage`
  persists between launches.
- No CSP meta tag: pywebview's own JS bridge relies on `eval`, and the page loads nothing remote.
  `OPEN_EXTERNAL_LINKS_IN_BROWSER` stays on.
- Dev mode is unchanged for the browser: `npm run dev` (Vite :5173) + `python backend/main.py`
  (uvicorn :8000). When `window.pywebview` is absent the frontend falls back to real `fetch`
  and `WebSocket`. `python backend/desktop_main.py --dev-url http://localhost:5173` runs the
  Vite dev server inside pywebview with the real bridge.

### 3.2 JS ↔ Python contract (`DesktopBridge`, exposed as `window.pywebview.api`)

All methods are synchronous Python functions (pywebview runs each call in its own thread and
returns a Promise to JS). Payloads are JSON.

| Method | Input | Output |
|---|---|---|
| `request(req)` | `{method, path, query, headers, body, files:[{field, filename, content_type, data_b64}], fields:[[k,v]]}` | `{status, headers:{}, body:string|null, body_b64:string|null}` |
| `stream_open()` | – | `{type:"SNAPSHOT", symbol, last_price, open_positions}`; registers the push sink |
| `open_popout(spec)` | `{label, title, query, width, height}` | `{created: bool, label}` |
| `save_file(spec)` | `{filename, content, encoding:"text"|"base64", mime}` | `{saved: bool, path: string|null}` |
| `download(spec)` | `{path, filename}` | same as `save_file` (fetches `path` in-process first) |
| `copy_text(text)` | string | `{ok: bool}` |
| `open_external(url)` | http(s) URL | `{ok: bool}` |
| `get_app_info()` | – | `{version, platform, gui, frozen, data_dir, gateway_url}` |

Push: Python calls `window.__kuantraPush(batch)` where `batch` is a JSON array of the exact
message objects the old WebSocket sent (`TICK`, `CANDLE_UPDATE`, `SNAPSHOT`, `COMPLIANCE_ALERT`,
`TV_SYNC_UPDATE`). Batches are flushed every 50 ms to every open window.

### 3.3 Frontend adapter (`frontend/src/lib/backend.ts`)

`apiFetch(input, init)` is a drop-in for `fetch` that returns a real `Response`. In desktop mode
it serialises the request (FormData files become base64), calls `api.request`, and rebuilds a
`Response` (`ok`, `status`, `json()`), honouring `AbortSignal` by racing the promise. Outside
pywebview it delegates to `window.fetch`. `apiUrl(path)` returns `path` in desktop mode and
`http://127.0.0.1:8000` + path in dev mode. All 104 call sites change only `fetch(` → `apiFetch(`.

The single WebSocket consumer (`useWebSocket`) becomes: `stream_open()` for the snapshot plus
`subscribePush()`; the dev fallback keeps the real WebSocket.

### 3.4 Backend runtime

- `BackendRuntime` owns one asyncio loop in a daemon thread, enters the FastAPI lifespan on
  start and exits it on stop. `call()` uses `httpx.AsyncClient(transport=ASGITransport(app))`
  so multipart uploads, query strings, JSON bodies, `FileResponse` and custom `Response`s all
  work unchanged.
- `PushChannel` is registered in `ws_manager` as a sink with `send_text`, subscribed to
  `market_ticks, kline_updates, open_positions, system_metrics, tv_sync`.
- `BackgroundTasks` in `plugin_endpoints.py` would block the in-process call until the download
  finishes; it is replaced by `app.core.background.fire_and_forget`.
- Long-lived app data moves out of the install directory: `DATA_DIR` is
  `~/Library/Application Support/Kuantra Terminal`, `%LOCALAPPDATA%\Kuantra Terminal`,
  `$XDG_DATA_HOME/kuantra-terminal`, overridable with `KUANTRA_DATA_DIR`. Dev (non-frozen) keeps
  `backend/data`. Downloaded plugins install under `DATA_DIR/plugins`.

### 3.5 Integrations gateway (external clients only)

Two features are used by *other programs* and therefore still need a socket:
the TradingView Chrome extension (`/ws/tv-sync`) and TradingView alert webhooks
(`/api/v1/webhook/tradingview`). They are served by a tiny FastAPI sub-app on uvicorn bound to
`127.0.0.1:8765` (settings `gateway_enabled`, `gateway_host`, `gateway_port`; env
`GATEWAY_PORT` etc.). The socket is pre-bound by us; if the port is busy the gateway is disabled
and logged, the app still starts. The frontend never talks to it. The Chrome extension defaults
to 8765 and lets the user change the port in its popup.

### 3.6 Packaging

- PyInstaller `--onedir` from a checked-in spec `packaging/kuantra.spec` (frontend `dist`,
  `alembic.ini`, `alembic/`, `app` data files, icons). `--windowed`. macOS `BUNDLE` with
  `com.kuantra.terminal`, `LSMinimumSystemVersion 11.0`, `NSHighResolutionCapable`.
- macOS: `Kuantra Terminal.app` → ad-hoc `codesign --deep -s -` → DMG via `hdiutil`
  (`Kuantra-Terminal-<ver>-aarch64.dmg`).
- Windows: WebView2 (pywebview `edgechromium`), NSIS per-user installer
  (`Kuantra-Terminal-<ver>-Setup.exe`), kills running instances, installs the WebView2 evergreen
  runtime if missing.
- Linux: pywebview `qt` backend (PyQt6 + PyQt6-WebEngine, self-contained) packaged as AppImage
  (`Kuantra-Terminal-<ver>-x86_64.AppImage`) with `.desktop` + icon.
- Every build ends with a smoke run: `<exe> --smoke --smoke-report smoke.json` opens a hidden
  window, waits for React to mount, performs a JS→Python roundtrip and an in-process
  `/health` call, writes the report and exits 0/1. CI fails on non-zero.
- Version single source: `backend/app/version.py`.

### 3.7 CI / release

- `ci.yml` (push/PR to main): per-OS pytest, frontend vitest + build, PyInstaller build, smoke,
  artifact upload. No publishing.
- `release.yml` (tag `v*`): build + package + smoke per OS, then one publish job with
  `MANIFEST.json` (sha256, size) attached to the GitHub release.

## 4. Removed

`src-tauri/` (all), root `package.json` Tauri script/dependency, `scripts/build_sidecar.sh`,
`backend/build_sidecar.py`, `backend/kuantra-backend-*.spec`, `backend/app/core/parent_watcher.py`,
the `KUANTRA_BACKEND_PORT` stdout handshake, `--parent-pid`, the Rust toolchain in CI, all
docs/tests that assert the Tauri/Nuitka contract.

## 5. Risks and mitigations

| Risk | Mitigation |
|---|---|
| WebView2 / QtWebEngine differences with `file://` | single-file bundle (no chunk loading); per-OS CI smoke test |
| `localStorage` lost | `private_mode=False` + `storage_path`; origin is the stable `file://` |
| Clipboard blocked on `file://` | `copy_text` bridge with `pbcopy`/`clip`/`xclip|wl-copy` |
| Downloads via `window.open` | `download`/`save_file` bridge with native save dialog |
| High-frequency ticks over `run_js` | 50 ms batching, single JSON array per flush |
| Windows windowed exe has no stdout | logging to `DATA_DIR/logs`, smoke report file |
| Slow first launch on macOS (Gatekeeper scan of onedir) | one-time per install, documented |
