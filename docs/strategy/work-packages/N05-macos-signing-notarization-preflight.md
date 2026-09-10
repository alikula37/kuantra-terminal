<!-- doc-role: reference -->
# N05 — macOS Signing / Notarization Preflight

```yaml
work_package: N05
version: 1.0.0
status: InProgress
date: 2026-09-10
baseline_commit: 9efd203
implementation_commit: 121a5cdaff2985245156875ffdd8e42ca79fceca
branch: main
strategy: KPR-001@current
depends_on: N01, N02, N03-final-validation, H04, H05
release_gate: owner-and-apple-account-required
```

## Amaç

N05'in kodla kapatılabilir kısmı, exact final DMG'nin içindeki gerçek `.app` üzerinde
imza, hardened runtime, entitlements, Gatekeeper ve notarization ticket sonuçlarını
tek bir source/provenance/hash zincirine bağlayan read-only bir preflight sağlamaktır.
Bu paket imza atmaz, notarization başlatmaz ve Apple hesabı/sertifika/Keychain
secret'ı istemez. Ad-hoc geliştirme artifact'ı doğru biçimde `BLOCKED` kalır.

Bu ayrım, bir dosyanın yalnızca hash'inin veya source-level testin commercial
distribution kanıtı gibi sunulmasını engeller. N05 PASS sonucu bile tek başına
production-ready veya commercial-support iddiası değildir.

## Kapsam

- Exact DMG'yi `hdiutil attach -readonly` ile mount edip yalnızca mount içindeki
  `Kuantra Terminal.app` executable'ını incelemek.
- Final mounted-DMG smoke/provenance raporunun source commit, clean tracked tree,
  lock hash'leri ve exact DMG/executable SHA-256 değerleriyle eşleşmesini doğrulamak.
- `codesign --verify --deep --strict`, Developer ID Application identity ve
  hardened-runtime flag'ini fail-closed değerlendirmek.
- Entitlement anahtarlarını sınırlı allowlist ile kontrol etmek; raw command output'u
  rapora yazmamak.
- Gatekeeper assessment ve DMG stapled-ticket validation sonucunu kaydetmek.
- Mount detach edilmezse sonucu başarısız saymak; no user data, credential, network
  application call veya live execution kullanmamak.
- Release workflow'a gate'i bağlamak; actual Apple signing/notarization sonucunu
  owner/host kanıtı gelmeden tamamlanmış saymamak.
- `package_macos.sh` içinde ad-hoc geliştirme default'unu korurken explicit
  `developer-id` signing mode, hardened runtime ve certificate-name guard sağlamak.
- Owner-approved Apple host için `notarize_macos.sh` explicit-submit wrapper'ı sağlamak;
  final DMG'yi stapling sonrası yeniden smoke ederek N05'e exact hash zinciriyle vermek.

## Davranış sözleşmesi

1. Provenance, smoke veya artifact hash mismatch `EVIDENCE_INVALID`/exit `1` olur;
   `OWNER_REVIEW_REQUIRED` ile karıştırılmaz.
2. Geçerli fakat ad-hoc, hardened-runtime'siz, Gatekeeper-rejected veya ticketsiz
   artifact `BLOCKED`/exit `2` olur; hiçbir blokaj PASS'e dönüştürülmez.
3. Yalnız Developer ID Application + valid codesign + approved entitlements +
   Gatekeeper PASS + DMG stapled ticket PASS birlikte N05 `PASS` üretir.
4. Report yalnız parsed public metadata, status, hash ve command-name bilgisi içerir;
   raw signing output, private key, password, token veya credential saklanmaz.
5. `production_ready`, `commercial_support` ve `live_execution` claim'leri her zaman
   `false` kalır; signing/notarized alanları yalnız doğrudan artifact kanıtını belirtir.

## Acceptance criteria

- [x] Read-only exact-DMG mount, explicit app selection, safe detach ve exit code
      sözleşmesi uygulanıp deterministik fixture'larla test edildi.
- [x] Smoke/provenance ile DMG ve mounted executable hash binding'i fail-closed test
      edildi; path/hash mismatch owner gate değil evidence failure olarak ayrıldı.
- [x] Ad-hoc artifact, Developer ID+hardened-runtime fixture, unapproved entitlement
      ve raw-output redaction negatif/pozitif testleri green.
- [x] macOS package script'i varsayılan ad-hoc davranışı koruyor; explicit `developer-id`
      modu identity prefix, hardened runtime ve signature verification ile fail-closed.
- [x] Notarization wrapper'ı varsayılan olarak upload yapmıyor; `--submit` olmadan duruyor,
      Keychain profile dışında secret kabul etmiyor, stapling sonrası exact smoke ve N05
      preflight çalıştırıyor.
- [ ] Developer ID Application ile imzalanmış gerçek final artifact üzerinde
      Gatekeeper assessment ve hardened-runtime kanıtı.
- [ ] Exact DMG üzerinde stapled notarization ticket kanıtı; Apple Developer
      enrollment/certificate/notary profile owner/host tarafından sağlanmalı.
- [ ] N03 temiz ikinci profil/host install-lifecycle kanıtı. N06 Windows/Linux kanıtı
      v1 Mac-only release kapsamı dışındadır ve yalnız multi-platform expansion kararıyla
      yeniden açılır.
