<!-- doc-role: archived -->
# P1-WP54 — Chart and local tracking clarity

```yaml
work_package: P1-WP54
status: Complete
date: 2026-10-02
branch: main
baseline: d87fc99c35be8b961b12150245a5c575ad4e9e75
```

Owner-approved UX item after WP53. Complete with clean-source CI and installed acceptance.
One presentation task; no new source/automation capability or financial authority.
WP29 owner-host obligations remain open; Release/tag/Intel refresh is not authorized.

## Reproduce before changing

Inspect Market Charts, chart review, MAE/MFE and Local Tracking. The installed MAE/MFE
no-history screen shows English text under Turkish locale; reproduce and cover it.
Identify confusing source/freshness, no-data, partial-history and local-estimate labels from
current code and UI. Do not treat an archived promise as a new capability work order.

## Bounded scope

- Clear EN/TR/DE explanations of chart history, partial/gap/delayed data, exact instrument
  and provider scope, manual refresh outcome and why a local plan is waiting.
- Distinguish current plan reference from historical validity, local estimates from source
  execution, unavailable metrics from genuine zero. Keep warnings readable in both themes.
- Preserve source identity, LIVE/provider-event/60-second eligibility, no synthetic fallback,
  no retrospective inferred closure and read-only chart review. No new automatic refresh,
  paid feed, broker connector, accounting/API/schema defaults or user-data mutation.
- Only change evidenced confusing presentation; keep diagnostic provenance available without
  presenting raw reason codes as the main user explanation. Weekly review and first-use/
  backup/update guidance are separate later work unless needed to resolve a direct dependency.

## Acceptance

- [x] Reproduce bounded defects and freeze red DOM/behavioral tests before implementation.
- [x] Clear empty/unknown/partial/delayed/error states and refresh outcome; no invented bars,
  successful automation or financial results; preserve cached content after refresh failure.
- [x] EN/TR/DE parity, both themes and keyboard controls covered; existing chart/tracking,
  source-identity and read-only regressions pass.
- [x] Relevant/full suites, typecheck/build/i18n/docs/truth/diff and canonical arm64 CI PASS.
- [x] Commit/push main, exact-DMG/native smoke, matching installed hashes and unchanged
  journal/evidence/preferences under AGENTS; no Release/tag refresh.
- [x] Update STATUS/registry with actual evidence, archive only after acceptance and select
  first-use/backup guidance under the approved sequence. External gates remain open.

## Expected files

`frontend/src/components/{MaeMfeVisualizer,LocalTrackingPanel}.tsx`, their DOM tests,
EN/TR/DE locales and current governance documents. Actual Market Charts component is
`TradingViewChart.tsx`; its refresh regression and `TradeReplayCanvas` partial/delayed/
exact-identity/manual-refresh/error-preservation regressions are retained, not rewritten.
Backend behavior changes require a separately reproduced defect and scope review.

## Current evidence

Installed TR/light MAE/MFE no-data state displayed hardcoded English. Four new DOM
regressions failed before implementation (loading/no-data/ready localization and unknown
tracking wait reason/theme-aware ink). Localized primary explanations now distinguish
missing evidence from zero. Raw errors/reason codes remain in collapsed technical details.
READY labels, direction filter and descriptive distribution use EN/TR/DE; no recommended
target or simulated stop execution is asserted. Numerical filtering/calculations unchanged.
Tracking known waits retain localized explanations; unknown waits use a safe localized
fallback rather than a missing translation key. Warning ink uses existing semantic tokens.
Full frontend: **51 files / 370 tests PASS**; backend isolated suite: **1220 PASS / 3 warnings**.
`npm --prefix frontend run build`: typecheck, **1299** EN/TR/DE keys and production build PASS.
`python3.11 scripts/check_docs.py`: **140 documents / 188 links / 5 startup PASS**;
`git diff --check` clean. Changed source: `this change`. CI/native installation pending.
Native candidate dceaf0a revealed `.k-help` overrides Tailwind warning color. A red
DOM assertion freezes the absence of that conflicting recipe on warning text; keep the
14px size through `text-sm` instead. Candidate is not final acceptance; rebuild required.
The initial no-plot test selector was corrected to exclude decorative icon SVGs; it checks
absence of the actual 640px scatter plot. Earlier pending statements above describe intermediate evidence.

## Final acceptance — e15f4e7

Implementation dceaf0a plus native-found warning-recipe fix e15f4e7 pushed main.
Clean binary source **e15f4e7288e1cbf43619d4ca21f849a4504df617**. Canonical arm64
CI **13/13 PASS / MERGE READY / COMPLETE**, same full test counts above. Exact read-only
mounted-DMG native WKWebView/controller smoke PASS. Reports and operator attestation:
`artifacts/evidence/p1-wp54/{local-ci,exact-dmg-smoke,n05-preflight,installed-acceptance}.json`.
CI SHA **64f33ba9…**, exact-DMG report **422df488…**, N05 report **53490d1f…**.
Final DMG SHA **cd0a274bdb47ba678f07f258a98eda73d850ff1aa9b7623eb20b5d18895c3dcc**;
CI/mounted/installed executable **39549dc77d9eee8969232f1a7c1351422f0c67de77d4d86e9480906e5de53927**.
Installed **1.1.6 local build**, codesign strict/deep PASS (ad-hoc).

Final native tracking warning is brown in light / yellow in dark; exact XAUUSD candle
source remains display-only and waiting, not an invented automatic closure. MAE/MFE
TR/dark, DE/dark and EN/light no-data samples, EN loading and keyboard disclosure checked.
READY/sensitivity/error/unknown/partial-history/cache-preservation variants are synthetic
automated evidence, not injected installed data. Screenshots inspected, not retained.
Coordinate input failed with noWindowsAvailable; accessibility Raise/heading/PageDown and
Return worked. No all-app accessibility or live-provider verification claim.

Stopped DB hash identical before/after replacement; **5 trades / 24 events / 5 tracking
projections** and ordered trade/event hashes unchanged after native QA. Normal quit/reopen
preserves **TR/light/LITE, 3 hidden metrics**. Previous candidate backup:
`/tmp/kuantra-wp54-final-update.e2YGih/Kuantra Terminal.app`; previous accepted WP53 bundle
retained at `/tmp/kuantra-wp54-update.OEjmGQ/Kuantra Terminal.app`.
No saved/edited/canceled trades, reset, migration, credentials, Release/tag/workflow/Intel
refresh. Public market network occurred; no runtime-offline claim. **N05 BLOCKED**, all
WP29 external obligations and previous helper lifecycle follow-up unchanged.
Next selected item: first-use/backup guidance under existing roadmap. No WP54 obligation remains.
