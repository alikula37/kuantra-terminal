<!-- doc-role: archived -->
> Historical reference only. Not a current work order. Unchecked acceptance items remain open;
> see [current status](../../../strategy/STATUS.md). Read only for a relevant task.

# P2-WP09 — Injected Binance Depth Ingestor Boundary

```yaml
document_id: P2-WP09
version: 1.0.0
status: Active
date: 2026-09-06
baseline: 8438ffa
strategy: KPS-001@1.0.0
adr: ADR-0001, ADR-0002
depends_on: P2-WP03 Binance Depth Snapshot/Event Recovery Coordinator, P2-WP04 Binance Depth Payload Normalization ve Venue Projection, P2-WP07 Rotated Market Event Segments ve Manifest Recovery
implementation_commits: 57ba6e4
```

## Problem

P2-WP02–08 ayrı ayrı sequence, recovery, Decimal book, canonical envelope ve
durable segment sözleşmelerini kurdu; fakat transport adapter'ın bu parçaları
hangi sırayla kullanacağı henüz tek bir production boundary'de gösterilmedi.
Doğrudan `BinanceStreamClient`'a network kodu eklemek test edilebilir olmayan
canlı iddia riski taşır.

## Karar

1. `BinanceDepthIngestor` yalnızca injected raw snapshot/event ve optional event
   sink kabul eder. Websocket, REST, retry ve credential yönetimi bu sınıfa ait
   değildir.
2. Event path: normalize → sequence coordinator → venue book apply → canonical
   envelope → optional durable sink. Snapshot path aynı sırayı buffer replay ile
   tamamlar; replay event payload'ları coordinator'dan açıkça taşınır.
3. Sequence gap, malformed payload veya recovery state book/sink'e ulaşmaz.
   Sink append hatası `PERSISTENCE_ERROR` durumuna geçirir; sonraki ingest'ler
   başarı gibi görünmez.
4. Optional sink restart edildiğinde mevcut segment event'leri chain'e rehydrate
   edilir. Offline/injected akışta `source_verified=false` kalır.

## Teknik teslimatlar

- Coordinator replay event/sequence hand-off alanları.
- `MarketEventChain.from_events` durable rehydration helper'ı.
- `BinanceDepthIngestor` end-to-end injected boundary.
- Snapshot replay, live gap, malformed payload, restart ve sink failure testleri.

## Acceptance criteria

- [x] Buffer → snapshot → replay → book → chain → segment yolu tek testte geçer.
- [x] Live gap book ve sink state'ini değiştirmez.
- [x] Malformed payload fail-closed olur.
- [x] Segment restart sonrası chain sequence devam eder.
- [x] Sink error sonrası ingest başarı gibi raporlanmaz.
- [x] Focused suite: `5 passed`.
- [x] Full backend suite: `548 passed, 1 skipped` (Mac local CI, 2026-09-08).
- [ ] Remote CI: GitHub Actions kota/bütçe nedeniyle geçici disabled.

## Kesinlikle kapsam dışı

- Binance websocket/REST transport ve gerçek testnet/live bağlantı.
- Retry/backoff, rate limit, listen-key veya credential scope.
- UI/API exposure, source verification promotion veya execution.
- Parquet/Arrow/DuckDB sink.

## Risk ve sonraki sınır

Bu paket live network health veya disk performance SLA kanıtlamaz. Bir sonraki
paket injected interface'i gerçek Binance REST snapshot + websocket depth adapter'a
bağlamalı; testnet fixture, reconnect/gap metrics ve source provenance ölçülmeden
production market-data claim'i açılmamalıdır.

## Değişiklik geçmişi

### 1.0.0 — 2026-09-06

- Sequence/recovery, venue book, event chain ve optional durable sink'i birleştiren
  injected Binance depth ingestor boundary'si tanımlandı.
