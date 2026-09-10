#!/usr/bin/env bash
# Sign the .app (ad-hoc by default, explicit Developer ID when requested) and wrap it in a DMG.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
VERSION="$($PYTHON_BIN -c "import sys; sys.path.insert(0,'$ROOT/backend'); from app.version import __version__; print(__version__)")"

usage() {
  cat >&2 <<'USAGE'
Usage: scripts/package_macos.sh [--architecture arm64|x86_64] [--app PATH] [--output PATH]
USAGE
}

canonical_architecture() {
  case "${1:-}" in
    arm64|aarch64) printf '%s\n' arm64 ;;
    x86_64|amd64) printf '%s\n' x86_64 ;;
    *) return 1 ;;
  esac
}

EXPECTED_ARCH=""
APP="$ROOT/dist/Kuantra Terminal.app"
OUT=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --architecture)
      [ "$#" -ge 2 ] || { usage; exit 2; }
      EXPECTED_ARCH="$(canonical_architecture "$2")" || {
        echo "unsupported architecture: $2" >&2
        exit 2
      }
      shift 2
      ;;
    --app)
      [ "$#" -ge 2 ] || { usage; exit 2; }
      APP="$2"
      shift 2
      ;;
    --output)
      [ "$#" -ge 2 ] || { usage; exit 2; }
      OUT="$2"
      shift 2
      ;;
    -h|--help)
      usage >&2
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      usage
      exit 2
      ;;
  esac
done

HOST_ARCH="$(canonical_architecture "$(uname -m)")" || {
  echo "unsupported macOS host architecture: $(uname -m)" >&2
  exit 1
}
EXPECTED_ARCH="${EXPECTED_ARCH:-$HOST_ARCH}"
if [ "$EXPECTED_ARCH" = "x86_64" ]; then
  # An Apple Silicon process launched through Rosetta reports x86_64 via
  # uname -m.  Do not let that translated process produce Intel evidence.
  TRANSLATED="$(sysctl -in sysctl.proc_translated 2>/dev/null || true)"
  [ "$TRANSLATED" = "0" ] || {
    echo "x86_64 packaging requires a native Intel host; Rosetta status is ${TRANSLATED:-unknown}" >&2
    exit 1
  }
fi
APP="$(cd "$(dirname "$APP")" && pwd)/$(basename "$APP")"
OUT="${OUT:-$ROOT/dist/Kuantra-Terminal-${VERSION}-${EXPECTED_ARCH}.dmg}"
OUT="$(cd "$(dirname "$OUT")" && pwd)/$(basename "$OUT")"
EXECUTABLE="$APP/Contents/MacOS/Kuantra Terminal"
[ -d "$APP" ] || { echo "missing $APP (run scripts/build_desktop.py first)"; exit 1; }
[ -f "$EXECUTABLE" ] || { echo "missing app executable: $EXECUTABLE" >&2; exit 1; }

ARCHES="$(lipo -archs "$EXECUTABLE")" || {
  echo "could not inspect app executable architecture: $EXECUTABLE" >&2
  exit 1
}
ARCH_COUNT="$(wc -w <<<"$ARCHES" | tr -d ' ')"
[ "$ARCH_COUNT" = "1" ] || {
  echo "Universal2/fat app executables are not supported: $ARCHES" >&2
  exit 1
}
ACTUAL_ARCH="$(canonical_architecture "$ARCHES")" || {
  echo "unsupported app executable architecture: $ARCHES" >&2
  exit 1
}
[ "$ACTUAL_ARCH" = "$EXPECTED_ARCH" ] || {
  echo "app executable architecture mismatch: expected $EXPECTED_ARCH, got $ACTUAL_ARCH" >&2
  exit 1
}

STAGE="$(mktemp -d "$ROOT/dist/dmg-stage.XXXXXX")"
cleanup() {
  rm -rf "$STAGE"
}
trap cleanup EXIT

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
rm -f "$OUT"; mkdir -p "$(dirname "$OUT")"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
hdiutil create -volname "Kuantra Terminal" -srcfolder "$STAGE" -ov -format UDZO "$OUT"
echo "[+] $OUT ($(du -h "$OUT" | cut -f1), architecture=$ACTUAL_ARCH, signing=$SIGNING_MODE)"
