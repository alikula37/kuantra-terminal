<!-- doc-role: current-work-package -->
# H07 — Bounded Performance & Resource Limits

```yaml
work_package: H07
version: 3.1.0
status: InProgress
date: 2026-09-09
baseline_commit: 4e761fa
branch: codex/p1-wp01-evidence-ledger
strategy: KPR-001@current
depends_on: H01, H02, H04, H06
release_gate: H05-commercial-distribution-deferred
```

## Amaç

Kuantra'nın local-first Execution Intelligence & Trade Forensics Workstation
akışında sentetik veri boyutları büyüdüğünde ölçülebilir performans, bellek/disk
sınırı ve açık hata davranışı oluşturmak. Paket bir benchmark ve resource-boundary
kanıtıdır; maksimum kullanıcı/veri desteği veya production readiness ilanı değildir.

H05'in ticari dağıtım kapısı bu paket boyunca kapalı kalır. Ürün lisansı, third-party
notices, default-branch Dependabot, signing/notarization, Windows/Linux kanıtı, pilot
ve release işlemleri H07'nin kapsamına alınmaz.

## Davranış sözleşmesi

- Benchmark dataset'leri deterministik seed, sabit schema ve sentetik değerlerle
  üretilecek; gerçek kullanıcı verisi, credential, ağ veya canlı broker kullanılmayacak.
- En az `1k`, `10k` ve `100k` trade history boyutları ayrı ölçülecek. Her sonuç test
  host'u, OS/architecture, source commit, tracked-tree SHA, lock hash'leri, Python/
  Node/uv/toolchain sürümleri ve dataset seed'i ile bağlanacak.
- Import, query, projection rebuild, correction/replay, cancel ve Trade Evidence Pack
  export adımları için elapsed time, p50/p95/p99, peak RSS, temporary disk ve output
  determinism raporlanacak. Ölçülmeyen alan `UNKNOWN` kalacak.
- Resource budget aşımında işlem açık bir limit/error state ile duracak veya güvenli
  biçimde iptal olacak; kısmi başarı, sessiz veri kaybı veya `complete` sonucu
  üretilmeyecek. Canonical veriyi habersiz silen retention/cleanup eklenmeyecek.
- Evidence Pack p95 `<2s` KPS hedefi planlama hedefidir; baseline ölçülmeden destek
  limiti veya production SLO olarak ilan edilmeyecek.
- UI ölçümünde loading, cancel, error ve no-data/degraded durumları doğru görünür;
  network, AI order authority ve live execution yüzeyi açılmaz.

## Güncel teknik karar ve uygulama sırası

Bu bölüm, kullanıcının teknik kararları değerlendirme ve seçme yetkisini devretmesi
üzerine kaydedilmiştir. Aşağıdaki tarihsel "optimizasyon veya owner kararı" seçenekleri
için güncel seçim budur; ticari destek limiti veya release onayı değildir.

Puanlar ölçüm veya başarı olasılığı değil, mühendislik değerlendirmesidir.
Ağırlıklar: doğruluk/güven %40, kullanıcı değeri %30, maliyet/bakım %20,
kanıt kalitesi %10; her alt puan 1–5, yüksek daha iyi.

| Seçenek | Doğruluk | Değer | Maliyet | Kanıt | Toplam / 5 |
|---|---:|---:|---:|---:|---:|
| Sınırsız mikro-optimizasyonla her cold çağrıyı 2s altına zorlama | 4 | 3 | 1 | 3 | 3.0 |
| Mevcut üç cold örnekle hedefi gevşetip H07'yi kapatma | 2 | 2 | 5 | 1 | 2.5 |
| Bir hedefli optimizasyon paketi, ardından yeterli örnek ve UI/resource ölçümü | 5 | 5 | 4 | 4 | 4.7 |
| Full-chain doğrulamayı atlayarak hızlı sonuç verme | 1 | 2 | 4 | 1 | 1.9 |

Seçim üçüncü yoldur. Güvenlik/doğruluk invariant'ları puandan bağımsız veto
koşuludur. Sadece yeniden adlandırma, warm-up veya doğrulamayı erteleme ile cold
hedef geçmiş sayılamaz. Mevcut `<2s>` Evidence Pack planning hedefi korunur.

Sıra ve durma koşulları:

1. H07 içinde bir bounded paket: kalan full-chain maliyetini profille; yalnız
   doğruluğu aynı kalan, ölçümle gerekçelendirilmiş darboğazı optimize et.
   Canonical edge cases, corruption, cache invalidation, concurrent changes ve
   resource abort regresyonlarını koru. Kazanç yoksa denemeyi sonuçlandır;
   otomatik olarak yeni mikro-optimizasyon döngüsü başlatma.
2. Aynı temiz packaged artifact ile 1k/10k/100k için iki bağımsız run, her modda
   en az 20 operation örneği al. Warm process percentile için bağımsız process
   örneği gereklidir; tek process'in 20 operation'ı bu koşulu sağlamaz.
   Raw samples/min/max ve p50/p95/p99 birlikte kalsın; 20 örnek production tail
   garantisi değildir. OS cache uncontrolled sınırı korunur.
3. Aynı adayda gerçek UI→API→render cold/warm sürelerini, işlem sırasında başka
   local read/health isteğinin yanıtını ve loading/cancel/error davranışını ölç.
   Worker operation süresi kullanıcı bekleme süresinin yerine geçmez.
   UI'da pending verification, verified sonuç gibi sunulamaz. Async/job tasarımı
   ancak bloklama kanıtlanırsa ayrı bounded implementation olarak seçilir.
4. Projection-rebuild için yaklaşık 888 MB process peak RSS bulgusunu araştır;
   mevcut snapshot/rollback sözleşmesini koruyan bounded-memory yolunu tercih et.
   Repeated runs, concurrency ve düşük kaynak fixture'ları olmadan ölçülen peak'i
   ürünün RAM/disk limiti yapma. 100k test hacmidir; import hard cap değildir.
5. Kanıtı değerlendir: hedef karşılanırsa ilgili kriteri kapat; karşılanmazsa
   performance açığını açık tutarak UX/resource bulgularıyla somut bir hedef
   revizyonu gerekçelendir. Bu yetki devri teknik değerlendirme için yeterlidir;
   kullanıcıdan aynı soyut kararı yeniden isteme. Ticari destek/release kararı
   verilmiş sayılmaz. H07'nin tüm açık kabul koşulları sonuçlanmadan arşivleme.

Bu doküman değişikliği runtime davranışı değiştirmez; `670ee90` ölçümleri önceki
artifact'a aittir. H05 lisans/notices ve Dependabot ertelemesi, platform host
kanıtları ve ürünün read-only forensics kapsamı korunur.

Bu sıranın ilk bounded uygulaması `e3aacc8` ile başladı ve `4e761fa` ile tamamlandı:
Evidence Pack read bridge thread'inden ayrıldı, tek worker process içinde izole
edildi, pool başlangıcı lazy yapıldı ve worker-local verifier/adaptor state'i
bounded biçimde yeniden kullanıldı. Ardından aynı artifact ile planlanan iki-run
`1k/10k/100k` kampanyası ve native UI/concurrent-read ölçümü tamamlandı. 100k cold
operation p95 `<2s` hedefini karşılamadığı ve UI timer-gap percentile'ları
kanıtlanmadığı için sonraki otomatik mikro-optimizasyon döngüsü başlatılmayacaktır.
Yeni bir teknik deneme ancak yeni, ölçülebilir bir darboğaz hipoteziyle ayrı bir
bounded paket olarak seçilebilir; aksi yönde owner-approved measurement/resource/
support disposition gerekir.

## Red test kapsamı

- Aynı seed ve aynı source commit ile dataset üretiminin, import/query/rebuild ve
  Evidence Pack snapshot'ının deterministik olması.
- `1k/10k/100k` sentetik geçmişte canonical/projection/evidence sayılarının korunması;
  input permutation, replay ve duplicate import sonucu performans ölçümünü veya
  doğruluk snapshot'ını sessizce değiştirmemesi.
- Query/rebuild/import/cancel sırasında peak memory, temp disk ve süre limitlerinin
  ölçülmesi; limit aşımında rollback/explicit failure ve no-false-success.
- Büyük CSV/JSON, malformed input, missing coverage ve unsupported event fixture'ları
  için bounded rejection; dosya boyutu veya satır sayısı sınırsız kabul edilmemesi.
- Raporun host, seed, commit, tree/lock/toolchain, percentile ve hash alanları eksikse
  release-facing validator'ın fail-closed olması.
- Benchmark raporunun iki tekrarında sıralı ve hash'lenebilir sonuç üretmesi; yalnız
  “fast”/“responsive” gibi ölçümsüz iddiaların kabul edilmemesi.

## Uygulama sınırı

İlk adım mevcut import, projection, Evidence Pack ve test fixture yollarını okuyup
ölçülebilir operation boundary'lerini sabitlemektir. Önce red test/fixture ve rapor
şeması yazılacak; sonra gereken en küçük implementation yapılacaktır. Yeni dependency,
connector, database schema, market-data feed, AI capability veya UI ürün yüzeyi bu
pakete eklenmeyecektir.

## Acceptance criteria

- [x] Canonical JSON validation stdlib byte sözleşmesini korur; exponent yazımı,
  büyük tamsayı, Unicode/escape, duplicate/sırasız key, non-finite sayı ve nested
  secret regresyonları geçer. Hash hızlı yolu yalnız string-key/scalar string-int-null
  body için kullanılır. Bu değişiklik: 38 focused H07 testi PASS.
- [x] Kaynak süreç benchmark'ı ile gerçekten çalıştırılan packaged executable
  benchmark'ı ayrılır; fresh-process cold, warm ve append-tail koşulları ayrı ölçülür.
  Source contract `caef518`; packaged worker/launcher ve `cold`, `warm`,
  `append-tail` modları `af8e2a1` ile ayrıldı. `30be78d` ile fresh-process
  `projection-rebuild` ve process-level resource capture da açık sözleşmeye alındı.
  Final iki run × 20 sample kanıtı aşağıdaki kampanyalarda tamamlandı; H07'nin
  performans hedefi ve resource acceptance sonucu bu ayrımın dışında ayrıca
  değerlendirilir.
- [x] Explicit executable gerçekten çalıştırılır; normal data/log/backend/WebView
  startup'tan önce izole sentetik worker seçilir. PID/executable/pre-post artifact
  hash ve sonuç doğrulanır; worker/log manifest kalıcı yerel dizine yazılır.
  Source checkout gözlemi release build attestation sayılmaz.
