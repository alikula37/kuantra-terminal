<!-- doc-role: archived -->
# P1-WP46 — USD money math everywhere, monitor visibility, label/i18n fixes

```yaml
work_package: P1-WP46
status: Complete
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

- [x] Red-first regressions for each finding, then fixes; long/short, USD/base, leverage,
      edit-then-refresh and automatic-tracking coverage.
- [x] USD value, base quantity and margin stay separate in every money path: create/edit
      forms, dashboard live feed, replay payload, portfolio, local tracking, exports.
- [x] `unrealized = value × (price − entry) / entry`; short direction correct; leverage never
      multiplies price PnL; legacy base rows keep their old meaning.
- [x] API/WS/initial-load payloads keep unit metadata (`qty_unit`, `record_mode`); the
      frontend merges live position updates instead of replacing rows.
- [x] Monitor: ineligible/stale observations retry soon without backoff; fetch errors keep
      backoff; the waiting reason, last attempt and next poll are visible in the view/panel;
      one closure per eligible observation, no double close; freshness rules unchanged.
- [x] Pre-save warning when the TP/SL is already reached; a fresh eligible observation after
      saving is evaluated (no retrospective fill).
- [x] `verification_EXPLICIT_USD_VALUE` (and every dynamically composed verification key)
      resolves in EN/TR/DE with a content test, not just key-count parity.
- [x] Full suites, i18n/docs checks, canonical Mac local CI, commit/push, clean-commit arm64
      package, exact-DMG verification, data-preserving install, and a new labelled simulation
      record exercising the same scenario in the installed app. Release/tag unchanged.

## Scope boundaries

- No loosening of the LIVE + provider-event ≤60 s + armed_at eligibility contract.
- No changes to existing user records; the diagnostic record TRD-1789656201298 is reference
  only (all repros run on isolated copies/new labelled simulation records).

## Delivery verification (2026-09-18)

Commits `bd31ba4` (backend money paths), `909aeca` (frontend merge/locale/panel),
`af185ca` (docs) and `8b092b8` (provider clock-skew eligibility) are pushed. Red-first
evidence: base-formula risk/reward failed the new DOM test before the fix (600,000/1,400,000
vs 7.89/18.42), the merge helper/localization content tests failed before the helpers existed,
and the skew test failed before the bounded tolerance. Full suites: backend **1182 passed**,
frontend **43 files / 295 tests**, i18n **1235/1235/1235**, `tsc`/build clean, `check_docs`
PASS. Canonical arm64 local CI on the clean commit **MERGE READY** (`dist/p1-wp46b-local-ci.json`,
executable `55d020631c0c863eb22739491567eeed973ffaab7d7aafae9c6edd64c9af3fe1`). The arm64 DMG
(`Kuantra-Terminal-1.1.5-wp46b-arm64.dmg`, exact-DMG smoke PASS) was installed over
`/Applications/Kuantra Terminal.app` (backup `/tmp/kuantra-wp46b-update.HB7wlX`); installed
executable matches the CI build, codesign OK, version 1.1.5.

**Installed-app retest (new labelled simulation record `TRD-1789714741027`, note
QA-WP46-RETEST; existing records untouched):** entry 78,210.0 (live quote), value 100 USD,
leverage 2, simulation badge everywhere. The tracking editor showed the prominent
already-reached alert (`role=alert`) before saving; after saving a valid already-reached stop
the monitor fetched on a 7–9 s cadence and closed the plan automatically within ~3 s
(provider event `2026-09-18T10:19:09.516Z`, SL at 78,204 vs stop 78,209, gross
**-0.0077 USD** value-based, **single** closure, external record still OPEN, unit
`USD_NOTIONAL`); a second close attempt is rejected (`409 already closed`). Screenshots and
the result JSON are in `artifacts/evidence/p1-wp46-retest/`.

**Unverifiable limits:** the pre-fix sessions logged the monitor reason only at DEBUG, so the
exact split between transient feed errors and the clock-skew rejection during the user's
original 2-minute wait cannot be reconstructed beyond the surviving INFO fetch cadence and
the reproduced root causes; the feed itself answered live in this retest (age < 1 s). The
desktop Binance websocket still shows an environment SSL `CERTIFICATE_VERIFY_FAILED` in the
logs; automatic local tracking does not depend on it (it uses the documented public REST
trade event), and this remains an environment-level observation, not a code claim.
