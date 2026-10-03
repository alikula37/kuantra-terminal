<!-- doc-role: current-work-package -->
# P1-WP58 — Review revisions and Evidence Pack usability

```yaml
work_package: P1-WP58
status: Ready
date: 2026-10-03
branch: main
baseline: ab5ee8b
depends_on: P1-WP57
```

Selected next in the owner-approved 2026-10-03 sequence. No implementation yet.
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
- [ ] Known market-context reason codes localized EN/TR/DE; raw backend prose does not become
      the primary explanation. Unknown codes retain an honest localized fallback/diagnostic.
- [ ] Verified source-event/hash/revision metadata exposed read-only for recorded plan revisions;
      revision/reset lineage and trade/plan scope validated, no guessed backfill.
- [ ] Review distinguishes current reference from a selected recorded revision/as-of context;
      no revision before its recorded event time, deterministic UTC boundaries, TR display.
- [ ] Before-first-event, same-time, partial-close, correction/reset, missing/invalid lineage,
      open/closed and legacy/import states are tested; trade/ledger/tracking snapshots unchanged.
- [ ] Focused/backend/frontend/i18n/docs and clean canonical arm64 gate pass; exact DMG,
      installed hash, native keyboard/theme/review and normal quit/reopen accepted with data preserved.

## Evidence and next dependencies

No results recorded yet. Real three-person pilot acceptance and WP29 N03/N05/H05 remain
open. After this package: useful weekly review, then safe in-app backup/restore, each with
its own acceptance contract. Permanent XM import requires an actual anonymized statement;
multi-trade comparison stays demand-gated.
