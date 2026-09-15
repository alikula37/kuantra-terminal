#!/usr/bin/env bash
# Build dist/Kuantra-Terminal-<ver>-x86_64.AppImage from dist/kuantra-terminal/ using appimagetool.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$(python3 -c "import sys; sys.path.insert(0,'$ROOT/backend'); from app.version import __version__; print(__version__)")"
SRC="$ROOT/dist/kuantra-terminal"
APPDIR="$ROOT/dist/AppDir"
OUT="$ROOT/dist/Kuantra-Terminal-${VERSION}-x86_64.AppImage"
TOOL="${APPIMAGETOOL:-$ROOT/build/appimagetool}"
[ -x "$SRC/kuantra-terminal" ] || { echo "missing $SRC (run scripts/build_desktop.py first)"; exit 1; }
if [ ! -x "$TOOL" ]; then
  echo "appimagetool not found at $TOOL." >&2
  echo "Provide a verified tool via APPIMAGETOOL=/path/to/appimagetool; this script never downloads unverified binaries." >&2
  exit 1
fi
rm -rf "$APPDIR" "$OUT"
mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/share/applications" "$APPDIR/usr/share/icons/hicolor/256x256/apps"
cp -r "$SRC"/. "$APPDIR/usr/bin/"
cp "$ROOT/packaging/linux/AppRun" "$APPDIR/AppRun"; chmod +x "$APPDIR/AppRun"
cp "$ROOT/packaging/linux/kuantra-terminal.desktop" "$APPDIR/kuantra-terminal.desktop"
cp "$ROOT/packaging/linux/kuantra-terminal.desktop" "$APPDIR/usr/share/applications/"
cp "$ROOT/packaging/icons/128x128@2x.png" "$APPDIR/kuantra-terminal.png"
cp "$ROOT/packaging/icons/128x128@2x.png" "$APPDIR/usr/share/icons/hicolor/256x256/apps/kuantra-terminal.png"
APPIMAGE_EXTRACT_AND_RUN=1 ARCH=x86_64 "$TOOL" --no-appstream "$APPDIR" "$OUT"
rm -rf "$APPDIR"
echo "[+] $OUT ($(du -h "$OUT" | cut -f1))"
