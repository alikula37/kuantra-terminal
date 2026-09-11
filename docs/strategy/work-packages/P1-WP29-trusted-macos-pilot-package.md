<!-- doc-role: current-work-package -->
# P1-WP29 — Trusted macOS Pilot Package

```yaml
work_package: P1-WP29
version: 1.0.0
status: InProgress
date: 2026-09-10
baseline_commit: a58935a
implementation_commit: 8db2e53
latest_artifact_source_commit: 8db2e533f0dde972c0aba8ad6617da5ca722ec06
latest_evidence_date: 2026-09-11
branch: main
depends_on: P1-WP28 (arm64 chain for M-series; x86_64 chain for dual), N05
release_gate: owner-pilot-approval, exact-architecture-evidence
```

## Amaç

Üç kişilik kapalı macOS pilotu için exact mounted-DMG smoke/N05 kanıtını,
manifest/checksum dosyalarını ve teknik olmayan kullanıcı talimatını tek fail-closed
paket akışına bağlamak. Varsayılan yol iki native mimari DMG'yi aynı kaynak kimliğiyle
paketler; ilk pilot sırası için açıkça seçilen arm64 modu yalnız Apple Silicon/M-series
kapsamı üretir ve Intel desteği iddia etmez. Pilot ekip aynı zamanda kontrollü doğrulama
grubudur: Intel katılımcı, hazır x86_64 DMG üzerinde runtime ve N03 install-lifecycle
kanıtı sağlayabilir. Apple Developer ID alınmadığı sürece paket **trusted pilot only**
olarak kalır; production veya commercial support claim'i açılmaz.

## Kabul kriterleri

- [x] Settings manual pilot Release action replaces the fabricated update check;
      seven direct DOM tests cover native URL dispatch, browser link, failure/retry,
      missing bridge and timeout/late response. EN/TR/DE 734-key parity and build pass.
- [x] Refreshed clean arm64 package includes the manual update action; native browser
      handoff and exact DMG evidence are recorded before Release asset replacement.
      Source `119ae573`, DMG SHA-256 `7a07847d`, mounted executable SHA-256
      `9d70f2ac`, exact smoke SHA-256 `b59489cd`; native click-through opened the fixed
      private Release URL in Chrome from a clean temporary profile.
- [x] Pilot journal UI correction keeps the persisted theme toggle visible across the
      shell by applying light/dark DOM tokens, root `color-scheme` and a guarded settings
      sync; the standard journal exposes an explicit, confirmed `CANCELED` action for
      OPEN/CLOSED rows, preserves the tombstone instead of physically deleting evidence,
      validates the response and exposes a CANCELED filter. Canceled tombstones remain
      in the journal/evidence chain but are excluded from the dashboard asset-performance
      breakdown; canceling an OPEN row also removes it from the in-memory open-position
      list. The market-chart page is named and translated as `Market Charts` /
      `Piyasa Grafikleri` / `Marktcharts`, including its visible OHLCV and error content.
      Journal/Chart DOM coverage is `12 passed`; the portfolio regression is `11 passed`,
      full frontend coverage is `29 files / 133 tests`, i18n is `734/734`, and the arm64
      local candidate from source `8db2e53` passed locked local CI plus exact mounted-DMG
      smoke with `COMPLETE` provenance. The existing private Release asset still requires
      a later package refresh before pilot distribution.

- [x] GitHub private Release'ın yalnızca repository read erişimi olan kullanıcılara
      dağıtım sağlayabildiği; Apple signing/notarization yerine geçmediği resmi kaynaklarla
      kaydedildi.
- [x] `scripts/prepare_pilot_package.py` exact `arm64` ve `x86_64` DMG, final mounted
      WKWebView smoke ve N05 raporlarını aynı source/tree/lock/truth identity ile doğrular.
