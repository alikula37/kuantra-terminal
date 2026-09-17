<!-- doc-role: current-work-package -->
# P1-WP45 — USD position value as the only trade sizing

```yaml
work_package: P1-WP45
status: InProgress
branch: main
baseline: 5fbc1af
```

Owner instruction (2026-09-17): trade entries must size positions in **USD value** — traders
actually take trades with USD amounts, not base-unit quantities. Make the change
comprehensively ("fix everywhere"):
1. USD position value is the **only** sizing in the entry/edit UI; the base-quantity input is
   removed. Stored as `qty` with `qty_unit=USD` (no schema change needed; `qty_unit` is the
   existing declaration column).
2. Money math works from the USD value: notional = value, margin = value / declared leverage
   (spot = full payment), PnL = direction × price-return × value, R = PnL ÷ (price-risk ×
   value). No contract-size verification is required for this path.
3. Non-USD-quoted pairs (for example ETHBTC) are computed **approximately** (price-return ×
   USD value) and must be labeled `QUOTE_NOT_USD_APPROXIMATE`; the label is visible, never
   silent.
4. The owner explicitly instructed that all existing trade records are wrong under the old
   logic and must be **deleted** ("hepsini sil. mantık hatalıydı"). A full data-directory
   backup is taken first; only trade-domain data is removed (trades, their evidence/audit
   rows, local tracking plans, OLAP trade projections); settings/preferences and the market
   candle cache stay.
5. The change ships through the normal gates and as the `v1.1.5` pilot release (owner
   approved in the same instruction).

## Ordered acceptance

- [x] Entry: New Trade has one size field, "Position value (USD)"; the base-quantity input,
  size-mode toggle and base/unknown unit declaration are gone from the UI; payload carries
  `size_input_mode=NOTIONAL`, `qty_unit=USD` and the value.
- [x] Backend creates and edits trades with `qty_unit=USD` where `qty` is the USD value;
  validators accept `USD` (legacy `BASE`/`UNKNOWN` remain readable for imports/old rows) and
  reject nonsense combinations.
- [x] `position_math` gains the `USD_NOTIONAL` basis: monetary READY without provider
  verification, notional = value, margin from declared leverage, gross PnL = price-return ×
  value, R-multiple from the price-risk fraction; non-USD quote pairs add
  `QUOTE_NOT_USD_APPROXIMATE`.
- [x] Local tracking accepts USD-value plans, stores the unit in the plan state, and its
  internal gross-PnL consistency math uses the value formula for USD plans (legacy base
  plans keep the old math); the "base-unit declaration" refusal message no longer blocks a
  USD declaration.
- [x] Portfolio/dashboard math (open risk, notional, margin, unrealized, asset volume,
  equity curve inputs, exports CSV/PDF and the evidence pack) uses the USD value for USD
  trades; R-multiple/risk never multiplies by leverage.
- [x] Frontend display: quantity columns/rows show the USD value for USD trades (journal,
  open positions, edit modal, local tracking remaining/closed quantity, dashboard);
  `positionMath.ts` mirrors the backend basis and formats values as currency.
- [x] Tests: backend unit + API regressions for create/edit/close/tracking/portfolio with
  USD sizing (including the approximate-quote warning, R-multiple, margin, legacy rows kept
  working), frontend DOM regressions for the single USD entry field and USD displays; full
  suites, i18n, `tsc`, production build, canonical CI.
- [ ] Data hygiene: full backup taken and the trade-domain wipe executed and verified (empty
  journal on the installed app), with the backup path reported.
- [ ] v1.1.5 release train, tag, release assets and the data-preserving install (recorded in
  STATUS with the exact hashes).

## Scope boundaries

- No schema change: `qty_unit` already carries the declaration; the USD value lives in the
  existing `qty` column with `qty_unit=USD`.
- Legacy `BASE`/`UNKNOWN` rows remain readable and are never rewritten automatically; the
  edit surface writes USD when the user saves a value.
- The live-tracking price contract (LIVE + provider event ≤ 60s) is unchanged; leverage
  never multiplies price PnL; local estimates stay estimates.
- Provider quotes/candles, price provenance, chart review and the product-consistency check
  are untouched by this package.

## Evidence

**Implemented (this change):**
- Backend: `position_math` `USD_NOTIONAL` basis (monetary READY without provider
  verification; notional = value; margin from declared leverage; gross PnL = price-return ×
  value; `QUOTE_NOT_USD_APPROXIMATE` warning for non-USD-quoted pairs); create/close/edit
  handlers store and price the USD value; local tracking accepts USD plans, persists the
  unit in the plan state and uses the value formula for its closure math; portfolio risk,
  notional, margin, unrealized and asset volume use the value; the unit gate message and
  `unit_status` reflect the USD basis.
- Frontend: New Trade has a single "Position value (USD)" field (payload
  `size_input_mode=NOTIONAL`, `notional_size`, `qty_unit=USD`); Edit declares a changed
  value as USD explicitly (a notes-only save never converts a legacy row); the journal,
  open-positions table, local tracking panel and the trade summary show/format the USD
  value; `positionMath.ts` mirrors the basis, the approximate warning and
  `formatPositionValue`.
- Tests: `backend/tests/test_wp45_usd_position_value.py` **9 passed** (basis, value math,
  R-multiple, edit/close recompute, legacy rows keep withholding money until declared, the
  approximate label, tracking plan + closure pricing, portfolio risk/unrealized); existing
  gate-message assertions updated to the new unit-declaration message. Full backend **1173
  passed**. Frontend **41 files / 286 tests** (USD-only entry regression, USD currency in
  the journal and open positions, edit-modal declaration), i18n **1228/1228/1228**, `tsc`
  clean, production build clean, `check_docs` PASS, `git diff --check` clean.

**Pending in this change:** the trade-domain data wipe (backup first) and the `v1.1.5`
release/tag/install evidence, recorded in `docs/strategy/STATUS.md`.
