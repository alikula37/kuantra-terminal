<!-- doc-role: current-work-package -->
# P1-WP50 — Readable journal and compact, accessible actions

```yaml
work_package: P1-WP50
status: InProgress
date: 2026-10-02
branch: main
baseline: 84e7afd
```

Next bounded item of the owner-approved UX sequence. **Selected/prepared; implementation
not started.** WP49 quote-truth package is complete; WP29 external obligations remain open.

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

## Acceptance (not yet completed)

- [ ] Red regression for action discoverability/focus and preserved secondary workflows.
- [ ] Bounded frontend implementation; no date/price/status overlap in native visual QA.
- [ ] Focused/full frontend, i18n/tsc/build; relevant backend regressions and full local CI.
- [ ] Clean commit/push main, native arm64 build/exact-DMG smoke, data-preserving install.
- [ ] STATUS/registry closure with actual evidence; archive only after verified acceptance.
