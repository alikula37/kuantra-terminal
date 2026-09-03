# macOS Build & Packaging Runbook

Kuantra Terminal ships as a **single-process Python desktop application**: a
[pywebview](https://pywebview.flowrl.com/) window hosting the React bundle, with the FastAPI
backend running in the same process and dispatched in-process over ASGI. There is no local HTTP
port between the UI and the backend, and no Rust/Node runtime in the shipped app.

On macOS pywebview uses the **cocoa** GUI backend (WKWebView), which is part of the OS — nothing
extra to install for end users. The app tree is frozen with **PyInstaller** (`--onedir`,
`--windowed`), ad-hoc signed, and wrapped in a DMG.

---

## 1. Prerequisites

- **macOS 11 (Big Sur) or newer** — Apple Silicon or Intel
- **Xcode Command Line Tools**: `xcode-select --install`
- **Python 3.11+** (use an arm64 build on Apple Silicon)
- **Node.js 20+ & npm**

No code-signing identity is required: the DMG is ad-hoc signed (`codesign -s -`).

---

## 2. Install Dependencies

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt -r backend/requirements-desktop.txt

npm --prefix frontend install
```

`backend/requirements-desktop.txt` pulls in `pywebview` and `PyInstaller`. The PyQt6 entries in
that file are constrained to non-macOS platforms and are not installed here — macOS uses the
system WKWebView.

---

## 3. Build the App Bundle

```bash
python scripts/build_desktop.py
```

This builds the frontend (`npm --prefix frontend run build`, a single-file `index.html`) and then
runs PyInstaller against the checked-in spec `packaging/kuantra.spec`. Pass `--skip-frontend` to
reuse an existing `frontend/dist`.

Output: `dist/Kuantra Terminal.app`

---

## 4. Smoke Test

```bash
python scripts/smoke_desktop.py
```

Runs the frozen app with `--smoke`: it opens a hidden window, waits for React to mount, performs a
JS → Python bridge roundtrip and an in-process `/health` call, writes `dist/smoke.json` and exits
non-zero on failure. CI fails the build if this fails.

---

## 5. Package the DMG

```bash
bash scripts/package_macos.sh
```

The script ad-hoc signs the bundle (`codesign --force --deep --sign -`), stages it next to an
`/Applications` symlink and builds a compressed DMG with `hdiutil`.

Output: `dist/Kuantra-Terminal-<version>-aarch64.dmg`
(`x86_64` on Intel — the arch suffix comes from `uname -m`.)

The version is read from the single source of truth, `backend/app/version.py`.

---

## 6. First Launch Notes

- The app is **not notarized**. On first launch users must **right-click the app → Open** and
  confirm the Gatekeeper prompt; double-clicking shows "cannot be opened".
- The **first launch after installing from the DMG can take up to ~40 seconds** while Gatekeeper
  scans the whole app tree. Every later launch takes 1–2 seconds. This is a one-time cost per
  install, not a per-launch cost.

---

## 7. Data Directory

User data lives outside the install location so upgrades never destroy it:

```
~/Library/Application Support/Kuantra Terminal
```

It holds the SQLite/DuckDB databases, logs, downloaded plugins and the WebView `localStorage`
store. Override it with the `KUANTRA_DATA_DIR` environment variable. A dev checkout (non-frozen)
keeps using `backend/data` instead.

---

## 8. Integrations Gateway (port 8765)

The desktop app exposes exactly one socket, bound to `127.0.0.1:8765`, for programs outside the
app:

- `/ws/tv-sync` — the TradingView Chrome extension
- `/api/v1/webhook/tradingview` — TradingView alert webhooks

Configure it with `KUANTRA_GATEWAY_PORT`, `KUANTRA_GATEWAY_HOST` and `KUANTRA_GATEWAY_ENABLED`.
If the port is already in use the gateway is disabled automatically and logged; the app still
starts normally. The frontend never talks to this port.

---

## 9. Development Workflow

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
