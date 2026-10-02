<!-- doc-role: current-work-package -->
# P1-WP52 — Core workflow translation and readability

```yaml
work_package: P1-WP52
status: InProgress
date: 2026-10-02
branch: main
baseline: 2383cca
```

Selected next owner-approved UX step after completed WP51. **Implemented; clean-source
build and installed acceptance pending.**
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

- [x] Reproduce core contrast/translation/readability defects with actual observations
  and red tests; record the bounded changed surfaces, not an unverified all-app claim.
- [x] EN/TR/DE changed copy is semantically accurate; no raw keys/hardcoded new JSX;
  sample meanings of local estimate, external record, unavailable and incomplete data.
- [ ] Changed controls/text readable on light/dark fresh launch and after switching,
  focus/disabled states preserved; long translations and core keyboard journey checked.
- [ ] Relevant regression and full suites, i18n/typecheck/build, docs/truth/diff and
  canonical clean-source arm64 local CI pass with isolated synthetic data.
- [ ] Commit/push main and exact-DMG/native installed QA; executable/source hashes,
  no data loss and restored user preferences recorded. No Release/tag refresh.
- [ ] STATUS/registry closure with actual evidence; only then archive and select the
  next approved form-simplicity package. External obligations remain visible.

## Implementation evidence — this change

- Native WP51 dark New Trade had invisible filled accents/black-on-dark text. The
  Tailwind slash-alpha `rgb()` syntax consumed comma RGB tuples: CSS declaration parsing
  returned an empty color. Corrected all five semantic utility definitions to matching
  comma `rgba()` syntax; CSS/parser tests compile actual Tailwind utilities, opaque and
  translucent. ThemeProvider applies hex/RGB tokens together; cold dark/light and theme
  roundtrip tests prevent drift between utility/chart colors.
- Changed common palette text colors and filled-action ink/hover recipe; normal/muted
  text on five core surfaces, accent/gain/loss text on 0/10/15/20% tints and filled actions
  in both themes pass >=4.5:1. This is a bounded token/recipe test, not an all-app WCAG audit.
  Header, New Trade/Edit, journal/manual/empty-state CTA, tracking and sidebar controls
  adopt the recipe/focus/target conventions. Sidebar long labels wrap rather than truncate;
  selected core explanatory text uses system sans instead of inherited Courier fallback.
- Slower initial locale GET overwrote an intervening user's choice (TR became DE in
  red DOM test); guarded the response, preserved storage/backend preference contract,
  and set document language. No accounting or backend/API change.
- Removed stale price-times-base-quantity wording from the USD-only form (EN/TR/DE):
  declared USD position value, price return, gross before fees/funding, no leverage
  multiplier, not broker-confirmed profit, non-USD approximation. Journal's institutional
  execution wording becomes records/correction history/no orders. Five sidebar labels
  now translated; SQLite/DuckDB/ASYNCIO brand/protocol identifiers remain technical.
- Red focused run: **11 failed / 2 passed**, covering invalid semantic CSS, new contrast/
  ink contract, RGB application, locale race/document language and truncated navigation.
  Final frontend suite **51 files / 353 PASS**; i18n **1274** keys/language, tsc/build PASS;
  docs **138 documents / 186 links / 5 startup PASS**, truth/diff PASS. Full backend
  `uv run --offline --no-project --with-requirements backend/requirements.lock python -m
  pytest backend/tests -q`: **1220 PASS / 3 warnings**, isolated synthetic test directories.
  Native installed acceptance and canonical clean-source results are not claimed yet.
- Initial clean-source CI at **31f11bf** passed all 13 steps, COMPLETE. Final review found
  legacy pale amber warning text/light footer purple text outside that contrast recipe.
  Core manual-symbol/refresh/edit warning panels now share tested warning ink/tints;
  footer technical text uses normal muted ink. Extended warning recipe test red (missing
  explicit warning token) → green. A new clean-source build is required after this change;
  the earlier executable is not installed or offered as the final binary.
- Installed **59ecbd0** candidate exposed a second genuine native startup defect: first
  light launch had dark header/nav/control colors while other surfaces were light; theme
  roundtrip resolved it. Child-layout tests failed in both themes: the first child layout
  saw no initialized theme/RGB tokens. ThemeProvider now gates child mounting until the
  persisted theme is applied in the pre-paint layout phase. Local candidate was installed
  preserving data, but is **not final acceptance**; rebuild/reinstall is required.
