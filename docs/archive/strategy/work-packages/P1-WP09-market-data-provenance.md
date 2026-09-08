<!-- doc-role: archived -->
> Historical reference only. Not a current work order. Unchecked acceptance items remain open;
> see [current status](../../../strategy/STATUS.md). Read only for a relevant task.

# P1-WP09 — Market-Data Provenance Schema

```yaml
document_id: P1-WP09
version: 1.0.0
status: Active
date: 2026-09-06
baseline: 3bae45a
strategy: KPS-001@1.0.0
adr: ADR-0002, ADR-0003
depends_on: P1-WP08 deterministic replay ve market-context attachment
implementation_commits: 811cb6c
```

## Problem

`market_candles` yalnızca OHLCV ve zaman taşıyordu. Bu nedenle aynı sembol ve
zaman aralığındaki bir barın Binance WebSocket, bir REST adapter'ı veya eski
belirsiz bir import'tan geldiği kalıcı olarak ayırt edilemiyordu. Replay fingerprint
deterministic olsa da veri kaynağı kimliği kanıtlanabilir değildi.

Bu paket tick/order-book doğrulaması yapmaz ve public feed'i otomatik olarak
"verified market truth" ilan etmez. Yalnızca provenance'ın saklanabileceği ve
downstream tüketicilerin eksikliği fail-closed görebileceği tabanı kurar.

## Karar

1. `market_candles` canonical şeması şu alanları taşır:
   - `venue`: normalize edilmiş venue kimliği (`BINANCE`, `UNVERIFIED`, ...).
   - `feed`: feed/transport kimliği (`BINANCE_WS_KLINE`, ...).
   - `source_event_id`: feed'in tekrar üretilebilir olay/klavuz kimliği.
   - `source_sequence`: varsa feed sequence'i; sequence olmayan kline payload'ları
     bunu `NULL` bırakır.
   - `ingested_at`: UTC ingestion zamanı.
   - `source_verified`: yalnızca source adapter'ı açıkça ve deterministically
     doğruladığında `true`; mevcut Binance kline yolu `false` bırakır.
2. Eski dokuz kolonlu DuckDB dosyası additive migration ile açılır. Eski satırlar
   `venue=UNVERIFIED`, `feed=UNVERIFIED`, `source_verified=false` ve migration
   zamanı `ingested_at` ile işaretlenir. Tarihsel satırlar geriye dönük doğrulanmış
   sayılmaz.
3. `DuckDBDriver` ve `DuckDBHydrator` aynı schema helper'ı kullanır. Elle veya
   gelecekteki adapter girişleri explicit timestamp olmadan candle yazamaz; sistem
   mevcut zamanı piyasa zamanı gibi uydurmaz.
4. Evidence/replay, provenance alanlarını fingerprint gövdesine dahil eder.
   Aynı OHLCV dakikasında farklı provenance veya farklı OHLCV varsa satır
   conflict olarak reddedilir; last-write-wins uygulanmaz.
5. Market-context attachment venue/feed, ingestion window, sequence coverage ve
   `provenance_complete` taşır. Tüm barlar açıkça verified değilse
   `source_verified=false` korunur.

## Teknik teslimatlar

- `backend/app/db/market_candle_schema.py`: create + additive migration helper.
- `DuckDBDriver.insert_candles()` için provenance normalization ve validation.
- Adapter uyumluluğu için `insert_market_candle()` ve explicit provenance argümanları.
- Binance closed-kline persistence'inde venue/feed/event id/ingestion timestamp.
- `CandleEvidence` duplicate/conflict ve market-context provenance propagation.
- Eski şema migration, verified identity/timestamp ve replay context regression testleri.

## Acceptance criteria

- [x] Yeni candle kayıtları venue, feed, source sequence, ingestion timestamp ve
  verification state taşıyor.
- [x] Eski dokuz kolonlu DuckDB store destructive rebuild olmadan açılıyor ve
  satırlar explicit `UNVERIFIED` olarak okunuyor.
- [x] Verified candle explicit venue/feed olmadan yazılamıyor.
- [x] Source timestamp olmadan candle yazılamıyor; ingestion zamanı piyasa zamanı
  yerine geçmiyor.
- [x] Provenance aynı timestamp'te değişirse evidence conflict kapısı çalışıyor.
- [x] Replay market-context, provenance completeness ve sequence coverage taşıyor.
- [x] Focused provenance/evidence suite: `46 passed`.
- [x] Full backend suite: `382 passed, 1 skipped`.
- [x] `git diff --check` başarılıdır.
- [ ] Remote three-OS CI: GitHub Actions kota/bütçe nedeniyle geçici disabled;
  reset sonrası `811cb6c` için yeniden çalıştırılacak.

## Kesinlikle kapsam dışı

- Binance sequence recovery, gap detection, reconnect replay veya checksum doğrulaması.
- Tick/order-book canonical store, Parquet lake, Rust/Tokio data plane veya Arrow IPC.
- Broker fill/order lifecycle ile candle provenance'ı otomatik eşleştirme.
- `source_verified=true` için policy dışı adapter override'ı.
- Sentetik timestamp, fiyat, volume veya sequence fallback'i.

## Risk ve sonraki sınır

Bu şema provenance kimliğini saklar; kaynak verinin ekonomik doğruluğunu garanti
etmez. `source_verified` için sonraki bounded paket, gerçek feed sequence/gap
policy'si ve reconnect recovery ile birlikte ele alınmalıdır. O zamana kadar
Binance WebSocket barları identified-but-unverified kalır ve “production market
truth” claim'ine dahil edilmez.

## Değişiklik geçmişi

### 1.0.0 — 2026-09-06

- İlk canonical market-candle provenance schema, migration, evidence propagation
  ve regression gate.
