# P1-WP04 — Projection Read Adapter ve Coverage Gate

```yaml
document_id: P1-WP04
version: 1.0.0
status: Active
date: 2026-09-06
baseline: 34ac164
strategy: KPS-001@1.0.0
adr: ADR-0002, ADR-0003
depends_on: P1-WP03 rebuildable trade projection ve tombstone
implementation_commits: 3fbc5c0
```

## Problem

P1-WP03 ile canonical ledger'dan üretilebilen typed projection geldi; ancak eski
`trades` satırları explicit backfill yapılmadan projection'da bulunmayabilirdi. Bir
endpoint'in yalnız projection'ı, diğerinin yalnız compatibility tablosunu okuması
kullanıcıya sessizce eksik veya farklı journal göstermesi anlamına gelirdi. Ayrıca
canlı journal yazısından sonra projection'ın ayrıca rebuild edilmesi gerekiyorsa
read model güncel kabul edilemezdi.

## Karar

1. `SQLiteDriver.record_trade_with_evidence`, compatibility `trades` satırı,
   canonical `evidence_events` append'i ve typed projection upsert'ini aynı
   `BEGIN IMMEDIATE` transaction'ında commit eder.
2. `TradeReadAdapter` projection'a ancak exact coverage gate geçilirse geçer:
   `trades.id` kümesi ile `(account_id, venue, trade_id)` projection kümesi
   arasında missing veya extra ID bulunmamalıdır.
3. Coverage eksikse adapter bütün isteği compatibility SQLite read path'ine
   yönlendirir; projection ve legacy satırları sessizce birleştirmez.
4. İlk geçişte şu okuma yüzeyleri adapter'a bağlanır:
   - `GET /trades`, `GET /trades/open`, `GET /trades/{trade_id}`
   - portfolio summary, multi-asset breakdown, equity curve ve heatmap
   - `/analytics/quant`
5. `sqlite_driver.insert_trade/update_trade/delete_trade` hâlâ compatibility
   yüzeyidir; bu paket bunları fiziksel olarak kaldırmaz. Yeni production journal
   yazıları `SyncPipeline`/atomic evidence boundary üzerinden devam eder.

## Teknik teslimatlar

- `EvidenceTradeProjectionRepository.upsert_event_in_transaction` ve ortak
  conflict-safe projection upsert SQL'i.
- Exact ID coverage raporu: `trade_count`, `projected_count`, `missing_count`,
  `extra_count`, `ready`.
- `backend/app/services/trade_read_adapter.py` ile dependency-injectable read
  boundary ve kontrollü legacy fallback.
- API/portfolio/quant seçili read path'lerinin adapter'a geçirilmesi.
- Projection güncelliği, transaction rollback, legacy fallback ve coverage sonrası
  projection okuması için regression testleri.

## Acceptance criteria

- [x] Yeni journal yazısı explicit rebuild olmadan typed projection'da görünür.
- [x] Projection upsert'i başarısız olursa compatibility trade ve ledger event'i
  birlikte rollback olur.
- [x] Eksik coverage durumunda hiçbir seçili read path kısmi projection dönmez.
- [x] Coverage tamamlandıktan sonra seçili API ve portfolio/quant okumaları typed
  snapshot'tan gelir.
- [x] Tombstone (`CANCELED`) snapshot'ı adapter üzerinden kaybolmadan görünür.
- [x] Focused projection/read suite: `18 passed`.
- [x] Full backend suite: `372 passed, 1 skipped`.
- [x] `git diff --check` başarılıdır.
- [ ] Remote three-OS CI: GitHub Actions kota/bütçe nedeniyle geçici disabled;
  reset sonrası `3fbc5c0` için yeniden çalıştırılacak.

## Kesinlikle kapsam dışı

- Tüm eski service'lerin tek seferde adapter'a geçirilmesi.
- DuckDB analytics projection'ının canonical ledger'dan rebuild edilmesi.
- Parquet/tick/order-book event store, Rust/Tokio data plane veya Arrow IPC.
- Broker reconciliation, live execution, FIX/DMA ve AI auditor yetki sınırı.
- Compatibility CRUD API'lerinin bu pakette fiziksel olarak silinmesi.

## Migration ve sonraki iş

Eski kurulumlarda önce `evidence-ledger projection-rebuild --dry-run`, rapor
doğrulandıktan sonra `--apply` çalıştırılır. Yeni yazılar projection'ı transaction
içinde güncel tuttuğu için backfill sonrası read adapter otomatik olarak projection'a
geçer. Coverage `ready=false` kaldığı sürece kullanıcı veri kaybetmez; fakat sistem
legacy fallback kullandığını telemetry/log seviyesinde izlemelidir.

Sonraki bounded iş, DuckDB hydrator ve seçili research servislerini canonical
projection/ledger provenance'ına taşımaktır. Bu yapılmadan “tek canonical read model”
iddiası verilmemelidir.

## Değişiklik geçmişi

### 1.0.0 — 2026-09-06

- İlk coverage-gated projection read adapter ve atomic live projection update paketi.
