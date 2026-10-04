<!-- doc-role: archived -->
# P1-WP58 — Review revisions and Evidence Pack usability

```yaml
work_package: P1-WP58
status: Complete
date: 2026-10-03
branch: main
baseline: ab5ee8b
depends_on: P1-WP57
```

Completed with final native acceptance on 2026-10-04 in the owner-approved 2026-10-03 sequence.
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

- [x] WP57 native Evidence Pack PDF clipping reproduced in a responsive layout regression;
      all four export actions remain visible/reachable at 1440x900 and narrower supported views.
- [x] Known market-context reason codes localized EN/TR/DE; raw backend prose does not become
      the primary explanation. Unknown codes retain an honest localized fallback/diagnostic.
- [x] Verified source-event/hash/revision metadata exposed read-only for recorded plan revisions;
      revision/reset lineage and trade/plan scope validated, no guessed backfill.
- [x] Review distinguishes current reference from a selected recorded revision/as-of context;
      no revision before its recorded event time, deterministic UTC boundaries, TR display.
- [x] Before-first-event, same-time, partial-close, correction/reset, missing/invalid lineage,
      open/closed and legacy/import states are tested; trade/ledger/tracking snapshots unchanged.
- [x] Focused/backend/frontend/i18n/docs and clean canonical arm64 gate pass; exact DMG,
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
navigation mode. Second native candidate **a31889b** passed clean gates but background
parent price updates recreated the close callback and reset export focus. A third red
DOM regression reproduced it. Opt-in navigation now retains focus across callback changes
and Escape uses the latest callback; non-opt-in dialogs keep their previous lifecycle.
Third native candidate **f64d702** retained keyboard focus correctly and passed clean gates;
recorded-plan selection exposed another native layout fault: long provenance/revision text
pushed seek/play controls outside an unscrollable review surface. One red layout-contract
DOM regression pins a scrollable bounded root, minimum chart height and retained controls;
the reader is now vertically scrollable, with a non-shrinking controls footer. Actual pixel
acceptance remains native, not inferred from jsdom layout. Final clean/native acceptance
remains pending; prior candidates are not final acceptance.

Fourth candidate **9efd2ea** passed clean CI (1246 backend / 386 frontend) and was installed
with exact hashes/data preservation, but native selection still clipped the footer:
the percent-height flex root and canvas intrinsic size were not bounded by the viewport.
It is **not final native acceptance**. Two red DOM regressions now require a zero-basis
flex root, absolute-contained canvas and a ResizeObserver that updates the chart when
revision text changes allocated space (and disconnects on unmount). Native retry required.
Its first exact-DMG tracking-editor smoke timed out (`None`); two unchanged-artifact
retries passed. Root cause unconfirmed; this is an open repeatability follow-up, not a
fixed timing defect. First failed report retained under `candidate-9efd2ea`.
Container-layout red regressions → focused **52 PASS**, full frontend **51 files / 387 PASS**,
EN/TR/DE **1329**, typecheck/production build/docs/diff PASS. Clean build/native pixel
acceptance must still verify the actual replacement, not jsdom class assertions.
Candidate **ebea2bb** passed clean CI **1246/387**, exact mounted-DMG eight checks and
native long-revision controls at 1440x900 and ~1028x705 (including forward/reset and
vertical scroll). Native theme switching exposed a pre-existing chart-only stale palette:
the surrounding panel changed, the candle canvas did not. One red regression pins in-place
chart/series palette updates without a refetch, cursor reset or chart recreation. Final
native theme acceptance remains pending for its replacement.
Theme red → focused **53 PASS**, full frontend **51 files / 388 PASS**, typecheck,
i18n **1329**, production build/docs/diff PASS; clean source artifact validation follows.

## Final acceptance — 2026-10-04

Final implementation **24c3c5fbce2d0dd9bdceda392b7b16c1a8ab6a5d**, pushed main.
Clean canonical command: `uv run --offline --no-project --with-requirements
backend/requirements.lock python scripts/run_local_ci.py --expected-architecture arm64
--report dist/p1-wp58-theme-local-ci.json`: **13/13 MERGE READY / COMPLETE**, full backend
**1246 PASS / 3 warnings**, frontend **51 files / 388 PASS**, EN/TR/DE **1329**,
typecheck/build/docs/truth/packaging/diff PASS. Python **3.11.16**, Node **24.20.0**,
npm **11.19.0**, uv **0.12.10**, PyInstaller **6.22.2**, macOS **26.6.2 arm64**.
Exact mounted-DMG smoke ran `scripts/smoke_macos_dmg.py` with explicit architecture,
isolated data and `KUANTRA_SMOKE_LOCAL_TRACKING=1`, `KUANTRA_MARKET_DATA_ENABLED=false`:
**8/8 PASS**, readonly mount/detach, actual WKWebView/controller, spawned Evidence Pack,
synthetic CSV/PDF and partial-close/editor/final-local-close. Stream disabled does not
disable public catalog/quote requests; canonical stream connected. **Not runtime-offline evidence.**

