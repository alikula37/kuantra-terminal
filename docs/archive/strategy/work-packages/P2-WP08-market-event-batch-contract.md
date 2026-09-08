<!-- doc-role: archived -->
> Historical reference only. Not a current work order. Unchecked acceptance items remain open;
> see [current status](../../../strategy/STATUS.md). Read only for a relevant task.

# P2-WP08 — Columnar Market Event Batch Contract

```yaml
document_id: P2-WP08
version: 1.0.0
status: Active
date: 2026-09-06
baseline: da5da7c
strategy: KPS-001@1.0.0
adr: ADR-0001, ADR-0002
depends_on: P2-WP05 Canonical Market Event Envelope ve Hash Chain, P2-WP07 Rotated Market Event Segments ve Manifest Recovery
implementation_commits: 463b847
```

## Problem

Parquet/Arrow runtime'ı mevcut offline doğrulama ortamında kurulu değil; bu
durumda doğrudan sink eklemek test edilmemiş columnar yazma iddiası yaratır.
Buna rağmen envelope → event row/level row şeması belirlenmezse sonraki sink
implementasyonu yeniden semantik karar vermek zorunda kalır.

## Karar

1. `MarketEventBatchProjector` canonical envelope'ları bounded event rows ve
   ayrı level rows'a çevirir. Decimal price/quantity yalnızca canonical string
   olarak taşınır; float veya implicit cast yoktur.
2. Batch yalnızca contiguous chain slice kabul eder; event/level limitleri
   aşılırsa truncation yapmadan fail-closed olur.
3. Batch `batch_sha256` event+level row içeriğinden deterministic üretilir.
   `source_verified` offline bütün batch'lerde false kalır.
4. Bu paket Arrow/Parquet/DuckDB yazmaz. Runtime dependency ve disk sink kararı
   ayrı benchmark/validation kapısından geçmelidir.

## Teknik teslimatlar

- `MarketEventBatchProjector` bounded row projection.
- Event row ve bid/ask level row schema version `MARKET_EVENT_BATCH_V1`.
- Deterministic JSONL preview ve batch hash.
- Contiguous chain, malformed level ve bound regression testleri.

## Acceptance criteria

- [x] Event/level rows canonical envelope hash/provenance alanlarını taşır.
- [x] Decimal level değerleri string olarak korunur.
- [x] Empty batch explicit ve deterministic'tir.
- [x] Bounds veya chain gap truncation olmadan reddedilir.
- [x] Offline `source_verified=false` korunur.
- [x] Focused suite: `5 passed`.
- [x] Full backend suite: `548 passed, 1 skipped` (Mac local CI, 2026-09-08).
- [ ] Remote CI: GitHub Actions kota/bütçe nedeniyle geçici disabled.

## Kesinlikle kapsam dışı

- PyArrow/Polars/DuckDB dependency eklemek veya kurmak.
- Parquet file write, compaction, schema evolution ve query service.
- Binance live transport veya canonical writer wiring.

## Risk ve sonraki sınır

String row contract'ı columnar numeric predicate performansını henüz kanıtlamaz.
Bir sonraki paket, dependency politikası ve gerçek disk benchmark'ı ile Decimal
şema seçimini (DECIMAL veya string) kararlaştırıp yalnızca valid segment batch'leri
Parquet'e yazmalıdır.

## Değişiklik geçmişi

### 1.0.0 — 2026-09-06

- Arrow/Parquet öncesi deterministic event/level row batch sözleşmesi tanımlandı.
