<!-- doc-role: current-work-package -->
# P1-WP44 — Confirmed identity, simulation separation and reachable journal actions

```yaml
work_package: P1-WP44
status: InProgress
branch: main
baseline: f6286a5
```

Owner instruction (2026-09-17): three problems were seen in a real UI test on the installed
application. Reproduce them, verify the causes and apply narrow fixes; never modify the
owner's existing records and keep regressions in isolated synthetic data. The working
behaviours (quantity/leverage/TP edit saves, local automatic closes, the LIVE/freshness
contract, and the real-vs-local split) must not regress, and a local estimate must never be
converted into a real broker result.

## Issue 1 — a manual entry price erased the confirmed market identity

**Reproduced (isolated data):** creating a Simulation trade with Binance BTCUSDT confirmed,
a fetched LIVE quote, then a hand-typed entry price produced
`price_source=manual / price_source_symbol=null`; the journal quote refresh answered
`UNAVAILABLE / NO_VERIFIED_QUOTE_IDENTITY`, the editor's price refresh failed the same way,
and the chart review said "no declared provider" while the local plan kept the Binance
identity and closed correctly.

**Cause:** `NewTradeModal` derived `price_source`/`price_source_symbol` from the *entry-price
provenance* decision (`price_origin`), so any manual execution price dropped the identity;
`quote_refresh._identity`, `declared_provider_identity` (chart review) and the live monitor
all read those same two columns.

**Fix (narrow):** the confirmed provider identity and the entry-price provenance are now
separate claims on the same existing columns. The modal always sends the confirmed
provider/symbol (from the selected instrument or the fetched quote) while
`price_origin=MANUAL` keeps `price_status=UNAVAILABLE` and no observation time; the create
validator accepts a free-source identity under `MANUAL` only with its provider symbol, and
still rejects a manual claim carrying quote evidence. A trade with no confirmed identity
stays honestly UNAVAILABLE and no provider is ever inferred from symbol text. Legacy rows
are untouched (no backfill).

## Issue 2 — simulation and local tracking were indistinguishable in the journal

**Reproduced:** a Simulation record appeared in the open positions table and the journal row
with no simulation label; a completed local plan left the row looking like a plain OPEN
trade; and the "does simulation mix into real performance?" question was verified: the
portfolio summary, multi-asset breakdown, equity curve, daily heatmap, `/analytics/overview`
and the pivot grid all aggregated SIMULATION records.

**Fix (narrow):** journal rows and open-position rows carry an explicit SIMULATION badge; the
journal row shows the local plan state and remaining quantity as a separate annotation with a
fixed notice when the local plan is complete while the external trade stays open (the
external status is never rewritten, and local completion is never presented as a broker
close). The portfolio summary, multi-asset breakdown, equity curve and daily heatmap now
exclude simulation records from real monetary aggregates and report explicit
`simulation_closed_trades`, `simulation_open_positions` and `simulation_realized_pnl`
counters instead.

## Issue 3 — journal actions clipped at the pilot window size

**Reproduced (1229×768):** the horizontal overflow hid the actions column; Edit was
partially visible, Evidence/Inspect chart/Cancel were off-screen and reachable only by
dragging the horizontal scrollbar.

**Fix (narrow):** the actions header and cell are pinned to the right edge of the scrolling
table (sticky, with row-hover background sync), so every row action stays visible without
dragging; no font sizes changed; the four row actions are real `type=button` controls with
visible keyboard focus rings, verified focusable at this window size.

## Ordered acceptance

- [x] Manual entry price with a confirmed identity persists that identity on the trade row;
  journal quote refresh resolves it to a LIVE quote; the chart review reports the declared
  provider identity; the local plan keeps the same identity (backend end-to-end tests +
  one real credential-free run).
- [x] The fixed creation payload is pinned by a frontend regression (Simulation + Binance
  BTCUSDT + manual entry price keeps `price_source=binance_public`,
  `price_source_symbol=BTCUSDT`, `price_origin=MANUAL`, `price_status=UNAVAILABLE`).
