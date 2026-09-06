# P2-WP03 — Binance Depth Snapshot/Event Recovery Coordinator

```yaml
document_id: P2-WP03
version: 1.0.0
status: Active
date: 2026-09-06
baseline: f5f17fd
strategy: KPS-001@1.0.0
adr: ADR-0001, ADR-0002
depends_on: P2-WP02 Binance Snapshot + Delta Sequence Validator
implementation_commits: pending
```

## Problem

P2-WP02 sequence validator'ı tek bir snapshot veya delta event'ini doğru
kararlaştırıyor; ancak Binance'in dokümante ettiği “websocket event'lerini
önce buffer et, REST snapshot al, snapshot ID'sinden eski event'leri at, sonra
replay et” yarışını henüz orkestre etmiyor. Bu koordinasyon olmadan validator'ı
doğrudan websocket loop'una bağlamak snapshot/event penceresinde yanlış gap veya
eksik local book riski yaratır.

## Karar

1. `BinanceDepthRecoveryCoordinator` network ve order-book mutation'dan ayrıdır.
   Transport adapter event'i `ingest_event`, REST sonucu `apply_snapshot` ile
   verir; yalnızca `APPLIED`/`SNAPSHOT_APPLIED` sonucu bir sonraki katmana aktarılır.
2. Snapshot alınmadan önce event'ler bounded `max_buffer_events` deque içinde
   tutulur. Limit aşılırsa buffer temizlenir ve `BUFFER_OVERFLOW` ile yeni
   snapshot cycle zorunlu kılınır; olaylar sessizce düşürülmez.
3. Snapshot'ın `lastUpdateId` değeri ilk buffered event'in `U` değerinden küçükse
   snapshot reddedilmez; `SNAPSHOT_RETRY_REQUIRED` dönülür ve buffer korunur.
4. Snapshot yüklendikten sonra `u <= lastUpdateId` event'leri stale olarak atılır;
   kalan event'ler P2-WP02 validator'ından arrival order ile geçirilir. Replay
   sırasında gap veya malformed event olursa local sequence `RECOVERY_REQUIRED`
   olur ve sentetik onarım yapılmaz.
5. Live gap sonrası yeni event'ler otomatik buffer'a alınmaz. Adapter önce
   `start_buffering()` çağırarak yeni connection/snapshot cycle'ı açıkça başlatır.

## Teknik teslimatlar

- Bounded pre-snapshot event buffer.
- Snapshot-behind retry ve stale buffered event filtering.
- Replay sonrası live hand-off ve explicit recovery state.
- Buffer overflow, malformed event ve live gap telemetry reason code'ları.
- Transport-free coordinator regression suite.

## Acceptance criteria

- [x] Snapshot sonrası buffered event'ler sequence validator üzerinden replay edilir.
- [x] Snapshot ilk event'in `U` değerinin gerisindeyse buffer kaybolmadan retry dönülür.
- [x] `u <= snapshot.lastUpdateId` event'leri açıkça stale sayılır.
- [x] Gap, malformed event ve buffer overflow sentetik veri üretmeden recovery ister.
- [x] Recovery cycle açık `start_buffering()` çağrısı gerektirir.
- [x] Focused suite: `6 passed`.
- [ ] Full backend suite: implementation commit sonrası yeniden çalıştırılacak.
- [ ] Remote CI: GitHub Actions kota/bütçe nedeniyle geçici disabled.

## Kesinlikle kapsam dışı

- Websocket/REST network client, retry/backoff veya rate-limit yönetimi.
- Binance order-book price level mutation ve canonical tick persistence.
- UI, source_verified promotion veya live execution.
- Rust/Tokio data plane ve latency SLA.

## Risk ve sonraki sınır

Coordinator, payload dizilerini (`b`/`a`) uygulamaz ve snapshot'ın içerik
bütünlüğünü doğrulamaz; bunlar transport/book adapter'ının sonraki sözleşmesidir.
Bir sonraki paket, bu coordinator'ı Binance depth websocket + REST adapter'ına
bağlamalı ve snapshot/delta kararlarını canonical market event ledger'ına
append-only olarak yazmalıdır.

## Değişiklik geçmişi

### 1.0.0 — 2026-09-06

- Bounded snapshot/event buffer ve explicit recovery hand-off sözleşmesi tanımlandı.
