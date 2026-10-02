<!-- doc-role: current-work-package -->
# P1-WP52 — Core workflow translation and readability

```yaml
work_package: P1-WP52
status: Ready
date: 2026-10-02
branch: main
baseline: 2383cca
```

Selected next owner-approved UX step after completed WP51. **Prepared, not implemented.**
One bounded readability/translation package, not a competing roadmap or all-app redesign.
WP29 external obligations remain open; Release/tag and Intel updates are not authorized.

## Starting observations to reproduce

WP50 and installed WP51 native QA show the global New Trade and dashboard empty-state
trade-entry buttons black-on-dark. WP51's first light screenshot also showed low-contrast
active header/sidebar controls; after a theme roundtrip their colors returned. Reproduce
fresh launch vs theme switching before determining the cause; do not label this merely
a missing translation. Existing sidebar truncation and thin/small secondary labels also
need sampled core-workflow inspection, not a claim that every screen has been audited.

## Bounded scope

- Header/sidebar and Dashboard → Journal → New Trade/Edit/Tracking core journey. Confirm
  wrong/missing/raw translation keys, misleading wording and unreadable text before edits.
- Correct actual EN/TR/DE semantic defects, including descriptions that imply live
  execution or complete results when the product only records/reviews. Parity alone is
  not proof of correct wording. Keep financial/source/status distinctions intact.
- Restore semantic accent/surface/ink colors and readable normal/hover/focus/disabled
  states in light and dark, including fresh startup and theme roundtrips. Measure contrast
  for changed enabled text (4.5:1 normal, 3:1 large text) and visibly preserve disabled state.
- Improve small/thin text only where confirmed in this journey; preserve keyboard focus,
  minimum control targets, useful density, long German labels and readable numeric values.
- Existing preferences and translations remain compatible. No form restructuring here;
  progressive form simplicity is the following approved step.
- No change to accounting, unit verification, quote identity/freshness, auto-close/risk
  authority, providers/connectors, data schema, user trades, Release/tag or workflows.
  Shutdown-helper reproduction remains a separate lifecycle obligation.

## Acceptance

- [ ] Reproduce core contrast/translation/readability defects with actual observations
  and red tests; record the bounded changed surfaces, not an unverified all-app claim.
- [ ] EN/TR/DE changed copy is semantically accurate; no raw keys/hardcoded new JSX;
  sample meanings of local estimate, external record, unavailable and incomplete data.
- [ ] Changed controls/text readable on light/dark fresh launch and after switching,
  focus/disabled states preserved; long translations and core keyboard journey checked.
- [ ] Relevant regression and full suites, i18n/typecheck/build, docs/truth/diff and
  canonical clean-source arm64 local CI pass with isolated synthetic data.
- [ ] Commit/push main and exact-DMG/native installed QA; executable/source hashes,
  no data loss and restored user preferences recorded. No Release/tag refresh.
- [ ] STATUS/registry closure with actual evidence; only then archive and select the
  next approved form-simplicity package. External obligations remain visible.
