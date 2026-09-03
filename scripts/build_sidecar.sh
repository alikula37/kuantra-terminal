#!/usr/bin/env bash
# Builds the Python backend into the Tauri sidecar binary with PyInstaller.
#
# Usage: scripts/build_sidecar.sh [target-triple]
#   target-triple defaults to the host (aarch64-apple-darwin, x86_64-pc-windows-msvc, ...)
#   PYTHON env var selects the interpreter (default: python). It must have
#   backend/requirements.txt and pyinstaller installed.
#
# This is the single source of truth for the sidecar recipe. CI calls it too.
#
# macOS builds a --onedir tree (src-tauri/binaries/macos/kuantra-backend/) that
# tauri.macos.conf.json ships under Contents/Resources/backend. A --onefile
# binary re-extracts ~70MB on every launch and macOS re-scans each dylib, which
# costs 35-50s per start; --onedir pays that only once per install (~1s after).
# Windows/Linux keep --onefile and the externalBin sidecar mechanism.
# numpy / pandas / scipy / duckdb are hard runtime dependencies of the backend
# (app/quant/*, app/db/*, app/ai/*): never add them to the exclude list.
# unittest/doctest must stay too: scipy imports numpy.testing which needs them.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-python}"

detect_triple() {
  local os arch
  os="$(uname -s)"
  arch="$(uname -m)"
  case "$arch" in
    arm64|aarch64) arch="aarch64" ;;
    x86_64|amd64)  arch="x86_64" ;;
  esac
  case "$os" in
    Darwin)               echo "${arch}-apple-darwin" ;;
    Linux)                echo "${arch}-unknown-linux-gnu" ;;
    MINGW*|MSYS*|CYGWIN*) echo "${arch}-pc-windows-msvc" ;;
    *) echo "unsupported OS: $os" >&2; exit 1 ;;
  esac
}

TRIPLE="${1:-$(detect_triple)}"
NAME="kuantra-backend-${TRIPLE}"
case "$TRIPLE" in *windows*) NAME="${NAME}.exe" ;; esac

EXCLUDES=(
  torch bleak web3 quickfix PIL matplotlib tkinter
  pytest test alembic.testing
  setuptools pkg_resources ccxt.pro aiohttp.test_utils
)
case "$TRIPLE" in *windows*) ;; *) EXCLUDES+=(winloop) ;; esac

ARGS=()
for m in "${EXCLUDES[@]}"; do ARGS+=(--exclude-module "$m"); done
for m in app starlette fastapi uvicorn pydantic cryptography; do ARGS+=(--collect-submodules "$m"); done

mkdir -p "$ROOT/src-tauri/binaries"
echo "[*] Building sidecar for $TRIPLE with $("$PYTHON" --version 2>&1)"

case "$TRIPLE" in
  *apple-darwin)
    DIST="$ROOT/src-tauri/binaries/macos"
    rm -rf "$DIST/kuantra-backend"
    "$PYTHON" -m PyInstaller \
      --onedir --clean \
      --name "kuantra-backend" \
      --distpath "$DIST" \
      --workpath "$ROOT/backend/build" \
      --specpath "$ROOT/backend" \
      "${ARGS[@]}" \
      "$ROOT/backend/main.py"
    OUT="$DIST/kuantra-backend/kuantra-backend"
    chmod +x "$OUT"
    echo "[+] Backend tree ready: $DIST/kuantra-backend ($(du -sh "$DIST/kuantra-backend" | cut -f1))"
    ;;
  *)
    "$PYTHON" -m PyInstaller \
      --onefile --clean \
      --name "$NAME" \
      --distpath "$ROOT/src-tauri/binaries" \
      --workpath "$ROOT/backend/build" \
      --specpath "$ROOT/backend" \
      "${ARGS[@]}" \
      "$ROOT/backend/main.py"
    OUT="$ROOT/src-tauri/binaries/$NAME"
    chmod +x "$OUT" 2>/dev/null || true
    echo "[+] Sidecar ready: $OUT ($(du -h "$OUT" | cut -f1))"
    ;;
esac
