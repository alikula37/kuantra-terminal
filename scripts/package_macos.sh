#!/usr/bin/env bash
# Sign the .app (ad-hoc by default, explicit Developer ID when requested) and wrap it in a DMG.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$(python3 -c "import sys; sys.path.insert(0,'$ROOT/backend'); from app.version import __version__; print(__version__)")"
ARCH="$(uname -m)"; [ "$ARCH" = "arm64" ] && ARCH="aarch64"
APP="$ROOT/dist/Kuantra Terminal.app"
OUT="$ROOT/dist/Kuantra-Terminal-${VERSION}-${ARCH}.dmg"
STAGE="$ROOT/dist/dmg-stage"
[ -d "$APP" ] || { echo "missing $APP (run scripts/build_desktop.py first)"; exit 1; }

SIGNING_MODE="${KUANTRA_MACOS_SIGNING_MODE:-adhoc}"
case "$SIGNING_MODE" in
  adhoc)
    codesign --force --deep --sign - "$APP"
    ;;
  developer-id)
    SIGNING_IDENTITY="${KUANTRA_MACOS_SIGNING_IDENTITY:-}"
    [ -n "$SIGNING_IDENTITY" ] || {
      echo "KUANTRA_MACOS_SIGNING_IDENTITY is required for developer-id signing" >&2
      exit 1
    }
    case "$SIGNING_IDENTITY" in
      "Developer ID Application:"*) ;;
      *)
        echo "KUANTRA_MACOS_SIGNING_IDENTITY must name a Developer ID Application certificate" >&2
        exit 1
        ;;
    esac
    SIGN_ARGS=(--force --deep --options runtime --timestamp --sign "$SIGNING_IDENTITY")
    ENTITLEMENTS="${KUANTRA_MACOS_ENTITLEMENTS:-}"
    if [ -n "$ENTITLEMENTS" ]; then
      [ -f "$ENTITLEMENTS" ] || { echo "missing macOS entitlements file: $ENTITLEMENTS" >&2; exit 1; }
      SIGN_ARGS+=(--entitlements "$ENTITLEMENTS")
    fi
    codesign "${SIGN_ARGS[@]}" "$APP"
    ;;
  *)
    echo "unsupported KUANTRA_MACOS_SIGNING_MODE: $SIGNING_MODE (use adhoc or developer-id)" >&2
    exit 1
    ;;
esac

# Packaging must never hide an invalid signature.  N05 separately verifies the
# exact mounted DMG, Gatekeeper and notarization ticket.
codesign --verify --deep --strict --verbose=0 "$APP"
rm -rf "$STAGE" "$OUT"; mkdir -p "$STAGE"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
hdiutil create -volname "Kuantra Terminal" -srcfolder "$STAGE" -ov -format UDZO "$OUT"
rm -rf "$STAGE"
echo "[+] $OUT ($(du -h "$OUT" | cut -f1), signing=$SIGNING_MODE)"
