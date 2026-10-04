<!-- doc-role: archived -->
# P1-WP59 — Useful weekly review UX

```yaml
work_package: P1-WP59
status: Complete
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
- [x] Readable responsive light/dark, keyboard controls and native scroll reachability verified.
- [x] Full relevant backend/frontend/i18n/docs and clean canonical native arm64 CI; exact DMG
      and installed hashes, normal quit/reopen and core user-row preservation verified.
- [x] STATUS/registry updated with commands, exact counts/hashes and limitations; commit/push
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
Implementation-stage evidence below is followed by final clean/native/install acceptance.

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

## Final acceptance — 2026-10-04

Implementation **3b773515dc2789ff9d094eba8c73ca8b0dd94668**, pushed main. Clean canonical:
`uv run --offline --no-project --with-requirements backend/requirements.lock python
scripts/run_local_ci.py --expected-architecture arm64 --report
dist/p1-wp59-committed-local-ci.json`: **13/13 MERGE READY / COMPLETE**, full backend
**1246 PASS / 3 warnings**, frontend **51 files / 409 PASS**, i18n **1370** each EN/TR/DE,
typecheck/build/docs/release-truth/packaging/diff PASS. Python **3.11.16**, Node **24.20.0**,
npm **11.19.0**, uv **0.12.10**, PyInstaller **6.22.2**, macOS **26.6.2 arm64**.

`PYTHON_BIN=python3.11 bash scripts/package_macos.sh --architecture arm64 --output
dist/Kuantra-Terminal-1.1.6-wp59-arm64.dmg`; exact read-only mounted-DMG smoke via
`KUANTRA_MARKET_DATA_ENABLED=false KUANTRA_SMOKE_LOCAL_TRACKING=1 uv run --offline
--no-project --with-requirements backend/requirements.lock python scripts/smoke_macos_dmg.py
--dmg dist/Kuantra-Terminal-1.1.6-wp59-arm64.dmg --expected-architecture arm64
--report dist/p1-wp59-exact-dmg-smoke.json`: **8/8 PASS / COMPLETE**, actual WKWebView/controller,
CSV/PDF, spawned Evidence Pack and synthetic partial-close/editor/final-local-close.
Mount detached safely. Runtime public network occurred; uv offline is resolution only.
N05 distribution preflight **BLOCKED**, not PASS: ad-hoc, no Developer ID/notarization.
Previous WP58 intermittent tracking-editor smoke follow-up remains open despite this PASS.

Persistent evidence: `artifacts/evidence/p1-wp59/`.

| Report | SHA-256 |
| --- | --- |
| local-ci.json | 5c5a78f960be674080c46eac152a721ac46fdb9dd4cd6a9ef8fe6111d9e72701 |
| exact-dmg-smoke.json | 18e5f272f2ea9769c9416f0d37233fc4b9d946656fc815f59f4786eab8216163 |
| n05-preflight.json | 9e566e8d3beed1665519a55696b341162ff0c0c3dcdfaa809f4bc9374d9b39c0 |
| installed-acceptance.json | 950d7117a2d62b3794aa9f3ea251998f6589f407ba28cf7e6693e2f7c78fc110 |

CI/smoke copies are JSON-equivalent to raw dist reports with an added final LF, not
byte-identical. Raw CI hash **23a05243098301f8e0ef6349378787a19a233d7990436156a9562dffd79176e8**;
raw smoke **ba178be0e5a0502429e03c477238e3cae1c1f250fe4e1e50704f8a521fc6efc3**.
DMG SHA-256 **502de48b667b1fe4e3ce8e440d1c3878bd93c189ae6dd42ff0dd18561ec5d2ef**.
CI/mounted/installed executable SHA-256
**5a97624748f7539feeb41baaa90efce9c2edde73416fd4fac5693c498e6f4aa9**.

Installed `/Applications/Kuantra Terminal.app`: Settings runtime **1.1.6 local source build**,
strict/deep ad-hoc codesign PASS. Native TR light/dark, DE dark, EN light, 1440x900 and
~1060x715 scrolling, folded advanced settings/diagnostics, explicit cutoff invalidation,
Tab/Return/Escape and disabled completion accepted. Installed period contained no review
evidence; partial/unknown/stale/completed/manual-decision/error cases are isolated DOM/backend
evidence, not real-profile financial acceptance. No real review decision/note/trade saved.
Normal Cmd+Q parent **13451** exited without manual termination; normal reopen **TR/light/LITE**.
Previous bundle `/tmp/kuantra-wp59-update.GuUne2/Kuantra Terminal.app` is recoverable.
Stopped database SHA unchanged across replacement; **5 trades / 24 events / 5 tracking**
canonical row hashes unchanged after QA and normal reopen (recorded in installed acceptance).
Runtime cache/preferences may change; no whole-DB-unchanged claim across runtime QA.
No Release/tag/Intel/workflow/credential/user reset/delete/restore/migration change.
N03/N05/H05/legal/gold/XM/actual pilot obligations stay open. Closure docs do not change binary.
Next selected bounded work: WP60 safe in-app backup and restore **preview**, Ready; actual
restore apply requires a separate recovery/explicit-confirmation contract and is not implemented.
Closure validation: `python3.11 scripts/check_docs.py` **146 documents / 193 links / 5 startup**
PASS; `python3.11 scripts/check_release_truth.py`, `python3.11 scripts/verify_packaging.py`
and `git diff --check` PASS. Only documentation/evidence changes follow the accepted binary.
