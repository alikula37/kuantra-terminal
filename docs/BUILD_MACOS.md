# macOS Build & Notarization Runbook

This guide covers compiling the universal/ARM64 C++ sidecar and generating Apple Developer notarized DMG bundles for macOS.

---

## 1. Prerequisites

- **macOS Sonoma / Sequoia (Apple Silicon or Intel)**
- **Xcode & Command Line Tools**: `xcode-select --install`
- **Python 3.11+**
- **Rust & Cargo**: `rustup default stable-aarch64-apple-darwin` or `x86_64-apple-darwin`
- **Node.js 18+ & npm**

---

## 2. Compile Nuitka C++ Sidecar for macOS

```bash
# Navigate to backend directory
cd backend

# Execute cross-platform build
python3 build_sidecar.py

# Target binary generated:
# src-tauri/binaries/kuantra-backend-aarch64-apple-darwin (or x86_64-apple-darwin)
```

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