- [x] Varsayılan dual package builder, Intel kanıtı eksikse exit 2 ile durur; açık
      `--architecture arm64` modu ise yalnız M-series kapsamını, `TRUSTED_MACOS_PILOT_ARM64`
      paket tipini ve Intel desteği olmadığını manifestte görünür kılar.
- [x] Ad-hoc N05 sonucu pakete yalnızca `AD_HOC_TRUSTED_PILOT_ONLY` olarak girer;
      production, commercial support, real-user outcome ve live execution claim'leri false kalır.
- [x] Paket `PILOT-MANIFEST.json`, evidence JSON'ları, `SHA256SUMS` ve standalone
      `PILOT-INSTRUCTIONS.md` üretir; mevcut user data, credential, Keychain veya migration
      bundle'ına dokunmaz.
- [x] Rosetta ile çevrilmiş x86_64 process native Intel build/package/smoke kanıtı olarak
      kabul edilmez; build job write izni read ile sınırlandırılır.
- [x] Private Release, Actions artifact, Apple Gatekeeper ve macOS model/OS sınırları
      [araştırma kaydında](../../release/PILOT-DISTRIBUTION-RESEARCH.md) açıkça ayrılır.
- [x] DMG build ve exact mounted-DMG smoke öncesinde `hdiutil verify` ile image/container
      bütünlüğü kontrol edilir; pilot talimatı indirilen DMG'de aynı kontrolü ister.
      Bu kontrol Gatekeeper, malware taraması, Developer ID veya notarization yerine
      geçmez; hiçbir güvenlik bypass'ı eklenmez.
- [x] Pilot ekip yalnızca paket tüketicisi olarak değil, native Intel Mac runtime/N03
      doğrulama hostu olarak da kullanılabilir; expected architecture, source provenance
      ve temiz profil koşulu kanıtlanmadan Intel veya production claim'i açılmaz. `75a4188`
      ile `run_local_ci.py --expected-architecture x86_64` native host/executable/provenance
      zincirini fail-closed doğrular; Mac mini'de yanlış x86_64 isteği exit 2 ile reddedildi.
- [x] Mac mini üzerinde `6646332` source commit'i için arm64 exact DMG, `hdiutil verify`
      (`VALID`), read-only mounted WKWebView smoke ve ad-hoc N05 evidence zinciri yeniden
      üretildi; N05 sonucu bilinçli olarak `BLOCKED/OWNER_REVIEW_REQUIRED` kaldı.
- [x] İlk M-series arm64-only pilot paketi source commit `6f8b1ed`'dan üretildi;
      manifest, checksum doğrulaması ve standalone M-series talimatı aynı pakette bulunur.
      Paket `dual_architecture_complete=false`, `intel_artifact_included=false` ve
      `intel_support_claim=false` alanlarını taşır. Paket durumu
      `AD_HOC_TRUSTED_PILOT_ONLY_ARM64`'tır; pilot tag'i
      `pilot-v1.0.0-arm64`, manifest SHA-256
      `cdcb68b0cc662e2d54a2805b4d8672c258f1ad9f2df37d44420bca5c56594f10`,
      `SHA256SUMS` SHA-256 `53610c49f7dd10e89cf13070e5d423e88fb1e50100352df90fa956967dcdeab9`.
- [x] Önceki `6f8b1ed` paket kanıtı superseded historical evidence olarak korunur; güncel
      M-series package doğrulamasında kullanılmaz.
- [x] Güncel M-series arm64-only pilot paketi temiz source commit `119ae57`'dan üretildi;
      manifest, checksum doğrulaması ve standalone M-series talimatı aynı pakette bulunur.
      Paket `dual_architecture_complete=false`, `intel_artifact_included=false` ve
      `intel_support_claim=false` alanlarını taşır. Paket durumu
      `AD_HOC_TRUSTED_PILOT_ONLY_ARM64`'tır; manifest SHA-256
      `4ed1e6cc4521223c6282257190d76deac50122c9763ccaa525f06bd1831cc9c2`,
      `SHA256SUMS` SHA-256 `a0bbf709e4236738f3f980f3a1b99e31e01faf908fb2e499030c8d9345bba18c`.
