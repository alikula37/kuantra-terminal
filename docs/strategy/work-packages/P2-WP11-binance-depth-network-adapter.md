# P2-WP11 — Public Binance Depth Network Adapter

```yaml
document_id: P2-WP11
version: 1.0.1
status: Active
date: 2026-09-06
baseline: 21b07ad
strategy: KPS-001@1.0.0
adr: ADR-0001, ADR-0002
depends_on: P2-WP10 Injected Async Binance Depth Transport Boundary
implementation_commits: 325819a, b1ceba6
```

## Problem

P2-WP10 bounded producer/consumer ve snapshot lifecycle'ını tanımladı; fakat
bu sınırı gerçek public Binance REST snapshot ve websocket depth bağlantısına
bağlayan bir adapter yoktu. Eski `BinanceStreamClient` trade/kline broadcast'ına
odaklanıyor; canonical depth ingestor, sequence recovery ve durable event
chain'ine bağlı değil.

## Karar

1. `BinanceDepthNetworkAdapter` yalnızca public market-data okur; credential,
   order submission ve execution state'i bu pakete ait değildir.
2. `BinanceDepthNetworkConfig` testnet'i varsayılan endpoint profili yapar.
   Live endpoint ancak `environment=LIVE` veya explicit live URL ile seçilir;
   REST `https://`, websocket `wss://` dışındaki endpoint'ler reddedilir.
3. HTTP status/JSON, websocket UTF-8/JSON/event type/symbol ve message-size
   hataları explicit network error olarak kalır; hiçbir hata synthetic event'e
   dönüştürülmez.
4. Adapter mevcut P2-WP10 transport'una injected client factory'leriyle bağlanır.
   Testler fake HTTP/WS client kullanır; canlı ağ çağrısı CI veya unit testte
   çalıştırılmaz.
5. Timeout ve queue sınırları bounded'dır. Otomatik reconnect, backoff, 24 saat
   bağlantı rotasyonu, source verification terfisi ve latency SLA sonraki
   operasyon paketleridir.

## Teknik teslimatlar

- Testnet varsayılanlı endpoint/timeout/message-bound config.
- `httpx.AsyncClient` ve `websockets.connect` için injectable factory boundary.
- Public snapshot fetch + raw depth websocket decoder.
- P2-WP10 transport/ingestor'a tek cycle adapter wiring'i.
- Yalnız explicit testnet soak opt-in altında tek-seferlik bounded websocket
  disconnect injection sınırı.
- Cross-symbol, non-depth, invalid JSON, UTF-8 ve oversized message fail-closed
  testleri.

## Acceptance criteria

- [x] Testnet endpoint profili varsayılan ve TLS-only doğrulanıyor.
- [x] Public snapshot ve websocket fixture'ı canonical ingestor üzerinden geçiyor.
- [x] HTTP failure `SOURCE_FAILED`; source success gibi raporlanmıyor.
- [x] Malformed/cross-symbol/non-depth/oversized mesajlar açık hata üretiyor.
- [x] Gerçek ağ çağrısı unit testte yok; client factory'leri inject ediliyor.
- [x] Focused suite: `6 passed`.
- [x] Full backend suite: `550 passed, 2 warnings` (Mac local CI, 2026-09-08).
- [ ] Testnet soak/reconnect/source verification promotion.
- [ ] Remote CI: GitHub Actions kota/bütçe nedeniyle geçici disabled.

## Kesinlikle kapsam dışı

- Binance API key, private user stream veya emir gönderme.
- Otomatik reconnect/backoff, rate-limit bütçesi ve 24-hour socket rotation.
- Live endpoint health/latency SLA veya `source_verified=true` üretim terfisi.
- UI/API wiring, Rust data plane ve execution reconciliation.

## Risk ve sonraki sınır

Bu adapter network client'ı gerçekten çağırabilecek kodu sağlar; ancak tek başına
testnet sürekliliği, reconnect sonrası sequence continuity veya disk durability
kanıtı değildir. Sonraki bounded paket testnet soak/reconnect ölçümlerini,
source provenance metriklerini ve failure injection raporunu eklemelidir.
Canlı market-data varsayılanı bu kanıtlar olmadan açılmamalıdır.

## Değişiklik geçmişi

### 1.0.0 — 2026-09-06

- Public Binance REST snapshot ve websocket depth kaynaklarını mevcut injected
  transport/ingestor boundary'sine bağlayan network adapter eklendi.

### 1.0.1 — 2026-09-08

- Testnet soak operatörü için default davranışı değiştirmeyen, bounded ve
  one-shot `disconnect-after` websocket injection sınırı eklendi.
