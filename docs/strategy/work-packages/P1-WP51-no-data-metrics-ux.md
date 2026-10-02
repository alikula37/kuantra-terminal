<!-- doc-role: current-work-package -->
# P1-WP51 — Distinguish no data, partial results and measured zero

```yaml
work_package: P1-WP51
status: InProgress
date: 2026-10-02
branch: main
baseline: 1326c3e
```

Selected next bounded item in the owner-approved UX sequence after completed WP50.
**Red tests reproduced; bounded implementation under verification.** WP29 external obligations
remain open. No Release/tag is authorized by this package.

## Verified starting observation

Installed WP50 source efe269b: all five journal records are simulations, no real closed
results. Dashboard shows win rate **0.0% / 0 trades** and maximum drawdown **0.00% / $0.00**,
which look measured despite no qualifying sample. Sharpe already shows unavailable, and
empty equity/asset sections already have honest empty states; preserve those behaviors.

Code inspection: `portfolio_service.py` returns 0.0 win rate when `known_closed` is empty,
and the drawdown helper returns zero without closed trades. `PortfolioKpiGrid.tsx` formats
these values unconditionally. Unknown-PnL counts exist; the win-rate subtitle counts total
closed trades rather than the known-result denominator. Confirm each user-facing path
with red tests before deciding the smallest necessary response/presentation change.

## Bounded scope and boundaries

- Dashboard win-rate/drawdown availability and known-result sample/partial coverage.
  Distinguish empty, all unknown, mixed known/unknown and genuine measured zero.
- Inspect nearby no-data metric labels and actual API consumers; correct only confirmed
  misleading states in this package. Do not replace valid zero cash/exposure with no data.
- Preserve simulation/cancelled exclusion, unknown != zero, existing financial math,
  local estimate vs external result separation and compatibility for API consumers.
- If API coverage metadata is needed, use a bounded additive contract with tests;
  do not silently redefine existing numeric fields or claim complete account performance.
- EN/TR/DE, light/dark, readable labels, loading/error distinct from no data.
- No new analytics engine, provider, connector, order authority, user-data edits/reset,
  schema migration or unapproved Release/tag/Intel build.

## Acceptance

- [x] Reproduce no-data/all-unknown misleading metrics with behavioral red tests; trace
  backend → API → dashboard and any confirmed adjacent consumers.
- [x] Empty/only-simulation/cancelled results do not become measured 0%; all-unknown
  results stay unavailable; partial known results show coverage/denominator; genuine
  zero from a qualifying sample remains zero. Existing formulas remain unchanged.
- [ ] Loading/error/empty/partial/ready states, EN/TR/DE and native visual QA verified.
- [ ] Focused and full frontend/backend, i18n/typecheck/build, docs/release truth and
  canonical arm64 local CI with isolated synthetic data.
- [ ] Commit/push main, clean-source native arm64/exact-DMG proof and installed-app
  update preserving journal/preferences, exact executable/source identity recorded.
- [ ] STATUS/registry closure with real evidence; archive only when criteria verified.

## Next dependencies

After acceptance: approved translation/readability step. WP50's dark global accent and
orphan-helper shutdown observations remain visible in STATUS; neither is silently closed
by preparing this package. WP29 owner-host, gold/XM and signing/legal gates remain separate.

## Implementation and verification (this change)

Backend → `/api/v1/portfolio/summary` → Dashboard/KPI and adjacent asset/heatmap
consumers inspected. Additive `known_pnl_trades`, `realized_pnl_basis` and
`drawdown_pct_basis` preserve all existing numeric fields and arithmetic. `COMPLETE`
means coverage of recorded PnL outcomes only: not broker verification, complete fees,
funding, full-account performance or a claim that configured capital is broker-confirmed.
Without positive configured starting capital the drawdown percentage is unavailable;
known USD drawdown remains visible. Old responses without coverage remain compatible
but cannot silently prove complete results.

KPI win rate/drawdown/profit factor now distinguish no sample/all unknown/partial/known
zero. A flat-only sample cannot measure a 0/0 profit factor. Empty cash-result delta,
all-unpriced open PnL, asset rows without known closed results and empty heatmap total
no longer advertise measured gain/zero; valid configured cash, zero activity/exposure,
known zero and existing simulation separation remain. Today flat outcomes are distinct
from explicitly unknown outcomes. Contradictory daily/coverage responses use the existing
dashboard error/last-valid-snapshot path, never manufactured successful zeros.

Red: 11 backend metadata/API tests and 13 frontend behavioral tests initially failed;
additional cash-delta and overlapping daily-count regressions reproduced and fixed.
Green (macOS arm64, synthetic isolated data): new backend 11, portfolio group **29**,
related WP48/A0 group **52**, full backend **1220 PASS / 3 warnings**. Frontend final
**48 files / 335 PASS**, including 15 no-data DOM and 7 coverage-helper tests;
dashboard malformed response and existing loading/error/snapshot regressions preserved.
`npm --prefix frontend run build`: i18n **1269/1269/1269**, tsc and Vite PASS.
The new API test disables public market startup and verifies unchanged journal/ledger/
tracking counts. An initial red API run did start the existing public Binance websocket;
it was stopped by test teardown, so that run is not runtime-offline evidence. No user
data or credentials were used. Clean-source CI, exact-DMG and installed visual acceptance
remain pending; previous WP50 binary evidence is not reused as WP51 proof.