- [ ] License/notices ve default-branch Dependabot disposition; H05 ticari gate'i
      owner kararıyla ayrıca yeniden açılacak, bu paketin kapsamına alınmayacak.
- [x] Focused regression, `python3.11 scripts/check_docs.py` ve canonical local CI
      aynı source commit/artifact ile yeniden çalıştırılıp kaydedildi.

## Kesinlikle kapsam dışı

- Developer ID sertifikası üretmek, Apple hesabına giriş yapmak, notarization upload
  etmek veya Keychain'e gerçek signing secret yazmak.
- Root `LICENSE`, third-party notices veya Dependabot alert'lerini varsayımla kapatmak.
- Automatic updater, migration, user data reset, exchange credential, live broker order
  veya yeni connector/event/schema.
- N03 clean-profile gate'ini current developer profile ile PASS saymak.
- N06 Windows WebView2/Linux final artifact kanıtını Mac üzerinde varsaymak.

## Çalıştırma

Exact final mounted-DMG smoke sonrasında:

```text
python3.11 scripts/run_n05_macos_distribution_preflight.py \
  --dmg dist/Kuantra-Terminal-<version>-arm64.dmg \
  --smoke-report dist/final-smoke-arm64.json \
  --output dist/n05-macos-distribution-arm64.json
```

Geliştirme DMG'si ad-hoc ve notarization'sız olduğu için beklenen sonuç `BLOCKED`
ve exit `2`'dir. Bu beklenen sonuç N05 implementation contract'ının çalıştığını,
Apple distribution gate'inin kapandığını değil, gösterir.

## Kanıt günlüğü

- Implementation source: `e4f8ba2` (preflight), `9733874` (release audit/manifest
  binding), `657922b` (explicit Developer ID package mode), `133c269`
  (owner-controlled notarization wrapper) and `121a5cd` (pre-submit signing gate),
  branch `main`.
- Focused evidence on implementation `121a5cd`: N05 contract **6 passed** and
  package-spec contract **9 passed**; `python3.11 scripts/check_docs.py` PASS with
  108 documents and 141 local links.
- Pre-reset v1.4.0 artifact evidence is retained in the earlier history of this record
  and is historical only; it must not be used as current v1.0.0 release evidence.
- Canonical locked local CI on macOS 26.6.2 arm64, source `00ce94e`: **13/13 PASS**,
  backend **797 passed / 2 warnings**, frontend **25 files / 104 tests**, i18n
  **608/608**, arm64 PyInstaller build, native `wkwebview` smoke and packaging
  provenance PASS. Report `dist/local-ci-report.json` SHA-256 is
  `4a356229e77f611947d6b54877ad2dde095629dceee064e9cd2ff61879507611`; tracked
  source tree SHA-256 is
  `7e5d3cdd0976b024b2a80b9deb4b9c9c27f1d3f046736711638b746d06d4fd16`; executable
  SHA-256 is `3971294f9b96aa85a3a0e9f185751098d42594da5e8fd616ff0f2f4e82f2c6b1`.
  `uv --offline` here proves locked dependency resolution only; it is not runtime
  network isolation evidence.
- Exact v1.0.0 arm64 DMG `dist/Kuantra-Terminal-1.0.0-aarch64.dmg` SHA-256 is
  `b759f1e2572d06bd9ffa7faf82949c9e06ee077711fb3067d715a29c58083bd3`; mounted
  DMG smoke PASS report `dist/candidate-final-smoke-v1.0.0-00ce94e.json` SHA-256 is
  `0bcf23e06419300f686d8863c565d30392ca8bb4a1a0fbb805f6cb3164b2e9c8`.
  The report binds canonical truth-matrix digest
  `dcbe267d933634033eb7ef000118e28b910088f9ee9caeeeebdc2a107471d768`.
- N05 preflight report `dist/candidate-n05-v1.0.0-00ce94e.json` SHA-256 is
  `338e83e77679633ecd1c16001690f3457fc243e17b7281032622e03c2d9d66d2`; it is
  `BLOCKED`/`OWNER_REVIEW_REQUIRED` with read-only mount attach/detach PASS,
  codesign verification PASS, but `AD_HOC`, no hardened runtime, Gatekeeper FAIL
  and no DMG ticket. This is the expected development boundary, not release PASS.
- Manual negative control: invoking `notarize_macos.sh --submit` against this ad-hoc
  DMG exits `2` at the local Developer ID gate before `notarytool submit` is reached.
- Platform: macOS arm64; no user data, credential, migration or live execution.
- Actual final Developer ID, Gatekeeper, notarization-ticket, clean-profile and
  commercial H05 evidence remains open.

## Sonraki bağımlılık

N05 code preflight'i green olduktan sonra v1 final artifact için owner-provided
Developer ID/notary access gerekir. N03 final clean-profile audit'i Mac-only v1
distribution/pilot validation'ın parçasıdır. N06 Windows/Linux host evidence'i v1
kapsamında değildir; yalnız gelecekte üç-OS production release iddiası yapılacaksa
yeniden açılır. H05 license/notices ve default-branch alert kararı da ticari dağıtım
öncesine kadar deferred kalır.