- [x] M-series private prerelease Release, `pilot-v1.0.0-arm64` tag'i ile
      yayımlandı; altı asset'in GitHub SHA-256 digest'i local `SHA256SUMS` ve
      manifest ile eşleşir. Release URL'si:
      `https://github.com/alikula37/kuantra-terminal/releases/tag/pilot-v1.0.0-arm64`.
- [x] Mevcut `pilot-v1.0.0-arm64` private prerelease asset seti yeni tag oluşturmadan
      source commit `119ae57`'ye bağlı arm64 paketle in-place yenilendi. Altı asset,
      güncel release body ve `PILOT-INSTRUCTIONS-M-SERIES.md` aynı pilot sınırını taşır;
      canonical `v1.0.0` Release/tag'i oluşturulmadı.
- [ ] Gerçek x86_64 native host (hosted runner veya açıkça seçilmiş pilot Intel Mac),
      exact DMG ve smoke/N05 zincirini üretir. GitHub billing/spending-limit durumu
      hosted yolu kapatırsa pilot Intel Mac kontrollü build hostu olabilir.
- [ ] N03 temiz ikinci Mac profil/host install → launch → import/review → close/reopen
      kanıtı tamamlanır; pilot Intel Mac'i bu host olabilir. Bu paket kodla varsayılan
      olarak PASS ilan etmez.
- [x] Owner-approved M-series pilot tag'i `pilot-v1.0.0-arm64` ile private prerelease
      yayımlanır ve altı asset yüklenir. Canonical `v1.0.0` dual Release/tag'i bu paketle
      oluşturulmaz.
- [ ] Owner, üç pilot kullanıcı için private repository read erişimini verir; erişim
      davetleri bu çalışma sırasında otomatik gönderilmez.

## Ürün ve güvenlik sınırı

Bu paket Kuantra'yı local-first Execution Intelligence & Trade Forensics Workstation
olarak tutar. AI order authority, live broker order, funding/transfer schema, tam hesap
PnL, Windows/Linux veya macOS 11 ve altı desteği eklemez. `SHA256SUMS` dosyasının geçmesi
dosya bütünlüğünü doğrular; Apple malware/notarization güveni veya finansal doğruluk
garantisi değildir. Kullanıcı Gatekeeper'ı kapatmaz ve karantina etiketini komutla silmez.

## Doğrulama

Focus testleri ve tam suite, gerçek mimari kanıtı üretene kadar her kod değişikliğinde
çalıştırılır. Package builder'ın beklenen mevcut sonucu:

```text
python scripts/prepare_pilot_package.py --output dist/pilot-package-v1.0.0
→ BLOCKED (x86_64 native DMG/evidence missing; dual mode)

python scripts/prepare_pilot_package.py --architecture arm64 \
  --output dist/pilot-package-v1.0.0-arm64
→ PASS (AD_HOC_TRUSTED_PILOT_ONLY_ARM64), once the current arm64 chain is present
```

İlk çağrının `BLOCKED` olması uygulama hatası değil, henüz üretilemeyen Intel dış
kanıtının doğru şekilde reddedilmesidir. Arm64 çağrısı yalnızca açık M-series pilot
kapsamı ile başarılanabilir. İki zincir hazır olduğunda varsayılan dual çağrı ve ardından:

```text
shasum -a 256 -c dist/pilot-package-v1.0.0/SHA256SUMS
```

### Güncel M-series package evidence (2026-09-11)

Temiz source commit `119ae573ce4e4885c2c83e0e8619ebd6038131dd` üzerinden arm64 pilot
zinciri yeniden üretildi. `uv run --offline --no-project --with-requirements
backend/requirements.lock python scripts/run_local_ci.py --expected-architecture arm64
--report dist/manual-update-local-ci-final.json` **MERGE READY** döndürdü: backend
**829 passed / 2 warnings**, frontend **28 test files / 128 tests**, EN/TR/DE **703/703**,
TypeScript, production build, native arm64 PyInstaller ve native WKWebView smoke PASS;
provenance `COMPLETE`. Local-CI report SHA-256:
`9345f70dbe4b28ef419931faceb90f4650d06fc8e97dfa0f8afcc4e146d4715b`.

