<!-- doc-role: archived -->
> Historical reference only. Not a current work order. Unchecked acceptance items remain open;
> see [current status](../../../strategy/STATUS.md). Read only for a relevant task.

# P1-WP25 — U04 Weekly Review & As-of Determinism Boundary

```yaml
work_package: P1-WP25
version: 1.0.0
status: Complete
date: 2026-09-08
baseline_commit: afedb70
implementation_commit: 26751f7
branch: codex/p1-wp01-evidence-ledger
strategy: KPR-001@current
depends_on: P1-WP24, P1-WP23, P1-WP21, P1-WP14
```

## Sonuç

P1-WP25, weekly review'ü belirli period/timezone ve evidence snapshot'ı üzerinden
tekrar üretilebilir hale getirdi. Review, canonical ledger'daki immutable evidence
üzerinden deterministic `review_id` ve snapshot SHA-256 üretir; `occurred_at` ve
`received_at` cutoff sonrasındaki geç event/correction'lar `STALE_REVIEW` olarak
görünür kalır. DST dönüşümü IANA timezone ile UTC boundary'ye deterministik çevrilir.

Rule effective time as-of cutoff'a göre uygulanır; future rule hindsight olarak
applicable rule listesine alınmaz. `UNKNOWN`, `PARTIAL` ve `NOT_AVAILABLE` coverage
downstream'de complete veya finansal başarıya dönüşmez. Empty period `NOT_READY` ve
completion-disabled kalır. Kullanıcı completion/reopen kararı yeni schema/event
eklemeden mevcut `JournalReviewAdded` event'i ile idempotent biçimde kaydedilir;
completion bir kullanıcı eylemidir, finansal doğrulama değildir.

Yeni ledger schema/event, funding/transfer modeli, connector, live execution veya
gerçek kullanıcı verisi eklenmedi. Review API'si period başlangıç/bitişi, IANA
timezone ve as-of cutoff'u explicit ister; Journal'dan bounded Weekly Evidence
Review paneline erişilir.

## Acceptance criteria

- [x] Period, timezone, as-of cutoff ve rule snapshot review/API/export'ta explicit ve deterministic'tir.
- [x] Late correction/re-import eski review snapshot'ını silmez; stale/revision lineage görünür.
- [x] `UNKNOWN`/`PARTIAL`/`NOT_AVAILABLE`/unsupported/malformed evidence no-data sonucunu PASS göstermez.
- [x] Rule effective time hindsight uygulamasını engeller; applicable rule provenance korunur.
- [x] User note ve completion kararı açık audit evidence üretir; completion financial validation değildir.
- [x] Duplicate/replay, DST/timezone ve invalid-boundary testleri aynı snapshot/fail-closed davranışı kanıtlar.
- [x] Focused red→green tests, full backend/frontend suite ve Mac local CI sonucu kaydedilir.

## Kesinlikle kapsam dışı

Full-account PnL/tax accounting, funding/transfer ledger schema, yeni venue/connector,
live broker order, AI recommendation/order authority, migration, signing/notarization,
Windows/Linux host proof, pilot ve release kararı.

## Değişen dosyalar

- `backend/app/api/endpoints.py`
- `backend/app/services/weekly_review.py`
- `backend/tests/test_p1_wp25_weekly_review.py`
- `frontend/src/components/JournalView.tsx`
- `frontend/src/components/WeeklyReviewPanel.tsx`
- `frontend/src/components/__tests__/WeeklyReviewPanel.dom.test.tsx`
- `frontend/src/locales/en.json`
- `frontend/src/locales/tr.json`
- `frontend/src/locales/de.json`

## Kanıt

- Red testleri önce eksik weekly-review service/API/panel import'larını gösterdi.
  Green focused WP25 backend tests **5 passed, 2 warnings**; frontend panel tests
  **2 passed**.
- Full backend suite **634 passed, 2 warnings**; full frontend suite **61 passed**;
  i18n parity **557/557**; production build PASS.
- İlk backend full-suite desktop smoke denemesi, backend testleri ile frontend build
  aynı anda `frontend/dist` yazdığı için controller readiness yarışına takıldı; aynı
  desktop smoke dist sabitken izole **1 passed** ve canonical local CI'da tekrar PASS
  oldu. Bu transient koşul PASS olarak gizlenmedi.
- Clean Mac local CI: **MERGE READY**; diff-check, compileall, release truth,
  packaging integrity, locked backend/frontend suites, arm64 PyInstaller build,
  native smoke and provenance contract PASS. Local CI report SHA-256
  `ef2f6ddf1aec78a3e18606572648f0498f3af6e829b4868b9bfec58caa3ee731`.
- Source commit `26751f72079a80c0589c9cc599b532b5d6bee78e`; tracked source tree
  SHA-256 `224950da874d8ef0a547ae48faf17be02d5f15d8ff82208bc05aca80132fb4aa`.
- Lock hashes: backend
  `6291588602869af34e2a4db5d7244a627f4e139cbbd4b034b7cc07d890812399`;
  frontend `b392a59d09ade73564ce082b1a5bc1236618ebeee11703a992980cfd1812882c`.
- Toolchain: macOS arm64, Python 3.11.16, Node v20.20.2, npm 10.8.2,
  uv 0.12.10, PyInstaller 6.22.2. `uv --offline` yalnız locked dependency
  hazırlama/çözümleme kanıtıdır; runtime network-offline kanıtı değildir.
- Local app executable SHA-256 `7e7763daec32943bf10a9e89d17970729da6cd8498b1d3ce496d33008aa34bdc`;
  `.app` artifact SHA-256 `54f21fa4f066a58686eaa43904b72900040000ee753976813715a744ac42d152`.
- Exact DMG `dist/Kuantra-Terminal-1.4.0-aarch64.dmg` SHA-256
  `3b6a8e748a83e8cb9536959a41a5bbfbaef7c32a23a3e653a97cd72190802103`.
  Read-only mount içindeki explicit executable SHA-256
  `7e7763daec32943bf10a9e89d17970729da6cd8498b1d3ce496d33008aa34bdc`; `wkwebview`,
  controller ready, artifact/executable identity and safe detach PASS. DMG smoke
  report SHA-256 `11b5aa9872461ecd3eb828dcd8f563a0e8238082461f7f8bb414b8ae5baab4dd`.
- Release provenance validator PASS; provenance `COMPLETE`. Ad-hoc signing yalnız
  packaging preflight'tir; Developer ID, notarization ve Gatekeeper kanıtı değildir.
- Native smoke default runtime'ın configured public Binance market-data connection'ı
  başlatmayı denedi; bu sonuç offline runtime kanıtı değildir. H03 disabled/degraded
  focused test boundary'si ayrı korunmaktadır.

## Kalan sınırlar ve sonraki bağımlılık

U05 erişilebilir/anlaşılır shell ve localized state boundary sonraki bounded pakettir.
H01/H02/H04–H07 hardening, N03–N06 platform evidence, lisans, pilot ve release-owner
kararları bu paketten geçilmiş sayılmaz.

## Değişiklik geçmişi

### 1.0.0 — 2026-09-08

- Deterministic weekly review, period/timezone/as-of, late correction, rule effective
  time, fail-closed coverage ve idempotent completion boundary'si kanıtlandı.
