<!-- doc-role: current-work-package -->
# P1-WP54 — Chart and local tracking clarity

```yaml
work_package: P1-WP54
status: InProgress
date: 2026-10-02
branch: main
baseline: d87fc99c35be8b961b12150245a5c575ad4e9e75
```

Selected owner-approved UX item after WP53. Presentation implemented; native acceptance pending.
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
- [ ] Clear empty/unknown/partial/delayed/error states and refresh outcome; no invented bars,
  successful automation or financial results; preserve cached content after refresh failure.
- [ ] EN/TR/DE parity, both themes and keyboard controls covered; existing chart/tracking,
  source-identity and read-only regressions pass.
- [ ] Relevant/full suites, typecheck/build/i18n/docs/truth/diff and canonical arm64 CI PASS.
- [ ] Commit/push main, exact-DMG/native smoke, matching installed hashes and unchanged
  journal/evidence/preferences under AGENTS; no Release/tag refresh.
- [ ] Update STATUS/registry with actual evidence, archive only after acceptance and select
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
absence of the actual 640px scatter plot. Full CI/install evidence remains pending.
