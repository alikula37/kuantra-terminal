# Windows Build & Packaging Runbook

Kuantra Terminal ships as a **single-process Python desktop application**: a
[pywebview](https://pywebview.flowrl.com/) window hosting the React bundle, with the FastAPI
backend running in the same process and dispatched in-process over ASGI. There is no local HTTP
port between the UI and the backend, and no Rust/Node runtime in the shipped app.

On Windows pywebview uses the **Evergreen WebView2** GUI backend. Windows 10/11 normally ships
the runtime through Microsoft Edge; the installer checks that prerequisite and aborts with a
clear remediation message if it is absent. The production Windows payload intentionally excludes
PyQt6 and Qt WebEngine because Qt's Chromium child-process sandbox can be rejected by hardened
Windows builds. `PYWEBVIEW_GUI=qt` is available only to a source or separately-built diagnostic
package; it is not a production fallback. The app tree is frozen with **PyInstaller**
(`--onedir`, `--windowed`) and wrapped in a per-user NSIS installer.

---

## 1. Prerequisites

- **Windows 10 / 11 (x64)**
- **Microsoft Edge WebView2 Evergreen Runtime** (normally installed with Edge; verify with the
  WebView2 bootstrapper on clean images)
- **Python 3.11+ (x64)**
- **Node.js 20+ & npm**
- **NSIS (Nullsoft Scriptable Install System)** with `makensis` on `PATH`
  (`choco install nsis`, or add `C:\Program Files (x86)\NSIS` to `PATH`)
- A **bash** shell to run the packaging script (Git Bash or the `bash` shell of a GitHub Actions
  `windows-latest` runner)

No MSVC toolchain and no Rust toolchain are needed — nothing is compiled from source.

---

## 2. Install Dependencies

```bash
python -m venv .venv
.venv/Scripts/activate
pip install -r backend/requirements.txt -r backend/requirements-desktop.txt

npm --prefix frontend install
```

`backend/requirements-desktop.txt` pulls in `pywebview`, `PyInstaller`, `PyQt6` and
`PyQt6-WebEngine`. PyQt6 remains in the lock for Linux and separately-built diagnostics; the
Windows production host uses the installed WebView2 runtime and does not embed Qt.

---

## 3. Build the App Directory

```bash
python scripts/build_desktop.py
```

This builds the frontend (`npm --prefix frontend run build`, a single-file `index.html`) and then
runs PyInstaller against the checked-in spec `packaging/kuantra.spec`. Pass `--skip-frontend` to
reuse an existing `frontend/dist`.

Output: `dist\Kuantra Terminal\Kuantra Terminal.exe` (plus its onedir payload)

---

## 4. Smoke Test

```bash
python scripts/smoke_desktop.py
```

Runs the frozen executable with `--smoke`: on Windows it opens a visible WebView2 window (then
closes it after checks); other platforms use their normal hidden smoke host. It waits for React to mount,
performs a JS → Python bridge roundtrip and an in-process `/health` call, writes `dist/smoke.json`
and exits non-zero on failure. Because a `--windowed` build has no stdout on Windows, the JSON
report is the authoritative result. CI fails the build if this fails.

---

## 5. Package the Installer

```bash
bash scripts/package_windows.sh
```

Invokes `makensis` on `packaging/windows/installer.nsi`. The installer is **per-user** (no admin
elevation) and **terminates any running `Kuantra Terminal` process** before installing or
uninstalling, so file locks never corrupt an upgrade.

Output: `dist\Kuantra-Terminal-<version>-Setup.exe`

The version is read from the single source of truth, `backend/app/version.py`.

---

## 6. Data Directory

User data lives outside the install location so upgrades and uninstalls never destroy it:

```
%LOCALAPPDATA%\Kuantra Terminal
```

It holds the SQLite/DuckDB databases, logs, downloaded plugins and the WebView `localStorage`
store. Override it with the `KUANTRA_DATA_DIR` environment variable. A dev checkout (non-frozen)
keeps using `backend/data` instead.

---

## 7. Integrations Gateway (port 8765)

The desktop app exposes exactly one socket, bound to `127.0.0.1:8765`, for programs outside the
app:

- `/ws/tv-sync` — the TradingView Chrome extension
- `/api/v1/webhook/tradingview` — TradingView alert webhooks

Configure it with `KUANTRA_GATEWAY_PORT`, `KUANTRA_GATEWAY_HOST` and `KUANTRA_GATEWAY_ENABLED`.
If the port is already in use the gateway is disabled automatically and logged; the app still
starts normally. The frontend never talks to this port.

---

## 8. Development Workflow

Browser dev loop (hot reload, backend on uvicorn :8000):

```bash
npm run dev            # Vite dev server on :5173
python backend/main.py # FastAPI on :8000
```

Desktop dev loop (real pywebview window and Python bridge, Vite hot reload):

```bash
npm run desktop        # python backend/desktop_main.py --dev-url http://localhost:5173
```

Tests:

```bash
python -m pytest backend/tests -q   # set KUANTRA_DATA_DIR to a fresh directory first
npm --prefix frontend test
```
