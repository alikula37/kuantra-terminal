<!-- doc-role: current-work-package -->
# P1-WP33 — Bounded market-chart history

```yaml
work_package: P1-WP33
status: InProgress
branch: main
baseline: f640e4b
```

Owner report (2026-09-15): Market Charts show only a very short history and cannot
load older data. The chart also froze on the first cached window because the
8-second refresh treated a full cache as fresh forever.

## Ordered acceptance

- [x] Cache freshness: a full cached window is reused only while it is at most two
  bar durations old; otherwise the provider is asked for newer bars. Exact
  start+end range queries keep their cache shortcut.
- [x] Crypto history pagination: an explicit `start_time` request walks Binance
  klines backwards in bounded pages (max 10 pages, 1000 bars per page), stops on
  a short page or when the requested start is reached, and merges/deduplicates
  by timestamp. Bybit remains the single-page fallback.
- [x] Macro/equity deep history: an explicit `start_time` switches the Yahoo
  chart request to `period1`/`period2`; intraday requests are clamped to the
  provider's documented window (1m=7d, 5m–30m=60d, 1h=730d) instead of failing
  or inventing bars. Daily/weekly/monthly keep the requested lookback.
- [x] Chart UI: initial request is 1000 bars, a "load older data" control fetches
  one bounded chunk (`start_time`/`end_time`), prepends it, keeps the visible
  window stable, disables itself when the provider is exhausted, and surfaces a
  clear notice on exhaustion or failure. The live refresh now merges with the
  loaded older history instead of wiping it.
- [x] EN/TR/DE strings for the new chart controls.
- [x] Backend tests for pagination, freshness, and Yahoo period ranges; frontend
  tests for the merge/window helpers; full suites and canonical local CI.

## Scope boundaries

- Free public sources only (Binance, Bybit, Yahoo, Stooq, Biquote); no paid data,
  credentials or new providers.
- Provider limits are honored, never bypassed: short pages, missing ranges and
  provider errors stay visible instead of being filled with synthetic bars.
- No historical replay/backfill engine and no user-data migration.

## Evidence

- `backend/tests/test_market_candle_history.py` **6 passed**: backward pagination
  (two pages, `endTime = oldest-1`, short-page stop), Yahoo `period1/period2`
  with 5m clamping and 1d lookback preservation, stale cache triggers a fetch,
  fresh cache stays cache-only, and an exact history query fills missing bars.
- Existing `test_public_data_fetcher.py` cache-hit test now uses current-bar
  timestamps to encode the freshness contract (the old fixed-2023 window is the
  stale case covered by the new test).
- Full backend **947 passed / 2 warnings**; frontend **38 files / 204 tests**
  (`lib/__tests__/candles.test.ts` covers merge, dedupe, window math and
  full-page detection); i18n **984/984/984**; `npx tsc --noEmit` clean.
