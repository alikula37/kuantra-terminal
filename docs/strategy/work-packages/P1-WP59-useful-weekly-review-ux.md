<!-- doc-role: current-work-package -->
# P1-WP59 — Useful weekly review UX

```yaml
work_package: P1-WP59
status: Ready
date: 2026-10-04
branch: main
baseline: 24c3c5f
depends_on: P1-WP58
```

Selected next in the owner-approved sequence; no WP59 implementation yet. Make the
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

- [ ] Baseline UX findings recorded with failing tests before bounded implementation.
- [ ] Period/as-of guidance and summary use verified response data; UTC/determinism unchanged.
- [ ] No-data/UNKNOWN/PARTIAL/STALE/COMPLETED and true zero are not misrepresented as PASS.
- [ ] Known codes EN/TR/DE; unknown diagnostic fallback honest; no raw primary warnings.
- [ ] Current-input/manual decision and abort/late/cancel/retry regressions remain green.
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