- [x] No-identity trades stay honest (`NO_VERIFIED_QUOTE_IDENTITY`, `PROVIDER_NOT_DECLARED`)
  and no provider is inferred from the symbol; manual claims cannot carry quote status and
  PUBLIC_QUOTE still requires the full observation record.
- [x] Simulation rows are labelled in the journal and in the open positions table; journal
  rows show the local plan status/remaining quantity and an explicit "local completion is an
  estimate; the external trade is still open" notice while the lifecycle status stays OPEN.
- [x] Portfolio summary, multi-asset breakdown, equity curve and daily heatmap exclude
  simulation records from real aggregates and expose separate simulation counters.
- [x] Journal actions stay inside a 1229×768 viewport despite horizontal overflow, are
  keyboard focusable, and keep their sizes; a DOM regression pins the sticky column and
  focus styling and a real visual run measures the button rectangles.
- [x] Full backend/frontend suites, i18n parity, TypeScript and production build; canonical
  local CI MERGE READY on the implementing commit.
- [ ] Simulation filtering in `/analytics/overview` and the pivot grid: the DuckDB
  `olap_trades` projection has no `record_mode` column, so this needs an OLAP projection
  schema addition (owner approval); the pivot grid also returns seed data when no closed
  trades exist, which must be revisited in the same decision.
- [ ] Legacy trades recorded before this fix keep `price_source=manual` without an identity
  and stay honestly UNAVAILABLE (no backfill by instruction); a re-declaration flow is a
  separate owner decision.

## Scope boundaries

- Uses the existing trade columns only: no schema change, no migration, no backfill and no
  edit to any existing record; all reproductions ran on isolated synthetic data.
- The LIVE + provider-event + <=60s contract for automatic local closes, the quantity/
  leverage/TP edit saves and the local plan identity are unchanged; local results are never
  converted into broker results.
- Only the four enumerated portfolio/analytics functions that read SQLite trades were
  filtered; the DuckDB OLAP projection and the pivot grid are explicit unchecked items.

## Evidence

- **Backend** (new `backend/tests/test_wp44_identity_and_separation.py`, 6 tests): fixed
  creation payload keeps the identity through create → quote refresh (LIVE) → chart review
  (`PROVIDER_MATCH_REQUIRED`); the provider symbol is required for a confirmed free source
  under MANUAL; a manual claim with quote status and an incomplete PUBLIC_QUOTE claim are
  rejected; an identity-less trade stays `NO_VERIFIED_QUOTE_IDENTITY`/
  `PROVIDER_NOT_DECLARED` with zero provider calls; simulation records never enter net PnL,
  equity, exposure, win rate, equity curve, heatmap or asset buckets while the explicit
  simulation counters report them.
- **Frontend:** `NewTradeModal` regression for the exact reported flow; `JournalView`
  regressions for the simulation badge, the local-plan row (status + remaining + completed
  note) and the sticky/focus-visible actions; `OpenPositionsTable` simulation badge test.
  Full suites: backend **1164 passed**, frontend **41 files / 284 tests**, i18n
  **1213/1213/1213**, `tsc` clean, production build clean.
- **Real runs (isolated data, credential-free):** API-level reproduction before the fix
  (`NO_VERIFIED_QUOTE_IDENTITY` / `PROVIDER_NOT_DECLARED`); after the fix the same flow
  returned a LIVE `binance_public BTCUSDT` quote (76362.0) and
  `PROVIDER_MATCH_REQUIRED` with the identity; local plan identity kept.
- **Visual (1229×768):** table overflow `scrollWidth 1717 > clientWidth 971` while all four
  actions measured inside the viewport (edit 727–811, evidence 815–936, replay 940–1091,
  cancel 1095–1200) and focusable; simulation badge, active local plan row
  (`WAITING_QUOTE · remaining 0.001`) and completed-plan row with the external-open notice
  all rendered. Screenshots and measurements:
  `artifacts/evidence/p1-wp44/`.
- Implementation and install evidence (commit SHAs, canonical CI report hash, installed
  executable hash) are recorded in `docs/strategy/STATUS.md`.