`bash scripts/package_macos.sh --architecture arm64 --output
dist/Kuantra-Terminal-1.0.0-arm64.dmg` **PASS** oldu; `hdiutil verify` sonucu `VALID`.
DMG SHA-256:
`7a07847da1134f6a098a491ee97a74db4e949b4ab373a99fa8bb086ada7f3e5d`.
`.venv/bin/python scripts/smoke_macos_dmg.py --dmg
dist/Kuantra-Terminal-1.0.0-arm64.dmg --expected-architecture arm64 --report
dist/final-smoke-arm64.json` exact read-only mounted executable üzerinde **PASS** oldu;
native arm64, WKWebView/controller identity ve detach doğrulandı. Mounted executable
SHA-256 `9d70f2acfdd1b81b124323d0ad1c4b0f280ff76f526a462774c076791161a90b`, smoke report
SHA-256 `b59489cdd444447297da51b249936ddf8ddb0d5054da4c11c60623fb6e54b3ef`.

N05 preflight structurally valid fakat ad-hoc artifact ve Developer ID/notarization kanıtı
olmadığı için exit 2 ile beklenen `BLOCKED/OWNER_REVIEW_REQUIRED` sonucunu verdi. N05 report
SHA-256 `2ebf924aa122042f409522cc3637c017ba90530e81ced130f2008ad0365d061f`.
`prepare_pilot_package.py --architecture arm64 --pilot-tag pilot-v1.0.0-arm64` **PASS**
oldu; package type `TRUSTED_MACOS_PILOT_ARM64`, scope `APPLE_SILICON_M_SERIES_ONLY`,
status `AD_HOC_TRUSTED_PILOT_ONLY_ARM64`. Package yolu:
`dist/pilot-package-pilot-v1.0.0-arm64-119ae57/`; manifest SHA-256
`4ed1e6cc4521223c6282257190d76deac50122c9763ccaa525f06bd1831cc9c2`, `SHA256SUMS` SHA-256
`a0bbf709e4236738f3f980f3a1b99e31e01faf908fb2e499030c8d9345bba18c`. Paketteki beş payload dosyası
`shasum -a 256 -c SHA256SUMS` ile `OK` oldu. Package, P1-WP30 değişikliklerini içerir;
Intel artifact, production/commercial-support, live execution veya Apple-trusted claim
taşımaz.

Settings → Application updates → Open update page düğmesi, final mounted DMG içindeki
uygulamada temiz geçici profille native olarak doğrulandı. Düğme Chrome'da sabit private
Release URL'sini açtı; otomatik sürüm karşılaştırması, indirme, kurulum veya veri migration'ı
yapmaz. Bu click-through kanıtı kullanıcı verisine dokunmadı.

### Current analytics/chart correction candidate evidence (2026-09-11)

Source commit `8db2e533f0dde972c0aba8ad6617da5ca722ec06` ve tracked source tree
`42600b6fb58197473b29c968ad82b21e4e356abab5a23c834ed8c8ea19ae402e` temizken:

- `uv run --offline --no-project --with-requirements backend/requirements.lock python
  scripts/run_local_ci.py --expected-architecture arm64 --report
  dist/p1-wp29-cancel-breakdown-chart-i18n-clean-local-ci-arm64.json --smoke-timeout 90`
  → **MERGE READY**; backend **830 passed / 2 warnings**, frontend **29 test files / 133
  tests**, i18n **734/734**, TypeScript, production build, native arm64 PyInstaller,
  WKWebView smoke and provenance **COMPLETE**. Report SHA-256:
  `6dea4f5dbec9bb98696031fdf0a5f7ebc517d017f98426f9be361e01d3cc4a31`.