- [ ] Canonical doğruluk düzeltmesi sonrası 1k/10k/100k ölçümleri yenilenir;
  cold hedef ve resource acceptance ayrı kanıtlarla sonuçlandırılır. `af8e2a1`
  final packaged kampanyası ölçümleri yeniledi ve 100k cold p95'in `<2s` hedefini
  karşılamadığını gösterdi. `30be78d` ile 100k fresh-process resource capture
  ve projection-rebuild kanıtı eklendi; 54/54 packaged manifestte RSS ve izole
  temporary-disk alanları `MEASURED`. Ancak `<2s` hedefi karşılanmadı ve resource
  acceptance için owner-approved bir limit/disposition henüz yoktur; kriter açık
  kalır. `67eafa2` ile projection rebuild yazımı deterministik 1,000-record
  `executemany` batch'lerine alındı; transaction/rollback ve schema değişmedi.
  Temiz packaged tekrarında 100k cold p95 `3350.5229 / 3152.2077 ms`, projection
  rebuild p95 `6718.6024 / 6287.9183 ms` operation ve `7919.5035 / 7359.8019 ms`
  process oldu. Bu bounded optimizasyon hedefi veya resource acceptance'ı
  kapatmadı; kriter açık kalır. `670ee90` ile canonical validation/read tekrarları
  azaltıldı ve temiz packaged tekrarında 100k cold p95 `2468.2571 / 2444.9360 ms`,
  projection rebuild p95 `5639.9834 / 5709.4251 ms` operation ve
  `6747.8792 / 6822.3076 ms` process oldu. 54/54 manifest ve 40 projection
  sample deterministik/ölçülmüş olsa da `<2s>` karşılanmadı. Bu change ayrıca
  kanıtın geçerli olduğu Mac arm64 + synthetic 100k + iki-run/sample-sayısı
  sınırını açıkça kaydeder; production SLO, maksimum supported history veya
  commercial support limit kararı vermez. Owner-approved resource/support
  disposition halen açık olduğundan kriter açık kalır. `4e761fa` ile aynı
  packaged executable üzerinde iki run × `1k/10k/100k`, her modda 20 operation
  örneği (`cold`, `warm`, `append-tail`, `projection-rebuild`) yenilendi; toplam
  366 packaged manifest ve 120/120 geçerli projection sample kaydedildi. Güncel
  100k cold operation p95 `2321.8877 / 2332.4201 ms`, projection operation p95
  `5141.0606 / 5143.9399 ms`, projection process peak RSS yaklaşık
  `400.4 / 400.5 MB` ve isolated temp footprint `388370264 B` oldu. Bu ölçümler
  `<2s>` hedefini veya production/resource/support disposition'ı kapatmaz.
- [x] Deterministic `1k/10k/100k` sentetik dataset ve tekrar üretilebilir benchmark
  raporu oluşturuluyor.
- [x] Import/query/projection rebuild/correction/replay/cancel/Evidence Pack export
  için p50/p95/p99, peak RSS ve temporary disk ölçümleri source/artifact kanıtına bağlı.
  1k tam benchmark'taki tek import örneği `UNKNOWN` kalır; ayrı `batch-size=100`
  ölçümü import percentile'larını tamamlar. `UNKNOWN` hiçbir yerde PASS sayılmaz.
- [ ] Resource limit, cancellation, malformed/oversized input ve partial/unknown
  coverage durumları fail-closed; canonical veri ve evidence lineage korunuyor.
  Dynamic budget abort/rollback import, correction, projection rebuild ve Evidence
  Pack sınırlarında; malformed/oversized input ve partial/unknown coverage
  propagation alt sınırlarında bounded backend kanıtı vardır. Legacy SQLite ve
  coverage-ready typed projection query'lerinde mid-operation abort bounded olarak
  uygulanmıştır. Evidence Pack, Reconciliation Inbox, Weekly Review ve CSV preview
  read/loading yüzeylerinde frontend cancellation/loading/error truth bounded olarak
  uygulanmıştır. Safe-persona görünür core read listesi ayrıca `c095025` ile audit
  edilmiştir; `kuantra_quant` altında deneysel workspace/Chart Vision yüzeyleri
  görünmez. H07'nin cold full-chain performans ve kalan resource acceptance boşlukları
  halen açıktır. `e3aacc8`→`4e761fa` ile native Evidence Pack read'i bounded async
  job ve tek izole worker process arkasına alınmış, worker pool lazy lifecycle ve
  bounded warm-state reuse kazanmıştır; bu UI isolation evidence'i bir RAM/support
  limiti veya responsiveness PASS değildir.
- [x] Backend correctness/performance regression suite ve frontend loading/cancel/error
  truth testleri geçiyor; yeni capability veya live execution yolu açılmıyor.
- [x] Aynı host ve aynı source/dataset girdisinde rapor snapshot/hash deterministik;
  eksik provenance veya ölçüm alanı `PASS` sayılmıyor.
- [x] Full backend/frontend/i18n/build gate, temiz Mac arm64 artifact ve gerekiyorsa
  exact mounted DMG smoke güncel evidence ile raporlanıyor.

## Kanıt planı

Her benchmark kaydı en az şu alanları taşıyacak: source commit, tracked source tree
SHA-256, backend/frontend lock SHA-256, OS/architecture, Python/Node/uv/toolchain,
dataset seed ve boyutu, operation, warm/cold koşulu, elapsed time percentile'leri,
peak RSS, temporary disk, result/error status, report SHA-256 ve artifact/executable
SHA-256. Ağ veya credential kullanılmadığı açıkça yazılacak. Benchmark sonucu hedefi
karşılamazsa hedef değiştirilmiş gibi değil, `OWNER_DECISION_REQUIRED` veya
`IMPLEMENTATION_REQUIRED` olarak raporlanacak.

## Kesinlikle kapsam dışı

Gerçek kullanıcı verisi, Windows migration ZIP'i, credential/Keychain yazımı, network
ve live broker, order gönderimi, AI order authority, yeni connector, funding/transfer
schema, tam hesap PnL/tax accounting, lisans/notices seçimi, Dependabot merge, signing,
notarization, pilot, release/tag ve main merge.

## Başlangıç kararı

H06'in bounded privacy/data-lifecycle kanıtı `a7b99b7` üzerinde tamamlanmıştır. Bu
kanıt H07'nin sentetik, non-release performans çalışmasına geçmek için yeterlidir;
H05 ticari dağıtım gate'i ve production iddiası değişmeden kalır. H07 tamamlandığında
sonuçlar ölçüm kanıtına göre sınıflandırılacak; hedef tutmadığında sınır sessizce
gevşetilmeyecek ve sonraki paket STATUS üzerinden seçilecektir.

## Güncel bounded uygulama ve ölçüm sonucu — 2026-09-09

### 2026-09-09 packaged worker — a850e7d/af8e2a1

`backend/desktop_main.py` diagnostic dispatch'i `app.core.paths` importundan önce
yapar. `desktop/h07_worker.py` yalnız kendi temporary fixture'ını oluşturur; normal
data directory, logging, runtime/market stream ve WebView başlamaz. Python audit
guard network/child-process çağrılarını reddeder; OS firewall iddiası değildir.
`scripts/run_h07_packaged_benchmark.py` explicit executable'ı gerçekten çalıştırır,
PID/path/hash/outcome ve pre/post artifact hash eşitliğini kontrol eder. Mevcut
output/evidence dizinine yazmaz; başarısız süreçte successful manifest üretmez.
PyInstaller yalnız worker ve mevcut H07 workload/provenance modüllerini ekler;
benchmark içinde source provenance collector çalıştırılmaz.

Red: 5 isolation/CLI test FAIL. Green: H07 worker + existing H07 **59 PASS**;
son full backend **752 PASS** (2 deprecation warning). Canonical locked local CI
`MERGE READY`: backend 752, frontend 25/102, i18n 608/608, production build,
arm64 PyInstaller ve normal WKWebView smoke PASS. Launcher/guard, append-tail
integrity ve campaign summary testleri bu 752 sayısına dahildir.
Docs/link ve diff gate PASS. Bu desktop değişikliğinin Windows/Linux host gate'i
henüz alınmadı; main merge/release yapılmaz.

Gerçek `.app` diagnostic komutu:

```text
.venv/bin/python scripts/run_h07_packaged_benchmark.py --executable "dist/Kuantra Terminal.app/Contents/MacOS/Kuantra Terminal" --artifact "dist/Kuantra Terminal.app" --size 1000 --repetitions 3 --evidence-dir artifacts/evidence/h07/packaged-worker-1000-v1
```

macOS 26.6.2 arm64 / Python 3.11.16; Node 20.20.2, npm 10.8.2, uv 0.12.10,
PyInstaller 6.22.2. `PACKAGED_PROCESS`, gerçek PID 9691, 1000 trade/projection ve
1003 immutable ledger event. Snapshot
`cf6a1ae220f083e0de63d4b8172fc860be9510555243af3072ace4a8a8f75d2e`
önceki source fixture ile eşit. Executable SHA-256
`a1ee09b5d2fdadaac2df35555c34a7ec78d370507d3f4acdcd90e7cdb2758b2c`;
`.app` tree SHA-256
`02a84893a239b652f1cecbe0ee1053fe01a4246767ec9c049f3581d5a2e09238`;
worker dosya SHA-256
`fb2eed5e167b217104229799e7958fb64fb16bef0b7303b3dedd8f29f5dec19f`;
manifest dosya SHA-256
`2f29069847b9d2b3c50a4e43ba7d1c3ba881abfc8a21fa88489037bad8d2f70f`.
Aynı komut yeni `packaged-worker-1000-v1-repeat` evidence diziniyle tekrarlandı:
ayrı PID 9742, aynı determinism snapshot ve sayımlar; pre/post hash kontrolü PASS.
Bu iki küçük diagnostic koşu, planlanan iki tam 20-sample performans koşusu değildir.
Manifest lock/toolchain ve `caef518` + dirty tree checkout gözlemini içerir.
Embedded build attestation değildir: source-to-binary `NOT_VERIFIED`, release
provenance `UNKNOWN` kalır. Yeni DMG/final distribution kanıtı üretilmedi.

Önceki mixed worker diagnostic'i `MIXED_AFTER_FIXTURE_IMPORT`, OS cache
`UNCONTROLLED`, `cold_process_measured=false` olarak kalır; aşağıdaki yeni modlar
bu sınırlamayı kaldırmadan koşul ayrımı sağlar. Final campaign protokol ayrımını ve
20×2 örnek yükünü tamamladı, ancak 100k cold hedefi ve process-level resource
acceptance'ı kapatmadı.

### 2026-09-09 cold/warm/append-tail protocol — af8e2a1

Fixture-backed packaged worker modları artık açıkça ayrıdır:

- `cold`: her sample ayrı packaged process, warm-up yok; Evidence Pack operation
  ve launcher process elapsed ayrı kaydedilir.
- `warm`: aynı process içinde bir warm-up dışarıda bırakılır; sonraki Evidence Pack
  örnekleri aynı verifier/cache durumu altında ölçülür.
