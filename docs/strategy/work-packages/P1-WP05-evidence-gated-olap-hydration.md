# P1-WP05 — Evidence-Gated DuckDB OLAP Hydration

```yaml
document_id: P1-WP05
version: 1.0.0
status: Active
date: 2026-09-06
baseline: d80ae9c
strategy: KPS-001@1.0.0
adr: ADR-0002
depends_on: P1-WP04 projection read adapter ve coverage gate
implementation_commits: 7a5b596
```

## Problem

DuckDB hydrator daha önce doğrudan compatibility `trades` tablosunu “canonical”
kabul ediyordu. Bu, evidence backfill'i yapılmamış veya projection'ı eksik eski
satırların OLAP'a sessizce taşınmasına; bozuk DuckDB dosyasının da kanıtsız veriyle
yeniden üretilmesine izin veriyordu. Ürün böyle bir durumda analytics sonucunu
“kanıtlanmış” diye sunmamalıdır.

## Karar

1. `DuckDBHydrator` yalnız `TradeReadAdapter` üzerinden okur.
2. Exact coverage gate geçmezse hydrator hiçbir DuckDB dosyasını silmez/değiştirmez;
   `BLOCKED` + `PROJECTION_COVERAGE_INCOMPLETE` + coverage ayrıntıları döner.
3. Coverage tamamlandığında kaynak açıkça `evidence_trade_projection` olarak raporlanır.
4. P1-WP01 backfill'inin `venue=legacy` çıktısı local journal migration'ında kabul edilir;
   ancak aynı trade ID'nin `local-journal` ve `legacy` venue'larında çift görünmesi
   `duplicate_count` ile gate'i kapatır.
5. Bu paket hydrator'ın source-of-truth sınırını düzeltir; DuckDB içindeki analytics
   sorgularının tümünü veya broker reconciliation'ı yeniden tasarlamaz.

## Teknik teslimatlar

- `DuckDBHydrator` dependency-injectable `TradeReadAdapter` kullanıyor.
- `EvidenceTradeProjectionRepository.coverage` multi-venue exact-ID, missing/extra ve
  duplicate kontrolü yapıyor.
- Legacy backfill sonrası `legacy` venue ile güvenli migration read desteği.
- Kanıtsız compatibility satırını bloklayan ve backfill/rebuild sonrası hydrate eden
  regression testleri.

## Acceptance criteria

- [x] Eksik projection coverage durumunda hydration `BLOCKED` döner.
- [x] Blocked durumda `force_rebuild=True` olsa bile mevcut/olmayan DuckDB dosyası
  değişmez.
- [x] Canonical write path sonrası hydrator `HYDRATED` ve source metadata döner.
- [x] Legacy backfill + projection rebuild sonrası hydration çalışır.
- [x] Aynı trade ID iki migration venue'sunda varsa hydrator/read adapter projection'a
  geçmez.
- [x] Focused hydration/projection suite: `15 passed`.
- [x] Full backend suite: `374 passed, 1 skipped`.
- [x] `git diff --check` başarılıdır.
- [ ] Remote three-OS CI: GitHub Actions kota/bütçe nedeniyle geçici disabled;
  reset sonrası `7a5b596` için yeniden çalıştırılacak.

## Kesinlikle kapsam dışı

- DuckDB'nin merkezi multi-process writer yapılması.
- Parquet/tick/order-book canonical store veya Rust/Tokio data plane.
- DuckDB query API'lerinin tümünün projection provenance'ı ile genişletilmesi.
- Live execution, FIX/DMA, broker reconciliation veya AI auditor.
- Eski compatibility CRUD yüzeylerinin bu pakette kaldırılması.

## Migration / operasyon sözleşmesi

Eski kurulum için güvenli sıra:

1. `evidence-ledger backfill --dry-run`
2. Ayrıştırma raporu incelenerek `evidence-ledger backfill --apply`
3. `evidence-ledger projection-rebuild --dry-run`
4. `evidence-ledger projection-rebuild --apply`
5. Hydrator sonucu `status=HYDRATED` ve `source=evidence_trade_projection` olarak
   doğrulanır.

Coverage tamamlanmadan analytics için DuckDB recovery sonucu başarı olarak
   işaretlenmez. Bu fail-closed davranış kullanıcıya kısa vadede “analytics hazır değil”
   gösterebilir; veri bütünlüğü açısından sessiz yanlış sonuçtan daha güvenlidir.

## Değişiklik geçmişi

### 1.0.0 — 2026-09-06

- İlk evidence-gated DuckDB hydration ve multi-venue coverage gate paketi.
