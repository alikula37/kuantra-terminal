<!-- doc-role: archived -->
<!-- Historical evidence: this file is not a current implementation instruction. -->
# P1-WP27 — G0–G2 Supported Matrix ve Packaged Value-Chain Audit

```yaml
work_package: P1-WP27
version: 1.1.0
status: Complete
date: 2026-09-09
baseline_commit: 3e8ecab
implementation_commit: e042790
evidence_commit: e042790
closeout_commit: this change
branch: codex/p1-wp01-evidence-ledger
strategy: KPR-001@current
depends_on: P1-WP16, P1-WP17, P1-WP18, P1-WP19, P1-WP20, P1-WP21, P1-WP22, P1-WP23, P1-WP24, P1-WP25, P1-WP26, H01, H02, H04, H06, H07
release_gate: H05-commercial-distribution-deferred
```

## Amaç

G0–G2 kapılarının mevcut bounded davranışla gerçekten eşleştiğini tek bir güncel
destek matrisi, bağımsız golden-oracle denetimi ve gerçek packaged executable üzerinde
sentetik import → review → Evidence Pack → export → reopen kanıtıyla doğrulamak.
Bu paket yeni ürün capability'si açmaz; mevcut P1-WP22–26 akışının kabul kanıtını
birleştirir ve kullanıcıya yanlış market, accounting veya production desteği sözü
verilmesini engeller.

## Ürün ve kanıt sınırı

Kuantra local-first Execution Intelligence & Trade Forensics Workstation'dır. Bu
paketin başarılı olması profitability, full-account PnL/tax doğruluğu, broker
reconciliation completeness, live execution, AI order authority, network isolation,
pilot veya production readiness kanıtı değildir. Gerçek kullanıcı verisi, credential,
migration bundle ve live broker kullanılmaz. Diagnostic çalışması yalnız temiz geçici
data directory ve sentetik CSV ile yapılır; network ve market-data stream disabled
kalır.

## G0–G2 destek matrisi — bu paketin current source'u

| Yüzey / kapsam | Durum | Bu pakette doğrulanacak gerçek sınır |
|---|---|---|
| Generic Kuantra CSV → local journal | `CANDIDATE_VALIDATED` | UTF-8 bounded CSV; preview read-only; explicit accounting fields; clean row import |
| CSV preview'da malformed/partial/unknown row | `SUPPORTED_FAIL_CLOSED` | DB değişmez; `PARTIAL`/`UNKNOWN` ve user-review/blocked kararı korunur; zero/PASS üretilmez |
| Local journal → canonical evidence/projection | `SUPPORTED_BOUNDED` | Source row/file hash, immutable event ve deterministic projection/evidence lineage korunur |
| Reconciliation inbox / correction decision | `SUPPORTED_BOUNDED` | Discrepancy source event'e bağlıdır; ACK/REJECT/CORRECT append-only'dir; correction eski kanıtı silmez |
| Trade Evidence Pack JSON/HTML/CSV export | `SUPPORTED_BOUNDED` | Coverage/rule/source hashes görünür; replay aynı payload/artifact hash'ini üretir; redaction korunur |
| Weekly review → COMPLETE → REOPEN | `SUPPORTED_BOUNDED` | Period/timezone/as-of deterministik; incomplete coverage `LIMITED`; `is_pass` false; reopen aynı snapshot lineage'ını korur |
| Binance USD-M / OKX SWAP venue claim'i | `NOT_YET_CLAIMED` | Ayrı venue/market/settlement/position-mode fixture ve owner kapsam kararı olmadan production desteği iddia edilmez |
| Spot, hedge/inverse, full account PnL/tax, transfer/funding ledger | `SCOPE_BOUNDARY` | Funding/transfer schema eklenmez; unavailable/unknown açık kalır; accounting kapsamı genişletilmez |
| Mac arm64 packaged app | `TESTED_NON_RELEASE` | Bu hostta sentetik packaged audit; signing/notarization/Gatekeeper/second-host kanıtı değildir |
| Windows/Linux artifact | `HOST_REQUIRED` | Bu Mac çalışması başka OS kanıtı yerine geçmez |
| AI, live order, connector promotion, plugin download | `DISABLED_OR_OUT_OF_SCOPE` | Audit yolunda görünür başarı veya order authority oluşmaz |

`CANDIDATE_VALIDATED` ve `SUPPORTED_BOUNDED` bu geliştirme/release-candidate kanıt
etiketleridir; ticari support, maksimum history veya production claim değildir.
Venue claim'leri matriste özellikle `NOT_YET_CLAIMED` bırakılır.

## B2 kapsam kararı

