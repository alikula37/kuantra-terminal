<!-- doc-role: current-work-package -->
# N05 — macOS Signing / Notarization Preflight

```yaml
work_package: N05
version: 1.0.0
status: InProgress
date: 2026-09-10
baseline_commit: 9efd203
implementation_commit: 97338746573d548eb348220bb28d834cc86ee090
branch: codex/p1-wp01-evidence-ledger
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
- [ ] Developer ID Application ile imzalanmış gerçek final artifact üzerinde
      Gatekeeper assessment ve hardened-runtime kanıtı.
- [ ] Exact DMG üzerinde stapled notarization ticket kanıtı; Apple Developer
      enrollment/certificate/notary profile owner/host tarafından sağlanmalı.
- [ ] N03 temiz ikinci profil/host install-lifecycle kanıtı ve N06 diğer OS kanıtları.
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
python scripts/run_n05_macos_distribution_preflight.py \
  --dmg dist/Kuantra-Terminal-<version>-aarch64.dmg \
  --smoke-report dist/final-smoke-macos.json \
  --output dist/n05-macos-distribution.json
```

Geliştirme DMG'si ad-hoc ve notarization'sız olduğu için beklenen sonuç `BLOCKED`
ve exit `2`'dir. Bu beklenen sonuç N05 implementation contract'ının çalıştığını,
Apple distribution gate'inin kapandığını değil, gösterir.

## Kanıt günlüğü

- Implementation source: `e4f8ba2` (preflight) and `9733874` (release audit/manifest
  binding), branch `codex/p1-wp01-evidence-ledger`.
- Focused evidence: N05 contract `6 passed`; manifest `4 passed`; Phase-0/workflow
  regression `6 passed`; `python3.11 scripts/check_docs.py` PASS with 108 documents
  and 141 local links.
- Canonical locked local CI on macOS 26.6.2 arm64, source `9733874`: **13/13 PASS**,
  backend **795 passed / 2 warnings**, frontend **25 files / 104 tests**, i18n
  **608/608**, arm64 PyInstaller build, native `wkwebview` smoke and packaging
  provenance PASS. Report `dist/n05-local-ci-report-9733874.json` SHA-256 is
  `f65a17dccaaf8a79a12759bc0fcc341620cd7738cae1ef793930e980d015e3a6`; tracked
  source tree SHA-256 is
  `2818ca6cf5748825086239ca7b543b3eaf8747b15e72c0b2d8c2aac4a924fb3f`; executable
  SHA-256 is `46044a362074ce736f6e2d25ca81737c45b25ada792777eaaec10460d8d64a06`.
- Exact DMG `dist/Kuantra-Terminal-1.4.0-aarch64.dmg` SHA-256 is
  `f0f2661ef12f631d5bd8512dfaa1e92f19a170f5673f00b2eb99258c70905a41`; mounted
  DMG smoke PASS report SHA-256 is
  `b6ad5c42ea6c12ced67ac74312edaf0007f14d7852803b4a78bb47eb443a890a`.
- N05 preflight report `dist/n05-macos-distribution-9733874.json` SHA-256 is
  `ac646a668be84a2eb95d658538ca328e2b6deb46ad786135c93118d244a73b18`; it is
  `BLOCKED`/`OWNER_REVIEW_REQUIRED` with read-only mount attach/detach PASS,
  codesign verification PASS, but `AD_HOC`, no hardened runtime, Gatekeeper FAIL
  and no DMG ticket. This is the expected development boundary, not release PASS.
- Platform: macOS arm64; no user data, credential, migration or live execution.
- Actual final Developer ID, Gatekeeper, notarization-ticket, clean-profile and
  commercial H05 evidence remains open.

## Sonraki bağımlılık

N05 code preflight'i green olduktan sonra gerçek final artifact için owner-provided
Developer ID/notary access gerekir. N03 final clean-profile audit'i ve N06
Windows/Linux host evidence'i tamamlanmadan üç-OS production release iddiası
yapılmaz. H05 license/notices ve default-branch alert kararı da ticari dağıtım
öncesine kadar deferred kalır.
