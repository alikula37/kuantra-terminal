# P2-WP12 — Bounded Binance Depth Reconnect Session

```yaml
document_id: P2-WP12
version: 1.0.0
status: Active
date: 2026-09-06
baseline: a58bc81
strategy: KPS-001@1.0.0
adr: ADR-0001, ADR-0002
depends_on: P2-WP11 Public Binance Depth Network Adapter
implementation_commits: pending
```

## Problem

P2-WP11 tek bir public REST/WS cycle'ını güvenli biçimde çalıştırıyor; fakat
socket kapanışı veya snapshot request hatası sonrası reconnect davranışı,
backoff bütçesi ve stop kapanışı tanımlı değildi. Sınırsız retry, masaüstü
uygulamasında hem ağ/CPU fırtınası hem de recovery durumunun gizlenmesi riskini
yaratır.

## Karar

1. `BinanceDepthSession` yalnızca `SOURCE_FAILED` ve
   `SNAPSHOT_RETRY_REQUIRED` cycle kararlarını retry eder. Her retry yeni bir
   bounded cycle'dır; ingestor snapshot cycle'ını yeniden başlatır.
2. `max_reconnects`, initial/max exponential backoff ve cycle başına event
   budget policy'de zorunlu ölçülebilir sınırlardır. Bütçe bitince sonuç
   `EXHAUSTED/RECONNECT_BUDGET_EXHAUSTED` olur; `COMPLETED` üretilmez.
3. `PERSISTENCE_FAILED`, `RECOVERY_REQUIRED` ve `SNAPSHOT_REJECTED` terminaldir;
   bunlar retry ile örtülmez. Stop event hem cycle öncesinde hem backoff
   sırasında hızlı kapanış sağlar.
4. Cycle runner protocol'ü injectable'dır. Unit testlerde gerçek network yoktur;
   P2-WP11 adapter production wiring'i aynı sonucu kullanır.
5. Session ve cycle `source_verified=false` kalır; reconnect sayısı kaynak
   doğrulaması anlamına gelmez.

## Teknik teslimatlar

- `BinanceDepthReconnectPolicy` bounded validation.
- Retry/backoff/reconnect budget coordinator.
- Stop-event interruptible backoff.
- Cycle-level result history ve aggregate metrics.
- Source, persistence, recovery, rejection ve exhaustion regression testleri.

## Acceptance criteria

- [x] Source failure sonrası policy bütçesi içinde yeniden cycle çalışıyor.
- [x] Bütçe bitince açık `EXHAUSTED` sonucu dönüyor.
- [x] Persistence/recovery/snapshot rejection retry edilmiyor.
- [x] Stop event cycle öncesinde ve backoff sırasında kapanışı kesiyor.
- [x] Focused suite: `5 passed`.
- [ ] Full backend suite: implementation commit sonrası yeniden çalıştırılacak.
- [ ] Testnet soak, disconnect injection ve sequence continuity ölçümü.
- [ ] Remote CI: GitHub Actions kota/bütçe nedeniyle geçici disabled.

## Kesinlikle kapsam dışı

- Sonsuz retry veya kullanıcıdan gizli reconnect.
- Jitter/remote scheduler, rate-limit quota accounting ve 24-hour rotation.
- `source_verified` terfisi, live latency SLA veya execution.
- UI/API wiring ve Rust data-plane geçişi.

## Risk ve sonraki sınır

Bu paket retry politikasının deterministik sözleşmesini kanıtlar; gerçek Binance
testnet'te uzun süreli socket soak, gap sonrası snapshot continuity ve rate-limit
davranışı henüz ölçülmez. Sonraki paket testnet fixture/soak harness'i, disconnect
enjeksiyonu, reconnect sonrası `last_update_id` ve durable segment continuity
metriklerini üretmelidir.

## Değişiklik geçmişi

### 1.0.0 — 2026-09-06

- Public depth cycle'larını bounded reconnect/backoff policy altında koordine
  eden session katmanı eklendi.
