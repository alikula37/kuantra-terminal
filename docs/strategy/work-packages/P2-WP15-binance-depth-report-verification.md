# P2-WP15 — Binance Depth Soak Report Verification Gate

```yaml
document_id: P2-WP15
version: 1.0.1
status: Active
date: 2026-09-07
baseline: 9a19f61
strategy: KPS-001@1.0.0
adr: ADR-0001, ADR-0002
depends_on: P2-WP14 Opt-in Binance Depth Testnet Soak Gate
implementation_commits: 845a0b4
```

## Problem

P2-WP14 soak raporu üretiyordu; fakat raporu elle okumak, `source_verified`,
chain veya persistence alanlarının sonradan değiştirilmediğini kanıtlamıyordu.
Bu, gözlem raporunun production market truth gibi yanlış terfi ettirilmesi
riskini bırakıyordu.

## Karar

1. `verify_depth_soak_report()` raporu repair etmez; schema, mode/environment,
   UTC timestamp, duration, session kararları, reconnect/attempt ilişkisi,
   chain hash ve durable segment event count alanlarını fail-closed kontrol eder.
2. `source_verified=true` veya `execution_authority=true` raporu geçersizdir.
   Geçerli fixture `VALID_OFFLINE_FIXTURE`, geçerli testnet gözlemi
   `VALID_TESTNET_OBSERVATION_UNVERIFIED` olarak sınıflanır; hiçbiri live
   execution veya production data authorization vermez.
3. `scripts/verify_binance_depth_soak_report.py` aynı sözleşmeyi CLI/exit code
   olarak sunar. Tamper veya başarısız session non-zero döner.
4. Fixture mode yalnızca `COMPLETED` ve `remaining_fixture_cycles=0` ile geçer;
   testnet gözlemi `COMPLETED`/`STOPPED` olabilir ama source verification false
   kalır.

## Teknik teslimatlar

- `binance_depth_report.py` typed verification result/verdict.
- Chain/sink/session cross-field consistency checks.
- Truth-flag tamper detection.
- JSON/terminal output veren report verifier CLI.
- Valid fixture, tamper, mismatch, duration ve mode regression testleri.

## Acceptance criteria

- [x] Valid fixture report `VALID_OFFLINE_FIXTURE` olarak geçiyor.
- [x] `source_verified`/`execution_authority` tamper'ı reddediliyor.
- [x] Chain invalid veya persistence event-count mismatch reddediliyor.
- [x] Mode ve minimum duration gate'leri çalışıyor.
- [x] CLI valid raporda zero, tamper raporunda non-zero exit veriyor.
- [x] Focused suite: `5 passed`.
- [x] Full backend suite: `482 passed, 1 skipped`.
- [ ] Gerçek testnet raporunun operator-run ile doğrulanması.
- [ ] Remote CI: GitHub Actions kota/bütçe nedeniyle geçici disabled.

## Operasyon kanıtı — 2026-09-07

- P2-WP14 offline fixture raporu CLI verifier ile `VALID_OFFLINE_FIXTURE`
  olarak, zero exit ile doğrulandı.
- Public testnet denemesi `FAILED_OBSERVATION` olarak, non-zero exit ile
  fail-closed reddedildi: `EXHAUSTED` / `RECONNECT_BUDGET_EXHAUSTED`,
  `SNAPSHOT_FETCH_FAILED`, `event_count=0`.
- Bu negatif sonuç, “gerçek testnet raporu doğrulandı” kabul maddesini
  karşılamaz; valid bir `VALID_TESTNET_OBSERVATION_UNVERIFIED` raporu ve
  source verification hâlâ yoktur.

## Kesinlikle kapsam dışı

- Raporu düzeltmek, eksik alan doldurmak veya hash chain'i yeniden üretmek.
- `source_verified` bayrağını verifier üzerinden yükseltmek.
- Broker execution, live/private Binance ve UI release promotion.

## Risk ve sonraki sınır

Verifier rapor bütünlüğünü ve operasyon kararını kontrol eder; verinin ekonomik
doğruluğunu veya Binance'ın eksiksiz packet delivery'sini kanıtlamaz. Sonraki
kapı, gerçek testnet raporlarını operatör imzası/retention politikasıyla saklamak
ve disconnect/gap/reconnect metriklerini ürün kararına bağlamaktır.

## Değişiklik geçmişi

### 1.0.1 — 2026-09-07

- Fixture ve public testnet operatör denemelerinin verifier sonuçları kaydedildi;
  başarısız testnet gözlemi non-zero ile korundu.

### 1.0.0 — 2026-09-07

- Binance depth soak raporlarını fail-closed doğrulayan backend contract ve CLI
  gate eklendi.
