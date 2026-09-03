#!/usr/bin/env bash
# Build dist/Kuantra-Terminal-<ver>-Setup.exe with NSIS. Requires makensis on PATH (choco install nsis).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$(python -c "import sys; sys.path.insert(0,'$ROOT/backend'); from app.version import __version__; print(__version__)")"
SRC="$ROOT/dist/Kuantra Terminal"
OUT="$ROOT/dist/Kuantra-Terminal-${VERSION}-Setup.exe"
[ -f "$SRC/Kuantra Terminal.exe" ] || { echo "missing $SRC (run scripts/build_desktop.py first)"; exit 1; }
w() { if command -v cygpath >/dev/null 2>&1; then cygpath -w "$1"; else echo "$1"; fi; }
makensis -V2 "-DVERSION=${VERSION}" "-DSRCDIR=$(w "$SRC")" "-DOUTFILE=$(w "$OUT")" "-DICON=$(w "$ROOT/packaging/icons/icon.ico")" "$(w "$ROOT/packaging/windows/installer.nsi")"
echo "[+] $OUT"
