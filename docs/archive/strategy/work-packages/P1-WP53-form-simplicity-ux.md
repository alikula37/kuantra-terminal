<!-- doc-role: archived -->
# P1-WP53 — Simpler New Trade and Edit workflow

```yaml
work_package: P1-WP53
status: Complete
date: 2026-10-02
branch: main
baseline: 793cab419ce4ae3aa3a1ae3eb9ea70b75919981a
```

Owner-approved UX sequence after completed WP52. **Complete with clean-source CI,
exact-DMG and installed acceptance.** One form-presentation task, not a financial-model change.
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
- [x] EN/TR/DE, keyboard focus and light/dark visual samples pass without hardcoded new text;
  relevant/full suites, i18n/typecheck/build, docs/truth/diff and canonical arm64 CI pass.
- [x] Commit/push main, clean-source exact-DMG/native smoke and installed acceptance with
  matching hashes, unchanged trade/evidence data and restored preferences. No Release/tag.
- [x] Update STATUS/registry with actual evidence; archive only after verified acceptance,
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

## Final delivery evidence — d87fc99

- Source **d87fc99c35be8b961b12150245a5c575ad4e9e75**, pushed main. Canonical
  `uv run --offline --no-project --with-requirements backend/requirements.lock python
  scripts/run_local_ci.py --expected-architecture arm64 --report dist/p1-wp53-local-ci.json`:
  **13/13 PASS / MERGE READY / COMPLETE**, clean tracked source. Backend 1220 / frontend 366.
- Native arm64 package from that source and `smoke_macos_dmg.py` against the explicit
  read-only mounted executable PASS. Reports: `artifacts/evidence/p1-wp53/` — local CI
  `d5c54f94…`, exact-DMG `ecbf4dae…`, N05 `0dda9af8…`, installed acceptance attestation.
  DMG **471ce0ba7ae8fb0eb9d0bc996ca43738db1cac01c842d1bbdbdf7be760471d7d**;
  installed executable **919e3610436692a89218d8fe32c0a99ea9fde2c4cf6cce64e12b4f31fb507384**
  matches CI/mounted-DMG. Codesign strict/deep PASS (ad-hoc), version **1.1.6 local build**.
- Native TR/light and EN/light New Trade, DE/dark New Trade/Edit, TR/light Edit samples
  at 1440×900 logical: footer summary/actions visible without initial scrolling and while
  inspecting lower optional details. Native broker/note disclosure Return toggles preserve
  draft values. Empty footer submission invokes native required-entry validation and focuses
  the field without creating a record. Edit reachable via Option+Tab/Return; Escape closes.
  Custom allocation/conflict/partial-close/valid-save states remain isolated DOM/API evidence,
  not mutations of the installed journal. OS validation popover uses OS language (English).
- Old bundle retained at `/tmp/kuantra-wp53-update.xQZLD4/Kuantra Terminal.app`.
  Stopped DB SHA **803dab191661e65f3fd4b1f78b03860d86c1104638f5ad7aaba23750822c7f78**
  unchanged across replacement. After native QA, **5 trades / 24 evidence events / 5 tracking
  projections**, ordered trade/event hashes unchanged. TR/light/LITE and 3 hidden metrics
  verified after normal quit/reopen. No successful trade mutation, reset, migration or secrets.
- Coordinate CUA input reported `noWindowsAvailable`; accessibility/keyboard navigation
  completed the checks; app remained running. Screenshots inspected, not retained as assets.
  No all-small-window/all-app accessibility claim. Public market network occurred; dependency
  resolution offline is not runtime isolation. **N05 BLOCKED**, N03/H05/legal/gold/XM and
  historical helper lifecycle follow-ups remain open. No Release/tag/workflow/Intel refresh.
  Next selected work: WP54 chart/tracking presentation clarity under the existing roadmap.