Bu audit, P1-WP17–21 ile taşınan bounded accounting truth'u yeniden doğrular:
bilinen fixture satırında verilen `pnl` ve `commission` korunur; account scope,
funding/transfer ve market context fixture'da mevcut değilse `NOT_AVAILABLE` kalır.
Tam hesap bakiyesi, vergi, funding/transfer muhasebesi veya venue-complete PnL
üretilmez. Bir değerin bilinmemesi sıfıra çevrilmez ve haftalık review `is_pass=true`
sonucu üretmez.

## Bounded uygulama

1. Önce bağımsız oracle ve packaged worker red testleri yazılır. Oracle, uygulamanın
   fingerprint/PnL/canonicalization fonksiyonlarını çağırmaz; beklenen değerleri
   küçük, elle okunabilir sentetik fixture'dan alır.
2. Diagnostic dispatch normal data/log/backend/WebView startup'tan önce çalışır;
   yalnız explicit executable, yeni geçici SQLite ve fixture kullanır.
3. Clean fixture için preview'nin read-only olduğu, import'un source hash'i taşıdığı,
   Evidence Pack'in coverage/lineage bilgisi verdiği ve JSON/HTML/CSV export'un
   tekrar üretilebilir olduğu kanıtlanır.
4. Malformed/partial preview DB'yi değiştirmeden `USER_REVIEW_REQUIRED` veya
   `IMPORT_BLOCKED` olarak kalır. No-data, unavailable coverage ve disabled market
   context başarı gibi gösterilmez.
5. Haftalık review sabit period/timezone/as-of ile oluşturulur; bounded `LIMITED`
   review explicit kullanıcı kararıyla tamamlanır, sonra `REOPEN` edilir. Her iki
   olay mevcut `JournalReviewAdded` sınırında kalır; yeni schema/event type eklenmez.
6. Launcher executable/artifact/fixture hash'lerini pre/post bağlar; packaged
   provenance release attestation'a yükseltilmez. Çıktı yalnız yeni evidence
   directory'ye yazılır ve mevcut kullanıcı data directory'sine dokunulmaz.

## Acceptance criteria

- [x] Current supported matrix bu dosyada tek kaynak olarak yazılı; her satırda
  durum, fixture/scope sınırı, bilinmeyen ve platform iddiası ayrılmış.
- [x] Bağımsız oracle; sembol, yön, miktar, PnL, commission, trade/event sayısı,
  coverage ve no-false-success durumlarını uygulama formülünü tekrar kullanmadan
  doğruluyor.
- [x] Gerçek packaged arm64 executable üzerinde temiz temporary directory ile
  preview → import → canonical read → Evidence Pack → JSON/HTML/CSV export akışı
  geçiyor; export replay payload/artifact hash'leri eşit.
- [x] Malformed/partial/unknown preview DB'yi değiştirmiyor; `UNKNOWN`, `PARTIAL`
  ve `NOT_AVAILABLE` downstream'de complete/zero/pass'e dönüşmüyor.
- [x] Weekly review fixed period/timezone/as-of ile `LIMITED` üretiyor; explicit
  COMPLETE ardından REOPEN aynı review identity/snapshot'ı koruyor ve `is_pass`
  false kalıyor.
- [x] Canonical event türleri, funding/transfer schema, authority ve connector
  kapsamı değişmiyor; no-network/no-credential/live-execution guard kanıtlı.
- [x] Focused backend/launcher tests, frontend regression, docs/link gate ve
  locked local CI sonucu aynı source commit ile kaydediliyor. Bu sonuç release,
  signing, notarization veya Windows/Linux platform kanıtı olarak yazılmıyor.

## Kanıt ve kapanış

Uygulama ve kanıt kaynağı `e04279032a8554b8005fffa83242f108d9d2b4bc` (`e042790`)
commit'idir. Paket; bağımsız oracle, packaged worker/launcher, aynı saniyedeki
COMPLETE → REOPEN karar sıralaması için deterministik review düzeltmesi ve mevcut
PyInstaller hidden-import kaydıyla sınırlandırılmıştır. Funding/transfer event veya
schema, yeni connector, AI order authority ve live execution yolu eklenmemiştir.

Final packaged audit Mac 26.6.2 arm64 üzerinde şu explicit executable ile PASS oldu:

```text
uv run --offline --no-project --with-requirements backend/requirements.lock python scripts/run_g0_g2_packaged_audit.py --executable "dist/Kuantra Terminal.app/Contents/MacOS/Kuantra Terminal" --artifact "dist/Kuantra Terminal.app" --output-dir "artifacts/evidence/p1-wp27/g0-g2-packaged-e042790-20260909" --timeout 180
```

