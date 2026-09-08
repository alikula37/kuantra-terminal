<!-- doc-role: archived -->
> Historical reference only. Not a current work order. Unchecked acceptance items remain open;
> see [current status](../../../strategy/STATUS.md). Read only for a relevant task.

# P2-WP02 — Binance Snapshot + Delta Sequence Validator

```yaml
document_id: P2-WP02
version: 1.0.0
status: Active
date: 2026-09-06
baseline: f89f653
strategy: KPS-001@1.0.0
adr: ADR-0001, ADR-0002
depends_on: P2-WP01 Sequence Gap-Aware Market Context
implementation_commits: e5c047a
```

## Problem

Kuantra'nın mevcut Binance websocket'i trade ve kline akışını tüketiyor; local
order-book snapshot + diff-depth recovery sözleşmesi bulunmuyor. Bu nedenle bir
sonraki data-plane adımı doğrudan canlı order-book entegrasyonu değil, önce
venue sequence kurallarını saf ve tekrar üretilebilir bir bileşenle sınırlandırmak
olmalıdır.

## Karar

1. Binance diff-depth event'leri local book'a ancak snapshot `lastUpdateId` ile
   ilk event aralığı `U <= lastUpdateId + 1 <= u` koşulunu sağladığında uygulanabilir.
2. Canlı akışta `u <= local_update_id` stale event olarak yok sayılır; event aralığı
   bir sonraki beklenen ID'yi kapsamıyorsa `GAP_DETECTED` üretilir ve local book
   yeniden snapshot alınana kadar güvenilmez sayılır.
3. `pu` taşıyan derivatives/futures akışlarında ilk bridge event'inden sonra
   `pu == önceki u` zorunludur. `pu` kaybı veya uyuşmazlığı gap'tir; sessizce
   atlanmaz.
4. Validator order-book seviyelerini uygulamaz, websocket/REST çağrısı açmaz ve
   eksik event'leri sentetik olarak üretmez. Sadece `APPLIED` kararı book adapter'ına
   uygulama yetkisi verir.
5. Hatalı event, yanlış sembol veya bozuk ID mevcut state'i güvenilir kabul
   etmez; validator `GAP` durumuna geçer. Hatalı snapshot mevcut geçerli snapshot'ı
   değiştirmez.

Kurallar Binance'in [resmi spot diff-depth local order book prosedürü](https://developers.binance.com/en/docs/products/spot/testnet/web-socket-streams)
ile uyumludur. Production entegrasyonu yapılırken seçilen spot/futures venue
belgesinin güncel sürümü ayrıca doğrulanmalıdır.

## Teknik teslimatlar

- `BinanceDepthSequenceValidator`: `COLD → READY → LIVE → GAP` state machine.
- `SNAPSHOT_ACCEPTED`, `APPLIED`, `STALE_IGNORED`, `GAP_DETECTED`,
  `RECOVERY_REQUIRED` ve `REJECTED` kararları.
- Spot `U/u` aralık kontrolü ve derivatives `pu` previous-ID kontrolü.
- JSON-safe sonuç nesnesi ve telemetry için reason code.
- Sembol, event tipi ve non-negative integer ID fail-closed doğrulaması.
- Snapshot/delta/recovery regression testleri.

## Acceptance criteria

- [x] Snapshot bridge (`U <= lastUpdateId + 1 <= u`) uygulanır.
- [x] Stale event local sequence'i değiştirmeden yok sayılır.
- [x] Eksik aralık, `pu` mismatch ve malformed event gap/recovery gerektirir.
- [x] Validator yanlış veya sentetik event uygulamaz.
- [x] Network, live websocket, REST snapshot fetch ve book mutation kapsam dışıdır.
- [x] Focused suite: `7 passed`.
- [x] Full backend suite: `548 passed, 1 skipped` (Mac local CI, 2026-09-08).
- [ ] Remote CI: GitHub Actions kota/bütçe nedeniyle geçici disabled.

## Kesinlikle kapsam dışı

- Binance websocket client'ını depth stream'e bağlamak.
- REST snapshot downloader, reconnect scheduler veya retry/backoff politikası.
- Python `LimitOrderBook` içinde gerçek venue level mutation.
- Rust/Tokio data plane, Arrow IPC/Flight veya latency SLA.
- “Live HFT”, “lossless feed” ya da “source verified” pazarlama iddiası.

## Risk ve sonraki sınır

Bu paket sequence kararını güvenilir hale getirir; ancak event payload'ındaki
price-level dizilerinin uygulanması, bounded buffering, snapshot fetch ile event
buffer yarışının yönetimi, reconnect ve canonical event persistence henüz
uygulanmamıştır. Bir sonraki paket validator'ı Binance depth stream adapter'ına
bağlamalı; `APPLIED` dışındaki tüm sonuçları market context'te unverified olarak
korumalıdır.

## Değişiklik geçmişi

### 1.0.0 — 2026-09-06

- Binance snapshot + diff-depth sequence state machine ve fail-closed recovery
  sözleşmesi tanımlandı.
