# Linux Build & Packaging Runbook

Kuantra Terminal ships as a **single-process Python desktop application**: a
[pywebview](https://pywebview.flowrl.com/) window hosting the React bundle, with the FastAPI
backend running in the same process and dispatched in-process over ASGI. There is no local HTTP
port between the UI and the backend, and no Rust/Node runtime in the shipped app.

On Linux pywebview uses the **Qt** GUI backend (PyQt6 + PyQt6-WebEngine). The browser engine is
bundled inside the AppImage, so no GTK/WebKit stack is required beyond the X11 libraries listed
below. The app tree is frozen with **PyInstaller** (`--onedir`, `--windowed`) and wrapped in an
AppImage.

---

## 1. Prerequisites

- **Ubuntu 22.04 / Debian 12 (x86_64)** or newer
- **Python 3.11+**
- **Node.js 20+ & npm**

System libraries required both to build and to *run* the AppImage (`binutils` is build-only:
PyInstaller shells out to `objdump` to scan shared-library dependencies):

```bash
sudo apt-get update
sudo apt-get install -y \
  binutils \
  libxcb-cursor0 libxkbcommon-x11-0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 \
  libxcb-render-util0 libxcb-shape0 libxcb-xinerama0 libnss3 libasound2 libgl1 \
  libegl1 libxdamage1 libxcomposite1 libxrandr2 libxtst6 libdbus-1-3
```

On a headless CI runner also install `xvfb` (to give Qt a display) and `libfuse2` (so the built
AppImage can be executed):

```bash
sudo apt-get install -y xvfb libfuse2
```

---

## 2. Install Dependencies

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt -r backend/requirements-desktop.txt

npm --prefix frontend install
```

`backend/requirements-desktop.txt` pulls in `pywebview`, `PyInstaller`, `PyQt6` and
`PyQt6-WebEngine`.

---

## 3. Build the App Directory

```bash
python scripts/build_desktop.py
```

This builds the frontend (`npm --prefix frontend run build`, a single-file `index.html`) and then
runs PyInstaller against the checked-in spec `packaging/kuantra.spec`. Pass `--skip-frontend` to
reuse an existing `frontend/dist`.

Output: `dist/kuantra-terminal/kuantra-terminal` (plus its onedir payload)

---

## 4. Smoke Test

```bash
xvfb-run -a python scripts/smoke_desktop.py
```

Runs the frozen executable with `--smoke`: it opens a hidden window, waits for React to mount,
performs a JS → Python bridge roundtrip and an in-process `/health` call, writes `dist/smoke.json`
and exits non-zero on failure. CI fails the build if this fails. Drop `xvfb-run` on a desktop
session with a real display.

---

## 5. Package the AppImage

```bash
bash scripts/package_linux.sh
```

The script assembles an `AppDir` (AppRun launcher, `.desktop` entry, 256×256 icon), downloads
`appimagetool` into `build/` on first use (set `APPIMAGETOOL` to point at an existing copy) and
produces the AppImage.

Output: `dist/Kuantra-Terminal-<version>-x86_64.AppImage`

The version is read from the single source of truth, `backend/app/version.py`.

Make it executable and run it:

```bash
chmod +x dist/Kuantra-Terminal-*-x86_64.AppImage
./dist/Kuantra-Terminal-*-x86_64.AppImage
```

---

## 6. Data Directory

User data lives outside the AppImage so upgrades never destroy it:

```
$XDG_DATA_HOME/kuantra-terminal      # or ~/.local/share/kuantra-terminal
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
KUANTRA_DATA_DIR="$(mktemp -d)" python -m pytest backend/tests -q
npm --prefix frontend test
```
