<!-- doc-role: current-work-package -->
# P1-WP58 — Review revisions and Evidence Pack usability

```yaml
work_package: P1-WP58
status: InProgress
date: 2026-10-03
branch: main
baseline: ab5ee8b
depends_on: P1-WP57
```

Selected in the owner-approved 2026-10-03 sequence; implementation under verification.
First resolve the two actual review-surface findings from WP57, then expose source-linked
plan revisions without representing today's plan as historically valid. Inspect current
ledger/tracking/replay contracts before writing code; refine this bounded contract if
evidence proves a required field unavailable, never fabricate historical state.

## Boundaries

- Salt-okunur grafik/kanıt incelemesi. Gerçekleşme, PnL, MAE/MFE veya kapanış hesabı değişmez.
- Yerel kayıt zamanı, planın broker'da o tarihte geçerli olduğunun kanıtı değildir.
- Güncel referans ve geçmişte kayıtlı revizyon ayrı etiketlenir; önceki mumlara gelecek
  revizyon, gelecekteki kapanış veya sonradan düzeltilmiş seviyeler sızdırılmaz.
- Eski/import kaydında tarihsel plan yoksa UNKNOWN/NOT_AVAILABLE; bugünkü planla doldurulmaz.
- Yerel tahmin ile harici kayıt ayrımı, exact instrument identity ve partial/delayed/gap
  sınırları korunur. Yeni mum/provider, Pine runtime, broker/live order, AI authority yok.
- Gerçek kullanıcı verisinde edit/reset/migration/restore uygulanmaz; sentetik test verisi.
- Native arm64 clean-commit build/install AGENTS'e göre; Release/tag/Intel/workflow ayrı yetki.

## Acceptance

- [ ] WP57 native Evidence Pack PDF clipping reproduced in a responsive layout regression;
      all four export actions remain visible/reachable at 1440x900 and narrower supported views.
- [x] Known market-context reason codes localized EN/TR/DE; raw backend prose does not become
      the primary explanation. Unknown codes retain an honest localized fallback/diagnostic.
- [x] Verified source-event/hash/revision metadata exposed read-only for recorded plan revisions;
      revision/reset lineage and trade/plan scope validated, no guessed backfill.
- [x] Review distinguishes current reference from a selected recorded revision/as-of context;
      no revision before its recorded event time, deterministic UTC boundaries, TR display.
- [x] Before-first-event, same-time, partial-close, correction/reset, missing/invalid lineage,
      open/closed and legacy/import states are tested; trade/ledger/tracking snapshots unchanged.
- [ ] Focused/backend/frontend/i18n/docs and clean canonical arm64 gate pass; exact DMG,
      installed hash, native keyboard/theme/review and normal quit/reopen accepted with data preserved.

## Evidence and next dependencies

Implementation: `TradeEvidencePanel` wraps its export actions; known market-context reasons
are localized, raw diagnostics folded. `LocalTrackingService.history` verifies the chain
and revision/reset links plus the exact producer contract within one SQLite read snapshot. Its producer's hash-bound
`occurred_at_utc` is a **local recording instant**, never broker validity. Review responses
carry separate `recorded_plans` using the candle **opening** instant as conservative UTC
cutoff; equal instants use ledger order. Only eligible revision levels/IDs/hashes/reset
indices leave the reader, no closures/PnL. Scope mismatch, clock regression, missing or
invalid lineage is UNKNOWN; empty/pre-first history is NOT_AVAILABLE. Old entry levels
remain their own snapshot after an entry correction/reset. Current reference remains an
explicit separate choice; rewind hides an ineligible selected revision without fallback.
Existing numerical metrics and recorded-close rules are unchanged, not as-of plan metrics.

Red evidence: two Evidence Pack DOM regressions and two revision-selector DOM regressions;
backend new reader initially absent (collection error). Focused backend **90 PASS**, frontend
**47 PASS** plus dynamic locale **2 PASS**. Actual installed baseline at logical 1440x900 reproduced PDF clipping and
English open-trade context. Full frontend caught a missing dynamic-key test registration;
the new revision status family was registered, not bypassed. Full backend caught a legacy
`timestamp` candle-shape compatibility regression; same-bar `time`/`timestamp` are supported
without a guessed time. Full backend retry **1245 PASS / 3 warnings**; one producer-contract
negative test subsequently added (clean gate includes it). Final frontend **51 files / 382 PASS**.
Typecheck/build/i18n **1329** and docs/diff PASS. Initial clean source **802db05** passed
canonical arm64 **13/13 / COMPLETE**, backend **1246** and frontend **382**. Exact mounted-DMG
smoke passed; installed candidate matched executable **b99e3075…** with user rows unchanged.
Native 1440x900 and ~1028x705 confirmed all four wrapped exports. Public Biquote refresh
returned 301 delayed/partial XAUUSD candles, with independent product check unavailable;
keyboard selector exposed the local event/hash/revision/TR recording instant, not broker
validity. No user trade mutation. Native Tab did not leave the close button under default
WKWebView keyboard settings: **candidate is not final acceptance**. Two additional red DOM
tests pin explicit export traversal and diagnostic-summary wrap. Evidence Pack now opts into
deterministic Tab/Shift+Tab navigation without changing macOS preferences or other dialogs'
navigation mode. Final clean/native acceptance remains pending.

Changed scope: `backend/app/{quant/trade_plan_reference,replay/replay_service,services/local_tracking}.py`,
`backend/tests/test_wp58_recorded_plan_review.py`, EvidencePanel/ReplayCanvas + DOM tests,
frontend types, EN/TR/DE, dynamic locale regression, opt-in dialog accessibility, this WP and STATUS. No DB schema,
provider, financial calculation, execution, release/version or lifecycle implementation change.

Real three-person pilot acceptance and WP29 N03/N05/H05 remain
open. After this package: useful weekly review, then safe in-app backup/restore, each with
its own acceptance contract. Permanent XM import requires an actual anonymized statement;
multi-trade comparison stays demand-gated.
