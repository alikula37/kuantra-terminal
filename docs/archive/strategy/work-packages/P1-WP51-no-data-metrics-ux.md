<!-- doc-role: archived -->
# P1-WP51 — Distinguish no data, partial results and measured zero

```yaml
work_package: P1-WP51
status: Complete
date: 2026-10-02
branch: main
baseline: 1326c3e
```

Completed bounded item in the owner-approved UX sequence after completed WP50.
**Implementation, clean-source CI, exact-DMG and installed acceptance verified.** WP29 external obligations
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
- [x] Loading/error/empty/partial/ready states, EN/TR/DE and native visual QA verified.
- [x] Focused and full frontend/backend, i18n/typecheck/build, docs/release truth and
  canonical arm64 local CI with isolated synthetic data.
- [x] Commit/push main, clean-source native arm64/exact-DMG proof and installed-app
  update preserving journal/preferences, exact executable/source identity recorded.
- [x] STATUS/registry closure with real evidence; archive only when criteria verified.

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
data or credentials were used. Previous WP50 binary evidence is not reused as WP51 proof.

## Clean-source delivery and installed acceptance

Implementation **2383cca0e251517af19b3e8e5376de88ec37d407**, pushed `main`.
Canonical command: `uv run --offline --no-project --with-requirements
backend/requirements.lock python scripts/run_local_ci.py --expected-architecture arm64
--report dist/p1-wp51-local-ci.json` → **13/13 PASS / MERGE READY / COMPLETE**;
backend **1220 PASS / 3 warnings**, frontend **48 files / 335 PASS** from this clean source.
macOS **26.6.2 native arm64**, Python **3.11.16**, Node **24.20.0**, npm **11.19.0**,
uv **0.12.10**, PyInstaller **6.22.2**. Tracked tree clean; full tree/lock/toolchain metadata
retained in reports. Docs **137 / 185 links / 5 startup**, truth `v1.1.6` and diff PASS.

`package_macos.sh --architecture arm64 --output dist/Kuantra-Terminal-1.1.6-wp51-arm64.dmg`
with the locked venv Python: hdiutil verify and codesign PASS. `smoke_macos_dmg.py`
selected this exact read-only mounted artifact: native **WKWebView/controller PASS**,
complete source/executable/DMG provenance. N05 preflight exit **2 / BLOCKED** as expected
for ad-hoc/no Developer ID/notarization, not an Apple-trusted distribution claim.

Reports retained under `artifacts/evidence/p1-wp51/`:

- `local-ci.json` SHA-256 `dfb23dea7dcb20354a505db3a2ab6d44bcd167d8829b1ef826c4177681e82677`.
- `exact-dmg-smoke.json` SHA-256 `98d402a596a45303055084d0b93fa6c56a116f4b5817542f4d241c76c97cc68e`.
- `n05-preflight.json` SHA-256 `b01cb5d349e71195b14f32dc5ac26c3cb0a6356b1604c48edaf5d7078aa526da`.
- `installed-acceptance.json`: operator UI/install attestation, not an automated all-app audit.

DMG SHA-256 `fb0c98eac2ebdecaf3fc771ff4dc7fddee8588238521fb2a6abad7081c1bfa7d`;
installed executable **ac56f48b4c22c2274df79099edb0ff6ffcf78f22fb919c8f11c54ee21511231a**
matches CI and exact-DMG smoke. Version **1.1.6 local source build**, running frozen
in-process ASGI/WKWebView; installed summary 200 and native launch successful.
Backup `/tmp/kuantra-wp51-update.5ZvXLa/Kuantra Terminal.app`; stopped DB SHA-256
**7deb63db39421ac6920378170920fb0ea1249c65c9d67f20dc16e8aaca2cf0a8** unchanged across
replacement before launch. Before/after native QA **5 trades / 24 events / 5 tracking
projections**; no saved/edited/canceled trade or user-data reset/migration apply.

Native six-state TR/EN/DE light/dark screenshot and AX inspection at 1440×900 logical:
win rate/drawdown `—` plus the translated no-real-closed-trades note; configured cash
preserved; heatmap says no known results; zero daily activity has its own explicit label.
New labels fit without overlap. Unknown/partial/known-zero and loading/error acceptance
is synthetic API/DOM evidence, not native real-result evidence. Hidden profit factor stays
hidden under the user's settings and is tested in DOM. TR/light/LITE and 3 hidden metrics
restored. No all-app accessibility, small-window or independent-profile acceptance claimed.
Existing dark global CTA contrast and occasional light active-control contrast remain for
the next translation/readability package; earlier orphan-helper observation not closed.
Smoke/native startup opened public market network; no runtime-offline claim. Release/tag,
Intel, N03/N05/H05/legal, real gold/XM gates unchanged. Closure docs/evidence are a docs-only
follow-up; they do not change or relabel the tested binary's implementation source commit.
Closure routing verification: `python3.11 scripts/check_docs.py` **138 documents / 186
links / 5 startup PASS**, release truth `v1.1.6`, packaging preflight and diff PASS;
`test_docs_contract.py`, `test_p0_wp09_release_truth.py`, `test_packaging_spec.py` **28 PASS**.
