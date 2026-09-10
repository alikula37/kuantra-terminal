<!-- doc-role: current-work-package -->
# P1-WP29 — Trusted macOS Pilot Package

```yaml
work_package: P1-WP29
version: 1.0.0
status: InProgress
date: 2026-09-10
baseline_commit: a58935a
implementation_commit: 25ce02a
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
- [x] Güncel source commit `25ce02a`'dan M-series arm64-only pilot paketi üretildi;
      manifest, checksum doğrulaması ve standalone M-series talimatı aynı pakette bulunur.
      Paket `dual_architecture_complete=false`, `intel_artifact_included=false` ve
      `intel_support_claim=false` alanlarını taşır. Paket durumu
      `AD_HOC_TRUSTED_PILOT_ONLY_ARM64`'tır; manifest SHA-256
      `88fe31e700b34f1a990dce427fe49dec1eb1914dde99fe7eb6580cea1362852b`,
      `SHA256SUMS` SHA-256 `2791053bd8ebb11402e0f53083813d66db978e145ad6e5e40b3668ed2be4ffbd`.
- [ ] Gerçek x86_64 native host (hosted runner veya açıkça seçilmiş pilot Intel Mac),
      exact DMG ve smoke/N05 zincirini üretir. GitHub billing/spending-limit durumu
      hosted yolu kapatırsa pilot Intel Mac kontrollü build hostu olabilir.
- [ ] N03 temiz ikinci Mac profil/host install → launch → import/review → close/reopen
      kanıtı tamamlanır; pilot Intel Mac'i bu host olabilir. Bu paket kodla varsayılan
      olarak PASS ilan etmez.
- [ ] Owner, üç pilot için private repository read erişimi ve pilot Release/tag onayını
      verir. Bu çalışma sırasında Release/tag oluşturulmaz veya asset yüklenmez.

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

### Güncel M-series çalıştırması

2026-09-10 tarihinde `25ce02a` source commit'i ile aşağıdaki zincir PASS oldu:

- `uv run --offline --no-project --with-requirements backend/requirements.lock python scripts/run_local_ci.py --expected-architecture arm64 --report dist/p1-wp29-local-ci-arm64-pilot.json --smoke-timeout 90` → **MERGE READY**; backend **815 passed / 2 warnings**, frontend **25/104**, i18n **608/608**, native arm64 build/smoke ve provenance `COMPLETE`. Local-CI report SHA-256: `4624f4f03c88cef8258c1158830556b21102f0e11fbf5e6b8d791485b51f192a`.
- `bash scripts/package_macos.sh --architecture arm64 --output dist/Kuantra-Terminal-1.0.0-arm64.dmg` → **PASS**; `hdiutil verify` exact image için `VALID`. DMG SHA-256: `a8b5204f0bb37ead68566c63656d3f0908eba259c341e953591bf1a713ca1d99`.
- `.venv/bin/python scripts/smoke_macos_dmg.py --dmg dist/Kuantra-Terminal-1.0.0-arm64.dmg --expected-architecture arm64 --report dist/final-smoke-arm64.json` → **PASS**; exact read-only mounted executable, native WKWebView/controller ve detach. Mounted executable SHA-256: `def6b706fd076b6048193380d55638100710b5466e718d30271d578c421b9d38`; report SHA-256: `6bace1057e2b776f9fda1bed4911ef09de59bf3b477e80f0679f657bc452108f`.
- `.venv/bin/python scripts/run_n05_macos_distribution_preflight.py ...` → **BLOCKED/OWNER_REVIEW_REQUIRED** (exit 2), çünkü ad-hoc artifact Developer ID/notarization ticket taşımıyor. Report SHA-256: `c9bf62099d3b326908248539baa286fcdf1c4092899ba7f6e56266b42105d7a7`.
- `.venv/bin/python scripts/prepare_pilot_package.py --architecture arm64 --dist dist --output dist/pilot-package-v1.0.0-arm64` → **PASS**; package type `TRUSTED_MACOS_PILOT_ARM64`, scope `APPLE_SILICON_M_SERIES_ONLY`, status `AD_HOC_TRUSTED_PILOT_ONLY_ARM64`. Paket içindeki beş dosyanın `shasum -a 256 -c SHA256SUMS` doğrulaması **OK**.

Paket yolu: `dist/pilot-package-v1.0.0-arm64/`. Bu çalışma kullanıcı verisi,
credential, Keychain veya migration bundle kullanmadı; GitHub Release/tag/upload ve
üç pilot cihazında gerçek install-lifecycle çalıştırması owner/host kapısı olarak açık
kalır. Sistem `python3.11` ile yapılan ilk smoke denemesi PyInstaller metadata'sı
olmadığı için provenance eksikliğiyle durdu; locked `.venv` Python ile tekrarlandığında
PASS oldu. Bu, paket güvenlik veya DMG bütünlüğü hatası değildir.

çalıştırılır. GitHub Release oluşturma/upload, Apple signing/notarization, pilot daveti
ve clean-host yürütmesi bu work package'ın kod otomasyonuna dahil değildir; owner/host
kapılarıdır.
