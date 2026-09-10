<!-- doc-role: current-work-package -->
# P1-WP28 — macOS Dual-Architecture Compatibility

```yaml
work_package: P1-WP28
version: 1.0.0
status: InProgress
date: 2026-09-10
baseline_commit: faf8d28
implementation_commit: bb6ce7c
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

- [x] PyInstaller build native runner mimarisiyle eşleşir; yanlış runner veya yanlış
      executable mimarisi fail-closed reddedilir. Guard ve arm64 Mac mini kanıtı
      `bb6ce7c` üzerinde green; dual-runner kapanışı Intel CI kanıtına bağlıdır.
- [x] `LSMinimumSystemVersion` `12.0` olur ve release-facing dokümanlarda macOS 12+
      sınırı tek biçimde yazılır.
- [ ] `Kuantra-Terminal-<version>-arm64.dmg` ve
      `Kuantra-Terminal-<version>-x86_64.dmg` ayrı üretilebilir; arm64 üretim kanıtı
      PASS, x86_64 native runner üretimi GitHub billing blocker nedeniyle bekliyor.
- [x] Packaging ana executable’ı `lipo -archs` ile doğrular; fat/Universal2 artifact
      kabul edilmez.
- [x] Provenance `architecture` alanı host Python’dan değil executable’dan gelir;
      host mimarisi ayrı alanda tutulur. Unit test ve temiz arm64 smoke bunu doğrular.
- [ ] Her artifact için read-only mounted-DMG smoke, native WKWebView identity,
      executable/DMG SHA-256 ve source commit aynı kanıt zincirindedir; arm64 PASS,
      x86_64 evidence bekliyor.
- [ ] Intel job gerçek x86_64 GitHub macOS runner’ında build, test, package ve exact
      smoke çalıştırır. Fiziksel Intel pilotu ek güven kanıtıdır; bu paket için zorunlu
      değildir.
- [ ] Manifest ve Phase 0 audit iki macOS architecture raporunu eşleştirir; tek
      mimari eksikse release-facing audit geçmez. Kod/test sözleşmesi hazır, gerçek
      x86_64 raporu olmadan kriter kapanmaz.
- [x] Gerçek kullanıcı data directory’si, credential, migration, live broker veya
      Apple signing/notarization işlemi kullanılmaz.

## Uygulanan sınır

Bu paket yalnızca native macOS compatibility ve evidence plumbing değiştirir. Ürün
kimliği Execution Intelligence & Trade Forensics Workstation olarak korunur; AI order
authority, live execution, yeni connector, funding/transfer schema, tam hesap PnL,
Windows/Linux ve ticari lisans/notices kararı eklenmez.

## Doğrulama

Önce architecture/provenance/packaging/workflow red testleri çalıştırılır. Sonra:

1. Mac mini üzerinde arm64 locked local CI ve focused regression (**PASS**, `bb6ce7c`);
2. `macos-15-intel` native runner üzerinde x86_64 locked dependency, test, build,
   DMG ve mounted smoke (**BLOCKED before job startup**: GitHub account billing/
   spending-limit condition);
3. iki raporun truth matrix, manifest ve Phase 0 audit ile doğrulanması;
4. docs/link registry ve tam backend/frontend gate.

Release-workflow app and final-DMG smoke steps explicitly set
`KUANTRA_MARKET_DATA_ENABLED=false`; this is a test boundary, not a change to the
runtime default (`true`).

CI veya dependency kanıtı üretilemezse Intel durumu `HOST_REQUIRED/BLOCKED` kalır;
destek matrisi sessizce PASS yapılmaz. Current arm64 exact evidence: executable
`cfb75d0a9b1aeb00bce657bb0b393284453ed8975856a5b50231312150c47924`, DMG
`4801d3c14fc3ffd4ef07af88a3b36c7eb1ef03032cdd6684227c500bbe8a0eb2`, mounted smoke
report `5ae96513963999df5284fb5b1d56d12fcaa2eda0d938e4942b287ac20e7d30eb` and
N05 report `9e92b104b27fcd30c31547a0b3c5ae9fdb30c5d4d89e159ae7cf55e9d315409e`; all
are bound to source commit `bb6ce7c` and truth-matrix digest
`740b33db5e73b3c9cd7d8fa078282e6d03d8f0c0cf690f0ac1cc2320a617bcf6`.
