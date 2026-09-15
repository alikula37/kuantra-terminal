<!-- doc-role: current-work-package -->
# P1-WP34 — Server-verified instrument catalog

```yaml
work_package: P1-WP34
status: InProgress
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

Per the owner standing instruction, the verified change was committed and the Mac's
installed application was rebuilt from the clean commit (details appended after the
run: source commit, CI report hash, DMG hash, smoke report, installed executable).
