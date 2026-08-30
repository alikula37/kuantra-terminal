# Windows Build & Packaging Runbook

This guide covers building the standalone Nuitka C++ sidecar and generating the signed Windows installer (.exe / .msi) for Kuantra Terminal.

---

## 1. Prerequisites

- **Windows 10 / 11 (64-bit)**
- **Visual Studio 2022** with "Desktop development with C++" workload installed (MSVC toolchain).
- **Python 3.11+ (x64)**
- **Rust & Cargo**: `rustup default stable-x86_64-pc-windows-msvc`
- **Node.js 18+ & npm**
- **NSIS (Nullsoft Scriptable Install System)** or **WiX Toolset**

---

## 2. Compile Nuitka C++ Sidecar

The FastAPI backend is compiled into a standalone, single-binary C++ executable:

```powershell
# Navigate to backend directory
cd backend

# Run automated cross-platform build script
python build_sidecar.py

# Verify generated binary target:
# src-tauri/binaries/kuantra-backend-x86_64-pc-windows-msvc.exe
```

Nuitka compilation flags applied:
- `--standalone`
- `--onefile`
- `--plugin-enable=fastapi`
- `--plugin-enable=pydantic`
- `--include-package=app`
- `--include-package=duckdb`
- `--include-package=sqlite3`

---

## 3. Build Frontend & Tauri Bundle

```powershell
# 1. Compile frontend production bundle
cd frontend
npm install
npm run build
cd ..

# 2. Package Tauri Desktop Application
npm run tauri build
```

Generated installer artifacts:
- `src-tauri/target/release/bundle/nsis/Kuantra Terminal_2.0.0_x64-setup.exe`
- `src-tauri/target/release/bundle/msi/Kuantra Terminal_2.0.0_x64_en-US.msi`