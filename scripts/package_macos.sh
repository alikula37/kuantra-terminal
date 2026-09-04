#!/usr/bin/env bash
# Ad-hoc sign the .app and wrap it in a DMG: dist/Kuantra-Terminal-<ver>-<arch>.dmg
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$(python3 -c "import sys; sys.path.insert(0,'$ROOT/backend'); from app.version import __version__; print(__version__)")"
ARCH="$(uname -m)"; [ "$ARCH" = "arm64" ] && ARCH="aarch64"
APP="$ROOT/dist/Kuantra Terminal.app"
OUT="$ROOT/dist/Kuantra-Terminal-${VERSION}-${ARCH}.dmg"
STAGE="$ROOT/dist/dmg-stage"
[ -d "$APP" ] || { echo "missing $APP (run scripts/build_desktop.py first)"; exit 1; }
codesign --force --deep --sign - "$APP"
rm -rf "$STAGE" "$OUT"; mkdir -p "$STAGE"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
hdiutil create -volname "Kuantra Terminal" -srcfolder "$STAGE" -ov -format UDZO "$OUT"
rm -rf "$STAGE"
echo "[+] $OUT ($(du -h "$OUT" | cut -f1))"
