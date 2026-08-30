# Linux Build & Packaging Runbook

This guide covers building the Nuitka C++ sidecar and packaging .AppImage and .deb distributions on Linux.

---

## 1. System Dependencies (Debian / Ubuntu / Pop!_OS)

```bash
sudo apt update
sudo apt install -y build-essential curl wget libssl-dev libgtk-3-dev libayatana-appindicator3-dev librsvg2-dev patchelf
```

---

## 2. Compile Nuitka C++ Sidecar

```bash
cd backend
python3 -m pip install -r requirements.txt
python3 build_sidecar.py

# Target binary generated:
# src-tauri/binaries/kuantra-backend-x86_64-unknown-linux-gnu
```

---

## 3. Build Frontend & Package AppImage / DEB

```bash
# 1. Compile frontend
cd frontend
npm install
npm run build
cd ..

# 2. Package Tauri Linux Bundles
npm run tauri build
```

Generated bundle artifacts:
- `src-tauri/target/release/bundle/appimage/kuantra-terminal_2.0.0_amd64.AppImage`
- `src-tauri/target/release/bundle/deb/kuantra-terminal_2.0.0_amd64.deb`