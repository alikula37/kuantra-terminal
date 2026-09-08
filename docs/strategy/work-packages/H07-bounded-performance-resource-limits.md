<!-- doc-role: current-work-package -->
# H07 — Bounded Performance & Resource Limits

```yaml
work_package: H07
version: 2.8.0
status: InProgress
date: 2026-09-08
baseline_commit: c095025
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
  halen açıktır.
- [ ] Backend correctness/performance regression suite ve frontend loading/cancel/error
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

## Güncel bounded uygulama ve ölçüm sonucu — 2026-09-08

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

Focused H07 bounded-performance suite `21 passed`; projection/H01 regression bundle
`42 passed`; value-chain frontend boundary suite `20 passed`;
dashboard/analytics/header focused suite `8 passed`; JournalView focused suite
`3 passed`; MAE/MFE focused suite `5 passed`; SettingsView focused suite `3 passed`;
Charts focused suite `4 passed`; plugin registry/ModStore/safe-persona focused suite
`8 passed`;
full backend suite `714 passed, 2 warnings`, full
frontend `25` test dosyası ve `102` test PASS; i18n `608/608`.
Locked local CI `MERGE READY` oldu.
Current code baseline source commit tam SHA'sı
`c0950250430f3c57034703a7d601ce5f3c790118`, tracked source tree SHA-256'sı
`33329015bb30b44fcf739a34d237e21790173e51662a559fbf20dce1652bae77`'dir.
Toolchain: Python `3.11.16`, Node `v20.20.2`, npm `10.8.2`, uv
`uv 0.12.10 (Homebrew 2026-09-04 aarch64-apple-darwin)`, PyInstaller `6.22.2`;
backend/frontend lock SHA'ları sırasıyla
`6291588602869af34e2a4db5d7244a627f4e139cbbd4b034b7cc07d890812399` ve
`b392a59d09ade73564ce082b1a5bc1236618ebeee11703a992980cfd1812882c`.

Local CI report SHA-256 `acd0215e8cc8f939314575b68bb2230c1e2b27e8d3ba4f7bf4a8a52e2adc936f`,
native local smoke report SHA-256 `72515c6a09be6b13019817d7937f43b69f7dbf8b1da980a818530f01f88f1f56`;
local smoke executable SHA-256 `551107a4de39194956c4e0bd6f7cc80306b6a6ac918cec133c7293528a745624`
ve `.app` artifact SHA-256 `0f613f846f51078538c5637e550ff1224370828a8a9951fe0798514722d3ba49`.
Canonical local CI'nin varsayılan desktop smoke adımı mevcut network davranışı nedeniyle
public Binance stream bağlantısını denedi; bu kayıt runtime offline kanıtı değildir.

Bu source baseline üzerindeki exact read-only DMG smoke report SHA-256
`d3f9bcfd55bd9642bd7b24f45e8571eb99b37be5fa4a7c08051a75840fd4159c`, DMG
SHA-256 `9853bb8058b55e672ce9dc3e40ee4f4740d385fa6ae4204313d3af9dbe83bf25`
ve mounted executable SHA-256
`551107a4de39194956c4e0bd6f7cc80306b6a6ac918cec133c7293528a745624`'dir.
DMG smoke read-only mount ve `KUANTRA_MARKET_DATA_ENABLED=false` ile yapıldı;
WKWebView/controller identity, React/bridge/health/push/plugin smoke kontrolleri
ve detach PASS oldu. Bu, ad-hoc development artifact'ıdır; signing,
notarization, Gatekeeper veya commercial distribution kanıtı değildir.

Bu source/artifact çiftiyle çalıştırılan güncel 100k sentetik benchmark raporu
`/tmp/h07-c095025-artifact.json`, report SHA-256
`7a1464a36f072cfb5fc5daf424ea0adbbc30cad1aafaae0d1120f83ff2466a5a`'dir.
Provenance `COMPLETE`, `network=false`, `credentials=false`, `live_execution=false`;
dataset SHA-256 `cbffe7e178c9efd9e08c876c902cc4dd5efb06e2bc1da7a428b8d001830051bd`,
determinism snapshot SHA-256
`6bb1eb94ba9293ab4039e4d03ee34a8d67e25361ebcd6c98679e7be9decf264e` ve sayımlar
`100000 trades / 100003 ledger events / 100000 projections` olarak kaldı. 100k
operation p95 değerleri import `180.5539 ms`, projection rebuild `6158.9151 ms`,
query `231.5765 ms`, Evidence Pack `350.8862 ms` ve export `342.8506 ms`'dir;
Evidence Pack p50 `342.0452 ms`'dir. Bu Evidence Pack sonucu, çalışan verifier'ın
önceden doğruladığı prefix sonrasındaki append-tail/correction akışını ölçer; yeni
verifier instance'ı ile yapılan ayrı no-cache full-chain auditinde üç örnek
`4558.6977 / 4548.2708 / 4560.6704 ms`, p95 `4560.05042 ms` ölçüldü; her örnek
`100003` event'i geçerli zincir olarak kontrol etti. Dolayısıyla
append-tail workload'unda `<2s` planning hedefi ölçülmüş olsa da full no-cache cold
startup hedefi karşılanmamıştır. H07 `IMPLEMENTATION_REQUIRED` kalır; bu değerler
support SLO veya production claim değildir. Max operation RSS `319.0156 MB`, max
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

Sonraki H07 adımı cold 100k projection rebuild ve Evidence Pack doğrulama maliyetini
ayrı red testlerle bounded biçimde azaltmak veya hedefin bu host/workload için
karşılanmadığını kanıtlı biçimde sınıflandırmaktır. Bu audit ve 100k planning target
kararı kapanmadan H07 tamamlanmış, production-ready veya desteklenen veri boyutu
olarak işaretlenmeyecektir.
