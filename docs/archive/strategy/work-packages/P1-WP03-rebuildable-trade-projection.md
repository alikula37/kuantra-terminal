<!-- doc-role: archived -->
> Historical reference only. Not a current work order. Unchecked acceptance items remain open;
> see [current status](../../../strategy/STATUS.md). Read only for a relevant task.

# P1-WP03 — Rebuildable Trade Projection ve Tombstone

```yaml
document_id: P1-WP03
version: 1.0.0
status: Active
date: 2026-09-06
baseline: 83e8f26
strategy: KPS-001@1.0.0
adr: ADR-0002, ADR-0003
depends_on: P1-WP02 atomic journal evidence write adapter
implementation_commits: ad45281
```

## Problem

Ledger event'leri canonical olsa da önceki journal `trades` compatibility tablosu
rebuild edilebilir bir read model değildi. Fiziksel `DELETE /trades/{id}` de kanıtı kaybediyordu.
Bu durum correction, backup restore ve “aynı ledger'dan aynı journal sonucu çıkar mı?” sorusunu
cevapsız bırakıyordu.

## Karar

1. `evidence_trade_projections` ayrı ve disposable SQLite tablosudur; source-of-record değildir.
2. Rebuild başlamadan önce ledger hash-chain doğrulanır. Invalid ledger veya malformed trade
   snapshot varsa işlem fail-closed olur ve mevcut projection değiştirilmez.
3. `LegacyTradeImported`, `IntentRecorded`, `FillRecorded` ve `TradeCorrected` event'leri
   `received_at_utc,event_id` sırasıyla replay edilir; aynı `(account, venue, trade_id)` için
   son snapshot kazanır.
4. `status=CANCELED` snapshot'ı physical delete yerine `is_tombstone=1` olarak tutulur.
5. `DELETE /trades/{id}` artık `TradeCorrected` tombstone event'i üretir; compatibility row
   korunur ve UI/API kaydın iptal edildiğini açıkça görür.
6. Projection rebuild yalnız explicit CLI ile çalışır:
   `python backend/app/cli.py evidence-ledger projection-rebuild --dry-run|--apply`.

## Teknik teslimatlar

- `backend/app/db/projection_schema.py` ve Alembic `003_trade_projection`.
- `EvidenceTradeProjectionRepository`: ledger verify, deterministic replay, typed validation,
  dry-run/apply, tombstone ve read helpers.
- API delete yolunda soft-cancel/tombstone.
- Projection ve migration regression testleri.

## Acceptance criteria

- [x] `OPEN → CLOSED → CANCELED` event zinciri tek güncel tombstone projection'a replay edilir.
- [x] Aynı ledger iki kez rebuild edildiğinde source event/hash ve snapshot aynıdır.
- [x] Invalid projectable event mevcut projection'ı temizlemeden fail-closed olur.
- [x] API delete fiziksel satır silmez; `CANCELED` event ve compatibility snapshot üretir.
- [x] Alembic head `003_trade_projection` idempotent çalışır.
- [x] Projection focused suite: `5 passed`.
- [x] Full backend suite: `369 passed, 1 skipped`.
- [x] `git diff --check` başarılıdır.
- [ ] Remote three-OS CI: GitHub Actions kota/bütçe nedeniyle geçici disabled; reset sonrası
  `ad45281` için yeniden çalıştırılacak.

## Kesinlikle kapsam dışı

- Mevcut UI/analytics read path'lerinin projection tablosuna geçirilmesi.
- DuckDB'nin projection rebuild'inin ledger'dan beslenmesi.
- CSV batch all-or-nothing transaction veya broker reconciliation.
- Live execution, FIX/DMA, Parquet/tick store, Rust data plane veya AI.

## Açık risk ve sonraki iş

Compatibility `trades` tablosu hâlâ mevcut analytics için okunur; projection henüz tek read
model değildir. Doğrudan `sqlite_driver.delete_trade/update_trade` çağrıları da kod yüzeyinde
duruyor. Sonraki paket, projection read adapter'ını seçili endpoint'lerde devreye alıp direct
CRUD çağrılarını deprecate etmeli ve DuckDB rebuild komutunu canonical projection'a bağlamalıdır.

## Değişiklik geçmişi

### 1.0.0 — 2026-09-06

- İlk typed rebuildable projection, tombstone delete ve explicit projection CLI teslimatı.