- `bash scripts/package_macos.sh --architecture arm64 --output
  dist/Kuantra-Terminal-1.0.0-arm64-cancel-breakdown-chart.dmg` → **PASS**;
  `hdiutil verify` **VALID**. DMG SHA-256:
  `99c4849becfdb17472af035d05aa01ac6c815b1b1c7459e4776fad54d9b69fc9`.
- `.venv/bin/python scripts/smoke_macos_dmg.py --dmg
  dist/Kuantra-Terminal-1.0.0-arm64-cancel-breakdown-chart.dmg --expected-architecture
  arm64 --report dist/final-smoke-arm64-cancel-breakdown-chart.json` → **PASS** on the
  exact read-only mounted executable; native `arm64`, WKWebView/controller identity and
  detach passed. Mounted executable SHA-256:
  `615e4cc7933d3f8b50b1e2fcba618f704db0b96fb29af2ca2aa2b0a96eb15e1d`; smoke report
  SHA-256: `1a1a1ddca0d5fff89767b9e3194f0ffe1c19e0be1a604c83e8334c2b89e7701b`.
- Native click-through confirmed that existing `CANCELED` tombstones no longer create
  dashboard performance buckets, while journal audit history is preserved. Turkish,
  English and German market-chart navigation, title, subtitle, OHLCV labels and error
  states were checked; light/dark chart rendering was toggled and restored. No real trade
  or user data was changed. The candidate is installed at
  `/Applications/Kuantra Terminal.app`; the previous bundle was moved recoverably to
  `/Users/kula/.Trash/Kuantra Terminal.app.before-cancel-chart-fix`. The private GitHub
  Release was not changed in this code task, so its assets must be refreshed explicitly
  before pilot distribution.

### Previous pilot UI correction candidate evidence (2026-09-11)

Source commit `e9f702b6b49da41e6249a0044abb3f2f0363bfc7` ve tracked source tree
`c1bdf652b2b84301ed7fa3eb33fc625e7c6f97b8176af5ac471296ab2a906509` temizken:

- `uv run --offline --no-project --with-requirements backend/requirements.lock python
  scripts/run_local_ci.py --expected-architecture arm64 --report
  dist/p1-wp29-ui-corrections-clean-local-ci-arm64.json --smoke-timeout 90` →
  **MERGE READY**; backend **829 passed / 2 warnings**, frontend **29 test files / 133
  tests**, i18n **716/716**, TypeScript, production build, native arm64 PyInstaller,
  WKWebView smoke and provenance **COMPLETE**. Report SHA-256:
  `82d63f1193dc16e0e2c14fb48f07f86fb847863bcaa81bf628ee00f1266f1046`.
- `bash scripts/package_macos.sh --architecture arm64 --output
  dist/Kuantra-Terminal-1.0.0-arm64.dmg` → **PASS**; `hdiutil verify` **VALID**.
  DMG SHA-256: `be1773896472e1827a359104954f4b025067959884ef01e890dac468b7b1b4b1`.
- `.venv/bin/python scripts/smoke_macos_dmg.py --dmg
  dist/Kuantra-Terminal-1.0.0-arm64.dmg --expected-architecture arm64 --report
  dist/final-smoke-arm64-ui-corrections-clean.json` → **PASS** on the exact read-only
  mounted executable; native `arm64`, WKWebView/controller identity and detach passed.
  Mounted executable SHA-256: `155913f6ebc268d863a30977a0e48a889a29c5badab5f8afa43e8233d5e4902a`;
  smoke report SHA-256: `cd76d0a9a26c6de6233b3b355445f6915d47251f7128a1d84bca4107fd657d90`.
- Native app click-through showed the translated Light/Dark control and `İptal et`
  action on existing OPEN/CLOSED rows. No real trade was canceled; the original dark
  preference was restored. The candidate is installed locally at
  `/Applications/Kuantra Terminal.app`; the previous app bundle was moved recoverably
  to the user's Trash. The private GitHub Release was not changed in this code task, so
  its assets must be refreshed explicitly before pilot distribution.

