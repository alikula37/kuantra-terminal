<!-- doc-role: current-work-package -->
# P1-WP59 — Useful weekly review UX

```yaml
work_package: P1-WP59
status: InProgress
date: 2026-10-04
branch: main
baseline: 24c3c5f
depends_on: P1-WP58
```

Selected in the owner-approved sequence. Make the
existing weekly evidence review understandable and usable, not a new financial/AI engine.

## Inspected baseline and bounded scope

`WeeklyReviewPanel.tsx` already defaults to a seven-day Europe/Istanbul period and
supplies UTC as-of, explicit manual COMPLETE/REOPEN and an input-key freshness guard.
It validates response shape and aborts stale loads. Current surface still displays raw
coverage field/state keys and warning codes, a technical UTC as-of entry and small text.
`weekly_review.py` supplies verified counts, coverage, warnings and `is_pass=false`;
completed review does **not** certify complete economic evidence. Preserve these contracts.

- Explain review period and as-of cutoff in Istanbul time without changing UTC storage,
  inclusive/exclusive period semantics or deterministic backend identity.
- Guide the user with existing counts, applicable recorded rules and missing coverage.
  No invented PnL, fee/funding, percentage success, profitable outcome or recommendations.
- Localize known review/coverage/warning codes EN/TR/DE. Unknown codes get an honest
  localized fallback and folded raw diagnostics, never an invented successful state.
- Distinguish no records, unknown/partial evidence, stale review and manual completion.
  Completing the user's review is not PASS or broker/accounting verification.
- Keep explicit decisions, note limit, current-input guard and async abort/late/retry
  behavior; changed period/timezone/as-of must not allow completing the old snapshot.
- Standard readable sizes, wrapping, light/dark and keyboard access. Inspect actual
  WKWebView behavior; opt-in dialog navigation only if justified by a red regression.

## Boundaries

No new schema/provider/connector/Pine/AI/order authority, historical fills, funding
inference, financial formulas, automatic decisions or broker verification. Real installed
records stay read-only; decision mutations tested in isolated synthetic data. No user
reset/delete/restore/migration or Release/tag/workflow/Intel/signing change. Existing WP29
owner-host obligations and WP58 smoke-repeatability follow-up remain open.

## Acceptance

- [x] Baseline UX findings recorded with failing tests before bounded implementation.
- [x] Period/as-of guidance and summary use verified response data; UTC/determinism unchanged.
- [x] No-data/UNKNOWN/PARTIAL/STALE/COMPLETED and true zero are not misrepresented as PASS.
- [x] Known codes EN/TR/DE; unknown diagnostic fallback honest; no raw primary warnings.
- [x] Current-input/manual decision and abort/late/cancel/retry regressions remain green.
- [ ] Readable responsive light/dark, keyboard controls and native scroll reachability verified.
- [ ] Full relevant backend/frontend/i18n/docs and clean canonical native arm64 CI; exact DMG
      and installed hashes, normal quit/reopen and core user-row preservation verified.
- [ ] STATUS/registry updated with commands, exact counts/hashes and limitations; commit/push
      main and installed update under standing instruction; no Release/tag refresh.

## File scope and verification

Primary: `frontend/src/components/WeeklyReviewPanel.tsx`, its DOM tests, EN/TR/DE and
dynamic locale regression; helper/types only where required by the existing API. Read
backend weekly-review/endpoint tests to preserve coverage and decision gates; any discovered
backend correctness defect needs a separately described red test and bounded scope.
Use synthetic no-data/unknown/partial/stale/complete payloads and failures. Run focused
DOM + weekly backend regressions, full suites/i18n/build, `python3.11 scripts/check_docs.py`,
diff/release-truth and canonical locked offline-resolution CI. Native operator acceptance
must not write decisions into the real user journal. After this WP, safe in-app backup/
restore requires its own contract; it is not implemented or authorized to apply here.

## Current implementation evidence (2026-10-04)

Baseline installed WKWebView TR/light showed raw NOT_READY/NOT_AVAILABLE, coverage field
names and NO_EVIDENCE/FEES/FUNDING/MARKET codes; pale warnings, small fixed-dark recipes
and technical UTC input. Seven added DOM regressions failed before implementation.
This change uses standard semantic theme recipes; returned snapshot counts (including
malformed events and rule references); localized known state/coverage/warning maps and
honest unknown fallback with folded raw diagnostics. Loaded start/end/cutoff displayed
in Europe/Istanbul; advanced IANA/UTC inputs preserved without rounding or changing UTC
identity. Inclusive start/exclusive end and recorded evidence vs financial verdict explicit.
Manual decisions retain freshness/abort guards; unknown/NOT_READY/STALE status cannot
complete even if an unexpected response flags permission. No backend/schema/formula change.
Full/native/install acceptance remains pending; no completed claim yet.

Additional red regression: prototype-like unknown code crashed translation lookup; explicit
own-key lookup now rejects it. Two red focus/Tab regressions justified opting this panel
into existing native navigation; folded details children are skipped, summary stays reachable,
parent quote callbacks do not reset note focus and Escape uses the latest callback.
Manual "use current cutoff" invalidates the old review without auto-load/decision. Folded
advanced UTC input retains original precision. Note max 500 and explicit COMPLETE/REOPEN
API body unchanged. No installed-profile decisions written.
Focused WeeklyReview/Evidence/localization: **51 PASS** (28 weekly, 20 Evidence, 3 locale).
Full frontend **51 files / 409 PASS**, i18n **1370** each EN/TR/DE, TypeScript and production
build PASS. Backend weekly regression **5 PASS / 2 warnings**. Earlier dirty canonical
candidate had **1246 backend / 3 warnings**, 13/13 MERGE READY, but predates final focus/
cutoff/code-lookup adjustments and is **not final binary acceptance**. Clean source CI,
exact DMG, N05 boundary and installed read-only acceptance follow this implementation commit.
