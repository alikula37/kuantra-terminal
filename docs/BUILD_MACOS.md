# macOS Build & Notarization Runbook

This guide covers compiling the universal/ARM64 C++ sidecar and generating Apple Developer notarized DMG bundles for macOS.

---

## 1. Prerequisites

- **macOS Sonoma / Sequoia (Apple Silicon or Intel)**
- **Xcode & Command Line Tools**: `xcode-select --install`
- **Python 3.11+**
- **Rust & Cargo** (1.77+ for Tauri 2; run `rustup update stable`)
- **Node.js 18+ & npm**

---

## 2. Compile Python Backend Sidecar for macOS

The backend is frozen with PyInstaller by `scripts/build_sidecar.sh`, the same
script CI uses. It needs a Python (3.11 recommended, **arm64** build) with
`backend/requirements.txt` and `pyinstaller` installed.

```bash
python3.11 -m venv .venv-sidecar
.venv-sidecar/bin/pip install -r backend/requirements.txt pyinstaller cryptography alembic psutil httpx pyyaml
PYTHON=.venv-sidecar/bin/python bash scripts/build_sidecar.sh

# Output tree (shipped into Contents/Resources/backend by tauri.macos.conf.json):
# src-tauri/binaries/macos/kuantra-backend/
```

Notes:

- On macOS the backend is a `--onedir` tree, not a single-file sidecar. A
  `--onefile` binary re-extracts ~70MB and is re-scanned by macOS on every
  launch (35-50s per start); the onedir layout only pays that once per install.
  The very first launch after installing a DMG can therefore take up to ~40s;
  every launch after that takes 1-2s.
- `numpy`, `pandas`, `scipy`, `duckdb`, `unittest` and `doctest` are hard
  runtime dependencies of the backend. Never add them to the exclude list.
- The backend binds an ephemeral port (`--port 0`). The frontend resolves it
  through the `get_backend_port` Tauri command (`frontend/src/lib/backend.ts`);
  never hardcode `127.0.0.1:8000` in frontend code.

---

## 3. Build Frontend & Package Signed DMG

```bash
# 1. Compile React production bundle
cd frontend
npm install
npm run build
cd ..

# 2. Build Tauri DMG
npm run tauri build
```

Generated bundle artifact:
- `src-tauri/target/release/bundle/dmg/Kuantra Terminal_2.0.0_aarch64.dmg`