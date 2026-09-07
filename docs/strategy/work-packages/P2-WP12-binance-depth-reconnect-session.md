# P2-WP12 — Bounded Binance Depth Reconnect Session

```yaml
document_id: P2-WP12
version: 1.1.0
status: Active
date: 2026-09-07
baseline: a58bc81
strategy: KPS-001@1.0.0
adr: ADR-0001, ADR-0002
depends_on: P2-WP11 Public Binance Depth Network Adapter
implementation_commits: 9bee5f4, 078dc02
```

## Problem

P2-WP11 tek bir public REST/WS cycle'ını güvenli biçimde çalıştırıyor; fakat
socket kapanışı veya snapshot request hatası sonrası reconnect davranışı,
backoff bütçesi ve stop kapanışı tanımlı değildi. Sınırsız retry, masaüstü
uygulamasında hem ağ/CPU fırtınası hem de recovery durumunun gizlenmesi riskini
yaratır.

## Karar

1. Varsayılan olarak `BinanceDepthSession` yalnızca `SOURCE_FAILED` ve
   `SNAPSHOT_RETRY_REQUIRED` cycle kararlarını retry eder. `retry_recovery=true`
   açıkça seçilirse `RECOVERY_REQUIRED` da aynı bounded reconnect bütçesi içinde
   yeni snapshot cycle'ı olarak denenir; varsayılan sessizce değişmez.
2. `max_reconnects`, initial/max exponential backoff ve cycle başına event
   budget policy'de zorunlu ölçülebilir sınırlardır. Bütçe bitince sonuç
   `EXHAUSTED/RECONNECT_BUDGET_EXHAUSTED` olur; `COMPLETED` üretilmez.
3. `PERSISTENCE_FAILED` ve `SNAPSHOT_REJECTED` her zaman terminaldir.
   `RECOVERY_REQUIRED`, `retry_recovery=false` iken terminal; açıkken aynı
   reconnect bütçesine tabi bounded retry'dır. Stop event hem cycle öncesinde
   hem backoff sırasında hızlı kapanış sağlar.
4. Cycle runner protocol'ü injectable'dır. Unit testlerde gerçek network yoktur;
   P2-WP11 adapter production wiring'i aynı sonucu kullanır.
5. Session ve cycle `source_verified=false` kalır; reconnect sayısı kaynak
   doğrulaması anlamına gelmez.

## Teknik teslimatlar

- `BinanceDepthReconnectPolicy` bounded validation.
- Retry/backoff/reconnect budget coordinator.
- Sequence-gap sonrası yalnızca explicit `retry_recovery` ile bounded resnapshot.
- Stop-event interruptible backoff.
- Cycle-level result history ve aggregate metrics.
- Source, persistence, recovery, rejection ve exhaustion regression testleri.

## Acceptance criteria

- [x] Source failure sonrası policy bütçesi içinde yeniden cycle çalışıyor.
- [x] Bütçe bitince açık `EXHAUSTED` sonucu dönüyor.
- [x] Persistence ve snapshot rejection retry edilmiyor; recovery varsayılanı terminal.
- [x] Explicit recovery retry aynı reconnect budget içinde çalışıyor ve bounded kalıyor.
- [x] Stop event cycle öncesinde ve backoff sırasında kapanışı kesiyor.
- [x] Focused suite: `6 passed`.
- [x] Full backend suite: `525 passed, 1 skipped`.
- [ ] Testnet soak, disconnect injection ve sequence continuity ölçümü.
- [ ] Remote CI: GitHub Actions kota/bütçe nedeniyle geçici disabled.

## Kesinlikle kapsam dışı

- Sonsuz retry veya kullanıcıdan gizli reconnect.
- Jitter/remote scheduler, rate-limit quota accounting ve 24-hour rotation.
- `source_verified` terfisi, live latency SLA veya execution.
- UI/API wiring ve Rust data-plane geçişi.

## Risk ve sonraki sınır

Bu paket retry politikasının deterministik sözleşmesini ve gap sonrası explicit
resnapshot seçeneğini kanıtlar; gerçek Binance testnet'te uzun süreli socket soak,
gap sonrası continuity ve rate-limit davranışı hâlâ ayrı operatör kanıtıdır.

## Değişiklik geçmişi

### 1.1.0 — 2026-09-07

- `retry_recovery` policy bayrağı eklendi. Varsayılan terminal recovery davranışı
  korunurken testnet soak için aynı reconnect bütçesine bağlı explicit resnapshot
  retry mümkün oldu.

### 1.0.0 — 2026-09-06

- Public depth cycle'larını bounded reconnect/backoff policy altında koordine
  eden session katmanı eklendi.
