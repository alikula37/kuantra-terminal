<!-- doc-role: current-work-package -->
# P1-WP53 — Simpler New Trade and Edit workflow

```yaml
work_package: P1-WP53
status: InProgress
date: 2026-10-02
branch: main
baseline: 793cab419ce4ae3aa3a1ae3eb9ea70b75919981a
```

Next step in the owner-approved UX sequence after completed WP52. **Implemented; final
clean-source CI/build and installed acceptance pending.** One form-presentation task, not a financial-model change.
WP29 external obligations and the observed outside-core translation/lifecycle follow-ups
remain open. Release/tag and Intel refresh are not authorized.

## Starting observations to reproduce

Installed WP52 New Trade has four vertically stacked sections, repeated sizing/tracking
explanations and summary/submit below the initial viewport. Edit similarly requires a long
scroll. Confirm which repetition and navigation actually obstruct completion before editing;
do not hide a required financial/source warning merely to shorten the screen.

## Bounded scope and invariant contracts

- Simplify New Trade and Edit presentation with progressive optional sections, concise
  contextual help, visible summary and discoverable save/cancel. Preserve entered values
  while opening/closing sections; keep error location and keyboard navigation clear.
- Preserve explicit external-record/simulation choice, exact instrument selection, user
  entry time in Europe/Istanbul, open/closed record state, declared USD position value and
  leverage semantics, quote provenance and TP/SL allocation validation.
- Optional note/broker declaration/targets/leverage may be presented progressively only
  where current contract permits. Existing values, partial closures and required exit data
  remain visible/editable according to existing rules; validation errors reveal their fields.
- Preserve revision-conflict handling, reached-target warning, unknown/delayed display-only
  data and local-estimate versus actual-source distinction. Do not weaken automatic-close
  eligibility, silently generate percentages or infer historical broker executions.
- No new automatic financial defaults, silent instrument/provider fallback, accounting/API/
  schema/provider changes, real orders, user-data reset/migration, Release/tag or workflows.
- EN/TR/DE, light/dark, long labels, keyboard focus and readability recipes from WP52 stay
  covered. All-app translation/redesign and chart/tracking clarity are later bounded work.

## Acceptance

- [x] Reproduce the current form-completion obstruction and freeze red behavioral/DOM tests;
  inspect current create/edit validation and payload contracts before changing presentation.
- [x] Required information, safety warnings and explicit choices remain available; progressive
  fields preserve values and expose errors; summary/save/cancel are discoverable.
- [x] Create/edit regressions cover empty/malformed inputs, backdated open/closed entries,
  unknown/delayed price, revision conflict, targets/partial closure and unchanged payloads.
- [ ] EN/TR/DE, keyboard focus and light/dark visual samples pass without hardcoded new text;
  relevant/full suites, i18n/typecheck/build, docs/truth/diff and canonical arm64 CI pass.
- [ ] Commit/push main, clean-source exact-DMG/native smoke and installed acceptance with
  matching hashes, unchanged trade/evidence data and restored preferences. No Release/tag.
- [ ] Update STATUS/registry with actual evidence; archive only after verified acceptance,
  then select chart/tracking clarity under the existing roadmap. External obligations stay open.

## Planned file scope

`frontend/src/components/{NewTradeModal,TradeEditModal}.tsx`, related shared presentation
helpers/styles if necessary, form DOM tests, EN/TR/DE locales, this WP and STATUS/registry.
Backend tests may be run to establish unchanged contracts; backend implementation changes
require a separately evidenced defect and explicit bounded-scope evaluation.

## Implementation evidence — this change

- Installed WP52 form observation and source inspection confirmed summary/save below the
  initial viewport and repeated sizing explanations. No real user trade was saved/changed.
  Added four DOM regressions: fixed actions/native form association, compact draft summary,
  collapsed optional venue persistence and existing-note persistence. **4 red / 34 existing
  green → 38 green**. Two more red tests reproduced hidden allocation/conflict feedback
  after fixed-footer submission; scoped scroll-to-alert behavior → **40 focused green**.
- Create/Edit actions are now outside the scrolling body, with a live compact draft summary.
  New Trade keeps a native form-associated submit button (`form=new-trade-form`), including
  existing busy/unconfirmed-symbol disabling and native validation. Required time/status/
  entry/size, declared leverage and TP/SL controls stay unfolded; only venue/note and read-only
  calculation/detail explanations fold. Values stay mounted and enter the identical payload.
  Existing edit notes open initially; partial-close/revision/close protections stay unchanged.
- Source/unknown/delayed/contract warnings, reached-level warning and tracking disclaimer
  remain outside collapsed explanations; fixed footer reiterates record-only/no broker orders
  and fee/funding exclusion. No leverage multiplication, source fallback, inferred closure,
  new defaults or backend/API/schema changes. Edit compact size uses neutral quantity/size
  wording rather than asserting legacy entries are already USD. EN/TR/DE add three matching
  keys; native presentation acceptance and full gate not yet claimed.
- Full isolated backend: **1220 passed / 3 warnings**; frontend: **51 files / 366 passed**;
  i18n **1277/1277/1277**, TypeScript and production build PASS. `check_docs.py` PASS
  (139 documents / 187 links / 5 startup); release truth v1.1.6, packaging preflight and
  `git diff --check` PASS. Clean-commit CI, exact-DMG and installed acceptance still pending.
