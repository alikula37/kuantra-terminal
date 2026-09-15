<!-- doc-role: reference -->
# P1-WP34 — Server-verified instrument catalog

```yaml
work_package: P1-WP34
status: Complete
branch: main
baseline: 14d77a8
```

Owner report (2026-09-15): the open ETHUSDT position still shows "contract size not
verified — monetary P/L is not calculated" although the backend can ask the exchange
directly. The owner asked why the server does not check the instrument itself.

Root cause: money math only accepted an explicit user declaration (`qty_unit=BASE`).
A client-supplied `price_source`/`price_source_symbol` label is never proof (round-4
decision), and no server-side verification path existed, so a directly verified spot
instrument (1 unit = 1 base unit) could not enable monetary results.

## Ordered acceptance

- [x] Server-side catalog: the backend queries the free provider metadata itself
  (Binance spot exchange info, Bybit spot instruments fallback) and records the
  verification in a local `verified_instruments` table in the same SQLite database
  as trades (additive schema, no user-data migration).
- [x] Honest freshness: a cache row is reusable for 24 hours; after 7 days without
  provider confirmation it counts as unverified. Provider errors and unknown
  symbols degrade silently to UNVERIFIED — never a guessed unit.
- [x] Verification sources: `EXPLICIT_QTY_UNIT` (owner declaration) and
  `PROVIDER_CATALOG` (server-verified spot instrument) enable base-unit money
  math; `NONE` remains unknown. Client labels remain non-proof.
- [x] Monetary gates read the catalog: trade creation, open-position summary
  (`attach_position_summary`), portfolio open risk/volume, local-tracking plan
  acceptance, and the trade-edit close-result recomputation all consult the
  server catalog; services bind the catalog to their own database path.
- [x] API: `GET /api/v1/market-data/instrument?symbol=` returns the verification
  status, provider, base/quote asset, and freshness for one symbol.
- [x] Frontend: New Trade and Edit verify the confirmed symbol once and hide the
  manual unit checkbox when the server confirms it; the open-positions table asks
  once per unverified symbol and enables monetary K/Z without a manual
  declaration; EN/TR/DE strings for the provider-verified state.
- [x] Tests: focused catalog tests, full backend/frontend suites, i18n check and
  canonical local CI.

## Scope boundaries

- Free public sources only (Binance, Bybit spot metadata); no paid data, no new
  credentials and no per-user API keys.
- Only a directly verified spot instrument (1 unit = 1 base unit) is proof of base
  units; no futures, inverse contracts or contract-size assumptions are inferred.
- Verification never overwrites user data and never rewrites existing trades; it
  only changes how a trade can be measured.

## Evidence

- `backend/tests/test_instrument_catalog.py` **9 passed**: Binance spot lookup +
  cache reuse, Bybit fallback, unknown symbol stays unverified, freshness (a
  25-hour-old row is refreshed from the provider, an 8-day-old row without
  provider confirmation stops counting while a 6-day-old row is retained),
  `position_summary` money math only with `server_verified`, API-verified symbol
  computes P/L without a declaration, `GET /market-data/instrument` payload, and
  local-tracking plan acceptance with a server-verified symbol.
- `backend/tests/test_instrument_catalog.py::test_local_tracking_accepts_server_verified_symbol`
  first failed because the tracking service used the global catalog against a
  different database; the services now bind the catalog to their own driver
  database path (fix recorded here).
- Full backend **957 passed / 2 warnings**; frontend **39 files / 209 tests**
  (positionMath `PROVIDER_CATALOG`, New Trade hides the declaration, open
  positions enable money math after verification); i18n **990/990/990**;
  `npx tsc --noEmit` clean.

### Clean build and installed-app update

Per the owner standing instruction, the verified change was committed (`2d0106e`,
pushed) and the Mac's installed application was rebuilt from the clean commit:

- Canonical arm64 local CI on `2d0106e`: **MERGE READY**, provenance **COMPLETE**,
  clean tree; report `dist/p1-wp34-clean-local-ci.json` SHA-256
  `8d380b2cb228da2797bf891b30e018a303cc6e32a0bc0baf1b16ae44222ebb3e`, executable
  `9d492a41311c1f819d461c6f8a67c3b3068d331627f28d6550e124ba786a034d`.
- arm64 DMG `dist/Kuantra-Terminal-1.1.0-arm64-wp34.dmg`: `hdiutil verify` VALID,
  SHA-256 `204887dc4ae330df6363deaf2637dbefe285a7961ddc8f6a9dc6cc98f823635a`;
  exact read-only mounted-DMG smoke **PASS** (`dist/p1-wp34-dmg-smoke.json`; the first
  attempt ran under system Python without PyInstaller and correctly refused to report
  a COMPLETE provenance — rerun under the canonical uv environment passed).
- `/Applications/Kuantra Terminal.app` replaced after a graceful quit; installed
  executable matches the CI build, `codesign --verify --deep --strict` passes,
  launched PID `49585`, runtime `{"status":"online","gateway":true,"version":"1.1.0"}`.
  User data was preserved.

### Live verification of the reported case

- The installed application's own UI verified the owner's open ETHUSDT position at
  startup: the user database now holds `ETHUSDT | binance_spot | ETH | USDT` in
  `verified_instruments` (2026-09-15T11:53:11Z).
- An isolated check on a copy of the owner database (same build) returned
  `binance_spot ETH/USDT` for `GET /market-data/instrument?symbol=ETHUSDT`; trade
  `TRD-1789460532666` (stored `qty_unit=UNKNOWN`) now reports verification
  `PROVIDER_CATALOG`, source `PROVIDER_CATALOG`, monetary calculation **READY** with
  notional `3725385.00` — the reported "contract size not verified" state is resolved
  without rewriting the trade.
