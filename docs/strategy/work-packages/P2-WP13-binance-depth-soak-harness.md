# P2-WP13 — Deterministic Binance Depth Soak Harness

```yaml
document_id: P2-WP13
version: 1.0.0
status: Active
date: 2026-09-06
baseline: 0f96f5b
strategy: KPS-001@1.0.0
adr: ADR-0001, ADR-0002
depends_on: P2-WP07 Rotated Market Event Segments ve Manifest Recovery, P2-WP12 Bounded Binance Depth Reconnect Session
implementation_commits: pending
```

## Problem

P2-WP12 reconnect policy'sini deterministically test edebiliyor; ancak reconnect
sonrası aynı ingestor, hash chain ve rotated durable segment set'inin gerçekten
devam ettiğine dair tek bir release/CI harness raporu yoktu. Gerçek testnet'i
unit testte kullanmak ise flaky network davranışını production kanıtı gibi
gösterebilirdi.

## Karar

1. `DepthFixtureCycle` snapshot, ordered events ve explicit disconnect failure
   injection taşır. Fixture failure hiçbir zaman synthetic market event üretmez.
2. `BinanceDepthFixtureRunner`, gerçek P2-WP10 transport ve P2-WP12 session
   protocol'ünü kullanır; test-only shortcut veya doğrudan chain mutation yoktur.
3. `BinanceDepthSoakHarness` session sonucu yanında chain verification, durable
   segment recovery ve kalan fixture bütçesini raporlar. `source_verified=false`
   değişmez.
4. Reconnect sonrası sequence gap `RECOVERY_REQUIRED` terminal sonucudur; eksik
   update doldurulmaz ve sink'e gap event'i yazılmaz.

## Teknik teslimatlar

- Fixture cycle/runner abstraction.
- Reconnect + rotated JSONL sink continuity report.
- Segment reopen/recovery proof.
- Disconnect success, gap terminality ve fixture exhaustion tests.

## Acceptance criteria

- [x] Disconnect sonrası yeni snapshot/event cycle aynı canonical chain'de devam ediyor.
- [x] Segment rotation ve process reopen sonrası manifest/chain valid kalıyor.
- [x] Reconnect sonrası sequence gap açık `RECOVERY_REQUIRED` olarak terminal kalıyor.
- [x] Fixture cycle bütçesi bitince `EXHAUSTED` sonucu dönüyor.
- [x] Focused suite: `3 passed`.
- [x] Full backend suite: `472 passed, 1 skipped`.
- [ ] Gerçek testnet soak ve disconnect injection scheduled validation.
- [ ] Remote CI: GitHub Actions kota/bütçe nedeniyle geçici disabled.

## Kesinlikle kapsam dışı

- Gerçek Binance endpoint'ine unit test bağlantısı veya fake source verification.
- Latency SLA, packet loss modelleme, rate-limit quota veya private execution.
- Gap doldurma, synthetic snapshot/update veya UI promotion.

## Risk ve sonraki sınır

Bu harness reconnect/chain/durability invariant'larını ağdan bağımsız kanıtlar;
gerçek testnet sürekliliğini kanıtlamaz. Bir sonraki operasyon kapısı, açıkça
opt-in testnet soak job'ında uzun süreli bağlantı, disconnect injection ve
sequence continuity metriklerini toplamaktır. Bu kanıt olmadan live varsayılanı
ve `source_verified=true` açılmamalıdır.

## Değişiklik geçmişi

### 1.0.0 — 2026-09-06

- Disconnect/reconnect fixture'larını gerçek transport/session/sink zinciri
  üzerinden çalıştıran deterministic soak harness eklendi.
