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

- **Native macOS build host** — current recorded validation is Mac mini Apple Silicon.
  macOS 11+ and Intel compatibility must be tested separately before being advertised;
  an arm64 build is not a universal or Intel artifact.
- **Xcode Command Line Tools**: `xcode-select --install`
- **Python 3.11+** (use an arm64 build on Apple Silicon)
- **Node.js 20+ & npm**

No code-signing identity is required: the DMG is ad-hoc signed (`codesign -s -`).

---

## 2. Install Dependencies

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.lock

npm --prefix frontend ci
```

The lock includes desktop dependencies (`pywebview` and `PyInstaller`) with platform
markers; macOS uses system WKWebView. Initial installation may need network. Cached
`uv --offline` resolution does not block application network connections.

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

Use an isolated `KUANTRA_DATA_DIR` for smoke, never a real user directory. Record
`KUANTRA_BUILD_COMMIT` from the build's actual source commit; `UNKNOWN` is not exact
provenance. Current local CI skips the macOS-specific renderer identity gate; inspect
actual renderer/controller fields and logs until that gate is hardened. App startup
can open public market-data connections: this is not a runtime-offline test.

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

**Evidence boundary:** `smoke_desktop.py --artifact <dmg>` only adds the artifact hash;
it does not mount or select that DMG's app. Final artifact validation must mount the
exact DMG read-only and pass the executable inside that mount using `--executable`,
plus `--artifact` and an isolated data directory. Preserve hashes and source commit,
then detach the mount. Follow the release workflow's mounted-artifact procedure;
the recorded Mac .app smoke + DMG preflight is not proof of clean-machine installation.

---

## 6. First Launch Notes

- The app is **not notarized**. On first launch users must **right-click the app → Open** and
  confirm the Gatekeeper prompt; double-clicking shows "cannot be opened".
- Launch duration depends on host, signing/quarantine and OS state; no measured universal
  launch-time guarantee is made. Administrator/Gatekeeper approval must be performed by
  the user in the OS UI, never bypassed by disabling system protections.

---

## 7. Data Directory

User data lives outside the install location so upgrades never destroy it:

```
~/Library/Application Support/Kuantra Terminal
```

It holds the SQLite/DuckDB databases, logs, plugin-directory metadata and the WebView `localStorage`
store. Override it with the `KUANTRA_DATA_DIR` environment variable. A dev checkout (non-frozen)
keeps using `backend/data` instead.

The plugin directory is not proof of an enabled download/runtime capability; remote
plugin execution remains disabled. For this Mac move there is no real user data:
start clean and let first startup create SQLite. Do not copy Windows databases,
logs, models, plugins, `.env`, credentials or migration ZIPs. Do not reset an existing
directory merely because a clean start is intended.

---

## 8. Integrations Gateway (port 8765)

The optional integrations gateway can bind a loopback listener (default port 8765)
for programs outside the app, subject to its enablement/authentication contract:

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

## 10. Windows-to-macOS data migration

Only after real user data exists, use the credential-safe, hash-verified migration tool before restoring a real
user directory on the Mac. It carries the canonical SQLite ledger and Parquet
cold storage, excludes DuckDB so the projection can be rebuilt locally, and
requires exchange credentials to be re-entered into macOS Keychain.

See [`docs/MACOS_MIGRATION.md`](MACOS_MIGRATION.md) for the create, verify and
restore commands and the migration acceptance checklist.