Reports under `artifacts/evidence/p1-wp58/`:

- `local-ci.json` SHA-256 **49bd788a64a2c174b1665138a7f4a0ca09a6539420c1b930b885bf8afbae010b**.
- `exact-dmg-smoke.json` **ed04f03d50192689159a56c29f7b2761ef043f916d76a5509d3adb4cf1532dd9**.
- `n05-preflight.json` **ba17032e5ab9638bd0cff28a55ac6ed3b7825cd6de7eb0be813749ce16a5bd9f**:
  **BLOCKED**, not PASS (ad-hoc, no Developer ID/notarization).
- `installed-acceptance.json`: operator observations on the final binary, not prior candidates.

Final DMG **5591b7d8b5d1b54ca50b63453b0df20520895f4912176e43aa5425f5307e65b6**;
CI/mounted/installed executable
**068d1353fd2a23922917676bf53ed630e5956fa3fa03006176fcbe4ec0a4f843**.
Installed `/Applications/Kuantra Terminal.app`, **1.1.6 local source build**, strict/deep
codesign PASS (ad-hoc). Native 1440x900 and ~1028x705: all four exports wrap; Tab reaches
PDF, Shift+Tab CSV, diagnostic summary and Escape work. Localized open context primary;
raw prose folded. Recorded revision/event/hash/TR time visible, current reference distinct.
Long revision/provenance: footer works directly at full width and after vertical scroll
at narrow width; forward/reset verified. Light → dark → light updates candle palette
in place while keeping bar 2 and chosen revision. Settings runtime version verified.
Actual Evidence Pack parent **7301**, worker **7393**, tracker **7392** all exit via normal
Cmd+Q; normal reopen retains **TR/light/LITE**. No manual termination.

Stopped database hash before/after final replacement
**d2ad53ecd74e03cf1cfc459feef2d11508df4e49d2b35ba6fb44cfcd56e48f1f**;
**5 trades / 24 events / 5 tracking** ordered row hashes unchanged after QA/reopen
(exact hashes in operator report). Runtime cache/preferences can change the whole DB;
no claim that the entire DB file stayed unchanged across runtime QA. Previous bundle
recoverable at `/tmp/kuantra-wp58-theme-update.5QSTXL/Kuantra Terminal.app`.
No user trade mutation/reset/restore/migration/credentials/Release/tag/Intel/workflow change.
Closure documents do not change this accepted binary's source commit.

## Open follow-ups, not completed by archiving

- [ ] **Native smoke repeatability:** first 9efd2ea tracking-editor timeout, two unchanged
  retries PASS, root cause unconfirmed. Failed report retained in `candidate-9efd2ea`;
  later successful smoke is not proof the intermittent condition was fixed.
- Real three-person pilot/N03/N05/H05 remain external obligations. Actual XAUUSD download
  was delayed/partial (301 bars, 20425 missing minutes); independent product comparison
  unavailable, not broker or all-gold support verification. Real XM sample still required.
- Next selected implementation is useful weekly review UX; safe in-app backup/restore
  follows under its own preview/validation/confirmation contract, not destructive authority.

Changed scope: `backend/app/{quant/trade_plan_reference,replay/replay_service,services/local_tracking}.py`,
`backend/tests/test_wp58_recorded_plan_review.py`, EvidencePanel/ReplayCanvas + DOM tests,
frontend types, EN/TR/DE, dynamic locale regression, opt-in dialog accessibility, this WP and STATUS. No DB schema,
provider, financial calculation, execution, release/version or lifecycle implementation change.

Real three-person pilot acceptance and WP29 N03/N05/H05 remain
open. After this package: useful weekly review, then safe in-app backup/restore, each with
its own acceptance contract. Permanent XM import requires an actual anonymized statement;
multi-trade comparison stays demand-gated.
