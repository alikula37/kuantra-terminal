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

## Round 2 — owner rejected the first pass; research-driven redesign

Owner feedback (2026-09-15, with a screenshot): "bu ne yav çok kötü" and an explicit
request to research design. Root causes found in the first pass:

- The first hero used a hardcoded dark `bg-[#0e141f]` that the light-theme compatibility
  shim did not remap, while the shim *did* remap `text-white` to the light text color:
  dark cards with near-invisible dark values in the light theme.
- Secondary cells used 9–10px label classes, but the pilot readability floor raises every
  `text-[8px]`–`text-xs` utility to 14px, so the six-cell rail wrapped into unreadable
  multi-line blocks.
- The dashboard scroller was a flex column; the chart row's explicit `min-h-[320px]`
  let it shrink below its content, so the open-positions card painted over the heatmap.
- Only the light-theme shim kept the older surfaces readable; nothing used the real
  theme variables.

Design research (web) applied: inverted-pyramid/F-pattern hierarchy (Tier-1 north-star
metrics largest, top-left), one fixed card anatomy (label -> value -> context) with
tabular numerals, "one metric = one meaning" (no duplicated exposure cell), consistent
color semantics (gain/loss/accent/warn only, no decorative palette), semantic design
tokens instead of hardcoded colors (the Carbon/USWDS approach), and visible freshness
("son veri" + live-price age).

What changed in round 2:

- Tailwind colors now resolve through the theme CSS variables (`background`, `surface`,
  `elevated`, `soft`, `deep`, `hover`, `surface-border`, `ink`, `muted`, `accent`,
  `gain`, `loss`, `warn` with `rgb(var(--…-rgb) / <alpha-value>)` for alpha support),
  and new `.k-kpi*`/`.k-kpi-strip*` primitives carry the card anatomy with no hardcoded
  colors.
- Hero: live equity (2/6 wide, 30px value, sparkline, realized/open breakdown and price
  freshness), open P&L, open risk, exposure, today; strip: win rate, profit factor,
  average R, max drawdown, active positions, unknown results.
- Chart, breakdown, heatmap and positions cards migrated to the tokens; chart SVG
  colors resolve from the theme; the scroller switched from flex to block flow so no
  card can be squeezed over another; negative money formats as `-$X`.
- Localized title and shorter TR/EN/DE copy for the unknown-results sub-label.

Visual verification: the running app was screenshotted with headless Chrome in **both**
themes at 1680x1050 (temporary copy of the owner database; nothing user-facing changed)
and the layout was measured through the DOM to prove the overlap is gone
(chart/right column bottom 874px, positions card starts at 886px).

## Round 3 — Sharpe on the dashboard (owner request)

Owner request (2026-09-15): "sharpe oranı hangisi oluyor?" then "ekle". The Sharpe ratio
lived only in the plugin-gated Analytics page (invisible in Lite mode) and used the
quant engine's default capital, which would have disagreed with the dashboard.

- `portfolio/summary` now reports `sharpe_ratio` (annualized mean/std × √252 of the
  realized per-trade returns scaled by the configured balance), `sharpe_basis`
  (`READY` / `NOT_AVAILABLE`) and `sharpe_trades` (known closed results used). Fewer
  than two results or a flat series report `null`/`NOT_AVAILABLE`, never `0.00`.
- The Analytics endpoint now passes the same configured initial capital into the quant
  engine, so the dashboard and the Analytics scorecard show one number with one meaning.
- The KPI strip gains a "SHARPE" cell with the formula tooltip, the closed-trade count
  under the value, and the honest "not enough data" state; EN/TR/DE strings added.
- Tests: `test_portfolio_service.py` **18 passed** (computable series matches the quant
  engine value, one trade / flat series / unknown results stay unavailable) and the KPI
  grid DOM test covers the ready and missing states.

## Round 4 — per-metric hide with hover ✕ (owner request)

Owner report (2026-09-15): "çok fazla metrik var hepsi anlamlı olmayabilir. mouse üzerlerine
geldiğinde sağ üstlerinde çarpı işareti çıksın her bir kutu için. kapatılırsa veya
açılırlarsa hizalama vs ona göre yapılsın."

- Every hero card and rail cell renders an ✕ button in its top-right corner that
  appears on hover (and on keyboard focus), hides its metric, and stops event
  propagation so the clickable equity card is not triggered.
- Hidden metrics are remembered per machine in `localStorage`
  (`kuantra_dashboard_metrics_hidden`); a blocked storage degrades to in-memory state
  instead of breaking the dashboard.
- Alignment reflows: the hero grid computes its column count from the remaining cards
  (the live-equity card keeps a double slot, so 5 visible cards render in 6 columns,
  4 in 5, and so on), and the rail strip keeps its auto-fit cells, so hiding any
  combination leaves no gaps.
- A "Metrikler · N gizli" control appears only while metrics are hidden; it opens a
  checkbox panel for every metric plus "show all", so closing is always reversible.
- EN/TR/DE strings for the hide/restore controls; screenshot-verified with three
  metrics hidden (hero reflowed to 4 cards, rail to 5 cells, restore chip visible).

## Round 5 — remove the "unknown results" cell (owner request)

Owner request (2026-09-15): "unknown results diye bir kutu var o. nedir?" then "onu
kaldıralım tamamen". The strip cell was removed together with its two now-unused locale
keys; the underlying honesty guard stays untouched — `unknown_pnl_trades` is still
reported by `portfolio/summary`, the dashboard still shows the amber
"completed trade(s) have an unknown result" warning while the count is above zero, and
those trades remain excluded from monetary aggregates instead of being counted as zero.

