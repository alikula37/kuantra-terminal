# P2-WP14 — Opt-in Binance Depth Testnet Soak Gate

```yaml
document_id: P2-WP14
version: 1.0.0
status: Active
date: 2026-09-07
baseline: 257e881
strategy: KPS-001@1.0.0
adr: ADR-0001, ADR-0002
depends_on: P2-WP11 Public Binance Depth Network Adapter, P2-WP13 Deterministic Binance Depth Soak Harness
implementation_commits: 17dc616
```

## Problem

P2-WP13 fixture'ları reconnect, gap ve durable chain continuity'yi kanıtlıyor;
ancak operatörün gerçek Binance Spot testnet'te bunu güvenli biçimde ölçmesi için
explicit opt-in komut, bounded duration ve rapor schema'sı yoktu. Network'in
varsayılan açılması, unit/CI çalıştırmalarında istemsiz dış çağrı riskidir.

## Karar

1. `scripts/run_binance_depth_soak.py` varsayılan olarak offline fixture çalıştırır.
   Testnet mode, ayrıca `--allow-network` verilmeden reddedilir; live/private
   endpoint seçeneği yoktur.
2. Testnet probe yalnızca public REST snapshot + public websocket depth kullanır;
   credential, order submission ve execution authority yoktur. Duration 1–86400
   saniye, reconnect 0–100 aralığında bounded'dır.
3. Rapor `BINANCE_DEPTH_SOAK_REPORT_V1` schema'sı ile session kararını, chain
   verification'ı, durable segment recovery'yi, run root'u ve elapsed ölçümünü
   taşır. `source_verified=false` invariant'ı raporda sabittir.
4. Network adapter stop event'i sessiz websocket `recv()` beklemesini keser;
   probe süresi dolduğunda transport `STOPPED` sonucu üretebilir. Timeout veya
   source failure başarıya çevrilmez.
5. Unit testler gerçek ağa bağlanmaz. Gerçek testnet çalışması operatörün açık
   komutuyla, ayrı storage root ve rapor dosyasıyla yapılır.

## Teknik teslimatlar

- Fixture/testnet modlu soak CLI.
- Explicit network opt-in ve bounded CLI validation.
- JSON report schema: session, chain, persistence ve truth flags.
- Stop-aware websocket receive boundary.
- CLI serialization, refusal, fixture report ve quiet-socket stop tests.

## Kullanım

Offline fixture (varsayılan):

```powershell
uv run python scripts/run_binance_depth_soak.py `
  --mode fixture `
  --storage-root "$PWD/.local-soak" `
  --output "$PWD/.local-soak/report.json"
```

Opt-in testnet (live/private değil):

```powershell
uv run python scripts/run_binance_depth_soak.py `
  --mode testnet `
  --allow-network `
  --symbol BTCUSDT `
  --duration-seconds 300 `
  --storage-root "$PWD/.local-testnet-soak" `
  --output "$PWD/.local-testnet-soak/report.json"
```

## Acceptance criteria

- [x] Default CLI network açmadan fixture çalıştırıyor.
- [x] Testnet mode `--allow-network` olmadan fail-closed reddediliyor.
- [x] Duration ve reconnect budget bounded validation'dan geçiyor.
- [x] Rapor chain/sink/session kanıtlarını ve false truth flags'ini taşıyor.
- [x] Sessiz socket stop event ile timeout beklemeden kapanabiliyor.
- [x] Focused suite: `5 passed`.
- [x] Full backend suite: `477 passed, 1 skipped`.
- [ ] Gerçek testnet raporu ve uzun süreli soak gözlemi.
- [ ] Remote CI: GitHub Actions kota/bütçe nedeniyle geçici disabled.

## Kesinlikle kapsam dışı

- Live/private Binance endpoint, API key, listen-key veya emir gönderme.
- `source_verified=true` terfisi, production market-data claim'i veya latency SLA.
- Otomatik schedule/daemon, sınırsız retry ve rapor üzerinden UI yetkisi.

## Risk ve sonraki sınır

Bu kapı gerçek testnet gözlemini mümkün kılar ama kendi başına ekonomik doğruluk,
packet-loss kapsamı veya production SLA kanıtlamaz. Gerçek soak raporlarında
disconnect sayısı, `last_update_id` sürekliliği, gap/recovery oranı ve durable
segment reopen sonucu incelenmeden canlı varsayılanı açılmamalıdır.

## Değişiklik geçmişi

### 1.0.0 — 2026-09-07

- Fixture-default, explicit-network opt-in Binance depth soak CLI ve stop-aware
  websocket operasyon kapısı eklendi.