### Superseded M-series çalıştırması (2026-09-10)

2026-09-10 tarihinde `6f8b1ed` source commit'i ile aşağıdaki zincir PASS oldu:

- `uv run --offline --no-project --with-requirements backend/requirements.lock python scripts/run_local_ci.py --expected-architecture arm64 --report dist/p1-wp29-local-ci-arm64-release.json --smoke-timeout 90` → **MERGE READY**; backend **816 passed / 2 warnings**, frontend **25/104**, i18n **608/608**, native arm64 build/smoke ve provenance `COMPLETE`. Local-CI report SHA-256: `d2dd6d663441c0202e8940018111a8190589ce82a3e1324c040ab6aea02595ae`.
- `bash scripts/package_macos.sh --architecture arm64 --output dist/Kuantra-Terminal-1.0.0-arm64.dmg` → **PASS**; `hdiutil verify` exact image için `VALID`. DMG SHA-256: `d2f8151e24e29ae0a3800165d823dfd3e6f44a2ef3b95f04674a6ed9ead6e540`.
- `.venv/bin/python scripts/smoke_macos_dmg.py --dmg dist/Kuantra-Terminal-1.0.0-arm64.dmg --expected-architecture arm64 --report dist/final-smoke-arm64-release.json` → **PASS**; exact read-only mounted executable, native WKWebView/controller ve detach. Mounted executable SHA-256: `c76315073ef72687bef2bb90dc9c0ec5adfdc1aff912898aa717562aaae2e870`; report SHA-256: `40573464091be5d43a3c31b973980559ebc4fe1112a4fa87948f37a428cda080`.
- `.venv/bin/python scripts/run_n05_macos_distribution_preflight.py ...` → **BLOCKED/OWNER_REVIEW_REQUIRED** (exit 2), çünkü ad-hoc artifact Developer ID/notarization ticket taşımıyor. Report SHA-256: `19fa90a538db42d9a110b58359c2c55a33e87cb3a082f9494f25fa948a092eb4`.
- `.venv/bin/python scripts/prepare_pilot_package.py --architecture arm64 --pilot-tag pilot-v1.0.0-arm64 --dist dist --output dist/pilot-package-pilot-v1.0.0-arm64` → **PASS**; package type `TRUSTED_MACOS_PILOT_ARM64`, scope `APPLE_SILICON_M_SERIES_ONLY`, status `AD_HOC_TRUSTED_PILOT_ONLY_ARM64`. Paket içindeki beş dosyanın `shasum -a 256 -c SHA256SUMS` doğrulaması **OK**; manifest SHA-256 `cdcb68b0cc662e2d54a2805b4d8672c258f1ad9f2df37d44420bca5c56594f10`, `SHA256SUMS` SHA-256 `53610c49f7dd10e89cf13070e5d423e88fb1e50100352df90fa956967dcdeab9`.

Paket yolu: `dist/pilot-package-pilot-v1.0.0-arm64/`. Bu çalışma kullanıcı verisi,
credential, Keychain veya migration bundle kullanmadı. Release private prerelease olarak
yayındadır; üç pilot kullanıcısının repository read erişimi ve gerçek cihazlarda
install-lifecycle çalıştırması hâlâ owner/host kapısıdır. Canonical `v1.0.0` product
Release/tag'i ve dual package bu işlemle oluşturulmadı.

## Superseded frontend pilot-flow hardening (`8da8019`)

The pilot-facing import → review → Evidence Pack path now has an explicit truth and
failure boundary in the UI:

- [x] Missing or `null` PnL/R values remain visibly unknown in the journal, open-position
      and CSV preview surfaces; they are never rendered as zero. Weekly review completion
      and reopen actions are disabled when period, timezone or as-of inputs differ from
      the loaded snapshot.
