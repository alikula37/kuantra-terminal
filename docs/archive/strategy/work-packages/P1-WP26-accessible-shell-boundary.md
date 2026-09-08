<!-- doc-role: archived -->
> Historical reference only. Not a current work order. Unchecked acceptance items remain open;
> see [current status](../../../strategy/STATUS.md). Read only for a relevant task.

# P1-WP26 — U05 Accessible & Understandable Review Shell Boundary

```yaml
work_package: P1-WP26
version: 1.0.0
status: Complete
date: 2026-09-08
baseline_commit: 0a94e22
implementation_commit: 30dfcd7
branch: codex/p1-wp01-evidence-ledger
strategy: KPR-001@current
depends_on: P1-WP25, P1-WP24, P1-WP23
```

## Sonuç

P1-WP26, mevcut Reconciliation Inbox, Trade Evidence Pack ve Weekly Evidence Review
shell'lerinde bounded erişilebilirlik ve anlaşılabilir hata davranışını tamamladı.
Dialog'lar açıldığında ilk focus close kontrolüne taşınır; Escape ile kapanır ve Tab
focus'u dialog içinde tutulur. Loading, error/retry, warning ve decision mesajları
screen-reader için semantik durumlarla görünür kalır. Retry aynı local request'i
yeniden dener; sayfa reload'u, veri silme veya sahte completion yoktur.

Weekly Review numeric count'ları aktif locale ile formatlar; uzun snapshot/rule/error
metinleri kırılarak görünür. EN/TR/DE sözlük parity'si korunur ve visible focus ring
kontrolleri native WebView'da çalışır. `NOT_READY`, `STALE_REVIEW`, `LIMITED`, `READY`
ve `COMPLETED` anlamları değişmez; `UNKNOWN`, `PARTIAL`, `NOT_AVAILABLE` veya
no-data hiçbir yerde PASS/complete/sıfır değildir.

Yeni ledger schema/event, funding/transfer modeli, connector, live execution veya
release/pilot capability'si eklenmedi.

## Acceptance criteria

- [x] Import, reconciliation, Evidence Pack ve weekly review shell'inde keyboard/focus,
  label, visible focus, retry/error ve dialog Escape sınırları test edildi.
- [x] Loading/error/retry/disabled/degraded durumları görünür ve fail-closed; no-data/
  unknown state başarı veya complete olarak gösterilmedi.
- [x] EN/TR/DE parity ve timezone/as-of/numeric rendering regression kontrolleri yeşil.
- [x] Focused red→green testler, full backend/frontend suite ve Mac local CI kaydı
  aynı source commit ile tamamlandı.
- [x] Yeni ledger schema/event, funding/transfer, connector, live order, AI authority
  veya release/pilot claim'i eklenmedi.

## Kesinlikle kapsam dışı

Full-account PnL/tax accounting, funding/transfer ledger schema, yeni venue/connector,
live broker order, AI recommendation/order authority, migration, signing/notarization,
Windows/Linux host proof, pilot ve release kararı.

## Değişen dosyalar

- `frontend/src/components/ReconciliationInbox.tsx`
- `frontend/src/components/TradeEvidencePanel.tsx`
- `frontend/src/components/WeeklyReviewPanel.tsx`
- `frontend/src/components/__tests__/ReconciliationInbox.dom.test.tsx`
- `frontend/src/components/__tests__/TradeEvidencePanel.dom.test.tsx`
- `frontend/src/components/__tests__/WeeklyReviewPanel.dom.test.tsx`
- `frontend/src/hooks/useDialogAccessibility.ts`
- `frontend/src/locales/en.json`
- `frontend/src/locales/tr.json`
- `frontend/src/locales/de.json`

## Kanıt

- Red→green focused shell tests: **14 passed** across the three panels; full frontend
  suite **67 passed** (17 test files), production build PASS; i18n parity **560/560**.
- Full backend suite **634 passed, 2 warnings**. Clean Mac local CI: **MERGE READY**;
  diff-check, compileall, release truth, packaging integrity, locked backend/frontend
  suites, arm64 PyInstaller build, native smoke and provenance contract PASS.
- Local CI report SHA-256 `e1280c20eae290f9d04050aaa0adedb08d2d1cc0e4eefddd2b1aec230fa50bbe`;
  source commit `30dfcd7105d06a13297267e0b938660906921f4e`; tracked source tree
  SHA-256 `74b98749d6cfa65b7704134ae093fdaf2d2cd2ed818fbb2ac204f920ac767351`.
- Lock hashes: backend
  `6291588602869af34e2a4db5d7244a627f4e139cbbd4b034b7cc07d890812399`;
  frontend `b392a59d09ade73564ce082b1a5bc1236618ebeee11703a992980cfd1812882c`.
- Toolchain: macOS arm64, Python 3.11.16, Node v20.20.2, npm 10.8.2,
  uv 0.12.10, PyInstaller 6.22.2. `uv --offline` yalnız locked dependency
  hazırlama/çözümleme kanıtıdır; runtime network-offline kanıtı değildir.
- Local app executable SHA-256 `b07d22760115822d428480c2f0323d88f6a9d447a3b328c147a9777395fa2f42`;
  `.app` artifact SHA-256 `573059e49551fc2151c4b21ed53dfbac4814ae33fb67c49c26abda5d0fd23831`.
- Exact DMG `dist/Kuantra-Terminal-1.4.0-aarch64.dmg` SHA-256
  `01e4813f402efc7f4cc3993b7de3d013d2be7936be32c1c60697affcafea4599`.
  Read-only mount içindeki explicit executable SHA-256 aynı
  `b07d22760115822d428480c2f0323d88f6a9d447a3b328c147a9777395fa2f42`; `wkwebview`,
  controller ready, artifact/executable identity and safe detach PASS. DMG smoke
  report SHA-256 `bcc5ce2668fa2ab17c9ebd000dece071be9d06e996179861df43003e2023f5ac`.
- Release provenance validator PASS; provenance `COMPLETE`. Ad-hoc signing yalnız
  packaging preflight'tir; Developer ID, notarization ve Gatekeeper kanıtı değildir.
- Native smoke default runtime'ın configured public Binance market-data connection'ı
  başlatmayı denedi; bu sonuç offline runtime kanıtı değildir. H03 disabled/degraded
  focused test boundary'si ayrı korunmaktadır.

## Kalan sınırlar ve sonraki bağımlılık

H01 canonical persistence hardening sonraki bounded pakettir. H02/H04–H07, N03–N06
platform evidence, lisans, pilot ve release-owner kararları bu paketten geçilmiş
sayılmaz.

## Değişiklik geçmişi

### 1.0.0 — 2026-09-08

- Review shell keyboard/focus, state semantics, retry/error, locale/numeric and
  long-content boundary'si kanıtlandı.
