# P2-WP10 — Injected Async Binance Depth Transport Boundary

```yaml
document_id: P2-WP10
version: 1.0.0
status: Active
date: 2026-09-06
baseline: f0a581f
strategy: KPS-001@1.0.0
adr: ADR-0001, ADR-0002
depends_on: P2-WP09 Injected Binance Depth Ingestor Boundary
implementation_commits: pending
```

## Problem

P2-WP09 raw payload hattını tek bir ingestor'da birleştirdi; fakat websocket
event source ile REST snapshot fetcher'ın async lifecycle ve bounded backpressure
sözleşmesi yok. Gerçek `websockets`/HTTP client'ını doğrudan üretim client'ına
eklemek bu yarışları test edilemez hale getirir.

## Karar

1. `BinanceDepthTransport` event source ve snapshot fetcher'ı injected async
   callable/iterable olarak alır. Network client oluşturmaz; bu sayede fixture,
   testnet ve gerçek adapter aynı ingestion boundary'yi kullanır.
2. Event queue bounded'dır; producer queue dolunca bekler, event silently drop
   edilmez. Snapshot fetch başarısızsa cycle `SOURCE_FAILED`, success gibi rapor
   edilmez.
3. Event source exception, stop event, snapshot retry/rejection ve persistence
   error ayrı kararlar olarak döner. `source_verified=false` sabittir.
4. URL builder yalnızca explicit `https://` REST ve `wss://` websocket endpoint'i
   üretir; credential, retry, reconnect ve rate-limit policy gerçek adapter'ın
   sonraki sınırıdır.

## Teknik teslimatlar

- Bounded async producer/consumer queue.
- Injected snapshot/event source lifecycle.
- Safe Binance spot URL contract.
- Snapshot fetch, source failure, stop ve source verification regression testleri.

## Acceptance criteria

- [x] Delayed snapshot sırasında event source queue'ya alınır ve ingestor buffer/replay yapar.
- [x] Snapshot veya event source failure `COMPLETED` olarak raporlanmaz.
- [x] Stop event explicit `STOPPED` sonucu üretir.
- [x] Queue bounded ve event drop policy yoktur.
- [x] REST/WSS URL'leri güvenli scheme ile deterministic üretilir.
- [x] Focused suite: `5 passed`.
- [ ] Full backend suite: implementation commit sonrası yeniden çalıştırılacak.
- [ ] Remote CI: GitHub Actions kota/bütçe nedeniyle geçici disabled.

## Kesinlikle kapsam dışı

- Gerçek `websockets.connect` veya HTTP client entegrasyonu.
- Credential, retry/backoff, reconnect/24-hour rotation ve rate-limit.
- Testnet/live network validation, latency SLA veya source_verified promotion.
- UI/API exposure ve execution.

## Risk ve sonraki sınır

Injected transport lifecycle gerçek network ordering/latency kanıtı değildir.
Bir sonraki paket gerçek Binance testnet adapter'ını bu interface'e bağlamalı;
network fixture replay, reconnect gap metrics ve credential scope gate'leri
geçmeden production stream varsayılanı açılmamalıdır.

## Değişiklik geçmişi

### 1.0.0 — 2026-09-06

- Async event source/snapshot fetcher için bounded, network'süz transport boundary
  sözleşmesi tanımlandı.