- [x] Evidence Pack JSON responses, weekly review responses and CSV preview/import
      responses are runtime-validated before rendering. Malformed successful responses
      remain visible errors and cannot be interpreted as empty, complete or successful
      evidence.
- [x] Evidence Pack JSON/HTML/CSV export uses the native desktop save bridge on pywebview;
      the UI reports ready only when the bridge confirms an actual save, and reports
      cancellation/failure separately. Browser fallback behavior remains bounded.
- [x] CSV file replacement clears the previous preview/review, accepts case-insensitive
      `.csv`/`.txt` extensions, aborts stale preview requests and exposes a keyboard-
      accessible dropzone/modal.
- [x] Journal reads `201` records as a page sentinel, keeps the first `200`, loads older
      pages with an offset, de-duplicates by trade ID and preserves the loaded page when
      a load-more request fails.
- [x] Journal, CSV import, weekly review and Evidence Pack additions are covered by the
      synchronized EN/TR/DE translation contract.

Verification for this bounded change is recorded by `8da8019`: frontend **25 test
files / 116 tests**, i18n **670/670**, TypeScript `--noEmit` and production build pass;
the locked arm64 local CI also passes backend **816 tests / 2 warnings**, native arm64
PyInstaller build, WKWebView smoke and `COMPLETE` provenance on a clean commit. The
native bridge/export path has focused unit/DOM coverage, but the exact rebuilt DMG still
requires a manual pilot click-through of import → review → Evidence Pack → native
JSON/HTML/CSV save before this package can be called end-to-end pilot-validated. The
existing private prerelease asset set was then refreshed in place from this source commit;
that asset set is superseded by the clean `119ae57` package above; no new Release/tag was
created for the historical refresh.

Dual GitHub Release, Apple signing/notarization, pilot kullanıcı erişimi ve
clean-host yürütmesi bu work package'ın otomatik kod kapıları değildir; owner/host
kapılarıdır. M-series private prerelease yayımlanmış olsa da canonical product Release
yetkisi verilmiş değildir.

## Superseded private Release asset yenilemesi (2026-09-10)

2026-09-10 tarihinde mevcut `pilot-v1.0.0-arm64` private prerelease, aynı tag korunarak
source commit `8da8019ae93513c474a3122d450cffb40f66261b` ile üretilen arm64 paketle
yenilenmişti. Bu bölüm yalnızca audit history içindir; güncel DMG SHA-256
`900ce30ebe93bc9a1ded399c0067edfa2f7475b892da9193ff608e579f291a76`, mounted executable
SHA-256 `6b3b9985058933f655b2a0e1ece69a41b7d51eb28f00c2c2c0023a7792e41ce1`, final smoke
report SHA-256 `81eb80f7a77191325c43e313a4ce1664aefe4ba27f4f76292adaaaf97d34d6fd` ve N05
report SHA-256 `5b24b09d1d42aef456777ab398a71e23d1e1a9ee42e0bfad8dc74840454b1ca3` olarak
kanıtlandı. N05 ad-hoc artifact nedeniyle `BLOCKED/OWNER_REVIEW_REQUIRED` durumundadır;
bu beklenen pilot sınırıdır. Release body, DMG, evidence JSON'ları, manifest, checksums ve
standalone talimat asset'leri aynı arm64 pilot kapsamını taşır. Local-CI report SHA-256
`cde81fe18e0346b534b4828589c462bc4d7381719611df959b5a7000f6bf0c79`, tracked source tree
SHA-256 `964e672c8c05da2b490de83856a8a4e81e2c4b77f2a333751bdc783547f764cd`, package
manifest SHA-256 `1b196a795a82d2dc7b9fea006f0e12e4cf55690956a75b797bbedce4235bc548` ve
`SHA256SUMS` SHA-256 `5577f7ae8b69197b36b754a4290472ad9dcca8314c74d62fbce72911af67e89e` olarak
doğrulandı.
