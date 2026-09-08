<!-- doc-role: archived -->
> Historical reference only. Not a current work order. Unchecked acceptance items remain open;
> see [current status](../../../strategy/STATUS.md). Read only for a relevant task.

# P2-WP24 — Binance Depth Soak Series Quality Gate

```yaml
document_id: P2-WP24
version: 1.0.1
status: Active
date: 2026-09-07
baseline: 2a45956
strategy: KPS-001@1.0.0
adr: ADR-0001, ADR-0002, ADR-0003
depends_on: P2-WP15 Binance Depth Soak Report Verification Gate, P2-WP23 Binance Depth Soak Observation Series
implementation_commits: 2a63a9c
```

## Problem

P2-WP23 seri aggregate'i doğru raporluyor; fakat minimum süre, event hacmi ve
izin verilen gap/recovery oranları ayrı bir karar olarak tanımlı değildi. Bir
seri yapısal olarak valid olsa bile çok kısa olabilir veya recovery olayları
içerebilir. Bu durum review ile production truth'un birbirine karışmasına yol
açar.

## Karar

1. Default quality policy üç valid observation, observation başına en az 300.000
   ms (5 dakika) ve en az 100 processed event ister.
2. Default gap event rate, recovery cycle rate, source-failure cycle rate ve
   invalid observation rate toleransı `0.0`'dır. Reconnect tek başına yasak
   değildir; fakat gap/recovery/source failure üretirse gate reddeder.
3. Gate önce P2-WP23 series verifier'ını çalıştırır. Structural invalid veya
   `overall_ok=false` seri kaliteye terfi edemez.
4. Başarılı karar yalnız `ELIGIBLE_FOR_REVIEW`'dır. Bu karar source
   verification, production market-data completeness veya order submission
   authority vermez; iki truth flag de false kalır.
5. Kısa probe için policy değerleri CLI'da açıkça override edilebilir; override
   operasyon kanıtını default 5 dakikalık gate olarak göstermeyecektir.

## Teknik teslimatlar

- `binance_depth_soak_quality.py`: typed policy ve fail-closed quality gate.
- `scripts/evaluate_binance_depth_soak_quality.py`: JSON/terminal policy
  değerlendirme komutu.
- Minimum observation/duration/event ve rate threshold regression testleri.

## Kullanım

Default production-aday review policy:

```powershell
uv run --offline --cache-dir .uv-cache --no-project `
  --with-requirements backend/requirements.lock `
  python scripts/evaluate_binance_depth_soak_quality.py `
  "$env:TEMP\kuantra-depth-soak-series\series.json" `
  --json
```

Kısa probe için açık override örneği:

```powershell
python scripts/evaluate_binance_depth_soak_quality.py `
  "$env:TEMP\kuantra-depth-soak-series\single-valid-series.json" `
  --minimum-observations 1 `
  --minimum-elapsed-seconds 120 `
  --minimum-processed-events 100
```

## Operasyon kanıtı — 2026-09-07

Mevcut 120 saniyelik valid testnet observation serisi network çağrısı
yapılmadan kalite gate'inden geçirildi:

| Policy | Sonuç | Gerekçe |
|---|---|---|
| Default: minimum 3, minimum 300 s, minimum 100 event | `REJECTED`, exit `1` | `valid=1 < 3`; elapsed `125441.41 ms < 300000 ms` |
| Explicit kısa-probe override: minimum 1, minimum 120 s, minimum 100 event | `ELIGIBLE_FOR_REVIEW`, exit `0` | Gap/recovery/source-failure oranları `0`; truth/execution false |

İkinci karar yalnız review eligibility'dir. Bu 2026-09-07 kanıtında üç ayrı
default-compliant valid observation mevcut değildi; live/source verification
kapısı kapalı kaldı.

## Operasyon kanıtı — 2026-09-08 (Mac mini)

Üç bağımsız `BTCUSDT` public testnet gözlemi default quality policy ile
değerlendirildi. Aggregate `1,092` processed event ve `920,714.54 ms` toplam
elapsed taşıyor; gap, recovery ve source-failure oranlarının üçü de `0.0`.
Quality gate sonucu `ELIGIBLE_FOR_REVIEW`, canonical series SHA-256
`81d0466e380b248ea061d64118af8c61d67376becf0c153b107293ad2a4735bb` oldu.
`source_verified=false` ve `execution_authority=false` değişmeden kaldı.

## Acceptance criteria

- [x] Gate P2-WP23 structural verifier'ını ön koşul yapıyor.
- [x] Default minimum observation, duration ve event hacmi uygulanıyor.
- [x] Gap/recovery/source-failure/invalid rate threshold'ları fail-closed.
- [x] Açık policy override kısa probe için çalışıyor ve yalnız review sonucu
  üretiyor.
- [x] `source_verified=false`, `execution_authority=false` korunuyor.
- [x] Focused suite: `4 passed`.
- [x] Full backend suite: `540 passed, 1 skipped, 2 warnings`.
- [x] Default policy'yi karşılayan üç ayrı valid testnet observation (Mac mini,
  2026-09-08; quality series SHA-256 `81d0466e380b248ea061d64118af8c61d67376becf0c153b107293ad2a4735bb`).
- [ ] Remote CI: GitHub Actions kota/bütçe nedeniyle geçici disabled.

## Kesinlikle kapsam dışı

- `ELIGIBLE_FOR_REVIEW` değerini source verification veya execution authority'ye
  çevirmek.
- Policy override'ını kalıcı production config yapmak.
- Gap/recovery event'lerini sentetik olarak silmek veya doldurmak.
- Network scheduler, private endpoint, order submission veya live default.

## Risk ve sonraki sınır

Gate yalnız mevcut report/series metadata'sının kalite eşiklerini kontrol eder;
Binance packet completeness veya ekonomik doğruluğu kanıtlamaz. Sonraki sınır
default policy'yi karşılayan üç ayrı 5–15 dakikalık testnet gözlemi toplamak ve
aynı policy ile tekrarlanabilir review bundle üretmektir.

## Değişiklik geçmişi

### 1.0.0 — 2026-09-07

- Observation series için süre, event hacmi, gap/recovery ve invalid-rate
  quality gate'i eklendi.

### 1.0.1 — 2026-09-08

- Mac mini üzerinde default üç gözlem, 5 dakika, 100 event ve sıfır gap/
  recovery/source-failure rate politikası `ELIGIBLE_FOR_REVIEW` olarak geçti;
  production/source verification terfisi yapılmadı.
