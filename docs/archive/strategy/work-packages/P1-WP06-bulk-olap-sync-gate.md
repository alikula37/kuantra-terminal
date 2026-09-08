<!-- doc-role: archived -->
> Historical reference only. Not a current work order. Unchecked acceptance items remain open;
> see [current status](../../../strategy/STATUS.md). Read only for a relevant task.

# P1-WP06 — Bulk OLAP Sync Evidence Gate

```yaml
document_id: P1-WP06
version: 1.0.0
status: Active
date: 2026-09-06
baseline: 8a2fbe0
strategy: KPS-001@1.0.0
adr: ADR-0002
depends_on: P1-WP05 evidence-gated DuckDB OLAP hydration
implementation_commits: 99d6ad2
```

## Problem

P1-WP05 hydrator'ı evidence projection'a bağlasa da `SyncPipeline.full_sync()`
ayrı bir bulk yol olarak doğrudan compatibility `trades` listesini DuckDB'ye
taşıyabiliyordu. Bu iki recovery/sync rotasının farklı doğruluk kuralları kullanması
canonical read model iddiasını bozuyordu.

## Karar

1. Bulk sync, mevcut module-level SQLite driver ile oluşturulan aynı coverage-gated
   `TradeReadAdapter` üzerinden çalışır.
2. Coverage `ready=false` ise `full_sync()` DuckDB writer'ını hiç çağırmadan `0`
   döner ve warning log üretir.
3. Coverage hazırsa yalnız typed projection snapshot'ları `sync_all_trades`'a verilir.
4. Live `record_and_sync_trade()` zaten atomic projection update sonrasında tek trade
   sync yaptığı için bu paket onu değiştirmez.

## Acceptance criteria

- [x] Compatibility-only legacy satırı bulk DuckDB sync'e ulaşamaz.
- [x] Coverage tamamlanmış projection bulk sync'te DuckDB writer çağrılır.
- [x] Temp database dependency injection ile iki davranış regression testine alınır.
- [x] Full backend suite: `376 passed, 1 skipped`.
- [x] `git diff --check` başarılıdır.
- [ ] Remote three-OS CI: GitHub Actions kota/bütçe nedeniyle geçici disabled;
  reset sonrası `99d6ad2` için yeniden çalıştırılacak.

## Kesinlikle kapsam dışı

- DuckDB'nin multi-process write modeli veya yeni OLAP şeması.
- Parquet/tick store, Arrow IPC/Flight veya Rust data plane.
- Analytics query endpoint'lerinin tümünü projection metadata ile yeniden yazmak.
- Broker reconciliation, execution, FIX/DMA veya AI.

## Sonraki iş

DuckDB writer/read API'larının provenance ve source coverage bilgisini response'a
taşıması ayrı bir observability paketi olmalıdır. O zamana kadar analytics sonucu
yalnız coverage-gated hydrate/sync sonrasında güvenilir kabul edilir.

## Değişiklik geçmişi

### 1.0.0 — 2026-09-06

- İlk bulk OLAP sync coverage gate ve regression paketi.
