<!-- doc-role: current-work-package -->
# H07 — Bounded Performance & Resource Limits

```yaml
work_package: H07
version: 1.2.0
status: InProgress
date: 2026-09-08
baseline_commit: d2463b2
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
- [ ] Import/query/projection rebuild/correction/replay/cancel/Evidence Pack export
  için p50/p95/p99, peak RSS ve temporary disk ölçümleri source/artifact kanıtına bağlı.
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

## İlk bounded uygulama ve ölçüm sonucu — 2026-09-08

İlk implementation `f0b93ba` ile deterministik synthetic benchmark harness'i,
correlation-index üzerinden trade event lookup ve fail-closed benchmark report
validator'ı eklendi. `779e2d7` ile grouped canonical batch'e cooperative
`cancel_check` sınırı eklendi; iptal transaction commit'inden önce gerçekleşirse
compatibility trade row, canonical ledger event ve typed projection birlikte rollback
oluyor. `d2463b2` ile `verify_chain` aynı tam hash/JSON doğrulamalarını tek SQLite
read snapshot'ında, gereksiz decoded row listesi oluşturmadan yürütüyor. Bu API
yüzeyleri UI'ya veya live execution'a açılmadı.

Focused H07 suite `10 passed`; full backend suite `693 passed, 2 warnings`. Frontend
değişmedi: `19` test dosyası ve `71` test PASS; i18n `574/574`. Bu commit'te
`uv run --offline --no-project --with-requirements backend/requirements.lock
python scripts/run_local_ci.py` sonucu **MERGE READY** oldu; local-ci report SHA-256
`f675b1ff8122fa9bd341980dbdcc0de130db083fa31fd0368375036092e675a5`, source commit
`d2463b203a9847560fbe6343ef0f04f12435946c`, tracked source tree SHA-256
`f88bf83005b4a411d50a08670bb6774fef4c1f417533b138a28def4d6fe418b8` ve provenance
`COMPLETE` olarak kaydedildi. Toolchain: Python `3.11.16`, Node `v20.20.2`, npm
`10.8.2`, uv `0.12.10`, PyInstaller `6.22.2`; backend/frontend lock SHA'ları
raporda kayıtlıdır.

### Sentetik baseline

`/tmp/h07-d2463b-artifact-benchmark.json` report SHA-256
`ce93f1a9bed1a050544d7b0800112193c6877c59df6d7cb5ff7f743862e509cd` ile 1k/10k/100k
koşuldu. 1k import için tek batch yüzünden percentile `UNKNOWN` kalmıştır; yeterli
örnek almak üzere `--batch-size 100` ile ayrı 1k raporu üretildi. Bu raporun SHA-256'sı
`f11d29131150feecfb10dfa54f57700f9fde221a6837f948f7c9536864256d78`'dir. Her iki
raporda da `real_data=false`, `credentials=false`, `network=false`,
`live_execution=false` ve `support_limit_claim=false` sözleşmesi korunmuştur.

| Sentetik geçmiş | Import p95 | Projection rebuild p95 | Query p95 | Evidence Pack p95 | Export p95 | Cancel p95 | Peak RSS | Temp disk |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1,000 | 15.7145 ms | 72.1581 ms | 3.1059 ms | 261.2186 ms | 53.8550 ms | 0.0278 ms | 112.1250 MB | 303,104 B |
| 10,000 | 146.8722 ms | 746.8787 ms | 21.4798 ms | 453.1828 ms | 454.8826 ms | 0.0480 ms | 164.5156 MB | 2,899,968 B |
| 100,000 | 177.3521 ms | 8,067.4208 ms | 222.3159 ms | 4,523.3492 ms | 4,515.7266 ms | 0.0480 ms | 331.1406 MB | 2,949,120 B |

Dataset SHA-256'ları sırasıyla `ac6a639a04c15e17abc36572087a1358ce5cde70dbb326c4443a3acd30d1d27a`,
`f058faf806ea8f5c4f547dfe23005a5ab4c2eaeb7cf673cd6a019ffbc5c5af79` ve
`cbffe7e178c9efd9e08c876c902cc4dd5efb06e2bc1da7a428b8d001830051bd`; run snapshot
SHA-256'ları sırasıyla `c41bfa653ebd2add989c0b3952aba9d4e84d7dc99a0eef3bd31ed8d3f67fe144`,
`12fcd18a762856bb95f3a787e853b861a11350ac71325aaa2a92602feb33f453` ve
`a6e337ba06dbe9030d9920c55e420f0fcdf3a32cc42fd13527ff7fe662c14a18`'dir.

Bu ölçüm 100k için Evidence Pack p95'inin planlama hedefi olan `<2s` altında
olmadığını ve projection rebuild p95'inin de yaklaşık `8.07s` olduğunu gösteriyor.
H07 **IMPLEMENTATION_REQUIRED** kalır; support limit, production SLO veya “fast”
ürün iddiası çıkarılamaz. `verify_chain` bütün account ledger'ını doğruladığı için
Evidence Pack yolu hâlâ doğruluk öncelikli pahalı bir boundary'dir. d2463b2 önceki
ölçümdeki decoded-row maliyetini azalttı ve snapshot hash'ini değiştirmedi; ancak
ölçüm host varyansı ve hedef dışı p95 nedeniyle bu bir support SLO değildir.
Correction/replay
ölçümü, gerçek import cancellation'ın API/UI'ya bağlanması, dinamik RSS/disk limitinde
transaction abort davranışı ve frontend loading/cancel/error truth testleri bu
paketin açık alt işleridir.

### Mac artifact kanıtı

d2463b2 source commit'i ile clean Mac arm64 build ve native smoke PASS oldu. Exact
read-only DMG smoke `KUANTRA_MARKET_DATA_ENABLED=false` ile çalıştırıldı; public market
stream başlatılmadı, gerçek veri/credential kullanılmadı, mount güvenli biçimde detach
edildi. DMG smoke report SHA-256
`9cf42e65143d92b5e8008a3b33e74d8787a6db5ea3b51200389154f20fa0f2a5`, DMG SHA-256
`43b25776976c20de88b69f0c3ac1d92c30172926bf8d4f27e6d98e763d79d8e2`, mounted
executable SHA-256 `e13972922292092da1f4069d5c820a2a544bef3a0c0aea9f20ed22b4f8bc3556`.
WKWebView controller identity, bridge, health, React mount, push sink ve plugin
boundary kontrolleri PASS oldu. Bu artifact ad-hoc development artifact'ıdır;
Developer ID, notarization, Gatekeeper veya commercial distribution kanıtı değildir.