- Removed: the `unknown-results` strip cell, its entry in the hidden-metric registry
  and label map, and `portfolio.unknown_results` / `portfolio.of_closed` in EN/TR/DE.
- The rail now carries six cells (win rate, profit factor, average R, max drawdown,
  active positions, Sharpe) and keeps reflowing with the hide controls.
- Evidence: frontend **39 files / 223 tests**, i18n **1028/1028/1028**, TypeScript clean.

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
- Round 4: frontend **39 files / 223 tests** (hide from the ✕, storage persistence,
  grid class reflow, restore panel and show-all covered); i18n **1030/1030/1030**;
  full backend **966 passed / 2 warnings**.
- Round 3: full backend **966 passed / 2 warnings**; frontend **39 files / 221 tests**;
  i18n **1026/1026/1026**; both-theme screenshot re-checked with the seven-cell strip.
- Round 2: frontend rerun **39 files / 220 tests** (unchanged tests keep passing through
  the token migration), both-theme screenshots reviewed, DOM-measured layout check
  (no overlap; the grid row now sizes to its content).

### Round 4 clean build and installed-app update

- Source `3ad50ed` passed canonical arm64 local CI with **COMPLETE** provenance and a
  clean tree; report `dist/p1-wp36d-clean-local-ci.json` SHA-256
  `c495e26d18dd9207e242e680524a7f48164e9f9cf7eb44bc47a23f006228c2cf`, executable
  `b1419395a2812706d7a0bacb7efea23bbcf8fec87873c56797a3d1ccb9a3467f`.
- arm64 DMG `dist/Kuantra-Terminal-1.1.0-arm64-wp36d.dmg` `hdiutil verify` VALID,
  SHA-256 `b3c07ce3777925f4ab492ca519e9a6cf4fcecd2a87106b715131fa808b9b3619`; mounted
  read-only smoke **PASS** (`dist/p1-wp36d-dmg-smoke.json`).
- `/Applications` replaced after a graceful quit; installed executable matches the CI
  build, launched PID `65266`, runtime `{"status":"online","gateway":true,"version":"1.1.0"}`,
  user data preserved.

### Round 3 clean build and installed-app update

- Source `43a3c06` passed canonical arm64 local CI with **COMPLETE** provenance and a
  clean tree; report `dist/p1-wp36c-clean-local-ci.json` SHA-256
  `a08edaa406f1191fff41a4e0e1558a2dec2dc786c61f5b7190b9903b21cdf58e`, executable
  `01dc9eefa8c26eb40c873407bcbc84f406beb08b6950cd159b19365b6192ae56`.
- arm64 DMG `dist/Kuantra-Terminal-1.1.0-arm64-wp36c.dmg` `hdiutil verify` VALID,
  SHA-256 `c1d47fb7dd6386b684d6cc1b525c348d0dbd9572c2d395ab2984837d911ce44f`; mounted
  read-only smoke **PASS** (`dist/p1-wp36c-dmg-smoke.json`).
- `/Applications` replaced after a graceful quit; installed executable matches the CI
  build, launched PID `63300`, runtime `{"status":"online","gateway":true,"version":"1.1.0"}`,
  user data preserved.

### Round 2 clean build and installed-app update

- Source `ffa3a77` passed canonical arm64 local CI with **COMPLETE** provenance and a
  clean tree; report `dist/p1-wp36b-clean-local-ci.json` SHA-256
  `f13e3c4a6a0ec7e0aaf3af05733d791d8d3b4573a5697d71f1eb8e238fd6a192`, executable
  `fa00cd733caba6413ea2f0a98e4e998d1f5f07964650d9f72e06107a4621da14`.
- arm64 DMG `dist/Kuantra-Terminal-1.1.0-arm64-wp36b.dmg` `hdiutil verify` VALID,
  SHA-256 `9c779575497a2edc8eddbf2d7cadb9d540adc93f5a9643b1ee34e8f57d783dc8`; mounted
  read-only smoke **PASS** (`dist/p1-wp36b-dmg-smoke.json`).
- `/Applications` replaced after a graceful quit; installed executable matches the CI
  build, launched PID `61170`, runtime `{"status":"online","gateway":true,"version":"1.1.0"}`,
  user data preserved (5 trades).

### First-pass clean build and installed-app update

Per the owner standing instruction, the verified change was committed (`4b874ad`,
pushed) and the Mac's installed application was rebuilt from the clean commit:

- Canonical arm64 local CI on `4b874ad`: **MERGE READY**, provenance **COMPLETE**,
  clean tree; report `dist/p1-wp36-clean-local-ci.json` SHA-256
  `59dd43d9b6d716bb093dbf6dca00e601001790efddfd76b39e7256734d338726`, executable
  `903c713b7be2d813fc5197ee1aa3be9bce3663137bbf7232ebfe4e149579a9b5`.
- arm64 DMG `dist/Kuantra-Terminal-1.1.0-arm64-wp36.dmg`: `hdiutil verify` VALID,
  SHA-256 `f92f22851674614e9c77134b381dafa7bb2704e82a6018cfcb2f38972983a42c`;
  exact read-only mounted-DMG smoke **PASS** (`dist/p1-wp36-dmg-smoke.json`).
- `/Applications/Kuantra Terminal.app` replaced after a graceful quit; installed
  executable matches the CI build, launched PID `57042`, runtime
  `{"status":"online","gateway":true,"version":"1.1.0"}`, user data preserved.
