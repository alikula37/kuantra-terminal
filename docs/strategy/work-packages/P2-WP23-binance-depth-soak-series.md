# P2-WP23 — Binance Depth Soak Observation Series

```yaml
document_id: P2-WP23
version: 1.0.0
status: Active
date: 2026-09-07
baseline: 4942f4d
strategy: KPS-001@1.0.0
adr: ADR-0001, ADR-0002
depends_on: P2-WP14 Opt-in Binance Depth Testnet Soak Gate, P2-WP15 Binance Depth Soak Report Verification Gate, P2-WP22 Binance Depth Fault-Injection ve Recovery Matrix
implementation_commits: c5560a2
```

## Problem

Tek bir `VALID_TESTNET_OBSERVATION_UNVERIFIED` raporu süreklilik veya gap oranı
kanıtı değildir. 30 ve 300 saniyelik gerçek koşuların verifier tarafından
geçersiz tutulması, valid ve invalid raporların tek aggregate içinde sessizce
birleştirilemeyeceğini gösterdi. Tekrarlı gözlemler için ayrı bir seri sözleşmesi
gereklidir.

## Karar

1. Her input önce P2-WP15 `verify_depth_soak_report()` ile testnet + durable
   rapor olarak doğrulanır. Yalnız `VALID_TESTNET_OBSERVATION_UNVERIFIED`
   verdict'li raporlar aggregate'e dahil edilir.
2. Bir invalid, eksik veya yanlış sembollü gözlem serinin `overall_ok` değerini
   false yapar; invalid gözlem kaybolmaz, kendi verifier hatalarıyla raporda
   görünür kalır.
3. Seri minimum gözlem sayısı default `3`'tür. Bu sayı sağlanmadan seri valid
   kabul edilmez. Operasyonel kısa probe için minimum açıkça `1` seçilebilir;
   bu hiçbir source verification veya production terfisi sağlamaz.
4. Aggregate yalnız dahil edilen gözlemlerden şu değerleri türetir: toplam
   elapsed, processed event, gap event, cycle, reconnect, recovery-required
   cycle ve source-failure cycle sayıları; ayrıca gap/recovery/source-failure
   oranları.
5. Seri verifier raporu repair etmez; aggregate veya verdict tamper'ı
   non-zero/invalid sonucu üretir. `source_verified` ve `execution_authority`
   her seviyede false kalır.

## Teknik teslimatlar

- `binance_depth_soak_series.py`: tekil verifier'a bağlı seri builder ve
  cross-field verifier.
- `scripts/aggregate_binance_depth_soak_series.py`: network'süz JSON rapor
  aggregate komutu.
- Observation başına SHA-256, verifier verdict/errors ve dahil edilme durumu.
- Gap/recovery oranı ve invalid-series regression testleri.

## Kullanım

```powershell
uv run --offline --cache-dir .uv-cache --no-project `
  --with-requirements backend/requirements.lock `
  python scripts/aggregate_binance_depth_soak_series.py `
  "$env:TEMP\report-1.json" "$env:TEMP\report-2.json" "$env:TEMP\report-3.json" `
  --minimum-observations 3 `
  --output "$env:TEMP\kuantra-depth-soak-series\series.json"
```

Default minimum `3` sağlanmazsa veya bir input invalid ise command exit `1`
döner. Bu komut probe çalıştırmaz; yalnız mevcut raporları doğrular.

## Operasyon kanıtı — 2026-09-07

Mevcut public testnet raporları aynı host'ta, network çağrısı yapılmadan seri
katmanından geçirildi:

| Girdi | Sonuç | Aggregate | Seri SHA-256 |
|---|---|---|---|
| 120 s valid + 30 s invalid + 300 s invalid, minimum `3` | `INVALID_TESTNET_SERIES`, exit `1` | `valid=1`, `invalid=2`; yalnız valid gözlemde 159 event, 0 gap, 0 recovery cycle | `5D27D161415301B41F56A1B9ED6B703D7A7BAA34B4C663162098FA0BDF3F6557` |
| Yalnız 120 s valid, minimum `1` | `VALID_TESTNET_SERIES_UNVERIFIED`, exit `0` | 159 event, gap rate `0`, recovery rate `0`; production/source terfisi yok | `59C6566089C96C747A9C5A22D22130E5E2B196E609AFD01CE66869CCB4D0A3EB` |

Bu kanıt üç geçerli uzun gözlem bulunduğunu göstermiyor; default minimum `3`
kapısı bu nedenle açık kalıyor.

## Acceptance criteria

- [x] Her input P2-WP15 verifier'ından geçirilmeden aggregate'e alınmıyor.
- [x] Invalid observation seride görünür kalıyor ve `overall_ok=false` üretiyor.
- [x] Minimum observation gate'i ve explicit minimum `1` davranışı çalışıyor.
- [x] Gap/recovery/source-failure oranları yalnız dahil edilen raporlardan
  yeniden hesaplanıyor.
- [x] Aggregate tamper'ı verifier tarafından reddediliyor.
- [x] `source_verified=false`, `execution_authority=false` invariant'ları
  korunuyor.
- [x] Focused suite: `3 passed`.
- [x] Full backend suite: `536 passed, 1 skipped, 2 warnings`.
- [ ] Default minimumu karşılayan üç ayrı valid testnet observation.
- [ ] Remote CI: GitHub Actions kota/bütçe nedeniyle geçici disabled.

## Kesinlikle kapsam dışı

- Seri katmanının invalid raporu onarması veya source verification açması.
- Network probe scheduler/daemon, private endpoint veya order submission.
- Üç valid observation yokken live execution/default market-data terfisi.
- Gap olaylarının sentetik event ile doldurulması.

## Risk ve sonraki sınır

Seri yalnız doğrulanmış raporların sayısal özetidir; gerçek packet loss veya
exchange completeness kanıtı değildir. Bir sonraki sınır, default minimum `3`
ve ardından 5–15 dakikalık valid testnet gözlemlerinin aynı sembol ve aynı
operasyon koşullarıyla toplanmasıdır. Invalid oranı sıfır değilse execution
yatırımı ilerletilmemelidir.

## Değişiklik geçmişi

### 1.0.0 — 2026-09-07

- Tekil soak raporlarını fail-closed doğrulayan ve gap/recovery oranlarını
  aggregate eden observation series sözleşmesi eklendi.
