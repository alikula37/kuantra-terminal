<!-- doc-role: current-work-package -->
# H07 — Bounded Performance & Resource Limits

```yaml
work_package: H07
version: 1.3.0
status: InProgress
date: 2026-09-08
baseline_commit: 4e85e3f
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

`4e85e3f` ile önceki H07 benchmark/cancellation/integrity sınırlarının üzerine
deterministik correction, idempotent correction replay ve recorded-bar replay ölçümü
eklendi. `SQLiteDriver.record_trade_with_evidence` içindeki mevcut yazma yoluna
yalnızca `event_id` ve `received_at` için optional test/ingestion bağlamı eklendi;
şema genişletilmedi, funding/transfer event type eklenmedi ve immutable correction
lineage korunuyor. Üç correction event'i yeniden oynatıldığında ledger event sayısı
artmıyor; replay snapshot'ları `READY` ve deterministik kalıyor. Bu API yüzeyleri
UI'ya veya live execution'a açılmadı.

Focused H07 suite `10 passed`; correction/replay ile birlikte ilgili regression
seti `33 passed, 2 warnings`; full backend suite `693 passed, 2 warnings`. Frontend
değişmedi: `19` test dosyası ve `71` test PASS; i18n `574/574`. Locked local CI
`MERGE READY` oldu. Current source commit tam SHA'sı
`4e85e3ff35984c37a3baa9e11ef67d62d1de07a1`, tracked source tree SHA-256'sı
`6acd4cf41c9958845d7978f12d7077779a053a68abf2c00d3813c2e464e0321b`'dir.
Toolchain: Python `3.11.16`, Node `v20.20.2`, npm `10.8.2`, uv
`uv 0.12.10 (Homebrew 2026-09-04 aarch64-apple-darwin)`, PyInstaller `6.22.2`;
backend/frontend lock SHA'ları sırasıyla
`6291588602869af34e2a4db5d7244a627f4e139cbbd4b034b7cc07d890812399` ve
`b392a59d09ade73564ce082b1a5bc1236618ebeee11703a992980cfd1812882c`.

Local CI report SHA-256 `fdefe3be9b161b2fb20bbdbbbb4b0bbb30d1ea4969a408b7bc3d4cf819f8ff38`,
native local smoke report SHA-256 `4f13939b97d5a67d6cfcb04df5a4537d168fd4c3268bb35a56c308eb212fc1af`.

### Artifact-bağlı sentetik baseline

1k/10k/100k raporu `/tmp/h07-4e85e3f-artifact-benchmark.json`, SHA-256
`82eb76e5cd08bb78909d484cb7da3d6fc75401e6aba3db8b51ba7b368169aed0` ile; 1k
import percentile'larını yeterli örnekle doğrulayan `--batch-size 100` raporu
`/tmp/h07-4e85e3f-1000-b100.json`, SHA-256
`da8bb8072d5a6c192eb35b7ccd5a05419ccdf399b540267e068e1c0e73c3dff7` ile üretildi.
Ana rapordaki 1k import tek örnek nedeniyle `UNKNOWN`/`INSUFFICIENT_SAMPLES` olarak
kalır; aşağıdaki 1k satırındaki import değeri ayrı batch-100 raporundan gelir.
Diğer tüm operasyonlarda üç veya daha fazla örnek, projection rebuild'de dört örnek
vardır. Hücrelerdeki sıra `p50 / p95 / p99 ms`'dir; RSS ve temporary disk, o boyuttaki
operasyon özetleri arasındaki maksimum değerdir.

| Sentetik geçmiş | Import | Projection rebuild | Query | Correction | Correction replay | Recorded-bar replay | Evidence Pack | Export | Cancel | Max RSS | Max temp disk |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1,000 | 15.3208 / 15.5612 / 15.6206 | 60.6454 / 71.6859 / 73.2260 | 3.1540 / 3.2107 / 3.2157 | 2.1961 / 2.2439 / 2.2481 | 0.8830 / 0.9789 / 0.9875 | 0.0814 / 0.1164 / 0.1195 | 50.7957 / 50.9788 / 50.9950 | 51.1166 / 51.6642 / 51.7128 | 0.0322 / 0.0348 / 0.0350 | 121.1406 MB | 303,104 B |
| 10,000 | 138.3207 / 143.3688 / 143.8882 | 622.4468 / 745.3964 / 762.7501 | 21.0480 / 21.4688 / 21.5062 | 2.2236 / 2.3050 / 2.3122 | 0.9373 / 0.9801 / 0.9839 | 0.0737 / 0.0983 / 0.1005 | 449.1722 / 449.3347 / 449.3491 | 449.9332 / 451.2008 / 451.3134 | 0.0472 / 0.0480 / 0.0481 | 165.0156 MB | 2,899,968 B |
| 100,000 | 165.5465 / 177.4708 / 185.9861 | 6,576.5317 / 8,250.7935 / 8,482.8942 | 220.9887 / 222.0413 / 222.1349 | 2.6927 / 3.0591 / 3.0917 | 0.9566 / 1.0360 / 1.0430 | 0.0848 / 0.1055 / 0.1073 | 4,470.0229 / 4,473.6330 / 4,473.9539 | 4,480.1803 / 4,487.7439 / 4,488.4162 | 0.0456 / 0.0479 / 0.0481 | 336.2188 MB | 2,949,120 B |

Her boyutta `trades` ve `projections` sayısı sırasıyla 1k/10k/100k, immutable
correction ekleriyle `ledger_events` sayısı 1,003/10,003/100,003 oldu. Coverage
raporu her boyutta `ready=true`, `missing=0`, `duplicate=0`, `extra=0` gösteriyor.
Dataset SHA-256'ları sırasıyla `ac6a639a04c15e17abc36572087a1358ce5cde70dbb326c4443a3acd30d1d27a`,
`f058faf806ea8f5c4f547dfe23005a5ab4c2eaeb7cf673cd6a019ffbc5c5af79` ve
`cbffe7e178c9efd9e08c876c902cc4dd5efb06e2bc1da7a428b8d001830051bd`; yeni correction/
replay run snapshot SHA-256'ları `cf6a1ae220f083e0de63d4b8172fc860be9510555243af3072ace4a8a8f75d2e`,
`fcffc5419329c23d86305176000e05c3f20731543d56c9f4d7d5ff5b26e7edf7` ve
`6bb1eb94ba9293ab4039e4d03ee34a8d67e25361ebcd6c98679e7be9decf264e`'dir.
Rapor sözleşmesi `real_data=false`, `credentials=false`, `network=false`,
`live_execution=false` ve `support_limit_claim=false` olarak kalmıştır.

Bu ölçümde 100k Evidence Pack p95'i `4,473.6330 ms`, export p95'i `4,487.7439 ms`
ve projection rebuild p95'i `8,250.7935 ms` oldu; planlama hedefi olan `<2s`
karşılanmıyor. H07 **IMPLEMENTATION_REQUIRED** kalır. Bu sonuç support limit,
production SLO veya “fast” ürün iddiası değildir; host ve workload varyansı ayrıca
değerlendirilmelidir.

### Mac artifact kanıtı

`4e85e3f` source commit'i ile clean Mac arm64 build, native smoke ve exact read-only
DMG smoke PASS oldu. DMG smoke `KUANTRA_MARKET_DATA_ENABLED=false` ile çalıştırıldı;
market-data stream başlatılmadı, gerçek veri/credential kullanılmadı ve mount güvenli
biçimde detach edildi. DMG smoke report SHA-256
`d22be62d47c876ccd6e3d5fc48601d2f8695897a9387c616357b9cebff235353`, DMG SHA-256
`e6d76e95bac2f20270115ee556d23ee02baccd7bf2dbe0913d96b8385fb4ab2a`, mounted
executable SHA-256 `59a690fe3aeadc2a558872465f54a42b3462e60198b4e63be0b6fdae467ed0fb`.
WKWebView controller identity, bridge, health, React mount, push sink ve plugin
boundary kontrolleri PASS oldu. Bu artifact ad-hoc development artifact'ıdır;
Developer ID, notarization, Gatekeeper veya commercial distribution kanıtı değildir.

### H07'nin halen açık teknik sınırları

- Benchmark'teki `ResourceBudget` ölçülen RSS/disk değerlerine karşı explicit bir
  rapor/exception sınırıdır; production import, projection veya Evidence Pack akışında
  dinamik budget aşımını transaction içinde abort eden ortak boundary henüz yoktur.
- Grouped canonical batch için cooperative cancellation ve rollback kanıtı vardır;
  gerçek import pipeline'ının tüm uzun operasyonları ve frontend AbortSignal/cancel
  durumu bu backend boundary'sine bağlanmış değildir.
- Malformed/oversized input, partial/unknown coverage ve UI loading/cancel/error
  truth için H07 red testleri ve fail-closed implementation tamamlanmamıştır.

Sonraki H07 adımı dinamik RSS/disk budget abort semantics ve ardından frontend
loading/cancel/error truth testleridir. Bu iki sınır kapanmadan H07 tamamlanmış,
production-ready veya desteklenen veri boyutu olarak işaretlenmeyecektir.
