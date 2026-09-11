<!-- doc-role: archived -->
<!-- Historical evidence: this file is not a current implementation instruction. -->
# P1-WP30 — Free Multi-Asset Journal and Quote Boundary

```yaml
work_package: P1-WP30
version: 1.0.0
status: Complete
date: 2026-09-11
baseline_commit: b972b18
implementation_commit: this change
branch: main
depends_on: P1-WP21, H03; P1-WP29 remains a separate distribution gate
release_gate: bounded-local-evidence; no production or live-execution claim
evidence_commit: this change
closeout_commit: this change
```

## Amaç

Yeni işlem formunu gerçek borsaya emir gönderen bir ekran olmaktan çıkarıp, başka
bir yerde gerçekleştirilmiş işlemi kanıt/provenance bilgisiyle kaydeden güvenli bir
günlük girişine dönüştürmek. Kullanıcı istediği varlık sembolünü girebilir; otomatik
fiyat yalnızca sembol kimliğini değiştirmeden destekleyen ücretsiz public kaynaktan
alınır. Kaynak uygun değilse fiyat `UNAVAILABLE` kalır ve kullanıcıdan gerçek fiyatı
manuel girmesi istenir.

Bu paket Kuantra'nın ürün kimliğini değiştirmez: Kuantra hâlâ local-first Execution
Intelligence & Trade Forensics Workstation'dır. Geniş sembol günlüğü desteği, geniş
otomatik broker/hesap reconciliation veya tüm varlıklar için canlı veri garantisi
değildir.

## Kabul kriterleri

- [x] Ücretsiz quote registry yalnızca `binance_public`, `bybit_public`,
      `yahoo_public` ve `stooq_public` kaynaklarını kabul eder; ücretli/API-key
      gerektiren kaynak isteği ağ çağrısı yapmadan `UNAVAILABLE` döner.
- [x] Crypto pair açık quote currency ile Binance → Bybit public sırasını kullanır;
      genel ticker `GOOG` gibi semboller sahte `GOOGUSDT` çiftine çevrilmez ve
      Yahoo/Stooq'ta exact sembol olarak denenir.
- [x] `XAUUSD` hiçbir koşulda `GC=F` veya `PAXGUSDT` ile sessizce değiştirilmez;
      explicit `GOLD`/`GC=F` alias'ı ayrı kaynak sembolü olarak görünür.
- [x] Quote sonucu fiyat, kaynak sembolü, `LIVE`/`DELAYED`/`EOD`/`UNAVAILABLE`,
      fiyat türü, gözlem zamanı ve başarısızlık nedenini taşır. Eksik fiyat hiçbir
      zaman simülasyon veya sıfır olarak üretilmez.
- [x] `EXTERNAL` harici işlem günlüğü yeni formun varsayılanıdır; form `/trades`
      journal endpoint'ine yazar ve `/execution/order` çağırmaz.
- [x] `SIMULATION` yalnızca açık kullanıcı seçimiyle kullanılabilir ve yine journal
      kaydıdır; otomatik fiyat fallback'i veya canlı emir yetkisi yoktur.
- [x] Trade snapshot, canonical evidence event ve rebuildable projection record mode
      ile quote provenance alanlarını korur; eski satırlar `UNKNOWN`/`UNAVAILABLE`
      olarak kalır ve migration additive/idempotent'tir.
- [x] TradingView webhook gözlemi immutable `PENDING_REVIEW` olayı olarak kaydedilir;
      kullanıcı onayı olmadan trade oluşturulmaz. Onaylanan kayıt alert lineage'ını
      ve manuel gerçekleşen fiyatı taşır.
- [x] İlk açılış arayüzü canlı emir/routing seçeneği sunmaz; harici günlük kaydı
      varsayılan, simülasyon açıkça seçilebilir durumdadır; credential/API key toplamaz.
      EN/TR/DE anahtarları parity'dir.
- [x] Red/green focused backend ve frontend testleri tamamlanmış; ilgili regression
      suite, i18n, TypeScript, production build ve docs gate sonucu kaydedilmiştir.

## Kapanış kanıtı

Bu bounded paketin red → green ve regresyon kanıtı, `this change` kapanış commit'inde
korunmuştur. Gerçek kullanıcı verisi, credential, Keychain, migration bundle veya live
broker kullanılmadı.

Focused backend/regression komutu:

```text
PYTHONPATH=backend .venv/bin/pytest -q backend/tests/test_p1_wp01_evidence_ledger.py backend/tests/test_h02_schema_upgrade_restore.py backend/tests/test_p1_wp30_free_quote_external_journal.py
→ 35 passed, 2 warnings
```

Canonical Mac local gate:

```text
uv run --offline --no-project --with-requirements backend/requirements.lock python scripts/run_local_ci.py --expected-architecture arm64
→ MERGE READY; 13/13 steps PASS
```