Rapor `artifacts/evidence/p1-wp27/g0-g2-packaged-e042790-20260909/g0-g2-packaged-audit.json`
altında tutuldu; rapor SHA-256'sı
`89d3d8d8332c1cf32fbc0c79dc437961add0a966d4371cfd530c772602eefad8`, sentetik
fixture SHA-256'sı `2f6e4694de01aaa04e52f2bef712aca8241cd804fbb2f7dc378cd6c67f2456ee`,
executable SHA-256'sı
`9d08205787b0915d2abf4f2c24e8fec04d19eac0288585b6cee7241a43d46d40` ve `.app`
tree SHA-256'sı
`ef3b14508df61980050341afd6c20009f964c9df2a660550606d13958df6e87e`'dir.

Packaged worker kanıtında clean preview `READY/IMPORT_ALLOWED` ve DB satır sayısı
`0 → 0`, malformed preview `REJECTED/IMPORT_BLOCKED` ve `0 → 0`, clean import bir
trade/event, canonical typed projection ve Evidence Pack, JSON/HTML/CSV export replay
eşitliği, ayrıca weekly `LIMITED → COMPLETED → LIMITED` akışı görüldü. Reopen aynı
review identity/snapshot'ı ve `is_pass=false` değerini korudu. Coverage `PARTIAL`,
fee/PnL `COMPLETE`, account/market/funding-transfer `NOT_AVAILABLE` kaldı; hiçbir
bilinmeyen değer zero/complete/pass yapılmadı. Caller data directory değişmedi ve
forbidden event/schema/module guard PASS oldu; market-data ve gateway disabled'dı.

Red → green kanıtı: ilk testte packaged worker modülü yokluğu (`ModuleNotFoundError`)
ile red; implementasyon sonrası P1-WP27 focused suite `4 passed`, P1-WP22–25 ve
P1-WP27 regression seti `23 passed, 2 warnings` oldu. Aynı source commit'te canonical
locked local CI komutu:

```text
env -u KUANTRA_MARKET_DATA_ENABLED uv run --offline --no-project --with-requirements backend/requirements.lock python scripts/run_local_ci.py --report dist/p1-wp27-local-ci-report-e042790.json
```

`MERGE READY` ve 13/13 adım PASS: backend `769 passed` (2 deprecation warning),
frontend `25 files / 104 tests`, i18n `608/608`, release truth, packaging integrity,
Mac arm64 desktop build, native `wkwebview` smoke ve provenance contract PASS oldu.
Local-CI rapor SHA-256'sı
`8aedef66a73bb0bd7dca2a1bff685092ac59971e84d3d524767facc063954575`;
`dist/local-ci-smoke.json` SHA-256'sı
`c6eff747625c82e550160c60dacc8d49f37698d922d9c4106b4e6f110ffc1992`'dir.
Provenance `COMPLETE`, source commit `e04279032a8554b8005fffa83242f108d9d2b4bc`,
tracked source tree SHA-256'sı
`ca98a15a11325b3f47b89947fb099fdd345fba9a7eac16714ea2790f437fe101`, backend lock
SHA-256'sı `6291588602869af34e2a4db5d7244a627f4e139cbbd4b034b7cc07d890812399` ve
frontend lock SHA-256'sı
`b392a59d09ade73564ce082b1a5bc1236618ebeee11703a992980cfd1812882c` olarak
raporlandı. Canonical local CI'nin varsayılan smoke adımı public Binance stream'e
erişim denedi; bu runtime-offline kanıtı değildir. P1-WP27 packaged audit'i ise
network, credential ve live execution olmadan ayrı audit guard'ı ile PASS oldu.

Bu kanıt geliştirme/non-release sınırındadır: signing, notarization, Gatekeeper,
second-host, Windows/Linux, commercial support, license/notices, Dependabot merge,
pilot veya production readiness iddiası üretmez. H05 ticari dağıtım kapısı kullanıcı
kararı doğrultusunda deferred kalır.

## Kesinlikle kapsam dışı

- Yeni broker/venue connector, order endpoint'i, AI capability veya plugin promotion.
- Funding/transfer event type, ledger schema, migration veya full-account accounting.
- Gerçek kullanıcı verisi, credential/Keychain, Windows migration, network market
  stream veya canlı broker.
- Production SLO, ticari support limit, signing/notarization, Dependabot merge,
  LICENSE/third-party notices veya main merge.

## Sonraki bağımlılık

Paket tamamlandı ve arşivlendi. Bir sonraki seçili teknik sıra N03 temiz Mac
profil/ikinci host install-lifecycle kanıtıdır; bunun için aynı geliştirici profili
veya yalnız temporary data directory yeterli değildir. N03 kanıtı alınana kadar
N03 `HOST_REQUIRED` kalır. N04 sentetik update/uninstall data-preservation,
signing/notarization, Windows/Linux, commercial distribution, pilot ve release
kararları kendi owner/host kapıları olarak kalır.
