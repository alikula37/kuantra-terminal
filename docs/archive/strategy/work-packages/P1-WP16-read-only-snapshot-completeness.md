<!-- doc-role: archived -->
> Historical reference only. Not a current work order. Unchecked acceptance items remain open;
> see [current status](../../../strategy/STATUS.md). Read only for a relevant task.

# P1-WP16 — Read-Only Snapshot Completeness

```yaml
work_package: P1-WP16
version: 1.1.0
status: Verified
date: 2026-09-08
baseline_commit: f746132
implementation_commit: ef909d1
branch: codex/p1-wp01-evidence-ledger
strategy: KPS-001@1.1.0
depends_on: P1-WP11, P1-WP12
```

## Problem ve sonuç

Timestamp-only pagination `max_timestamp + 1` ile aynı milisaniyedeki henüz
alınmamış kayıtları atlayabilir. Snapshot hash'i bu kaybı tespit etmez. Bu paketin
amacı supported read-only snapshot akışının eksiksizliği kanıtlanamadığında başarılı
complete/reconciled claim üretmesini engellemektir; yeni venue desteği değildir.

Bağlam: [KRR-001 B1/R1](../ROADMAP-REVIEW-2026-09-08.md), ADR-0001/0002/0003.

## Dosya kapsamı

- `backend/app/services/exchange/read_only_broker_sync.py`
- İlgili read-only sync/import model ve route'ları, yalnız incomplete propagation için.
- İlgili `backend/tests/` fixture ve regression testleri.
- P1-WP12/16 ve strateji kanıt kaydı; unrelated UI/schema refactor yok.

## Davranış sözleşmesi

1. Önce limit'ten fazla aynı timestamp kaydı olan fake client ile bug reproduction.
2. Venue'ya özgü güvenilir cursor/tie-break kanıtı yoksa full-page timestamp sınırı
   `INCOMPLETE`/açık warning ile sonuçlanır; eksik kaydı sessizce atlayıp complete olmaz.
3. Sırasız, tekrarlanan, cursor'ı ilerlemeyen, zamanı eksik ve history-retention kapsamı
   bilinmeyen sayfalar false completeness üretmez. Request/page bütçesi bounded kalır.
4. `until_ms` sınırındaki aynı timestamp kümesi ve request aralığı açıkça tanımlanır;
   bir satırın sınıra ulaşması bütün satırların alındığını kanıtlamaz.
5. Import/persistence davranışı mevcut sözleşmeyle uyumludur; kısmi kanıt saklanırsa
   incomplete durumu downstream'e taşınır, hash/reconciliation başarı etiketiyle örtülmez.
6. Retry/idempotency ve manifest determinism korunur; secret/raw auth log'a girmez.

## Acceptance criteria

- [x] Bug'ı yakalayan same-timestamp boundary testi önce kırmızı (3 failure), sonra yeşil.
- [x] Empty/short/full/repeated/unsorted page; max-pages; missing timestamp testleri.
- [x] Inclusive `until` sınırı ve retention/capability belirsizliğinde fail-closed testleri.
- [x] Incomplete snapshot'ın import/API sonucuna ve reconciliation claim'ine propagation testi.
- [x] Retry/duplicate/re-import ve canonical snapshot hash regression suite'i.
- [x] İlgili backend testleri ve tam local CI; network/credential olmadan fixtures. Backend suite
  `566 passed, 2 warnings`; Mac local CI `MERGE READY` (frontend 51, build/smoke passed).
- [x] Değişen dosya, exact commit, test sonuçları ve kalan riskler kaydedildi: `ef909d1`; B4
  `build_commit=UNKNOWN` provenance obligation remains open.

## Kapsam dışı

Gerçek hesap veya credential; canlı broker çağrısı; finansal accounting redesign
(R2); yeni connector/market; otomatik migration; P2 soak; AI veya execution.
Venue dokümantasyonu gerekiyorsa yalnız güncel resmi kaynaklar incelenir; test edilmemiş
cursor varsayımı eklenmez. Bu paket tamamlandı ve `Verified` olarak arşivlendi; finansal
accounting, fee/unit ve source identity kapsamı sonraki bounded paketlere aittir.

## Değişiklik geçmişi

### 1.0.0 — 2026-09-08

- Denetim bulgusundan ilk bounded doğruluk paketi oluşturuldu.

### 1.0.1 — 2026-09-08

- Inclusive timestamp overlap, page fingerprint, ordering/timestamp/boundary fail-closed
  kontrolleri ve P1-WP12 regression fixture'ları eklendi. Full local CI ve final commit
  kanıtı bu iş tamamlanana kadar açık.

### 1.1.0 — 2026-09-08 — Verified

- `ef909d1` ile backend 566 test, frontend 51 test, arm64 desktop build, WKWebView
  native smoke ve Mac local CI `MERGE READY` kanıtı kaydedildi.