Bu çalıştırmada backend **829 passed / 2 warnings**, frontend **27 test files / 121
tests**, EN/TR/DE **696/696**, TypeScript/production build, arm64 PyInstaller ve native
WKWebView smoke PASS oldu. `git diff --check`, `python3.11 scripts/check_docs.py`
(`115 documents`, `152 local links`, `5 startup documents`) ve
`python3.11 scripts/check_release_truth.py` PASS oldu. Local-CI raporu
`dist/local-ci-report.json` SHA-256
`109477ef3f7b66fd779a62c41cec9d1a29d796a1e4f394459a5d4b69e43d5d52`, eşlik eden
native smoke raporu `dist/local-ci-smoke.json` SHA-256
`26675daf07354aacf8c0981b5a2af9d9f8652eede6861e4538b0cf5e577af0ad`'dir.

Provenance raporu checkout commit'i `b972b1848c03d2ad3d6a896750f66f1814ea1247`,
tracked tree SHA-256'sı `d643951f6f8cd32b8820ca05b4f22778cff48ea01ccdc5025f619d488f1600a6`,
backend lock SHA-256'sı `6291588602869af34e2a4db5d7244a627f4e139cbbd4b034b7cc07d890812399`,
frontend lock SHA-256'sı `396c757d5733e9618aa71f665aa3f23f5d53fcdaa8d9ff67c11d172464fcc6bc`;
Mac `26.6.2 arm64`, Python `3.11.16`, Node `v20.20.2`, npm `10.8.2`, uv `0.12.10`
ve PyInstaller `6.22.2`'dir. Çalışma ağacı implementation commit öncesi dirty olduğu
için provenance status bilinçli olarak `DEVELOPER_DIRTY`'dir; bu sonuç release
attestation'ı değildir.

Yerel DMG doğrulaması da tamamlandı:

```text
PYTHON_BIN=.venv/bin/python bash scripts/package_macos.sh --architecture arm64 --output dist/Kuantra-Terminal-1.0.0-arm64.dmg
→ PASS; hdiutil verify: VALID

.venv/bin/python scripts/smoke_macos_dmg.py --dmg dist/Kuantra-Terminal-1.0.0-arm64.dmg --expected-architecture arm64 --report dist/final-smoke-arm64-wp30.json
→ mounted executable functional checks: SMOKE_OK; WKWebView/controller/arm64/detach PASS
```

DMG SHA-256 `23be62393a725b0e598145cc2a483042a4f2c06ec008d7b5308e5cf603ad226f`,
mounted executable SHA-256 `14f8d0120b8442689a5c702b439093638cc507514edca00cb20d61c8e137e1a8`
ve exact smoke raporu SHA-256
`5281ddc74a91080e018caaa9461e6064f445ec285d781eefdf3f92c42f2eedfe`'dir. Final
release-facing validator, dirty source tree nedeniyle exit 1 vererek provenance'ı
doğru biçimde blokladı; DMG içi functional smoke sonucu bu nedenle release PASS'ı
olarak yazılmamıştır.

Bu kapanış yeni bir GitHub Release/tag yayımlamaz. Mevcut private
`pilot-v1.0.0-arm64` asset'i source `8da8019`'a bağlı olduğundan P1-WP30 akışını
içermez; güncel pilot paketi P1-WP29 dağıtım kapısında yeniden üretilmelidir.

## Kesinlikle kapsam dışı

- Ücretli market-data servisi, API-key gerektiren quote entegrasyonu veya ücretli veri
  satın alma.
- TradingView'i quote API gibi kullanmak; webhook sinyali fill kanıtı değildir.
- Yeni broker connector, live order, copy trading, funding/transfer schema veya
  otomatik simulation fallback.
- XAUUSD, hisse, forex, endeks veya diğer varlıkları başka bir sembole dönüştürerek
  destekleniyor göstermek.
- Apple Developer ID/signing/notarization, Intel artifact, clean-host N03 veya release
  onayı. Bunlar P1-WP29/N03/N05 owner-host kapılarıdır.

## Kanıt ve kalan sınırlar

Testlerde network/credential kullanılmaz; public fetcher çağrıları dependency injection
fixture'larıyla doğrulanır. `UNAVAILABLE` bir hata olarak değil, kullanıcıya manuel
fiyat girişi sunan gerçek bir veri durumu olarak taşınır. Auto quote kaydı gözlenen
public fiyatı kanıtlar; kullanıcının dış borsadaki fill'inin gerçekleştiğini kanıtlamaz.

Bu paket tamamlandığında production-ready veya tüm varlıklar için canlı veri iddiası
açılmaz. Gerçek cihaz pilotu ayrıca import → review → export ve packaged DMG akışını
doğrulamalıdır.
