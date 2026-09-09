#!/usr/bin/env bash
# Owner-controlled macOS notarization wrapper for one exact, Developer ID DMG.
# It is deliberately opt-in: no submission occurs without the explicit --submit flag.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DMG=""
SMOKE_REPORT=""
N05_REPORT=""
TIMEOUT="120"

usage() {
  cat >&2 <<'EOF'
Usage:
  KUANTRA_MACOS_NOTARY_PROFILE=<keychain-profile> \
    bash scripts/notarize_macos.sh --submit \
      --dmg dist/Kuantra-Terminal-<version>-aarch64.dmg \
      --smoke-report dist/final-smoke-macos.json \
      --output dist/n05-macos-distribution.json

The --submit flag is mandatory. The keychain profile must already exist on the
owner-controlled macOS host; this wrapper never creates, reads or prints a
password, private key, API key or certificate secret.
EOF
}

fail() {
  echo "[notarize] $*" >&2
  exit 2
}

require_value() {
  [ "$#" -ge 2 ] || fail "missing value for $1"
  [ -n "$2" ] || fail "empty value for $1"
}

resolve_file() {
  local candidate="$1"
  case "$candidate" in
    /*) ;;
    *) candidate="$ROOT/$candidate" ;;
  esac
  [ -f "$candidate" ] || fail "missing file: $candidate"
  local directory
  directory="$(cd "$(dirname "$candidate")" && pwd -P)"
  printf '%s/%s\n' "$directory" "$(basename "$candidate")"
}

SUBMIT="false"
while [ "$#" -gt 0 ]; do
  case "$1" in
    --submit)
      SUBMIT="true"
      shift
      ;;
    --dmg)
      require_value "$1" "${2:-}"
      DMG="$2"
      shift 2
      ;;
    --smoke-report)
      require_value "$1" "${2:-}"
      SMOKE_REPORT="$2"
      shift 2
      ;;
    --output)
      require_value "$1" "${2:-}"
      N05_REPORT="$2"
      shift 2
      ;;
    --timeout)
      require_value "$1" "${2:-}"
      TIMEOUT="$2"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      usage
      fail "unknown argument: $1"
      ;;
  esac
done

[ "$SUBMIT" = "true" ] || { usage; fail "explicit --submit is required"; }
[ "$(uname -s)" = "Darwin" ] || fail "notarization requires a macOS host"
[ -n "$DMG" ] || { usage; fail "--dmg is required"; }
[ -n "$SMOKE_REPORT" ] || { usage; fail "--smoke-report is required"; }
[ -n "$N05_REPORT" ] || { usage; fail "--output is required"; }
case "$DMG" in
  *.dmg) ;;
  *) fail "--dmg must point to a .dmg file" ;;
esac

DMG="$(resolve_file "$DMG")"
case "$SMOKE_REPORT" in
  /*) ;;
  *) SMOKE_REPORT="$ROOT/$SMOKE_REPORT" ;;
esac
case "$N05_REPORT" in
  /*) ;;
  *) N05_REPORT="$ROOT/$N05_REPORT" ;;
esac

PROFILE="${KUANTRA_MACOS_NOTARY_PROFILE:-}"
[ -n "$PROFILE" ] || fail "KUANTRA_MACOS_NOTARY_PROFILE is required"
command -v xcrun >/dev/null 2>&1 || fail "xcrun is required"
xcrun --find notarytool >/dev/null 2>&1 || fail "xcrun notarytool is unavailable"
xcrun --find stapler >/dev/null 2>&1 || fail "xcrun stapler is unavailable"

if [ -x "$ROOT/.venv/bin/python" ]; then
  PYTHON_BIN="$ROOT/.venv/bin/python"
elif command -v python3.11 >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python3.11)"
else
  fail "Python 3.11 is required for the final smoke/preflight"
fi

TEMP_DATA="$(mktemp -d "${TMPDIR:-/tmp}/kuantra-notarize-data.XXXXXX")"
cleanup() {
  rm -rf -- "$TEMP_DATA"
}
trap cleanup EXIT

echo "[notarize] submitting exact DMG with the configured Keychain profile"
# Discard tool output so signing/notary command output cannot become an evidence
# artifact. The exit code is the only submission signal consumed here.
if ! xcrun notarytool submit "$DMG" --keychain-profile "$PROFILE" --wait >/dev/null 2>&1; then
  fail "notarytool submission failed or was rejected"
fi

echo "[notarize] stapling ticket to exact DMG"
if ! xcrun stapler staple "$DMG" >/dev/null 2>&1; then
  fail "stapling notarization ticket failed"
fi

# Stapling changes the DMG bytes. Re-run the mounted-DMG smoke after stapling so
# the smoke artifact hash and N05 evidence refer to the final exact DMG.
echo "[notarize] re-running exact mounted-DMG smoke after stapling"
env KUANTRA_MARKET_DATA_ENABLED=false KUANTRA_GATEWAY_ENABLED=false \
  "$PYTHON_BIN" "$ROOT/scripts/smoke_macos_dmg.py" \
  --dmg "$DMG" --data-dir "$TEMP_DATA" --report "$SMOKE_REPORT" --timeout "$TIMEOUT"

echo "[notarize] running N05 read-only final-artifact preflight"
set +e
"$PYTHON_BIN" "$ROOT/scripts/run_n05_macos_distribution_preflight.py" \
  --dmg "$DMG" --smoke-report "$SMOKE_REPORT" --output "$N05_REPORT"
STATUS="$?"
set -e
exit "$STATUS"
