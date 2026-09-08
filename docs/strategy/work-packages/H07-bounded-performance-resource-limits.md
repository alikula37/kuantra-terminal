<!-- doc-role: current-work-package -->
# H07 — Bounded Performance & Resource Limits

```yaml
work_package: H07
version: 1.1.0
status: InProgress
date: 2026-09-08
baseline_commit: 779e2d7
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
oluyor. Bu API yüzeyi UI'ya veya live execution'a açılmadı.

Focused H07 suite `9 passed`; full backend suite `692 passed, 2 warnings`. Frontend
değişmedi: `19` test dosyası ve `71` test PASS; i18n `574/574`. Bu commit'te
`uv run --offline --no-project --with-requirements backend/requirements.lock
python scripts/run_local_ci.py` sonucu **MERGE READY** oldu; local-ci report SHA-256
`70486a35fb52f6a22488c6e01f71690e8bf722e84df3bb97b9710d60e4e398f1`, source commit
`779e2d7fc58aa686b913909a4e311b85faa59a18`, tracked source tree SHA-256
`0330ac5afafd3ba2b3c0c0dd5b1a96aec8a483208fbba7d91ed46f5b95e1c6b9` ve provenance
`COMPLETE` olarak kaydedildi. Toolchain: Python `3.11.16`, Node `v20.20.2`, npm
`10.8.2`, uv `0.12.10`, PyInstaller `6.22.2`; backend/frontend lock SHA'ları
raporda kayıtlıdır.

### Sentetik baseline

`/tmp/h07-benchmark-779e2d7.json` report SHA-256
`94b7b4990ea4f05ff84aacd7d2caf930841b06bcbfb7589633f33eee3b4fa062` ile 1k/10k/100k
koşuldu. 1k import için tek batch yüzünden percentile `UNKNOWN` kalmıştır; yeterli
örnek almak üzere `--batch-size 100` ile ayrı 1k raporu üretildi. Bu raporun SHA-256'sı
`0b0c39018813b3901a184c44c50225b066394388fd58106b2d361451a5b79390`'dır. Her iki
raporda da `real_data=false`, `credentials=false`, `network=false`,
`live_execution=false` ve `support_limit_claim=false` sözleşmesi korunmuştur.

| Sentetik geçmiş | Import p95 | Projection rebuild p95 | Query p95 | Evidence Pack p95 | Export p95 | Cancel p95 | Peak RSS | Temp disk |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1,000 | 16.4002 ms | 78.2435 ms | 3.2654 ms | 238.7106 ms | 60.0789 ms | 0.0319 ms | 117.6406 MB | 303,104 B |
| 10,000 | 147.5002 ms | 812.8729 ms | 21.9377 ms | 518.5187 ms | 537.0838 ms | 0.0566 ms | 171.7500 MB | 2,899,968 B |
| 100,000 | 186.1977 ms | 8,862.8957 ms | 229.4677 ms | 5,248.0007 ms | 5,255.8811 ms | 0.0491 ms | 337.8438 MB | 2,949,120 B |

Dataset SHA-256'ları sırasıyla `ac6a639a04c15e17abc36572087a1358ce5cde70dbb326c4443a3acd30d1d27a`,
`f058faf806ea8f5c4f547dfe23005a5ab4c2eaeb7cf673cd6a019ffbc5c5af79` ve
`cbffe7e178c9efd9e08c876c902cc4dd5efb06e2bc1da7a428b8d001830051bd`; run snapshot
SHA-256'ları sırasıyla `c41bfa653ebd2add989c0b3952aba9d4e84d7dc99a0eef3bd31ed8d3f67fe144`,
`12fcd18a762856bb95f3a787e853b861a11350ac71325aaa2a92602feb33f453` ve
`a6e337ba06dbe9030d9920c55e420f0fcdf3a32cc42fd13527ff7fe662c14a18`'dir.

Bu ölçüm 100k için Evidence Pack p95'inin planlama hedefi olan `<2s` altında
olmadığını ve projection rebuild p95'inin de yaklaşık `8.86s` olduğunu gösteriyor.
H07 **IMPLEMENTATION_REQUIRED** kalır; support limit, production SLO veya “fast”
ürün iddiası çıkarılamaz. `verify_chain` bütün account ledger'ını doğruladığı için
Evidence Pack yolu hâlâ doğruluk öncelikli pahalı bir boundary'dir. Correction/replay
ölçümü, gerçek import cancellation'ın API/UI'ya bağlanması, dinamik RSS/disk limitinde
transaction abort davranışı ve frontend loading/cancel/error truth testleri bu
paketin açık alt işleridir.

### Mac artifact kanıtı

779e2d7 source commit'i ile clean Mac arm64 build ve native smoke PASS oldu. Exact
read-only DMG smoke `KUANTRA_MARKET_DATA_ENABLED=false` ile çalıştırıldı; public market
stream başlatılmadı, gerçek veri/credential kullanılmadı, mount güvenli biçimde detach
edildi. DMG smoke report SHA-256
`665655f2cdc02d01c4bcb8092c87f16d94db4a5a3167db4ef56169dff737b8c6`, DMG SHA-256
`cdf6da2bf9dd0a22ddfa8b8cb16fb6bef695f96f64f857b9fcb8bf5884a0c7e1`, mounted
executable SHA-256 `8a38af367b43f48f7d237783752a74847ccdfc46220548cb56a9737753f69ec7`.
WKWebView controller identity, bridge, health, React mount, push sink ve plugin
boundary kontrolleri PASS oldu. Bu artifact ad-hoc development artifact'ıdır;
Developer ID, notarization, Gatekeeper veya commercial distribution kanıtı değildir.
