# P2-WP14 — Opt-in Binance Depth Testnet Soak Gate

```yaml
document_id: P2-WP14
version: 1.1.2
status: Active
date: 2026-09-07
baseline: 257e881
strategy: KPS-001@1.0.0
adr: ADR-0001, ADR-0002
depends_on: P2-WP11 Public Binance Depth Network Adapter, P2-WP13 Deterministic Binance Depth Soak Harness
implementation_commits: 17dc616, 078dc02, 070998a, 0aa0dfd
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
5. Sequence gap sonrası resnapshot retry varsayılan değildir. Testnet operatörü
   aynı bounded reconnect bütçesi içinde `--retry-recovery` seçerse recovery
   yeniden denenir; persistence/rejection hataları yine terminaldir.
6. Unit testler gerçek ağa bağlanmaz. Gerçek testnet çalışması operatörün açık
   komutuyla, ayrı storage root ve rapor dosyasıyla yapılır.
7. CLI, raporu aynı fail-closed verifier'dan geçirir; session kararı `STOPPED`
   olsa bile cycle tamamlanmamışsa exit code `1` döner.

## Teknik teslimatlar

- Fixture/testnet modlu soak CLI.
- Explicit network opt-in ve bounded CLI validation.
- JSON report schema: session, chain, persistence ve truth flags.
- Stop-aware websocket receive boundary.
- CLI'nin verifier ile fail-closed exit gate'i.
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
  --retry-recovery `
  --symbol BTCUSDT `
  --duration-seconds 300 `
  --storage-root "$PWD/.local-testnet-soak" `
  --output "$PWD/.local-testnet-soak/report.json"
```

## Operasyon kanıtı — 2026-09-07

Bu kanıtlar aynı Windows host'ta, `uv run --offline` ile kilitli backend
bağımlılıkları kullanılarak üretildi. Geçici storage/report kökleri repoya
alınmadı; SHA-256 değerleri rapor dosyasının değişmediğini takip etmek için
verilmiştir.

| Çalışma | Sonuç | Önemli alanlar | Rapor SHA-256 |
|---|---|---|---|
| Offline fixture, `BTCUSDT`, reconnect budget `1` | `COMPLETED`; verifier `VALID_OFFLINE_FIXTURE` | 4 chain event'i, 2 durable segment, chain/persistence valid; `source_verified=false`, `execution_authority=false` | `238095970798F52B976D33BAD2A2587378356BA5AC19A185C408147BBD76A932` |
| Public Binance testnet, 5 s, `--allow-network`, reconnect budget `0` | **Başarısız gözlem; terfi edilmedi** | `EXHAUSTED` / `RECONNECT_BUDGET_EXHAUSTED`, `SNAPSHOT_FETCH_FAILED`, 0 event; verifier `FAILED_OBSERVATION`; truth flags false | `A21FF7CE4D94A4983AC2DAEE046B712A48EA29CC0B5100FD136E0BCE6A0B1D70` |
| Public Binance testnet, 20 s, `--allow-network --retry-recovery`, reconnect budget `3` | `STOPPED`; verifier `VALID_TESTNET_OBSERVATION_UNVERIFIED` | 38 depth event'i işlendi, 39 chain/persistence event'i, chain/persistence valid; `source_verified=false`, `execution_authority=false` | `9182585DBCCB58D3FF115CD27F67FF28D17F5F0C8AA8881B86C5FB50E6AF4D0A` |
| Public Binance testnet, 60 s, `--allow-network --retry-recovery`, reconnect budget `3` | **Geçersiz gözlem; terfi edilmedi** | 110 event alındı; sequence gap sonrası `RECOVERY_REQUIRED`, stop backoff sırasında geldi; 1 chain/persistence event'i; verifier `INVALID` / non-zero | `31327613A973CF8960F155C92F2BEA28D2C0E66FE443846035E7F5CADBA52967` |

Tüm testnet çalışmaları credential, private endpoint veya emir yetkisi kullanmadı.
İlk 5 saniyelik deneme host proxy'si (`127.0.0.1:9`) yüzünden snapshot fetch'te
başarısız oldu. 20 saniyelik geçerli raporda proxy yalnızca probe prosesinden
çıkarıldı; bu kalıcı sistem ayarı değişikliği değildir. Rapor verifier'ı geçse de
`source_verified` ve canlı/production terfi kapıları kapalı kalır.

Geçerli rapor aynı host'ta P2-WP16–21 akışından geçirildi: archive report id
`1c467ec04d264349`, attestation `50925819189b9d60`, gate
`ELIGIBLE_FOR_REVIEW`, review `da5d4a9b329ecbc9`, evidence bundle id
`f7f31d856b1492f99ab8e41a058da36ffab19ac2a1b584ac13befe9abcfe983b`.
Bundle verify ve boş hedefe restore zero exit verdi; bundle SHA-256
`09FE8B7D9857A0CAC8C510480489A5AFC7E655CA3F8DEE767AC863D5E488CB08`.

## Acceptance criteria

- [x] Default CLI network açmadan fixture çalıştırıyor.
- [x] Testnet mode `--allow-network` olmadan fail-closed reddediliyor.
- [x] Duration ve reconnect budget bounded validation'dan geçiyor.
- [x] Rapor chain/sink/session kanıtlarını ve false truth flags'ini taşıyor.
- [x] Sessiz socket stop event ile timeout beklemeden kapanabiliyor.
- [x] Focused suite: `8 passed`.
- [x] Full backend suite: `527 passed, 1 skipped`.
- [x] Bounded gerçek testnet raporu verifier'dan geçti ve operator archive/attestation/review akışına bağlandı.
- [ ] Uzun süreli soak, kontrollü disconnect sonrası recovery continuity ve 24 saatlik gap metriği.
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

### 1.1.2 — 2026-09-07

- Soak CLI, `verify_depth_soak_report()` ile aynı fail-closed sözleşmeye bağlandı;
  recovery backoff sırasında duran ve terminal cycle üretmeyen raporlar artık
  doğrudan non-zero exit ile reddediliyor.

### 1.1.1 — 2026-09-07

- 60 saniyelik gerçek testnet soak'ta sequence gap ve backoff stop sonucu
  kaydedildi. Verifier, başarılı session kararını son cycle'ın gerçekten
  `COMPLETED`/`STOPPED` olmasına bağlayarak bu raporu fail-closed reddetti.

### 1.1.0 — 2026-09-07

- Explicit `--retry-recovery` ile bounded resnapshot seçeneği ve doğrudan public
  testnet operator kanıtı kaydedildi. Geçerli rapor archive, attestation, review
  ve evidence bundle restore akışından geçirildi; source verification açılmadı.

### 1.0.1 — 2026-09-07

- Offline fixture doğrulaması ve fail-closed public testnet operatör denemesi
  kaydedildi. Testnet snapshot fetch başarısızlığı başarıya çevrilmedi;
  gerçek testnet kabul maddesi açık kaldı.

### 1.0.0 — 2026-09-07

- Fixture-default, explicit-network opt-in Binance depth soak CLI ve stop-aware
  websocket operasyon kapısı eklendi.
