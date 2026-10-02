<!-- doc-role: archived -->
# P1-WP52 — Core workflow translation and readability

```yaml
work_package: P1-WP52
status: Complete
date: 2026-10-02
branch: main
baseline: 2383cca
```

Completed owner-approved UX step after WP51. **Clean-source build and installed
acceptance verified at 793cab419ce4ae3aa3a1ae3eb9ea70b75919981a.**
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
- [x] Changed controls/text readable on light/dark fresh launch and after switching,
  focus/disabled states preserved; long translations and core keyboard journey checked.
- [x] Relevant regression and full suites, i18n/typecheck/build, docs/truth/diff and
  canonical clean-source arm64 local CI pass with isolated synthetic data.
- [x] Commit/push main and exact-DMG/native installed QA; executable/source hashes,
  no data loss and restored user preferences recorded. No Release/tag refresh.
- [x] STATUS/registry closure with actual evidence; only then archive and select the
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
- Native **0c7c6fc** repeated the mixed first-light appearance; the child-layout gate alone
  was insufficient. Added deferred initial-settings-read and 1500ms stalled-read fallback
  tests, plus removal of color interpolation from shared core recipes. Initial backend
  preference is now applied before controls mount (native storage may be empty). Theme
  transforms/shadows remain, user toggles still beat late responses. The earlier candidate
  is not accepted; final build/native checks must prove the first launch, not just a toggle.
- Native **70ecb85** cold light and cold dark launch both showed coherent header/nav/control
  colors without a theme roundtrip. Further DE/light journal/edit sampling found two more
  bounded defects: fixed amber-500 quote-quality ink unreadable on light surfaces, and edit
  tracking-start date using Turkish month text in EN/DE. QuoteQuality now shares the tested
  theme warning/muted tokens; all three edit date displays pass the active locale while
  preserving Europe/Istanbul. Red **3 failures** → **31 focused PASS**. A new clean-source
  build is required for these final changes. An accidentally opened weekly-review panel
  revealed separate legacy pale warning text/raw diagnostic codes; no review was saved.
  That panel is outside the selected core form scope and remains a visible follow-up, not
  an all-app translation/accessibility claim.

## Final clean-source and installed acceptance — 2026-10-02

- Implementation sequence pushed on main: **31f11bf / 59ecbd0 / 0c7c6fc / 70ecb85 /
  793cab4**. Final binary source is the full SHA above, not this later docs-only closure.
  Earlier unsuccessful native candidates remain documented as unsuccessful; passing CI
  did not conceal their mixed first-light appearance.
- Final backend **1220 PASS / 3 warnings**; frontend **51 files / 360 PASS**; i18n
  **1274/1274/1274**, TypeScript/production build PASS. Final canonical command:
  `uv run --offline --no-project --with-requirements backend/requirements.lock python
  scripts/run_local_ci.py --expected-architecture arm64 --report dist/p1-wp52-local-ci.json`.
  **13/13 PASS / MERGE READY / provenance COMPLETE**, tracked source tree clean.
- Evidence in `artifacts/evidence/p1-wp52/`: `local-ci.json` SHA-256
  `915bca313742a775ca07de0770e11b6dbc7e966ae2503c674d8075a760d647ae`;
  `exact-dmg-smoke.json`
  `bba6d7df8f2c60ae401841629c780fca5c3fb3c87bc1470903dbb30bee3e9ddb`;
  `n05-preflight.json`
  `02fadb0dc0453d8995a734301c78f4e88f724e971b4cb470964141552ddd24aa`;
  `installed-acceptance.json` contains operator-attested native checks and preservation.
- Native macOS **26.6.2 arm64**, Python **3.11.16**, Node **24.20.0**, npm **11.19.0**,
  uv **0.12.10**, PyInstaller **6.22.2**. Exact read-only mounted-DMG WKWebView/controller
  smoke PASS. DMG `Kuantra-Terminal-1.1.6-wp52-arm64.dmg` SHA-256
  `61f9b61bfc11d936d2373e674b51597f727e59b01cd2498f60c20761a970d3cd`.
  CI, mounted DMG and installed executable all match
  `1f0fae9de0df19e1fe5cd55d91e65bae45774f2922e9efc5a18afdb262dfbb86`.
- `/Applications/Kuantra Terminal.app` is **1.1.6 local source build**, codesign strict/deep
  verification PASS (**ad-hoc, not Developer ID/notarized**). Recoverable preceding bundle:
  `/tmp/kuantra-wp52-final-acceptance.NsYllN/Kuantra Terminal.app`.
  Stopped DB SHA-256 before/after replacement identical:
  `f6bfe9056a04e721e31024b8d59a5778165e98173d374e63d2e55cbec24422c1`.
  Native QA preserved **5 trades / 24 evidence events / 5 tracking projections** and ordered
  trade/event row hashes. No trade save/edit/cancel, data reset/delete/migration or credentials.
- Final binary native checks: cold light and dark header/nav/CTA are coherent; theme and
  language roundtrips preserve readable controls. DE/light and DE/dark journal quote warnings
  readable; DE edit tracking-start shows **18.09.2026, 14:32**, not Turkish month text.
  Tab moves input focus, Escape/cancel close unsaved forms. EN/dark New Trade and EN/light
  journal sampled; TR/light tracking source/wait warning and no-data Dashboard sampled.
  Final normal quit/reopen shows **TR/light/LITE / 3 hidden metrics**, without a theme toggle.
  Native observations are operator attestations (no retained screenshots); disabled/busy/
  error/partial variants are automated DOM/API evidence, not all native scenarios.
- Runtime frozen native **wkwebview**, in-process ASGI/no socket, app visibly running.
  Public market network occurred; `uv --offline` proves dependency resolution only, not
  runtime network isolation. **N05 BLOCKED** remains expected; clean-profile, legal/notices,
  independent gold/FX provider and real XM evidence obligations remain open. No Release/tag,
  workflow or Intel distribution changes.
- Outside-core follow-ups: weekly-review pale warning/raw diagnostic codes, MAE/MFE hardcoded
  English no-history state, existing raw diagnostic BUY/OPEN labels and the prior shutdown
  helper observation are not claimed fixed. Form length/duplicated explanation follows
  selected WP53; all-app accessibility, small-window coverage and broker verification are
  not claimed. Roadmap order and product authority unchanged.
- Docs-only closure checks after archive/WP53 selection: `python3.11 scripts/check_docs.py`
  **139 documents / 187 links / 5 startup PASS**; `check_release_truth.py --tag v1.1.6`,
  `verify_packaging.py` and `git diff --check` PASS; docs/release/packaging regressions
  **34 PASS**. These checks verify the closure change, not a newly built executable.
