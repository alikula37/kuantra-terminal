<!-- doc-role: current-work-package -->
# P1-WP28 — macOS Dual-Architecture Compatibility

```yaml
work_package: P1-WP28
version: 1.0.0
status: InProgress
date: 2026-09-10
baseline_commit: faf8d28
implementation_commit: this change
branch: main
depends_on: P1-WP27, N01, N02, H01, H02, H03, H04, H06
release_gate: N03-final-validation, N05, H05
```

## Amaç

Kuantra v1 macOS artifact’ını macOS 12 Monterey veya üzeri için iki native mimaride
üretmek ve her mimarinin kendi executable, DMG, provenance ve mounted-DMG smoke
kanıtını oluşturmak:

- Apple Silicon: `arm64`
- Intel: `x86_64`

Universal2, cross-build ve arm64 kanıtını Intel kanıtı olarak yeniden kullanma bu
paketin dışındadır. Windows/Linux release claim’i açılmaz.

## Kabul kriterleri

- [ ] PyInstaller build native runner mimarisiyle eşleşir; yanlış runner veya yanlış
      executable mimarisi fail-closed reddedilir.
- [ ] `LSMinimumSystemVersion` `12.0` olur ve release-facing dokümanlarda macOS 12+
      sınırı tek biçimde yazılır.
- [ ] `Kuantra-Terminal-<version>-arm64.dmg` ve
      `Kuantra-Terminal-<version>-x86_64.dmg` ayrı üretilebilir.
- [ ] Packaging ana executable’ı `lipo -archs` ile doğrular; fat/Universal2 artifact
      kabul edilmez.
- [ ] Provenance `architecture` alanı host Python’dan değil executable’dan gelir;
      host mimarisi ayrı alanda tutulur.
- [ ] Her artifact için read-only mounted-DMG smoke, native WKWebView identity,
      executable/DMG SHA-256 ve source commit aynı kanıt zincirindedir.
- [ ] Intel job gerçek x86_64 GitHub macOS runner’ında build, test, package ve exact
      smoke çalıştırır. Fiziksel Intel pilotu ek güven kanıtıdır; bu paket için zorunlu
      değildir.
- [ ] Manifest ve Phase 0 audit iki macOS architecture raporunu eşleştirir; tek
      mimari eksikse release-facing audit geçmez.
- [ ] Gerçek kullanıcı data directory’si, credential, migration, live broker veya
      Apple signing/notarization işlemi kullanılmaz.

## Uygulanan sınır

Bu paket yalnızca native macOS compatibility ve evidence plumbing değiştirir. Ürün
kimliği Execution Intelligence & Trade Forensics Workstation olarak korunur; AI order
authority, live execution, yeni connector, funding/transfer schema, tam hesap PnL,
Windows/Linux ve ticari lisans/notices kararı eklenmez.

## Doğrulama

Önce architecture/provenance/packaging/workflow red testleri çalıştırılır. Sonra:

1. Mac mini üzerinde arm64 locked local CI ve focused regression;
2. `macos-15-intel` native runner üzerinde x86_64 locked dependency, test, build,
   DMG ve mounted smoke;
3. iki raporun truth matrix, manifest ve Phase 0 audit ile doğrulanması;
4. docs/link registry ve tam backend/frontend gate.

CI veya dependency kanıtı üretilemezse Intel durumu `HOST_REQUIRED/BLOCKED` kalır;
destek matrisi sessizce PASS yapılmaz.
