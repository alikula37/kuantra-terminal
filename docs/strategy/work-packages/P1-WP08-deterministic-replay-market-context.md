# P1-WP08 — Deterministic Replay ve Market-Context Attachment

```yaml
document_id: P1-WP08
version: 1.0.0
status: Active
date: 2026-09-06
baseline: 3dd08d7
strategy: KPS-001@1.0.0
adr: ADR-0002, ADR-0003
depends_on: P1-WP07 trade evidence pack API
implementation_commits: de93a48
```

## Problem

Replay daha önce doğrudan SQLite compatibility trade okuyor ve bar history ile
ilişkisini hash'lenmiş bir kimlikle taşımıyordu. Aynı trade/context yeniden açıldığında
hangi tarih aralığının, kaç barın ve hangi veri kalitesinin kullanıldığı kullanıcıya
kanıtlanabilir şekilde bağlı değildi. Bu yüzey tick/fill replay değildir; bu sınır
özellikle korunmalıdır.

## Karar

1. Replay trade okuması `TradeReadAdapter` üzerinden yapılır; projection hazırsa
   typed snapshot, değilse açıkça compatibility fallback kullanılır.
2. Replay session, normalize edilmiş trade kimliği + ordered OHLCV context + entry/exit
   index'lerinden SHA-256 `replay_fingerprint` üretir.
3. `market_context` attachment şu alanları taşır: bar/timeframe, UTC context sınırları,
   trade bar sayısı, lookback/lookforward, complete-window flag, source ve limitation'lar.
4. `source_verified=false` ve `quality=BAR_APPROXIMATION` korunur. Bar history yoksa
   `NO_DATA`/`UNAVAILABLE` döner; sentetik candle, fiyat veya latency üretilmez.
5. `GET /api/v1/trades/{trade_id}/market-context` bounded `0..300` lookback/lookforward
   parametreleriyle attachment'ı read-only sunar. Trade Evidence Pack aynı sonucu
   `market_context` alanında iliştirir.

## Teknik teslimatlar

- `market_context_attachment()` deterministic fingerprint ve boundary metadata üretir.
- `ReplaySession` projection-aware trade reader, `replay_fingerprint` ve context taşır.
- `TradeReadAdapter.get_market_context()` bounded candle evidence consumer'ıdır.
- Market-context REST endpoint'i ve replay/evidence regression testleri.

## Acceptance criteria

- [x] Aynı trade ve aynı ordered candle seti aynı fingerprint'i üretir.
- [x] Replay response context boundary, completeness ve quality provenance taşır.
- [x] Replay/read path direct compatibility-only SQLite erişimine bağlı değildir.
- [x] Market context lookback/lookforward `0..300` ile bounded'dir.
- [x] Eksik/conflicting/unaligned candle history fail-closed kalır.
- [x] Evidence Pack market-context sonucunu `READY`, `NO_DATA` veya `UNAVAILABLE`
  olarak açıkça taşır.
- [x] Focused replay/candle/evidence suite: `68 passed`.
- [x] Full backend suite: `379 passed, 1 skipped`.
- [x] `git diff --check` başarılıdır.
- [ ] Remote three-OS CI: GitHub Actions kota/bütçe nedeniyle geçici disabled;
  reset sonrası `de93a48` için yeniden çalıştırılacak.

## Kesinlikle kapsam dışı

- Tick/order-book replay, exchange feed authentication veya broker fill replay.
- Synthetic candle/fiyat/latency fallback'leri.
- Parquet canonical market-data store, Rust/Tokio data plane veya Arrow IPC/Flight.
- AI auditor inference, execution authority veya optimal-exit recommendation.
- Frontend replay redesign; mevcut API sözleşmesi önce pilotta ölçülecek.

## Operasyon ve sonraki iş

Replay fingerprint bir kanıt kimliğidir; tek başına candle kaynağını doğrulanmış yapmaz.
`DUCKDB_CANDLES` legacy source verification hâlâ false'tur. Sonraki bounded paket,
market-data provenance/schema'sını (venue, feed, sequence, ingestion timestamp) kalıcı
hale getirmeli; bu alanlar olmadan “historical market truth” iddiası verilmemelidir.

## Değişiklik geçmişi

### 1.0.0 — 2026-09-06

- İlk projection-aware deterministic replay ve bounded market-context attachment.
