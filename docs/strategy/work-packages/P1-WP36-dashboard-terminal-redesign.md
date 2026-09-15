<!-- doc-role: current-work-package -->
# P1-WP36 — Dashboard terminal redesign

```yaml
work_package: P1-WP36
status: InProgress
branch: main
baseline: 3fc5047
```

Owner report (2026-09-15): "gösterge panelindeki dashboard hoşuma gitmiyor. çok basit ve
anlaması zor görünüyor. daha efektif bir şey olmalı." Follow-up answers: the pain is
plain/empty visuals, an unclear information hierarchy and missing critical data; the top
of the page must answer "live cash + open P/L + risk" at one glance; the style should be a
professional trading terminal (dense grid, color coding, compact typography).

## Ordered acceptance

- [x] Hero row (one glance, five blocks): LIVE equity with the realized/open
  breakdown, price freshness and an equity sparkline; OPEN P&L (unrealized $ and %
  with live/unpriced state); OPEN RISK (R and $, or the unverified-unit notice);
  EXPOSURE (notional + margin with recorded leverage and coverage notes); TODAY
  (realized P/L with W/L and unknown count).
- [x] Compact rail (always visible): win rate with closed-trade count, profit
  factor with gross profit/loss (or "no losses yet"), average R (or "no R data"),
  max drawdown with peak-to-trough dollars, active positions with verification
  state, unknown results vs closed count.
- [x] Backend exposure metrics: `open_notional_usd`, `open_margin_usd` (only
  positions with a recorded leverage), `open_margin_positions`,
  `open_exposure_basis` (COMPLETE/PARTIAL/NOT_AVAILABLE) and
  `open_exposure_unpriced`; unverified units never enter the exposure sum.
- [x] Density and hierarchy: tighter page padding and gaps, left color accents per
  hero block, compact money formatting ($1.25M / $125.0K), formula tooltips on
  profit factor, average R, drawdown, unrealized, risk, exposure and margin.
- [x] Localized dashboard title (the hardcoded "LITE PORTFÖY & RİSK DASHBOARD" /
  "BIG PICTURE QUANT DASHBOARD" strings are now EN/TR/DE keys) plus a "son veri"
  timestamp from the summary payload.
- [x] Rebalanced layout: the 90-day heatmap moves into the right column under the
  asset breakdown, removing a full-width section and the extra scrolling.
- [x] Tests: backend exposure math (verified units only, leverage-covered margin,
  partial/not-available bases) and DOM tests for the hero/rail states, sparkline
  and localized title; all previous truth states (unknown R, unverified risk,
  infinite PF, zero drawdown, live/partial/fallback equity) keep their tests.

## Scope boundaries

- No new endpoints beyond the existing summary fields; no fabricated values — every
  new cell reuses the truth bases already established in P1-WP33/34/35.
- No charting library: the sparkline is a small inline SVG.
- Navigation, sidebar and other views are untouched.

## Evidence

- `backend/tests/test_portfolio_service.py` **16 passed**: new exposure test covers
  verified-only notional (unknown units excluded), margin contribution only from a
  recorded 10x leg, PARTIAL and NOT_AVAILABLE bases.
- Frontend **39 files / 220 tests**: hero/rail DOM tests (exposure and open P&L
  cells, compact formatting, unpriced exposure and unknown-today flags, sparkline)
  plus the localized-title test; all earlier dashboard truth tests still pass.
- Full backend **964 passed / 2 warnings**; i18n **1022/1022/1022**; `npx tsc --noEmit`
  clean.

### Clean build and installed-app update

Per the owner standing instruction, the verified change was committed and the Mac's
installed application was rebuilt from the clean commit (details appended after the
run: source commit, CI report hash, DMG hash, smoke report, installed executable).
