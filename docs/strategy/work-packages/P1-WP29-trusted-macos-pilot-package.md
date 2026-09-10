<!-- doc-role: current-work-package -->
# P1-WP29 — Trusted macOS Pilot Package

```yaml
work_package: P1-WP29
version: 1.0.0
status: InProgress
date: 2026-09-10
baseline_commit: a58935a
implementation_commit: this change
branch: main
depends_on: P1-WP28, N03, N05
release_gate: owner-pilot-approval, exact-dual-architecture-evidence
```

## Amaç

Üç kişilik kapalı macOS pilotu için iki native mimari DMG'yi, exact mounted-DMG
smoke/N05 kanıtını, manifest/checksum dosyalarını ve teknik olmayan kullanıcı
talimatını tek fail-closed paket akışına bağlamak. Pilot ekip aynı zamanda kontrollü
doğrulama grubudur: Intel katılımcı, hazır x86_64 DMG üzerinde runtime ve N03
install-lifecycle kanıtı sağlayabilir. Apple Developer ID alınmadığı sürece paket
**trusted pilot only** olarak kalır; production veya commercial support claim'i açmaz.

## Kabul kriterleri

- [x] GitHub private Release'ın yalnızca repository read erişimi olan kullanıcılara
      dağıtım sağlayabildiği; Apple signing/notarization yerine geçmediği resmi kaynaklarla
      kaydedildi.
- [x] `scripts/prepare_pilot_package.py` exact `arm64` ve `x86_64` DMG, final mounted
      WKWebView smoke ve N05 raporlarını aynı source/tree/lock/truth identity ile doğrular.
- [x] Intel kanıtı eksikse package builder exit 2 ile durur; tek arm64 DMG'yi pilot
      paketi gibi üretmez.
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
      ve temiz profil koşulu kanıtlanmadan Intel veya production claim'i açılmaz.
- [x] Mac mini üzerinde `6646332` source commit'i için arm64 exact DMG, `hdiutil verify`
      (`VALID`), read-only mounted WKWebView smoke ve ad-hoc N05 evidence zinciri yeniden
      üretildi; N05 sonucu bilinçli olarak `BLOCKED/OWNER_REVIEW_REQUIRED` kaldı.
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

Focus testleri ve tam suite, gerçek iki mimari kanıtı üretene kadar her kod değişikliğinde
çalıştırılır. Package builder'ın beklenen mevcut sonucu:

```text
python scripts/prepare_pilot_package.py --output dist/pilot-package-v1.0.0
→ BLOCKED (x86_64 native DMG/evidence missing)
```

Bu `BLOCKED`, uygulama hatası değil, henüz üretilemeyen dış kanıtın doğru şekilde
reddedilmesidir. İki zincir hazır olduğunda başarılı çağrı ve ardından:

```text
shasum -a 256 -c dist/pilot-package-v1.0.0/SHA256SUMS
```

çalıştırılır. GitHub Release oluşturma/upload, Apple signing/notarization, pilot daveti
ve clean-host yürütmesi bu work package'ın kod otomasyonuna dahil değildir; owner/host
kapılarıdır.
