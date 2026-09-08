<!-- doc-role: current-work-package -->
# P1-WP16 — Read-Only Snapshot Completeness

```yaml
work_package: P1-WP16
version: 1.0.0
status: Ready
date: 2026-09-08
baseline_commit: f746132
branch: codex/p1-wp01-evidence-ledger
strategy: KPS-001@1.1.0
depends_on: P1-WP11, P1-WP12
```

## Problem ve sonuç

Timestamp-only pagination `max_timestamp + 1` ile aynı milisaniyedeki henüz
alınmamış kayıtları atlayabilir. Snapshot hash'i bu kaybı tespit etmez. Bu paketin
amacı supported read-only snapshot akışının eksiksizliği kanıtlanamadığında başarılı
complete/reconciled claim üretmesini engellemektir; yeni venue desteği değildir.

Bağlam: [KRR-001 B1/R1](../../archive/strategy/ROADMAP-REVIEW-2026-09-08.md), ADR-0001/0002/0003.

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

- [ ] Bug'ı yakalayan same-timestamp boundary testi önce kırmızı, sonra yeşil.
- [ ] Empty/short/full/repeated/unsorted page; max-pages; missing timestamp testleri.
- [ ] Inclusive until sınırı ve retention/capability belirsizliğinde fail-closed testleri.
- [ ] Incomplete snapshot'ın import/API sonucuna ve reconciliation claim'ine propagation testi.
- [ ] Retry/duplicate/re-import ve canonical snapshot hash regression suite'i.
- [ ] İlgili backend testleri ve tam local CI; network/credential olmadan fixtures.
- [ ] Değişen dosya, exact commit, test sonuçları ve kalan riskler kaydedildi.

## Kapsam dışı

Gerçek hesap veya credential; canlı broker çağrısı; finansal accounting redesign
(R2); yeni connector/market; otomatik migration; P2 soak; AI veya execution.
Venue dokümantasyonu gerekiyorsa yalnız güncel resmi kaynaklar incelenir; test edilmemiş
cursor varsayımı eklenmez. Bu paket henüz uygulanmadı, acceptance kutuları bilerek açıktır.

## Değişiklik geçmişi

### 1.0.0 — 2026-09-08

- Denetim bulgusundan ilk bounded doğruluk paketi oluşturuldu.
