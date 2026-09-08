<!-- doc-role: current-work-package -->
# P1-WP26 — U05 Accessible & Understandable Review Shell Boundary

```yaml
work_package: P1-WP26
version: 1.0.0
status: Ready
date: 2026-09-08
baseline_commit: 26751f7
branch: codex/p1-wp01-evidence-ledger
strategy: KPR-001@current
depends_on: P1-WP25, P1-WP24, P1-WP23
```

## Amaç

P1-WP26, mevcut import/reconciliation/Evidence Pack/weekly review akışlarının
erişilebilir, anlaşılır ve hata durumlarında fail-closed görünmesini doğrular. Paket
new capability, connector, ledger schema/event veya accounting claim eklemez; U05'te
zaten tanımlanmış shell sınırını test edilebilir hale getirir.

## Davranış sözleşmesi

- EN/TR/DE sözlükleri aynı leaf-key setini, boş olmayan metinleri ve aynı interpolation
  parametrelerini korur; fallback anahtar metni yerine güvenli İngilizce açıklama verir.
- Dialog açıldığında başlık, close/retry/action kontrolleri ve form alanları klavye
  ile erişilebilir; focus sırası ve görünür focus göstergesi korunur. Escape/close,
  başarısız request veya loading state veri kaybı ya da sahte completion üretmez.
- `NOT_READY`, `LIMITED`, `STALE_REVIEW`, `READY` ve `COMPLETED` açıkça ayrıdır;
  `UNKNOWN`, `PARTIAL`, `NOT_AVAILABLE` ve no-data hiçbir görünümde PASS/complete
  veya sıfır değere çevrilmez.
- Dar ekran, uzun çeviri, büyük hash, uzun note ve network/error/retry durumları
  taşma veya sessiz kayıp olmadan görünür. Timezone, tarih/saat ve numeric display
  kaydın canonical UTC/as-of anlamını bozmaz.
- Zoom/kontrast ve native WebView davranışı mevcut UI contract'ı içinde doğrulanır;
  yeni browser/renderer veya production capability açılmaz.

## Red test kapsamı

- Weekly Review, Reconciliation Inbox ve Evidence Pack DOM testlerinde role/label,
  visible focus, keyboard tab/close/retry ve loading/error states.
- `NOT_READY`/`STALE_REVIEW`/`LIMITED`/`READY`/`COMPLETED` mapping ve coverage
  propagation; no-data veya unknown hiçbir zaman PASS gibi sunulmaz.
- EN/TR/DE parity, uzun metin, narrow viewport, timezone/as-of ve numeric display
  regression fixture'ları.
- API failure/retry ve disabled/degraded market-data state'lerinde local import,
  review ve export akışlarının kullanılabilir kaldığı negative testler.

## Acceptance criteria

- [ ] Import, reconciliation, Evidence Pack ve weekly review shell'i keyboard/focus,
  label, contrast/zoom ve narrow/long-content testlerini geçer.
- [ ] Loading/error/retry/disabled/degraded durumları görünür ve fail-closed; hiçbir
  no-data/unknown state başarı veya complete olarak gösterilmez.
- [ ] EN/TR/DE parity ve timezone/date/numeric rendering regression testleri yeşildir.
- [ ] Focused red→green testler, full backend/frontend suite ve Mac local CI kaydı
  aynı source commit ile tamamlanır.
- [ ] Yeni ledger schema/event, funding/transfer, connector, live order, AI authority
  veya release/pilot claim'i eklenmez.

## Kesinlikle kapsam dışı

Full-account PnL/tax accounting, funding/transfer ledger schema, yeni venue/connector,
live broker order, AI recommendation/order authority, migration, signing/notarization,
Windows/Linux host proof, pilot ve release kararı.

## İlk uygulama alanı

Önce existing panel DOM contract'ları ve locale fallback davranışı için red test;
sonra yalnız keyboard/focus/status/error görünürlüğü için bounded implementation.
P1-WP26 tamamlanmadan H01–H07 hardening veya release-facing owner kararları
tamamlanmış sayılmaz. H03 network boundary ve P1-WP25 as-of sözleşmesi değişmeden
korunur.
