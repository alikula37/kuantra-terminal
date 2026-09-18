<!-- doc-role: current-work-package -->
# P1-WP46 — USD money math everywhere, monitor visibility, label/i18n fixes

```yaml
work_package: P1-WP46
status: InProgress
branch: main
baseline: 957af60
```

Owner instruction (2026-09-18): four real-UI findings on installed 1.1.5, verified with
red-first regressions:

1. **USD position value miscounted as base quantity in remaining paths.** With entry 76,000,
   value 100 USD, leverage 2, SL 70,000, TP 90,000 and price 76,787.70 the create form showed
   risk/reward 600,000/1,400,000 instead of 7.89/18.42 USD (base formula `|price-diff| × value`),
   and the dashboard live feed (`binance_client._recalculate_open_positions`) produced 78,770
   instead of 1.04 USD. The WS `open_positions` payload likewise replaced the dashboard table
   rows and dropped their `record_mode`/`qty_unit` metadata (finding 3).
2. **Automatic TP close looked absent.** Log evidence (local time = UTC+3): the monitor did
   poll 17:43:25–17:48:20 UTC on 2026-09-17 and the plan **did auto-close** via TP1 at
   76,606 (gross 1.5947 USD, single closure, correct USD math). The delay came from the
   monitor's backoff: an ineligible/stale observation (including the normal
   "observed_at <= armed_at" case right after saving) is counted as a fetch failure and
   escalates 15→30→60→120 s, and the UI only said "waiting for a live quote" with no reason.
3. **Simulation label lost on the dashboard** because the WS position rows (no metadata)
   overwrote the server-loaded rows.
4. **Raw locale key** `order_ticket.verification_EXPLICIT_USD_VALUE` rendered in create/edit.

## Ordered acceptance

- [ ] Red-first regressions for each finding, then fixes; long/short, USD/base, leverage,
      edit-then-refresh and automatic-tracking coverage.
- [ ] USD value, base quantity and margin stay separate in every money path: create/edit
      forms, dashboard live feed, replay payload, portfolio, local tracking, exports.
- [ ] `unrealized = value × (price − entry) / entry`; short direction correct; leverage never
      multiplies price PnL; legacy base rows keep their old meaning.
- [ ] API/WS/initial-load payloads keep unit metadata (`qty_unit`, `record_mode`); the
      frontend merges live position updates instead of replacing rows.
- [ ] Monitor: ineligible/stale observations retry soon without backoff; fetch errors keep
      backoff; the waiting reason, last attempt and next poll are visible in the view/panel;
      one closure per eligible observation, no double close; freshness rules unchanged.
- [ ] Pre-save warning when the TP/SL is already reached; a fresh eligible observation after
      saving is evaluated (no retrospective fill).
- [ ] `verification_EXPLICIT_USD_VALUE` (and every dynamically composed verification key)
      resolves in EN/TR/DE with a content test, not just key-count parity.
- [ ] Full suites, i18n/docs checks, canonical Mac local CI, commit/push, clean-commit arm64
      package, exact-DMG verification, data-preserving install, and a new labelled simulation
      record exercising the same scenario in the installed app. Release/tag unchanged.

## Scope boundaries

- No loosening of the LIVE + provider-event ≤60 s + armed_at eligibility contract.
- No changes to existing user records; the diagnostic record TRD-1789656201298 is reference
  only (all repros run on isolated copies/new labelled simulation records).
