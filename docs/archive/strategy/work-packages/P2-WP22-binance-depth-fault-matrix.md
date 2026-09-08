<!-- doc-role: archived -->
> Historical reference only. Not a current work order. Unchecked acceptance items remain open;
> see [current status](../../../strategy/STATUS.md). Read only for a relevant task.

# P2-WP22 — Binance Depth Fault-Injection ve Recovery Matrix

```yaml
document_id: P2-WP22
version: 1.0.1
status: Active
date: 2026-09-07
baseline: 72a2000
strategy: KPS-001@1.0.0
adr: ADR-0001, ADR-0002
depends_on: P2-WP09 Injected Binance Depth Ingestor Boundary, P2-WP12 Bounded Binance Depth Reconnect Session, P2-WP13 Deterministic Binance Depth Soak Harness
implementation_commits: db2dbce
```

## Problem

P2-WP13 fixture'ları disconnect, gap ve budget exhaustion davranışlarını
kanıtlıyordu; ancak karar alanı tekil testlere dağılmıştı. 300 saniyelik public
testnet gözleminde gap sonrası backoff sırasında stop görülmesi, `STOPPED` veya
`COMPLETED` değerlerinin tek başına recovery kanıtı sayılamayacağını gösterdi.
Bu nedenle aynı production sınırlarını kullanan, ağsız ve isimlendirilmiş bir
fault matrix gerekir.

## Karar

1. Matrix yalnız offline fixture çalıştırır; network, credential, order
   submission ve `source_verified` terfisi yoktur.
2. Her vaka gerçek `BinanceDepthIngestor` → `BinanceDepthTransport` →
   `BinanceDepthSession` → `MarketEventSegmentSet` zincirinden geçer; test
   shortcut'ı veya doğrudan hash/sink mutasyonu yoktur.
3. Yedi vaka session decision, reason code, attempt/reconnect sayısı,
   continuity aggregate'leri, canonical chain ve durable event count ile
   karşılaştırılır:
   `clean_cycle`, `disconnect_reconnect`, `gap_terminal_without_retry`,
   `gap_recovered_with_opt_in`, `malformed_event_terminal`,
   `snapshot_rejected`, `reconnect_budget_exhausted`.
4. Gap recovery yalnız `retry_recovery=True` ve bounded reconnect bütçesi ile
   geçerlidir. Gap veya malformed event synthetic event/fill ile doldurulmaz.
5. Matrix verifier raporu repair etmez; herhangi bir vaka mismatch'i veya truth
   flag değişikliği tüm matrix'i non-zero ile reddeder.

## Teknik teslimatlar

- `binance_depth_fault_matrix.py`: canonical scenario definitions, runner ve
  fail-closed report verifier.
- `scripts/run_binance_depth_fault_matrix.py`: network'süz operasyon komutu.
- Her senaryo için expected/observed decision, continuity ve persistence
  cross-check'i.
- Tamper regression test'i.

## Kullanım

```powershell
uv run --offline --cache-dir .uv-cache --no-project `
  --with-requirements backend/requirements.lock `
  python scripts/run_binance_depth_fault_matrix.py `
  --storage-root "$env:TEMP\kuantra-depth-fault-matrix" `
  --output "$env:TEMP\kuantra-depth-fault-matrix\report.json"
```

Beklenen çıktı `VALID_OFFLINE_FAULT_MATRIX cases=7` ve zero exit'tir.

## Operasyon kanıtı — 2026-09-07

İlk matrix aynı Windows host'ta, locked backend dependencies ve network
olmadan çalıştırıldı:

- 7/7 vaka `ok=true`.
- Clean ve disconnect recovery canonical chain'i valid tuttu.
- Retry kapalı gap `RECOVERY_REQUIRED`; retry açık gap ikinci cycle'da
  `COMPLETED` oldu.
- Malformed event recovery'ye geçti; snapshot rejection'da durable event count
  `0` kaldı.
- Reconnect budget `0` source failure'ı `EXHAUSTED` olarak bıraktı.
- `source_verified=false`, `execution_authority=false`.
- Rapor SHA-256:
  `4578EAF11D8A43808D6A130842295F1750FB32D7542EA9309C4D283A2AD8777E`.

## Mac local revalidation — 2026-09-08

Fault matrix Mac mini üzerinde network'süz tekrarlandı ve `7/7` vaka valid
olarak geçti. Kontrollü disconnect recovery, gap retry açık/kapalı, malformed
event, snapshot rejection ve reconnect budget exhaustion kararları beklenen
continuity/persistence metrikleriyle eşleşti. Rapor SHA-256:
`c2c4eb9f92ab5533a03ff419be2d3568ea45f855fb0c399fbd401e6896846102`.

Bu kanıt public testnet bağlantı kesintisini veya 24 saatlik gap metriğini
kanıtlamaz; ilgili acceptance maddeleri açık kalır.

## Acceptance criteria

- [x] Yedi vaka aynı ingestor/transport/session/durable sink zincirinden geçiyor.
- [x] Gap retry açık/kapalı kararları ve reconnect bütçesi exact reason code ile
  doğrulanıyor.
- [x] Malformed event ve snapshot rejection fail-closed kalıyor; synthetic
  event/fill üretilmiyor.
- [x] Her vakanın continuity aggregate ve persistence event count'u beklenen
  değerle eşleşiyor.
- [x] Matrix tamper verifier'ı mismatch'i non-zero olarak reddediyor.
- [x] Focused suite: `3 passed`.
- [x] Full backend suite: `533 passed, 1 skipped, 2 warnings`.
- [ ] Public testnet uzun soak ve gerçek bağlantı kesintisi validation'ı.
- [ ] Remote CI: GitHub Actions kota/bütçe nedeniyle geçici disabled.

## Kesinlikle kapsam dışı

- Gerçek websocket bağlantısını test içinde kesmek veya public kaynağı
  `source_verified=true` yapmak.
- Live/private Binance endpoint, API key, order submission veya execution
  authority.
- Packet-loss olasılık modeli, latency SLA, 24 saatlik soak ve production
  release approval.

## Risk ve sonraki sınır

Matrix karar makinelerinin ve durable sink invariants'larının ağsız
tekrarlanabilirliğini kanıtlar; gerçek exchange sürekliliğini kanıtlamaz. Bir
sonraki teknik sınır, aynı fail-closed rapor sözleşmesiyle tekrarlı 5–15 dakikalık
testnet gözlemleri ve gap/recovery oranlarının zaman serisi olarak toplanmasıdır.

## Değişiklik geçmişi

### 1.0.0 — 2026-09-07

- Yedi senaryolu offline fault-injection/recovery matrix ve CLI verifier eklendi.

### 1.0.1 — 2026-09-08

- Mac mini üzerinde yedi vakalı offline fault matrix revalidation kanıtı
  kaydedildi; gerçek ağ validation sınırı korunuyor.
