<!-- doc-role: archived -->
> Historical reference only. Not a current work order. Unchecked acceptance items remain open;
> see [current status](../../../strategy/STATUS.md). Read only for a relevant task.

# P2-WP04 — Binance Depth Payload Normalization ve Venue Projection

```yaml
document_id: P2-WP04
version: 1.0.0
status: Active
date: 2026-09-06
baseline: a7ac71c
strategy: KPS-001@1.0.0
adr: ADR-0001, ADR-0002
depends_on: P2-WP02 Binance Snapshot + Delta Sequence Validator, P2-WP03 Binance Depth Snapshot/Event Recovery Coordinator
implementation_commits: 80f37e2
```

## Problem

P2-WP02/03 event sırası ve snapshot yarışını güvenli karara bağlıyor; fakat
Binance `b`/`a` level payload'ının float'a çevrilmesi, duplicate price
seviyeleri veya zero-quantity silme semantiği henüz ortak bir adapter
sözleşmesine sahip değil. Mevcut `LimitOrderBook` ise local matching/simulation
motorudur ve venue liquidity projection olarak yeniden kullanılmamalıdır.

## Karar

1. Binance snapshot ve diff event payload'ları `Decimal` tabanlı normalize edilir;
   price/quantity için sentetik varsayılan, float round-trip veya NaN/Infinity
   kabul edilmez.
2. Aynı payload içindeki duplicate price level fail-closed reddedilir. Quantity
   `0` yalnızca mevcut venue level'ını siler; yeni zero level eklenmez.
3. `BinanceDepthBook`, `services.matching.order_book.LimitOrderBook`'tan ayrı bir
   gözlemlenen venue L2 projection'ıdır. Fill, matching, order ID veya execution
   yetkisi taşımaz.
4. Book update ancak P2-WP02 validator'ından `APPLIED` kararı ve aynı final `u`
   değeri geldiğinde kabul edilir. Diğer tüm sequence sonuçları book'u değiştirmez.
5. Projection çıktısı açıkça `source_verified=false` kalır; canonical market
   event persistence ve gerçek transport wiring sonraki paketlerdir.

## Teknik teslimatlar

- `normalize_snapshot` ve `normalize_update` Decimal payload normalizer'ları.
- Duplicate/negative/non-finite/symbol/type validation.
- `BinanceDepthBook` atomic snapshot + sequence-gated level mutation.
- Deterministic string output, best bid/ask ve bounded depth görünümü.
- Matching engine'den ayrı venue projection regression suite.

## Acceptance criteria

- [x] Exact decimal text korunur; float kullanılmaz.
- [x] Snapshot/delta seviyeleri duplicate ve malformed payload'larda fail-closed olur.
- [x] Zero quantity mevcut seviyeyi siler, yeni seviye yaratmaz.
- [x] Sequence `APPLIED` değilse book state değişmez.
- [x] Venue projection local matching engine'e yazmaz.
- [x] Focused suite: `6 passed`.
- [x] Full backend suite: `548 passed, 1 skipped` (Mac local CI, 2026-09-08).
- [ ] Remote CI: GitHub Actions kota/bütçe nedeniyle geçici disabled.

## Kesinlikle kapsam dışı

- Binance websocket/REST network adapter veya reconnect loop.
- Coordinator replay payload'larının persistence'a yazılması.
- Canonical tick/order-book event ledger, Parquet veya DuckDB projection.
- UI, live execution, HFT latency veya source verification promotion.

## Risk ve sonraki sınır

Bu projection yalnızca process içi L2 görünümüdür; restart sonrası replay ve
audit mümkün değildir. Bir sonraki bounded paket coordinator + normalizer +
projection çıktısını canonical append-only market event envelope'ına bağlamalı;
ancak transport ve recovery ölçümleri gerçek testnet/feed ile ayrı bir validation
kapısından geçirilmelidir.

## Değişiklik geçmişi

### 1.0.0 — 2026-09-06

- Decimal tabanlı Binance depth payload normalizer ve sequence-gated venue L2
  projection sözleşmesi tanımlandı.