- `append-tail`: warm-up sonrası synthetic `TradeCorrected` immutable event append
  edilir; timed `verify_chain` çağrısı `APPEND_TAIL` ve
  `verified_events_this_call=1` doğrular. `checked_events` toplam scope sayısı olarak
  korunur; iki alan birbirine karıştırılmaz.

Her fixture önce read-only contract ile doğrulanır, worker-owned temporary DB'ye
kopyalanır ve normal application data directory'ye dokunulmaz. Launcher explicit
executable'ı gerçekten çalıştırır; PID, path, worker outcome, pre/post executable/
artifact/fixture hash'leri ve process elapsed kaydedilir. Existing output veya
artifact içi evidence overwrite edilmez. Campaign scripti source process'te yalnız
sentetik fixture hazırlayıp, modları ayrı packaged process'lerde çalıştırır.
OS page cache `UNCONTROLLED`; bu bir OS firewall veya cache flush kanıtı değildir.
Process-level RSS/disk ölçülmüyorsa `null` kalır; sampler dosya sistemi veya süreç
ölçüm hatasını `UNKNOWN` olarak bırakır ve sıfır değerle kapatmaz.

Red→green: mode/fixture/append-tail sınırları ve launcher percentile testleri
focused H07/worker suite içinde **59 PASS**. Final packaged campaign, güncel clean
source commit ve arm64 `.app` ile aşağıda tamamlandı. Önceki 1k/10k/100k sanity
koşuları yalnız protokol ayrımını doğrulayan diagnostic kanıttır; final kabul için
yerine geçmez.

### 2026-09-09 final packaged campaign — af8e2a1

Kampanya şu komutla, yeni ve yalnızca sentetik evidence dizininde çalıştırıldı:

```text
.venv/bin/python scripts/run_h07_measurement_campaign.py --executable "dist/Kuantra Terminal.app/Contents/MacOS/Kuantra Terminal" --artifact "dist/Kuantra Terminal.app" --output-dir artifacts/evidence/h07/measurement-campaign-af8e2a1 --sizes 1000,10000,100000 --runs 2 --cold-samples 20 --warm-samples 20 --append-samples 20 --batch-size 1000
```

Kampanya `H07-SYNTHETIC-V1` seed'iyle `1k/10k/100k`, iki run ve her boyutta
`cold=20`, `warm=20`, `append-tail=20` operation örneği üretti. `cold` ve
`append-tail` her örnekte yeni packaged process kullandı; `warm` tek process'te
bir warm-up'ı dışarıda bırakarak 20 operation örneği topladı. Bu nedenle warm
process elapsed summary'si bir process örneği içerir ve percentile olarak
`UNKNOWN (n=1)` kalır. Toplam 246 packaged worker manifesti/raporu (120 cold,
6 warm process ve 120 append-tail) bağımsız doğrulamalardan geçti. Her raporda
`artifact_executed=true`, explicit executable/PID/path/outcome ve artifact/fixture
pre/post hash kontrolleri PASS'tir; cold PID'leri sample'lar arasında tekrarlanmaz.

| Sentetik geçmiş | Mod | Run 1 operation p50 / p95 / p99 (ms) | Run 2 operation p50 / p95 / p99 (ms) | Run 1 process p95 (ms) | Run 2 process p95 (ms) | Peak operation RSS R1 / R2 (MB) |
|---:|---|---:|---:|---:|---:|---:|
| 1,000 | cold | 36.0391 / 37.0081 / 37.1012 | 36.1552 / 36.5792 / 36.7293 | 843.6756 | 799.1822 | 113.2031 / 112.7656 |
| 1,000 | warm | 7.7295 / 7.9814 / 8.0232 | 7.5532 / 7.9245 / 7.9836 | UNKNOWN (n=1) | UNKNOWN (n=1) | 112.3281 / 112.2500 |
| 1,000 | append-tail | 0.9397 / 0.9750 / 0.9868 | 0.9227 / 0.9914 / 1.0666 | 835.6287 | 833.7728 | 112.5625 / 112.5625 |
| 10,000 | cold | 313.4448 / 321.1551 / 348.6781 | 314.7394 / 317.5536 / 326.7266 | 1116.6733 | 1147.6363 | 120.2188 / 120.2812 |
| 10,000 | warm | 32.7716 / 37.4768 / 65.4339 | 32.5240 / 33.1552 / 33.5258 | UNKNOWN (n=1) | UNKNOWN (n=1) | 119.9219 / 119.9062 |
| 10,000 | append-tail | 3.1846 / 3.3783 / 3.4009 | 3.1871 / 3.2884 / 3.4538 | 1129.4907 | 1156.7504 | 120.2344 / 120.2344 |
| 100,000 | cold | 3157.0720 / 3212.6465 / 3267.3199 | 3181.6296 / 3221.5029 / 3229.6554 | 4216.9276 | 4252.6488 | 164.1875 / 163.4062 |
| 100,000 | warm | 334.6402 / 372.2994 / 633.3648 | 338.0782 / 342.2595 / 346.6211 | UNKNOWN (n=1) | UNKNOWN (n=1) | 163.0156 / 163.0781 |
| 100,000 | append-tail | 25.4267 / 32.9072 / 58.5853 | 25.7336 / 26.4382 / 27.1972 | 4240.3164 | 4298.6460 | 164.1719 / 164.0625 |

Operation ölçümü Evidence Pack assembly (`cold`/`warm`) veya warm-up sonrası tek
immutable `TradeCorrected` append'in `verify_chain` maliyetidir (`append-tail`).
Append-tail raporlarının tamamı `verification_mode=APPEND_TAIL` ve
`verified_events_this_call=1` kaydetti; Evidence Pack'in scope toplamı olan
`checked_events` bundan ayrı korunur. Base fixture sayımları `N trades / N
projections / N+3 ledger events`, append-tail sonrası sayımlar `N / N / N+4` oldu.
Run'lar arasında snapshot ve sayımlar deterministiktir. Böylece correction eski
event'i silmeden yeni immutable lineage ekler; yeni schema veya funding/transfer
event type açılmaz.

100k packaged cold Evidence Pack operation p95'i iki run'da `3212.6465 ms` ve
`3221.5029 ms` oldu; bu `<2s` planning hedefinin karşılanmadığı anlamına gelir.
1k ve 10k cold operation p95'leri hedefin altındadır; warm ve append-tail sonuçları
cache/işlem koşulu diagnostikleridir ve desteklenen maksimum history veya SLO
ilanı değildir. Operation-level peak RSS raporlanmış, operation temporary disk
artışı `0 B` kalmıştır; launcher process-level RSS/disk bu kampanyada ölçülmediği
için `null`/`UNKNOWN` olarak korunur. OS page cache `UNCONTROLLED`'dır. Bu eksik
resource kanıtı PASS sayılamaz; H07 `IMPLEMENTATION_REQUIRED` kalır.

Kanıt bağlamı: commit
`af8e2a1a3d4cc9e9afd22f83dc25537e930de7c6`, tracked source tree SHA-256
`64587f9bf4747f44ffbd0dec608774d92d1faadf013f8b0de94c68472542c956` ve status
`clean`; macOS 26.6.2 arm64, Python 3.11.16, Node v20.20.2, npm 10.8.2,
uv 0.12.10, PyInstaller 6.22.2. Lock SHA-256'ları backend
`6291588602869af34e2a4db5d7244a627f4e139cbbd4b034b7cc07d890812399`, frontend
`b392a59d09ade73564ce082b1a5bc1236618ebeee11703a992980cfd1812882c`;
canonical local-CI report SHA-256
`576160d93c1166ed1d899e9d93a8fff7e961512069cd8a5d4d9a54ef6d90daa3` ve
13/13 step `MERGE READY`'dir. Çalıştırılan executable SHA-256
`3a9cd6c237303e856ea3e0013003816a44fb48ceb24d6f847fdd879ba8b277a8`, `.app`
artifact SHA-256
`6c1457118b92d7e03a1fb12800591dcc6753dab9350b66f42153714d2054fa01`.

Campaign report embedded body SHA-256
`a691001a06cd3aa750a392aaaa981d4614255b3e66401530db02da530ef57617`, full
`campaign-report.json` SHA-256
`df3d469e9a50aa45e1f9fb36088dade5633ce192112f270507a0423489b36d7a`,
`campaign-manifest.json` SHA-256
`0d972ff81c96db4fbc43140ee2c5640a65544d1892eeb9abaa93407dbb11d6bd`.
Campaign contract `real_data=false`, `credentials=false`, `network=false`,
`live_execution=false`, `support_limit_claim=false`; `source_fixture_preparation`
`SOURCE_PROCESS`, `source_to_binary_attestation=NOT_VERIFIED` ve
`release_provenance=UNKNOWN`. Bu non-release `.app` kampanyası DMG mount,
Developer ID, notarization, Gatekeeper veya Windows/Linux platform kanıtı değildir.

### 2026-09-09 process resource ve projection-rebuild kampanyası — 30be78d

Önceki kampanyadaki process-level `null` boşluğunu kapatmak ve 100k projection
rebuild'i gerçek packaged süreçte ölçmek için kod/test commit'i `30be78d` üzerinde
şu bounded kampanya çalıştırıldı:

```text
.venv/bin/python scripts/run_h07_measurement_campaign.py --executable "dist/Kuantra Terminal.app/Contents/MacOS/Kuantra Terminal" --artifact "dist/Kuantra Terminal.app" --output-dir artifacts/evidence/h07/resource-projection-30be78d-20260909 --sizes 100000 --runs 2 --cold-samples 3 --warm-samples 3 --append-samples 3 --projection-rebuild-samples 20 --batch-size 1000 --timeout 1800
```

Her launch yeni packaged process'tir; `warm` yalnız aynı process'te warm-up sonrası
operation örneklerini toplar. Launcher RSS'i `psutil.Process.memory_info().rss` ile,
geçici disk footprint'ini ise yalnız launch'a ait izole temporary root içindeki
regular-file occupancy olarak 10 ms örnekleme aralığıyla kaydeder. Bu değerler OS
memory/disk allocation limiti, OS page-cache kontrolü veya production support limiti
değildir; page cache `UNCONTROLLED` kalır.

| Mod | Process örneği/run | Operation p95 R1 / R2 (ms) | Process p95 R1 / R2 (ms) | Peak process RSS R1 / R2 (MB) | Peak isolated temp R1 / R2 (B) |
|---|---:|---:|---:|---:|---:|
| `cold` | 3 / 3 | 3183.8090 / 3219.8153 | 4254.5621 / 4245.9253 | 164.1562 / 165.1250 | 287690752 / 287690752 |
| `warm` | 1 / 1 | 343.6737 / 340.8124 | UNKNOWN (n=1) / UNKNOWN (n=1) | 163.0938 / 163.5312 | 287690752 / 287690752 |
| `append-tail` | 3 / 3 | 25.9072 / 25.2780 | 4349.1619 / 4242.9028 | 165.2031 / 164.3125 | 287760824 / 287773184 |
| `projection-rebuild` | 20 / 20 | 6877.9656 / 7336.8517 | 8009.7547 / 8501.7438 | 888.1719 / 888.2656 | 388370264 / 388370264 |

