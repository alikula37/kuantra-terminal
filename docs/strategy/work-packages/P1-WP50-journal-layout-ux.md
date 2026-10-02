<!-- doc-role: current-work-package -->
# P1-WP50 — Readable journal and compact, accessible actions

```yaml
work_package: P1-WP50
status: InProgress
date: 2026-10-02
branch: main
baseline: 84e7afd
```

Next bounded item of the owner-approved UX sequence. **Implementation tested; clean native
delivery and visual acceptance pending.** WP49 is complete; WP29 obligations remain open.

## Verified starting finding

Installed 1.1.6 local WP49 build, native light-theme screenshot: wide sticky Actions
cell (Edit/Evidence/Chart/Cancel) hides date, price freshness and status columns while
the first row is excessively tall. AX includes the correct price explanations, but
their presence in AX is not evidence that the trader can see them without scrolling.

## Bounded scope

- Keep Edit discoverable; move secondary actions into a compact, keyboard-accessible
  arrangement without dropping Evidence/Chart/Cancel or changing their safety behavior.
- No sticky-cell overlay of essential values. Prioritize instrument, side, entry/value,
  quote freshness and status; keep full ID/time/PnL/R and provenance discoverable.
- Wrap/bound quote explanation width and offer detail disclosure where necessary;
  never hide delayed/unknown/stale state behind a reassuring live indicator.
- Check real native window layout, light/dark themes and EN/TR/DE; do not assume jsdom
  assertions validate CSS geometry. All new text translated, readable and focusable.
- No API/accounting/schema change, real orders or user record cleanup. Existing edit,
  cancellation, chart, evidence, simulation separation and quote-truth rules stay intact.
- No release/tag or Intel build is authorized by this UI package.

## Acceptance

- [x] Red regression for action discoverability/focus and preserved secondary workflows.
  WP50 DOM suite: 5 real red failures (12 columns / no disclosure) after correcting unstable
  test doubles, then green. Primary Edit, evidence/chart routing, confirmation-only cancellation,
  canceled tombstone, Escape focus return and EN/TR/DE text checked. Existing sticky assertion
  superseded by the no-overlay contract; original workflow regression tests retained.
- [ ] Bounded frontend implementation; no date/price/status overlap in native visual QA.
- [ ] Focused/full frontend, i18n/tsc/build; relevant backend regressions and full local CI.
- [ ] Clean commit/push main, native arm64 build/exact-DMG smoke, data-preserving install.
- [ ] STATUS/registry closure with actual evidence; archive only after verified acceptance.

## Implementation and pre-delivery evidence

Seven fixed-width columns replace the 12-column table; instrument, Istanbul entry time,
entry price, position value, quote quality and external/local statuses remain in the main row.
Edit and a labelled 44px disclosure control are in-flow, never a sticky overlay. Secondary
actions and complete ID/entry time/exit/PnL/R open in a full-width inline row. Closed PnL
remains in the main status cell (unknown is not zero). Cancellation still requires the existing
confirmation and keeps its audit tombstone. No API, schema or accounting change.

Compact journal quote rendering always shows status, age, provider/symbol and display-only
or unverified-time warning; only long timestamp explanation is disclosed. Entry/edit/dashboard
keep the existing full presentation. Local tracking and simulation labels remain separate.

Pre-delivery: focused frontend 29 PASS, related backend 89 PASS / 2 warnings (WP49,
WP44, WP32 trade edits, local tracking, journal export); i18n/tsc/build PASS. Full frontend
first found the new dynamic status-key family missing from the key-content registry; registry
extended with OPEN/CLOSED/CANCELED, not bypassed. Final suites and native proof recorded below.

Final pre-commit suites: full backend **1209 PASS / 3 warnings** in fresh isolated data;
full frontend **46 files / 309 tests PASS**, i18n **1259/1259/1259**, tsc/production build,
docs (**136 documents / 184 links / 5 startup**), release truth and diff check PASS.
No dependency install required; `uv --offline` proves dependency resolution only.
Native visual acceptance, canonical clean-source CI and install remain pending.
