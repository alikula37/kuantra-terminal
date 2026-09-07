# P2-WP15 — Binance Depth Soak Report Verification Gate

```yaml
document_id: P2-WP15
version: 1.1.2
status: Active
date: 2026-09-07
baseline: 9a19f61
strategy: KPS-001@1.0.0
adr: ADR-0001, ADR-0002
depends_on: P2-WP14 Opt-in Binance Depth Testnet Soak Gate
implementation_commits: 845a0b4, 070998a, 0aa0dfd, e27762b, 950f607
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
5. `STOP_EVENT_SET_DURING_BACKOFF` gibi başarılı session kararları, son cycle
   başarısız/recovery terminali ise geçerli gözlem sayılmaz; başarılı bir terminal
   cycle (`COMPLETED` veya `STOPPED`) zorunludur.
6. V2 raporlarda continuity aggregate'leri cycle kararları, reconnect sayısı,
   processed event ve sequence gap sayısıyla cross-field eşleşmelidir. V1
   raporlar legacy warning ile okunur; V2 alanları geriye dönük uydurulmaz.

## Teknik teslimatlar

- `binance_depth_report.py` typed verification result/verdict.
- Chain/sink/session cross-field consistency checks.
- Truth-flag tamper detection.
- JSON/terminal output veren report verifier CLI.
- V2 continuity aggregate cross-field doğrulaması ve V1 legacy read path.
- Valid fixture, tamper, mismatch, duration ve mode regression testleri.

## Acceptance criteria

- [x] Valid fixture report `VALID_OFFLINE_FIXTURE` olarak geçiyor.
- [x] `source_verified`/`execution_authority` tamper'ı reddediliyor.
- [x] Chain invalid veya persistence event-count mismatch reddediliyor.
- [x] Mode ve minimum duration gate'leri çalışıyor.
- [x] CLI valid raporda zero, tamper raporunda non-zero exit veriyor.
- [x] Focused suite: `9 passed`.
- [x] Soak CLI doğrudan aynı verifier'dan geçiyor; incomplete stop raporu non-zero.
- [x] Session toplam event sayısı cycle başına `events_processed` toplamıyla eşleşiyor.
- [x] Full backend suite: `530 passed, 1 skipped`.
- [x] Gerçek testnet raporu operator-run ile `VALID_TESTNET_OBSERVATION_UNVERIFIED`
  olarak doğrulandı; source verification açılmadı.
- [ ] Remote CI: GitHub Actions kota/bütçe nedeniyle geçici disabled.

## Operasyon kanıtı — 2026-09-07

- P2-WP14 offline fixture raporu CLI verifier ile `VALID_OFFLINE_FIXTURE`
  olarak, zero exit ile doğrulandı.
- Public testnet denemesi `FAILED_OBSERVATION` olarak, non-zero exit ile
  fail-closed reddedildi: `EXHAUSTED` / `RECONNECT_BUDGET_EXHAUSTED`,
  `SNAPSHOT_FETCH_FAILED`, `event_count=0`.
- Bu ilk negatif sonuç kendi başına “gerçek testnet raporu doğrulandı” kabulünü
  karşılamadı; sonraki proxy'siz bounded run geçerli
  `VALID_TESTNET_OBSERVATION_UNVERIFIED` olarak doğrulandı. Source verification
  hâlâ yoktur.
- Geçerli operator raporu SHA-256:
  `9182585DBCCB58D3FF115CD27F67FF28D17F5F0C8AA8881B86C5FB50E6AF4D0A`.
- 60 saniyelik soak raporu `RECOVERY_REQUIRED` cycle'ından backoff stop'a
  geçiş nedeniyle verifier tarafından `INVALID` / non-zero reddedildi; rapor
  SHA-256 `31327613A973CF8960F155C92F2BEA28D2C0E66FE443846035E7F5CADBA52967`.
- İlk V2 public testnet koşusu 52 event, 1 gap ve 1 recovery cycle ile
  `STOP_EVENT_SET_DURING_BACKOFF` sonucunda `INVALID` / non-zero reddedildi;
  rapor SHA-256 `AADF17DD20F8D9D2B6F963087C01847E230BD403406EC42A6DF7DF20181F5F0C`.
- 120 saniyelik V2 public testnet raporu 159 event, 0 gap ve 0 recovery cycle
  ile `VALID_TESTNET_OBSERVATION_UNVERIFIED` olarak doğrulandı; raw rapor
  SHA-256 `6A990BA2FDE2260BE357DAB8DAC2838C84696EB57BB072D3662765F6018C91B1`.

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

### 1.1.2 — 2026-09-07

- 120 saniyelik V2 valid testnet gözlemi ve continuity metrikleri kaydedildi.

### 1.1.1 — 2026-09-07

- V2 continuity metrikli gerçek testnet negatif gözlemi ve SHA-256 kanıtı eklendi.

### 1.1.0 — 2026-09-07

- V2 continuity aggregate'leri fail-closed doğrulanıyor; V1 raporları yeni alanlar
  eklenmeden legacy warning ile okunabiliyor.

### 1.0.5 — 2026-09-07

- `processed_event_count` ile cycle `events_processed` toplamı arasında fail-closed
  cross-field doğrulaması eklendi; oynanmış aggregate raporlar reddediliyor.

### 1.0.4 — 2026-09-07

- P2-WP14 soak CLI, report verifier gate'ine bağlandı; `STOPPED` kararının
  eksik/recovery cycle'ını başarı gibi döndürmesi engellendi.

### 1.0.3 — 2026-09-07

- Başarılı session kararının son cycle ile tutarlı olmasını zorunlu kılan
  fail-closed verifier kuralı ve 60 saniyelik negatif soak kanıtı eklendi.

### 1.0.2 — 2026-09-07

- Doğrudan public testnet operator raporunun verifier sonucu ve SHA-256 kanıtı
  kaydedildi; truth/execution bayrakları false kaldı.

### 1.0.1 — 2026-09-07

- Fixture ve public testnet operatör denemelerinin verifier sonuçları kaydedildi;
  başarısız testnet gözlemi non-zero ile korundu.

### 1.0.0 — 2026-09-07

- Binance depth soak raporlarını fail-closed doğrulayan backend contract ve CLI
  gate eklendi.