İki run'da toplam 54/54 `H07.packaged-manifest.v2` manifesti ve resource report'u
`MEASURED`'dir: 6 cold, 2 warm, 6 append-tail ve 40 projection-rebuild. Her
projection-rebuild örneğinde `ledger_valid=true`, `projections_written=100000`,
counts `100000 trades / 100000 projections / 100003 ledger events` ve snapshot
`f7df42fa141e9a903141fce3f6121093f31f5924d1c58e77939c2d78c753e0d8` aynıdır.
Operation-level projection-rebuild peak RSS'i run 1/run 2 için `304.2344 /
300.0312 MB`, temporary disk artışı `0 B`'dır; process-level değerler yukarıdaki
launch footprint'idir. `cold` 100k Evidence Pack operation p95'i
`3183.8090 / 3219.8153 ms` ile `<2s` planning hedefini yine karşılamaz; bu
sonuç hedefin gevşetildiği veya support limitinin belirlendiği anlamına gelmez.

Red→green: process-resource/projection-rebuild için eklenen üç red test ve
filesystem-error fail-closed testi düzeltme sonrası focused
`test_h07_bounded_performance.py` + `test_h07_packaged_worker.py` içinde
**63 PASS**; full backend **756 PASS / 2 deprecation warning**. Locked local CI
`uv run --offline --no-project --with-requirements backend/requirements.lock
python scripts/run_local_ci.py` ile 13/13 step `MERGE READY`: frontend 25/102,
i18n 608/608, production build, arm64 PyInstaller ve native WKWebView smoke PASS.
Local CI report SHA-256 `3433660d5e26433fe9f68f1b209c13911dbf4a9af147338ffbd7d199f92d6c47`,
smoke report SHA-256 `73724c2e40820db1d87b5b17f95a72db11634c8cebfbc6439106b3f68fb2cdb5`.

Provenance: source commit `30be78d46415923e308b716e2a267aa7f2ff5228`, tracked tree
SHA-256 `d18591bc73560b7e31730d3b5ab801d48d2cab45fc584dd4f44b75a4c3f9ff9e` ve
tracked status `clean`; macOS 26.6.2 arm64 (Darwin 25.6.0), Python 3.11.16,
Node v20.20.2, npm 10.8.2, uv 0.12.10, PyInstaller 6.22.2. Backend lock SHA-256
`6291588602869af34e2a4db5d7244a627f4e139cbbd4b034b7cc07d890812399`, frontend
lock SHA-256 `b392a59d09ade73564ce082b1a5bc1236618ebeee11703a992980cfd1812882c`.
Çalıştırılan executable SHA-256
`93475a6f2d29e4dad51bd6bdc20b9ffa5d6bff8edb734253af7f8350ead6bbff`, `.app`
artifact SHA-256 `d27cbd9cdfb9c9cb4846d4284320b32cd5b4836ccd97a70ed6e4c2eb84c04991`.
Campaign report embedded/body SHA-256
`ad45ae7441250d40489e4c02208dfbc7f00cdeb78063a22fe31c8ee3a91f3470`, full
`campaign-report.json` SHA-256 `c8e047f78979db3b7ec689365678071f624f8a3ddc9294b10665cc2e998835ef`,
`campaign-manifest.json` SHA-256
`f78f6d6a7adc32d625420ae2fbde0441425fb1be9c22de81442369a1dc3e6a42`.
Campaign contract `real_data=false`, `credentials=false`, `network=false`,
`live_execution=false`, `support_limit_claim=false`; `source_fixture_preparation`
`SOURCE_PROCESS`, `source_to_binary_attestation=NOT_VERIFIED` ve
`release_provenance=UNKNOWN`. Local CI provenance contract is `COMPLETE` for this
development artifact; it is not Developer ID/notarization, DMG, Gatekeeper,
Windows/Linux, or release evidence. H07 remains `IMPLEMENTATION_REQUIRED`; next
decision is an explicit optimization or owner-approved measured boundary, without
silently changing `<2s>`.

### 2026-09-09 projection rebuild batch-write optimization — 67eafa2

The projection rebuild path now uses one reusable deterministic upsert statement
and bounded 1,000-record `executemany` batches. The existing delete/write/commit
transaction boundary is preserved; correction lineage, projection values,
rollback behavior and schema are unchanged. Resource checks run before and after
each bounded batch rather than once per row. No funding/transfer event type,
ledger schema or new product capability was added.

The red test `test_projection_rebuild_uses_bounded_batch_writer` failed before the
implementation (`1 failed, 39 passed`). After the implementation, the focused H07
file passed `40/40`, the combined H07/packaged-worker suite passed `64/64`, and
the H07 plus P1-WP02 projection regression passed `52/52`. The source file also
passed compileall and the tracked diff passed `git diff --check`.

The clean packaged campaign used this command in a new ignored evidence directory:

```text
.venv/bin/python scripts/run_h07_measurement_campaign.py --executable "dist/Kuantra Terminal.app/Contents/MacOS/Kuantra Terminal" --artifact "dist/Kuantra Terminal.app" --output-dir artifacts/evidence/h07/resource-batch-67eafa2-20260909 --sizes 100000 --runs 2 --cold-samples 3 --warm-samples 3 --append-samples 3 --projection-rebuild-samples 20 --batch-size 1000 --timeout 1800
```

It executed the explicit arm64 `.app` binary in two 100k runs with 3 cold,
3 append-tail and 20 fresh-process projection-rebuild samples per run, plus one
same-process warm sample per run. The resulting p95/resource summaries are:

| Mode | Operation p95 R1 / R2 (ms) | Process p95 R1 / R2 (ms) | Peak process RSS R1 / R2 (MB) | Peak isolated temp R1 / R2 (B) |
|---|---:|---:|---:|---:|
| `cold` | 3350.5229 / 3152.2077 | 4434.6318 / 4137.1279 | 165.2969 / 163.3281 | 287690752 / 287690752 |
| `warm` | 329.9364 / 327.7377 | UNKNOWN (n=1) / UNKNOWN (n=1) | 163.1719 / 163.2812 | 287690752 / 287690752 |
| `append-tail` | 28.3022 / 25.2925 | 4236.1840 / 4176.3699 | 165.3750 / 163.4219 | 287773184 / 287760824 |
| `projection-rebuild` | 6718.6024 / 6287.9183 | 7919.5035 / 7359.8019 | 889.2812 / 888.3281 | 388370264 / 388370264 |

All 54/54 packaged manifests recorded `MEASURED` process resources. All 40
projection rebuilds reported `ledger_valid=true`, `projections_written=100000`,
counts `100000 trades / 100000 projections / 100003 ledger events`, and the same
deterministic snapshot
`f7df42fa141e9a903141fce3f6121093f31f5924d1c58e77939c2d78c753e0d8`. Operation
peak RSS for projection rebuild was `298.4062 / 294.9688 MB`, and operation
temporary disk growth was `0 B`; process-level peak isolated temporary footprint
was `388370264 B` in both runs. The lower projection p95 versus `30be78d` is
directionally consistent in both runs, but OS page cache is `UNCONTROLLED` and
the two artifact/runs do not provide an isolated causal percentage claim.

The 100k cold Evidence Pack p95 remains above the `<2s>` planning target, so this
optimization does not close H07 and does not define a supported history/resource
limit. The target is not silently relaxed; the remaining choice is another
evidence-led optimization of the full-chain cost or an explicit owner-approved
measured-boundary decision.

Campaign report embedded SHA-256 is
`8b37e07392569b928d78da17b1e11818f1dc0cbf3438f469fc4d39405ae319f3`; full
`campaign-report.json` SHA-256 is
`faa90561bfc92d0f3286e516ded334d7c15573c6bf79070562868729f6ef58b2`; and
`campaign-manifest.json` SHA-256 is
`31b5c2327043404a3e7e2408805e1eb47bedb74dc45b8cd2d11769bc4b08e317`.
The clean checkout is commit `67eafa2aaaa311ad8fb1488dec5f121c3e825f56` with
tracked source tree SHA-256
`f7925aab979cb164a92aeb8601e9a0edd0c5a5fc21f6a09e3da1f7c235346748`.
Platform/toolchain is macOS 26.6.2 arm64 (Darwin 25.6.0), Python 3.11.16,
Node v20.20.2, npm 10.8.2, uv 0.12.10 and PyInstaller 6.22.2. Backend/frontend
lock SHA-256 values are
`6291588602869af34e2a4db5d7244a627f4e139cbbd4b034b7cc07d890812399` and
`b392a59d09ade73564ce082b1a5bc1236618ebeee11703a992980cfd1812882c`.
The executed executable SHA-256 is
`1e0905928070c32539f1f1b25fc0ba0d9f50ab0ea62c06c84ec1a79087e7ece8`, `.app`
tree SHA-256 is
`bcbac11a1981108e99195c9f7d2b38a0d22de189dfb1518f051108b838f10ffb`, local-CI
report SHA-256 is
`7f3f26724548695faa7756aa982689d44393b9edd6e42d93e0ae576c2686f268`, and
local-CI smoke report SHA-256 is
`04f74054b1f2ae9126005a7caeeb1e76ddca2972c386ad1d717bda0d042a8d13`.
Local CI was `MERGE READY` with 13/13 steps: 757 backend tests with 2
deprecation warnings, frontend 25 files/102 tests, i18n 608/608, production
build, arm64 PyInstaller build and native WKWebView smoke. Its supply-chain step
still reports the deferred commercial notice owner review.

Campaign contract is `real_data=false`, `credentials=false`, `network=false`,
`live_execution=false`, `support_limit_claim=false`; fixture preparation is
`SOURCE_PROCESS`, source-to-binary attestation is `NOT_VERIFIED` and release
provenance is `UNKNOWN`. Local-CI provenance is `COMPLETE` for this development
artifact. The campaign is not DMG, signing/notarization, Gatekeeper,
Windows/Linux or production evidence. The default local-CI desktop smoke
attempted the existing public market-data behavior; that is separate from this
network-disabled synthetic campaign and is not runtime-offline proof.

### 2026-09-09 full-chain cold optimization ve ölçüm sınırı — 670ee90

The remaining Evidence Pack cold path was optimized without changing the
canonical contract or the product boundary. Canonical JSON validation now uses
an `orjson` fast path only after an exact canonical-byte match, with conservative
exponent handling; the strict stdlib path remains authoritative for exponent,
large-integer and other edge cases. `get_evidence_pack` reuses the coverage and
trade snapshot already evaluated for the request, then derives market context
from that snapshot instead of repeating the public read path. No ledger schema,
projection semantics, funding/transfer event type, correction lineage,
transaction boundary or AI/order authority changed.

The two new red tests failed before the implementation (`2 failed, 40 passed`):
the exact `orjson` path was not used and Evidence Pack assembly repeated the
coverage read. After the implementation, the focused H07 file passed `42/42`,
the combined H07/packaged-worker suite passed `66/66`, and the relevant H07,
P1-WP02 projection, Evidence Pack boundary and canonical persistence regression
set passed `96/96`. A source-only cProfile diagnostic moved
`get_evidence_pack` from about `5.720 s` to `4.677 s` and `verify_chain` from
about `5.392 s` to `4.527 s`; these values guide optimization only and are not
packaged SLA evidence.

The clean packaged campaign used this command in a new ignored evidence
directory:

```text
.venv/bin/python scripts/run_h07_measurement_campaign.py --executable "dist/Kuantra Terminal.app/Contents/MacOS/Kuantra Terminal" --artifact "dist/Kuantra Terminal.app" --output-dir artifacts/evidence/h07/cold-chain-670ee90-20260909 --sizes 100000 --runs 2 --cold-samples 3 --warm-samples 3 --append-samples 3 --projection-rebuild-samples 20 --batch-size 1000 --timeout 1800
```

It executed the explicit arm64 `.app` executable in two 100k runs with 3
fresh-process cold, 3 same-process warm, 3 fresh-process append-tail and 20
fresh-process projection-rebuild samples per run. The p95/resource summaries
are:

| Mode | Operation p95 R1 / R2 (ms) | Process p95 R1 / R2 (ms) | Peak process RSS R1 / R2 (MB) | Peak isolated temp R1 / R2 (B) |
|---|---:|---:|---:|---:|
| `cold` | 2468.2571 / 2444.9360 | 3481.5726 / 3448.4742 | 163.3906 / 164.2188 | 287690752 / 287690752 |
| `warm` | 143.1432 / 144.6606 | UNKNOWN (n=1) / UNKNOWN (n=1) | 162.9688 / 163.2969 | 287690752 / 287690752 |
| `append-tail` | 25.9044 / 25.7300 | 3523.4416 / 3501.9004 | 163.4531 / 163.3750 | 287773184 / 287773184 |
| `projection-rebuild` | 5639.9834 / 5709.4251 | 6747.8792 / 6822.3076 | 887.3594 / 887.8750 | 388370264 / 388370264 |

All 54/54 packaged manifests recorded `MEASURED` process resources. All 40
projection-rebuild samples were valid, wrote 100000 projections from
`100000/100000/100003` trade/projection/ledger-event counts and produced the
same determinism snapshot
`f7df42fa141e9a903141fce3f6121093f31f5924d1c58e77939c2d78c753e0d8`. The cold
and projection p95 values are lower than the preceding packaged campaign in
both runs, but OS page cache is `UNCONTROLLED`; the artifacts/runs do not
establish an isolated causal percentage improvement. The 100k cold operation
p95 remains above the `<2s>` planning target, so H07 remains open.

This package records the following explicit measurement boundary: one clean
Mac 26.6.2 arm64 packaged `.app` executable, synthetic `H07-SYNTHETIC-V1` data
at 100000 records, two runs and the sample counts above, with network,
credentials, real data and live execution disabled and OS page cache
uncontrolled. The boundary is valid for reproducible development measurement
only. It does not define a production SLO, maximum supported history, resource
cap or commercial support limit; owner approval for any such production
disposition remains a separate H07 gate. `UNKNOWN` warm process percentiles
remain `UNKNOWN` and are not converted to PASS or zero. No source-to-binary
attestation, release provenance, DMG, signing/notarization, Gatekeeper,
Windows/Linux or production claim is inferred.

Campaign report embedded SHA-256 is
`65cb34aa9fdb982f109fc0d36b59c3e7e69d0d040e51bcb5da4a83162e458bde`; full
`campaign-report.json` SHA-256 is
`df590c955af7e7233176f4600f5f95ca2b17c75c78e1f9fbf6bb259d9361b3d8`; and
`campaign-manifest.json` SHA-256 is
`54dbdc13dfce353d068ee5ff9dc90e56457d9a342fa83668207f124c70137a4c`.
The clean checkout is commit
`670ee9016ecc133ed998c7274738ed1ec9d697fe` with tracked source tree SHA-256
`68dc4ed4f8d65756489fcd0f6c92d39bedfd7b067bfee7c24a8af728b4141be9` and clean
tracked status. Platform/toolchain is macOS 26.6.2 arm64 (Darwin 25.6.0),
Python 3.11.16, Node v20.20.2, npm 10.8.2, uv 0.12.10 and PyInstaller 6.22.2;
backend/frontend lock SHA-256 values are
`6291588602869af34e2a4db5d7244a627f4e139cbbd4b034b7cc07d890812399` and
`b392a59d09ade73564ce082b1a5bc1236618ebeee11703a992980cfd1812882c`.
The executed arm64 executable SHA-256 is
`301d366b2167b77604d8dfd610143de5b8924d2a728af42abc3e4d84c4f59836`; the
`.app` tree SHA-256 is
`6b656164a7440c55099c10914189ede60744df3b940f26fb1b2e916cda6baad8`;
the clean local-CI report SHA-256 is
`e72be9ad813bc7003608eebcc2d66caa543cf241775e1546dd94060e862760d0`; and
the local-CI smoke report SHA-256 is
`7e6a29adceda53ad0b48700b99ec34c0614be578b492984ac30bb5fabfc9346b`.
Local CI was `MERGE READY` with 13/13 steps: 759 backend tests with 2
deprecation warnings, frontend 25 files/102 tests, i18n 608/608, production
build, arm64 PyInstaller build and native WKWebView smoke. Its supply-chain
step still reports the deferred commercial notice owner review.

Campaign contract is `real_data=false`, `credentials=false`, `network=false`,
`live_execution=false`, `support_limit_claim=false`; fixture preparation is
`SOURCE_PROCESS`, source-to-binary attestation is `NOT_VERIFIED` and release
provenance is `UNKNOWN`. Local-CI provenance is `COMPLETE` for this development
artifact. The default local-CI desktop smoke attempted the existing public
market-data behavior; that is separate from this network-disabled synthetic
campaign and is not runtime-offline proof.

### 2026-09-09 desktop worker isolation, cache reuse ve final ölçüm — 4e761fa

The selected bounded implementation sequence was completed across `e3aacc8`,
`dfa7252`, `5b82473` and `4e761fa`. The native Evidence Pack read now uses a
strictly validated asynchronous bridge job, a single isolated worker process and
a bounded four-job/300-second retention window. The process is created lazily,
closed with the desktop runtime and reconstructs only the existing read adapters;
it does not start the application runtime, connector or market stream. A small
process-local adapter/verifier cache reuses warm state. This keeps heavy forensic
work away from the bridge/UI process without changing the canonical ledger,
projection, correction lineage, schema, funding/transfer boundary or authority
model. The worker is a read-side implementation boundary, not a production RAM
limit or support promise.

Red→green evidence: the new bridge/job contract tests first failed because the
API did not exist. After implementation the focused desktop bridge suite passed
`12/12`, the frontend backend adapter suite `18/18`, and the relevant desktop,
H07 and packaged-worker backend set `86/86`. The full backend suite passed
`764` tests with two deprecation warnings; the full frontend suite passed `104`
tests in `25` files; frontend production build and i18n parity passed `608/608`.

The locked local gate was:

```text
uv run --offline --no-project --with-requirements backend/requirements.lock python scripts/run_local_ci.py
```

It returned **MERGE READY** with 13/13 steps on macOS 26.6.2 arm64 (Darwin
25.6.0), Python 3.11.16, Node v20.20.2, npm 10.8.2, uv 0.12.10 and PyInstaller
6.22.2. The local-CI report file SHA-256 is
`28f13f08bafd3fa08dd211f9a30a34b3ce0b012fae69896bc8773b08314c17da`; its
development provenance is `COMPLETE`, tracked source tree is clean, executable
SHA-256 is
`4052c8635f7dc1784ea328d52e3d66414476938b38a4b4210e045626df6d5f44`, and the
`.app` tree SHA-256 is
`92839bb06ec755d340e6368bc2643373ca6051a14051133c1efb8c44053ec843`.
The local-CI smoke report SHA-256 is
`dc5808335cb7002dd6504722726438add28342b75c34cbf9d16b5b655e2b1f08`.

The packaged campaign used this command and a new ignored evidence directory:

```text
.venv/bin/python scripts/run_h07_measurement_campaign.py --executable "dist/Kuantra Terminal.app/Contents/MacOS/Kuantra Terminal" --artifact "dist/Kuantra Terminal.app" --output-dir artifacts/evidence/h07/full-chain-4e761fa-20260909 --sizes 1000,10000,100000 --runs 2 --cold-samples 20 --warm-samples 20 --append-samples 20 --projection-rebuild-samples 20 --batch-size 1000 --timeout 1800
```

The same explicit arm64 executable was run in two independent runs with 20
operation samples for each of `cold`, `warm`, `append-tail` and
`projection-rebuild` at each size. This produced 366 packaged manifests (cold,
append-tail and projection-rebuild use fresh processes; warm uses one process
per size/run after an excluded warm-up). All 120 projection-rebuild samples were
valid, wrote the expected projections and retained the same deterministic
snapshot. Operation p95 values are:

| Synthetic history | `cold` R1 / R2 (ms) | `warm` R1 / R2 (ms) | `append-tail` R1 / R2 (ms) | `projection-rebuild` R1 / R2 (ms) |
|---:|---:|---:|---:|---:|
| 1,000 | 27.5070 / 27.9079 | 5.2767 / 5.2673 | 0.9973 / 0.9317 | 56.7655 / 52.7823 |
| 10,000 | 234.3171 / 235.0934 | 15.8222 / 19.6310 | 3.2873 / 3.2656 | 515.8394 / 514.9843 |
| 100,000 | 2321.8877 / 2332.4201 | 140.3421 / 140.4340 | 25.2783 / 25.2622 | 5141.0606 / 5143.9399 |

For 100k, process/resource evidence is:

| Mode | Process p95 R1 / R2 (ms) | Peak process RSS R1 / R2 (MB) | Peak isolated temp R1 / R2 (B) |
|---|---:|---:|---:|
| `cold` | 3303.9205 / 3318.6734 | 163.5000 / 163.4531 | 287690752 / 287690752 |
| `warm` | UNKNOWN (n=1) / UNKNOWN (n=1) | 163.3281 / 163.3281 | 287690752 / 287690752 |
| `append-tail` | 3374.3359 / 3361.3175 | 163.5312 / 163.4688 | 287777304 / 287773184 |
| `projection-rebuild` | 6217.4225 / 6208.4966 | 400.4375 / 400.5156 | 388370264 / 388370264 |

The current cold p95 remains above the `<2s>` planning target. The values are
lower than the preceding `670ee90` campaign, but OS cache is `UNCONTROLLED`, so
the runs do not prove an isolated causal percentage. The campaign report file
SHA-256 is
`108df12331909af500723427096cb828d2a0c92bd019105be4693ac3a09d605f`; its
embedded report SHA-256 is
`608424a3e2e6fb881aca309fefcd1cec5c763899b9e12b5fe211b7b2481837fb`; and the
campaign manifest SHA-256 is
`b2f96cbcd8c2eb3b435173dd4aae035b9f829b58424259f8f7332ce3a6ee2b9a`. The
campaign checkout is `4e761fa028f92f72de8305516c2b844f130365cf` with tracked
source tree SHA-256
`07f70a19d29b0e4856e3fa376447d9e04f00d61478840bbf3e60ac0ce4f1d1a1`, backend
lock SHA-256
`6291588602869af34e2a4db5d7244a627f4e139cbbd4b034b7cc07d890812399` and
frontend lock SHA-256
`b392a59d09ade73564ce082b1a5bc1236618ebeee11703a992980cfd1812882c`.
The campaign contract is `real_data=false`, `credentials=false`, `network=false`,
`live_execution=false`, `support_limit_claim=false`, with
`artifact_executed=true`, `source_to_binary_attestation=NOT_VERIFIED` and
`release_provenance=UNKNOWN`.

The native UI report was run against a clean 100k synthetic fixture with
`KUANTRA_MARKET_DATA_ENABLED=false` and the explicit current executable. React,
bridge, health, push-sink and plugin-boundary checks passed; loading was observed;
concurrent health/read calls returned HTTP 200; and the renderer was actual native
`wkwebview`. The cold sample took 4000 ms with a maximum observed timer gap of
1002 ms, while the warm sample took 819 ms with a 688 ms maximum gap. The report
correctly retains `process_cold=false`, `percentiles=UNKNOWN_SINGLE_SAMPLE` and
`network_isolation=NOT_VERIFIED`; these single-run timer observations are
diagnostic and are not a UI responsiveness PASS. Native report SHA-256 is
`e04d10148e7f7bf7edffbafbbffde8faa0ddafe3d779246fde0fd0e02b0aa95d`.

Accordingly the performance/resource acceptance criterion remains unchecked:
the `<2s>` target, a statistically sufficient UI responsiveness boundary and an
owner-approved production/resource/support disposition are still open. No
maximum supported history, RAM limit, commercial support limit, release
provenance, DMG/signing/notarization, Windows or Linux claim is inferred.

### 2026-09-09 doğruluk düzeltmesi — a97499b

`5a70f8b` payload/provenance hızlı kabulü, stdlib canonical sözleşmesinin reddettiği
`{"x":1e-7}` metnini kabul ediyordu. Payload validation stdlib'e döndürüldü;
hash serializer hızlı yolu açık tür kontrolüyle sınırlandı. Scalar leaf traversal
iyileştirmesi korunur. Üç red test önce başarısız oldu; düzeltme sonrası 38 H07 testi
PASS. Yeniden hash'lenmiş noncanonical payload da chain verification'da reddedilir.
Schema, event hash formatı veya veri migration'ı değişmedi.

Komut: `uv run --offline --no-project --with-requirements backend/requirements.lock
python scripts/run_local_ci.py`. Sonuç `MERGE READY`: backend 731 (2 deprecation
warning), frontend 25/102, i18n 608/608, arm64 build ve native WKWebView smoke PASS.
Host macOS 26.6.2 arm64; commit öncesi tracked diff ile koşuldu, clean release
artifact kanıtı değildir. Varsayılan smoke public network bağlantısını denedi.

**Önceki performans kanıtının sınırı:** aşağıdaki `5a70f8b` ölçümleri geçmiş kaynak
Python süreci ölçümleridir. Benchmark executable/DMG hash'lerini kaydeder fakat
executable'ı çalıştırmaz. Ayrı mounted DMG smoke geçerlidir; bu durum benchmark'ı
packaged runtime performans kanıtına dönüştürmez. Manuel cold p95 hesabı canonical
percentile fonksiyonuyla yeniden hesaplanmalıdır; yeni repository instance'ları
module/OS cache'lerinin soğuk olduğunu kanıtlamaz. Bu düzeltmeden sonra geçmiş
performans sayıları güncel davranışın veya `<2s` hedefinin kanıtı değildir.

### 2026-09-09 ölçüm sözleşmesi — caef518

Canonical düzeltme `a97499b`'dir. Source benchmark raporu `SOURCE_PROCESS`,
`artifact_executed=false`, `cold_process_measured=false`, `os_cache=UNCONTROLLED`
alanlarını taşır. Artifact hash metadata'sı execution iddiasına yükseltilemez;
validator sahte packaged execution değerini reddeder. Correction fixture sayısı
ölçüm tekrarından ayrıldı (üç veya küçük dataset boyutu). 3/5 tekrar arasında sayım
ve determinism snapshot aynı kalır. Default rapor yolu ignore edilmiş
`artifacts/evidence/h07/` altındadır. Native benchmark worker ve kalıcı manifest,
iki koşuda 20 fresh-process cold örneği ve güncel performance gate henüz açık.

Komut `.venv/bin/python -m pytest backend/tests -q --tb=short`: 732 PASS,
2 deprecation warning. Focused H07 39 PASS; diff/docs gate PASS. Bu alt paket yalnız
benchmark harness/test/docs değiştirir; yeni native binary veya smoke kanıtı üretmez.

Yerel diagnostic komut: `.venv/bin/python scripts/run_h07_benchmark.py --sizes 1000
--batch-size 100 --repetitions 20 --output artifacts/evidence/h07/canonical-source-1000.json`.
macOS 26.6.2 arm64 / Python 3.11.16 üzerinde MEASURED; 1000 trade/projection,
1003 ledger event. Rapor kaynak commit `a97499b` ve dirty tracked tree kaydeder;
artifact UNKNOWN/provenance INCOMPLETE korunur. Evidence Pack p95 12.3187 ms
(20 örnek) yalnız bu kaynak süreç koşuluna aittir; cold/native gate değildir.
Import 10, correction/replay 3 örnektir; `--repetitions 20` her operasyon için
20 örnek garantisi değildir. Raporun embedded body digest'i
`377cd4e856b0dc22c10bf0a039aa5b76b1850f2292598f4d13ff793e6d4a1bbb`;
bu değer dosyanın tamamının SHA-256 değeri değildir. Rapor yereldir, Git'e eklenmez.

`46531e4` ile dynamic resource-check callback'leri SQLite journal write,
projection rebuild, ledger verification/export ve Trade Evidence Pack assembly
sınırlarına eklendi. Explicit RSS/disk budget aşımı `SQLiteOperationResourceLimit`
veya benchmark `BenchmarkResourceLimitError` olarak fail-closed yükseliyor;
grouped import, correction ve projection transaction'ları commit öncesi rollback
oluyor. `6af4fd9` ile budgetsiz baseline ölçümünde guard'ın kendisinin performansı
bozmaması sağlandı: dynamic probe yalnız explicit budget'ta ölçüm yapıyor; ilk,
periodic ve commit/return sınırları korunuyor. Şema genişletilmedi, funding/transfer
event type eklenmedi ve immutable correction lineage korunuyor.

`6748d96` ile CSV import boundary'si strict parsing, extra-column rejection,
UTF-8 byte-based field guard ve review-gated atomic import davranışıyla
fail-closed hale getirildi. Header-only/empty input `CSV_NO_DATA` olarak
reddediliyor; malformed veya mixed input hiçbir trade yazmadan
`REJECTED` ya da `PARTIAL/USER_REVIEW_REQUIRED` dönüyor. Trade Evidence Pack
coverage summary, source'un açık `PARTIAL`, `UNKNOWN` veya `NOT_AVAILABLE` trade
snapshot değerini compatibility row varlığıyla `COMPLETE`'e yükseltmiyor.
Funding/transfer schema'sı ve ledger event type'ları değişmedi.

`5137383` ile `SQLiteDriver.list_trades`, typed projection query'si ve
`TradeReadAdapter` aynı cooperative `resource_check` boundary'sini taşıyor:
query başında, her materialize edilen trade row öncesinde ve başarılı bitişte
kontrol çalışıyor. Limit callback'i mid-stream hata verirse cursor/connection
`finally` ile kapanıyor, partial list dışarı dönmüyor ve okuma yolu false-success
üretmiyor. Legacy compatibility path ve exact-coverage typed projection path
ayrı red testlerle doğrulandı; H07 benchmark query callback'i de aynı boundary'ye
bağlandı. Bu read-only abort yeni schema, event type veya funding/transfer
kapsamı eklemiyor.

`27b3404` ile Evidence Pack, Reconciliation Inbox ve Weekly Review read request'leri
explicit `AbortController`, kullanıcıya görünür cancel state'i, stale-response
suppression ve unmount cleanup ile bounded hale getirildi. CSV preview aynı
korumayı taşır; import mutation'ı native bridge rollback garantisi olmadığı için
kullanıcıya iptal edilebilir gibi sunulmaz ve import sırasında modal kapanışı
devre dışı kalır. Loading state'leri `role=status`, hata ve iptal state'leri
`role=alert` ile görünürdür.

`42d67c6` ile Dashboard'ın dört portföy read endpoint'i tek cooperative
`AbortController` ile yüklenir; stale response'lar bastırılır, herhangi bir endpoint
başarısız veya malformed dönerse partial dashboard gösterilmez ve retry/cancel/error
state'leri explicit kalır. Quant Analytics aynı sözleşmeyle quant scorecard ve symbol
breakdown response shape'lerini doğrular; backend hatası veya incomplete payload sıfır
scorecard'a çevrilmez. Header portfolio telemetry de abort-on-unmount/stale guard ve
explicit unavailable/loading state taşır; backend erişilemezken sahte `$0.00` değerleri
gösterilmez. Yeni endpoint, schema, live execution veya plugin capability açılmadı.

`3de57c5` ile JournalView trade-list read yolu aynı bounded read sözleşmesine
taşındı: başarılı response shape'i strict doğrulanıyor; `AbortController`, kullanıcı
cancel'i, request-generation/stale-response guard ve unmount cleanup uygulanıyor;
loading, cancelled, error ve retry state'leri explicit. HTTP hata, malformed başarılı
payload veya geç response hiçbir koşulda boş journal olarak gösterilmiyor. Bu paket
yalnız mevcut trade-list read davranışını sınırlar; yeni endpoint, schema, live
execution veya plugin capability açmaz.

`f57da9d` ile MAE/MFE analytics read yolu bounded hale getirildi: response status,
numeric alanlar, excluded trade, stop sensitivity ve point shape'leri strict
doğrulanıyor; `READY`, `NO_DATA` ve `UNAVAILABLE` ayrımı korunuyor. `AbortController`,
kullanıcı cancel'i, request-generation/stale-response guard ve unmount cleanup ile
loading, cancelled, error, unavailable ve retry state'leri explicit. HTTP hata,
malformed başarılı payload veya geç response chart/empty success olarak gösterilmiyor;
valid `UNAVAILABLE` sonucu alert ve retry ile kalıyor. Descriptive candle-bar
approximation ve no-target boundary değişmedi; yeni capability, schema, live execution
veya AI order authority açılmadı.

`3fa98a9` ile SettingsView içindeki mevcut portfolio summary read'i aynı bounded read
sözleşmesine taşındı: `initial_balance` strict finite/non-negative response validation,
HTTP/malformed yanıtların explicit error state'e taşınması, sahte `0` fallback yerine
`null`/boş input, AbortSignal, kullanıcı cancel'i, request-generation/stale-response
guard ve unmount cleanup eklendi. Loading, cancelled, error ve retry state'leri
görünürdür; kullanıcı tarafından açıkça submit edilen capital mutation'ı native
rollback garantisi olmadığı için iptal edilebilir gibi sunulmaz. Yeni endpoint, schema,
funding/transfer event type, plugin capability, live execution veya AI order authority
açılmadı.

`dd0639b` ile core Charts/TradingViewChart historical OHLCV read'i bounded hale
getirildi: response envelope ve her candle'ın timestamp/OHLCV finite/invariant shape'i
strict doğrulanıyor; malformed/HTTP/empty yanıt chart veya empty success olarak
gösterilmiyor. AbortSignal, kullanıcı cancel'i, timeout ayrımı,
request-generation/stale-response guard ve unmount cleanup eklendi. Tarihsel candle'ın
son kapanışı sahte event age ile `LIVE` tick'e yükseltilmiyor; böylece historical
context ile live market data ayrımı korunuyor. Loading, cancelled, error ve retry
state'leri görünürdür. Yeni connector, schema, live execution veya AI order authority
açılmadı.

`950af74` ile backend-reported installed component registry/ModStore read'i bounded
hale getirildi: plugin metadata envelope ve alanları strict doğrulanıyor; malformed
veya backend-unavailable yanıt partial capability listesine dönüşmüyor. AbortSignal,
kullanıcı cancel'i, request-generation/stale-response guard ve provider unmount cleanup
eklendi. ModStore loading, cancelled, error ve retry state'lerini görünür kılıyor;
remote registry/download, plugin activation, runtime mounting ve execution authority
kapalı kalıyor. Yeni plugin capability, schema veya live execution açılmadı.

`da9af9b` ile append-only ledger integrity doğrulamasında güvenli tekrar-okuma sınırı
eklendi. `3863288` ile cache anahtarı artık yalnız `evidence_events` tablosunun
istenen scope içindeki append-only state fingerprint'ine bağlıdır: her account/day
grubu için event count, ilk/son sequence ve son event hash korunur. Böylece projection
commit'i canonical ledger doğrulamasını gereksiz yere invalid etmez; yeni ledger append'i
fingerprint'i değiştirip tam doğrulamayı yeniden çalıştırır. Fingerprint okunamazsa
cache kullanılmaz ve tam doğrulama yapılır; invalid zincir cache'lenmez, sonuç defensive
copy ile döner ve yeni schema/event type eklenmez. Fingerprint için kısa ömürlü SQLite
bağlantısı kullanılır; persistent verifier connection tutulmadığı için projection
apply sonrasında WAL sayfaları tutulmaz. Bu, Evidence Pack tekrar okumalarını azaltan
warm-read optimizasyonudur. `bf30860` ile cached valid prefix sonrasında yalnız yeni
append tail'i doğrulanır; Evidence Pack toplam `checked_events` sayısını korur ve
tail gap/prev-hash/hash hatasında fail-closed kalır. Bu append-tail yolu ile yeni
verifier instance'ının hiç cache olmadan yaptığı full-chain doğrulama ayrı ölçülür;
ikisi aynı cold/warm sonucu gibi birleştirilmez.

`2da9fe1` ile projection rebuild aynı verifier instance'ını reuse edecek şekilde
bounded hale getirildi; `f551b1f` ile apply rebuild sonrası WAL büyümesi için sınır testi
eklendi ve `3863288` ile bu sınır kalıcı bağlantı tutmayan fingerprint tasarımına
taşındı. `TradeReadAdapter`, projection repository'nin public `ledger_repo` verifier'ını
paylaşır; projection-only commit shared cache'i bozmaz, ledger append'i bozup yeniden
doğrulamayı zorlar. Rollback, ledger verisi ve projection semantiği değişmez.

`c095025` ile safe-persona surface audit'i tamamlandı. `kuantra_quant` yalnız
doğrulanmış `day_trader` ve `quant_lab` preset'lerini görür; Docking Grid, AI Auditor,
popup monitor ve deneysel panel içeren pop-out akışı bu persona altında render edilmez.
Header'daki Chart Vision tetikleyicisi yalnız doğrulanmış aktif AI plugin capability'si
raporlandığında gösterilir; mevcut production plugin allowlist'i boş olduğu için bu
release'te görünmez. Preset callback'i de UI dışından çağrılsa aynı sınırı korur.
Bu paket yeni plugin, AI, order-flow, live execution, schema veya connector açmaz;
yalnızca yanlış capability izlenimini ve deneysel yüzeye erişim yolunu fail-closed
keser. Bu, H07 frontend boundary audit'inin kapanış kanıtıdır; global cold-chain
performans hedefinin kapanışı değildir.

`f94ba8e` ile cold verifier'ın scalar-only canonical hash body'leri için mevcut
canonical JSON byte sözleşmesini koruyan hızlı yol ve tekrarlı canonical provenance/
secret-key validation cache'leri eklendi. `orjson` zaten locked backend dependency'sidir;
şema, event type, funding/transfer kapsamı ve hash çıktısı değişmedi. Red→green
contract testi Unicode, quote, backslash ve newline değerlerinde hızlı yol byte'larının
`canonical_json` ile birebir eşleştiğini doğruladı. Bu optimizasyon güvenlik
doğrulamasını kaldırmaz; malformed/corrupt chain hâlâ fail-closed kalır.

`5a70f8b` ile canonical JSON byte-eşleşen normalized payload/provenance validation'ında
kilitli `orjson` parse/dump hızlı yolu genişletildi; byte eşleşmeyen veya orjson'un
temsil edemediği değerler mevcut stdlib canonical/fail-closed fallback'e gider.
Secret-key traversal korunur; yalnız scalar leaf'lerde gereksiz recursive çağrı yapılmaz.
Bu paket hash byte sözleşmesini, malformed JSON reddini veya secret redaction sınırını
gevşetmez.

Focused H07 bounded-performance suite `23 passed`; projection/H01 regression bundle
`42 passed`; value-chain frontend boundary suite `20 passed`;
dashboard/analytics/header focused suite `8 passed`; JournalView focused suite
`3 passed`; MAE/MFE focused suite `5 passed`; SettingsView focused suite `3 passed`;
Charts focused suite `4 passed`; plugin registry/ModStore/safe-persona focused suite
`8 passed`;
full backend suite `716 passed, 2 warnings`, full
frontend `25` test dosyası ve `102` test PASS; i18n `608/608`.
Locked local CI `MERGE READY` oldu.
Current code baseline source commit tam SHA'sı
`5a70f8b74702338602379f8419b8b4938e0aae9c`, tracked source tree SHA-256'sı
`04b375e7a161feb8b3b3f8bfb4dc3b44af45ec345f69e0990c69d30f7a20a148`'dir.
Toolchain: Python `3.11.16`, Node `v20.20.2`, npm `10.8.2`, uv
`uv 0.12.10 (Homebrew 2026-09-04 aarch64-apple-darwin)`, PyInstaller `6.22.2`;
backend/frontend lock SHA'ları sırasıyla
`6291588602869af34e2a4db5d7244a627f4e139cbbd4b034b7cc07d890812399` ve
`b392a59d09ade73564ce082b1a5bc1236618ebeee11703a992980cfd1812882c`.

Local CI report SHA-256 `c513b5f4ce3a14270277c1a9031bcf0b9d51a3271a84ebe59f7deb2daa06be01`,
native local smoke report SHA-256 `413d5029e79276c66149ae4574be0ced14860a4ac72b7858e34490d6dc0e5c5e`;
local smoke executable SHA-256 `17508bbfa429689ab6adeeee419e166c604a15457a55a5f8a543bbb16b04cbc0`
ve `.app` artifact SHA-256 `36c84e727a00c305176f7ee45f2f4c32b6693e76cd59021aaa889bc1a4554459`.
Canonical local CI'nin varsayılan desktop smoke adımı mevcut network davranışı nedeniyle
public Binance stream bağlantısını denedi; bu kayıt runtime offline kanıtı değildir.

Bu source baseline üzerindeki exact read-only DMG smoke report SHA-256
`bc587f232c7f5d09c787412549d924aa8aa045524590bdcecdd3047490367963`, DMG
SHA-256 `f5183bee511352e97b6c4d6e363d0951fc32361d6a9d718ccfe3174752c45fc7`
ve mounted executable SHA-256
`17508bbfa429689ab6adeeee419e166c604a15457a55a5f8a543bbb16b04cbc0`'dir.
DMG smoke read-only mount ve `KUANTRA_MARKET_DATA_ENABLED=false` ile yapıldı;
WKWebView/controller identity, React/bridge/health/push/plugin smoke kontrolleri
ve detach PASS oldu. Bu, ad-hoc development artifact'ıdır; signing,
notarization, Gatekeeper veya commercial distribution kanıtı değildir.

Bu source/artifact çiftiyle çalıştırılan güncel 100k sentetik benchmark raporu
`/tmp/h07-5a70f8b-artifact.json`, report SHA-256
`c92200c37fe1db0e7d13727d818060998d112c54c049e1c9bd81201ee57f5087`'dir.
Provenance `COMPLETE`, `network=false`, `credentials=false`, `live_execution=false`;
dataset SHA-256 `cbffe7e178c9efd9e08c876c902cc4dd5efb06e2bc1da7a428b8d001830051bd`,
determinism snapshot SHA-256
`6bb1eb94ba9293ab4039e4d03ee34a8d67e25361ebcd6c98679e7be9decf264e` ve sayımlar
`100000 trades / 100003 ledger events / 100000 projections` olarak kaldı. 100k
operation p95 değerleri import `158.8446 ms`, projection rebuild `4153.3801 ms`,
query `225.548 ms`, Evidence Pack `349.5183 ms` ve export `340.3408 ms`'dir;
Evidence Pack p50 `340.2353 ms`'dir. Bu Evidence Pack sonucu, çalışan verifier'ın
önceden doğruladığı prefix sonrasındaki append-tail/correction akışını ölçer; yeni
verifier instance'ı ile yapılan ayrı no-cache full-chain auditinde üç örnek
`2217.7044 / 2190.9482 / 2208.2548 ms`, p95 `2216.36659 ms` ölçüldü; her örnek
`100003` event'i geçerli zincir olarak kontrol etti. Dolayısıyla
append-tail workload'unda `<2s` planning hedefi ölçülmüş olsa da full no-cache cold
startup hedefi karşılanmamıştır. H07 `IMPLEMENTATION_REQUIRED` kalır; bu değerler
support SLO veya production claim değildir. Max operation RSS `320.375 MB`, max
temporary disk `2949120 B` ölçüldü; projection rebuild operation'ının temporary
disk ölçümü `0 B`'dir.

### Önceki artifact-bağlı sentetik baseline

Aşağıdaki 1k/10k/100k ölçümleri source `6748d96` üzerinde üretilmiş önceki
non-release baseline'dır. `5137383` query abort paketi bu ölçüm sonuçlarını
değiştiren bir veri/schema değişikliği yapmadı; yeni query abort doğrulaması
focused/full test ve güncel Mac local-CI/DMG kanıtıyla ayrıca kaydedildi.

1k/10k/100k raporu `/tmp/h07-6af4fd9-artifact-benchmark.json`, SHA-256
`a65d1785c0d514dd2342e856aa137a7057ecf03468004ca5d7dc9f0f3c69ee13` ile; 1k
import percentile'larını yeterli örnekle doğrulayan `--batch-size 100` raporu
`/tmp/h07-6af4fd9-1000-b100.json`, SHA-256
`61c91fb7a639190949bd4bb60ca6c64986023d62ec19fe6877d5064aaeb4bcb9` ile üretildi.
Ana rapordaki 1k import tek örnek nedeniyle `UNKNOWN`/`INSUFFICIENT_SAMPLES` olarak
kalır; aşağıdaki 1k satırındaki import değeri ayrı batch-100 raporundan gelir.
Diğer tüm operasyonlarda üç veya daha fazla örnek, projection rebuild'de dört örnek
vardır. Hücrelerdeki sıra `p50 / p95 / p99 ms`'dir; RSS ve temporary disk, o boyuttaki
operasyon özetleri arasındaki maksimum değerdir.

| Sentetik geçmiş | Import | Projection rebuild | Query | Correction | Correction replay | Recorded-bar replay | Evidence Pack | Export | Cancel | Max RSS | Max temp disk |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1,000 | 15.3834 / 15.6872 / 15.7690 | 61.3190 / 72.8025 / 74.4147 | 3.0402 / 3.1181 / 3.1251 | 2.1671 / 2.2001 / 2.2031 | 0.9104 / 0.9738 / 0.9795 | 0.0828 / 0.1264 / 0.1302 | 51.0549 / 51.5364 / 51.5792 | 51.4011 / 53.1459 / 53.3010 | 0.0234 / 0.0279 / 0.0283 | 121.0000 MB | 303,104 B |
| 10,000 | 140.4530 / 145.1968 / 145.5939 | 630.2234 / 755.6386 / 772.8868 | 21.2117 / 21.4978 / 21.5232 | 2.3667 / 2.4139 / 2.4181 | 1.0152 / 1.0375 / 1.0395 | 0.0734 / 0.0995 / 0.1018 | 455.7966 / 457.2233 / 457.3501 | 457.7231 / 458.3418 / 458.3968 | 0.0473 / 0.0474 / 0.0474 | 166.1719 MB | 2,899,968 B |
| 100,000 | 165.5865 / 181.1898 / 187.0258 | 6,642.0935 / 8,347.3076 / 8,578.8930 | 222.0984 / 222.3455 / 222.3675 | 2.6187 / 3.0088 / 3.0435 | 0.9339 / 1.0671 / 1.0789 | 0.0833 / 0.1049 / 0.1068 | 4,527.0828 / 4,530.5968 / 4,530.9092 | 4,525.9790 / 4,545.3095 / 4,547.0277 | 0.0472 / 0.0494 / 0.0496 | 336.3438 MB | 2,949,120 B |

Her boyutta `trades` ve `projections` sayısı sırasıyla 1k/10k/100k, immutable
correction ekleriyle `ledger_events` sayısı 1,003/10,003/100,003 oldu. Coverage
raporu her boyutta `ready=true`, `missing=0`, `duplicate=0`, `extra=0` gösteriyor.
Dataset SHA-256'ları sırasıyla `ac6a639a04c15e17abc36572087a1358ce5cde70dbb326c4443a3acd30d1d27a`,
`f058faf806ea8f5c4f547dfe23005a5ab4c2eaeb7cf673cd6a019ffbc5c5af79` ve
`cbffe7e178c9efd9e08c876c902cc4dd5efb06e2bc1da7a428b8d001830051bd`; correction/
replay run snapshot SHA-256'ları `cf6a1ae220f083e0de63d4b8172fc860be9510555243af3072ace4a8a8f75d2e`,
`fcffc5419329c23d86305176000e05c3f20731543d56c9f4d7d5ff5b26e7edf7` ve
`6bb1eb94ba9293ab4039e4d03ee34a8d67e25361ebcd6c98679e7be9decf264e`'dir.
Rapor sözleşmesi `real_data=false`, `credentials=false`, `network=false`,
`live_execution=false` ve `support_limit_claim=false` olarak kalmıştır.

Bu ölçümde 100k Evidence Pack p95'i `4,530.5968 ms`, export p95'i `4,545.3095 ms`
ve projection rebuild p95'i `8,347.3076 ms` oldu; planlama hedefi olan `<2s`
karşılanmıyor. H07 **IMPLEMENTATION_REQUIRED** kalır. Bu sonuç support limit,
production SLO veya “fast” ürün iddiası değildir; host ve workload varyansı ayrıca
değerlendirilmelidir.

### Önceki Mac artifact kanıtı

`6748d96` source commit'i ile clean Mac arm64 build, native smoke ve exact read-only
DMG smoke PASS oldu. DMG smoke `KUANTRA_MARKET_DATA_ENABLED=false` ile çalıştırıldı;
market-data stream başlatılmadı, gerçek veri/credential kullanılmadı ve mount güvenli
biçimde detach edildi. DMG smoke report SHA-256
`9d594ca4e437210fe52cdbf8c2a9ba7ee628c13f7d156df6329e49f0fa676bca`, DMG SHA-256
`eb3949b5dc7cadcd713ccf1c85aa00b82c7cc2bb188da02f4e46765b9274096d`, mounted
executable SHA-256 `76d83a74a0fa854f49b1c693e1064dbf2cd585879f46368f66299a21520d414c`.
WKWebView controller identity, bridge, health, React mount, push sink ve plugin
boundary kontrolleri PASS oldu. Bu artifact ad-hoc development artifact'ıdır;
Developer ID, notarization, Gatekeeper veya commercial distribution kanıtı değildir.

### H07'nin halen açık teknik sınırları

- Explicit RSS/disk budget abort semantics artık import, correction, projection
  rebuild, Evidence Pack assembly ve trade-list query sınırlarında fail-closed
  olarak vardır. Query mid-operation abort legacy ve typed projection yollarında
  test edilmiştir; bu read-only yol rollback gerektirmediği için partial list
  döndürmeden connection'ı kapatır.
- Grouped canonical batch için cooperative cancellation ve rollback kanıtı vardır;
  frontend read yüzeyleri kendi request'lerinde AbortSignal/cancel state'i taşır;
  native bridge üzerinden yapılan import mutation'ı için rollback garantisi
  olmadığı için kullanıcıya iptal edilebilir mutation sunulmaz.
- Malformed/oversized input ve partial/unknown coverage için bounded backend red/
  green fixture ve fail-closed implementation tamamlandı: 10 yeni fixture PASS.
- Evidence Pack, Reconciliation Inbox, Weekly Review, CSV preview, Dashboard,
  Quant Analytics, Header portfolio telemetry, JournalView trade-list, MAE/MFE,
  SettingsView portfolio summary, Charts/TradingViewChart historical OHLCV ve
  plugin registry/ModStore için frontend AbortSignal/loading/cancel/error truth
  bounded olarak test edilmiştir. Bu liste safe-persona görünür core read
  yüzeylerinin mevcut audit sınırıdır; auxiliary onboarding/theme/telemetry/native
  reads ve disabled experimental surfaces production capability olarak açılmamıştır.
  Bu nedenle H07 tamamlanmış veya production-ready değildir.

Process-level RSS/disk capture ve cold 100k projection rebuild maliyeti artık
`30be78d`/`67eafa2`/`670ee90`/`4e761fa` ile aynı packaged-process sınırında
ölçülmüştür. Güncel `4e761fa` campaign'inde 366 packaged manifest, 120/120
geçerli projection rebuild sample'ı ve aynı determinism snapshot'ı vardır; 100k
cold Evidence Pack operation p95'i `2321.8877 / 2332.4201 ms`, process p95'i
`3303.9205 / 3318.6734 ms`, projection-rebuild operation p95'i
`5141.0606 / 5143.9399 ms` ve process p95'i `6217.4225 / 6208.4966 ms` oldu.
Projection process peak RSS `400.4375 / 400.5156 MB`, isolated temporary disk
`388370264 B` olarak ölçüldü. Native worker-cache UI raporu loading ve concurrent
health/read davranışını gösterdi; ancak timer-gap percentile'ları
`UNKNOWN_SINGLE_SAMPLE` ve network isolation `NOT_VERIFIED` kaldı. OS page cache
`UNCONTROLLED` olduğu için artifact'lar arasında izole nedensel yüzde veya destek
limiti iddiası yapılmamıştır.

Bu paket için ölçüm sınırı açıkça yazılmıştır: Mac arm64 packaged executable,
`H07-SYNTHETIC-V1` 100k dataset, iki run, tanımlı sample sayıları, network/
credential/real-data/live-execution disabled ve uncontrolled OS cache. Bu,
reproducible development evidence sınırıdır; production SLO, maximum supported
history, resource cap veya commercial support limit değildir. Owner-approved
production/resource/support disposition ayrı H07 gate olarak kalır. `<2s>`
planning target'ı sessizce değiştirilmemiştir ve güncel cold p95 hâlâ hedefin
üzerindedir. Worker isolation paketi tamamlanmıştır; H07 şimdi yeni bir bounded
darboğaz hipotezi veya açık owner measurement/support kararı bekler. H07 bu
karar kapanmadan tamamlanmış, production-ready ya da desteklenen veri boyutu
olarak işaretlenmeyecektir. `f94ba8e` ve `5a70f8b` source-process iyileştirmeleri
historical diagnostic olarak kalır; packaged cold-chain kanıtının yerine
geçmez.
