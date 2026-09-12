<!-- doc-role: reference -->
# P1-WP28 — macOS Dual-Architecture Compatibility

```yaml
work_package: P1-WP28
version: 1.0.0
status: InProgress
date: 2026-09-10
baseline_commit: faf8d28
implementation_commit: dd58142
branch: codex/p1-wp01-evidence-ledger
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
      executable mimarisi fail-closed reddedilir. Guard ve iki native runner kanıtı
      `dd58142` kaynaklı GitHub Actions run `34664574672` üzerinde green.
- [x] `LSMinimumSystemVersion` `12.0` olur ve release-facing dokümanlarda macOS 12+
      sınırı tek biçimde yazılır.
- [x] `Kuantra-Terminal-<version>-arm64.dmg` ve
      `Kuantra-Terminal-<version>-x86_64.dmg` ayrı native runner'larda üretilebilir;
      iki job da build, package ve artifact upload adımlarını PASS tamamladı.
- [x] Packaging ana executable’ı `lipo -archs` ile doğrular; fat/Universal2 artifact
      kabul edilmez.
- [x] Provenance `architecture` alanı host Python’dan değil executable’dan gelir;
      host mimarisi ayrı alanda tutulur. Unit test ve temiz arm64 smoke bunu doğrular.
- [x] Her artifact için read-only mounted-DMG smoke, native WKWebView identity,
      executable/DMG SHA-256 ve source commit aynı kanıt zincirindedir; iki mimarinin
      `final-smoke-<architecture>.json` raporu `COMPLETE` provenance ve `PASS` smoke
      kaydı taşır.
- [x] Native x86_64 build hostu `macos-15-intel` üzerinde build, test, package ve exact
      smoke çalıştırır. Her iki job source commit, lock hash, temiz tree, executable/DMG
      hash ve native host kimliğini raporlar; Rosetta veya arm64 artifact Intel kanıtı
      olarak kullanılmamıştır. Pilot Intel Mac'i ayrıca runtime/N03 kanıtı sağlayabilir.
- [x] Trusted pilot manifesti iki macOS architecture raporunu aynı source/tree/lock/truth
      identity ile eşleştirir; `Prepare Trusted Pilot Package` ve `SHA256SUMS` doğrulaması
      run `34664574672` üzerinde PASS oldu.
- [ ] Phase 0 release-exit audit'i ve final distribution gate'i N05 ad-hoc signing/
      notarization kanıtı olmadığı için çalıştırılıp PASS ilan edilmedi; bu açık kapı
      P1-WP28 teknik artifact kanıtından ayrı tutulur.
- [x] Gerçek kullanıcı data directory’si, credential, migration, live broker veya
      Apple signing/notarization işlemi kullanılmaz.

## Uygulanan sınır

2026-09-11 correction: the shell `sysctl -in sysctl.proc_translated` guard incorrectly
rejected an absent key on native Intel. [Apple's documented probe](https://developer.apple.com/documentation/apple-silicon/about-the-rosetta-translation-environment)
treats `sysctlbyname` failure with `ENOENT` as native, while other errors are unknown.
The shared Python helper now uses the native API and errno; packaging and hosted
workflow call that helper. Tests cover native, translated, ENOENT, permission/I/O
errors, malformed values and unavailable API; focused architecture/packaging/workflow/
release regression is **43 passed** on macOS arm64. The actual host guard accepts
arm64 and rejects x86_64 on the Mac mini. Native Intel artifact evidence is now closed
by the hosted native `macos-15-intel` job; Intel pilot runtime/N03 evidence remains an
optional later host-validation record.

Bu paket yalnızca native macOS compatibility ve evidence plumbing değiştirir. Ürün
kimliği Execution Intelligence & Trade Forensics Workstation olarak korunur; AI order
authority, live execution, yeni connector, funding/transfer schema, tam hesap PnL,
Windows/Linux ve ticari lisans/notices kararı eklenmez.

## Doğrulama

Önce architecture/provenance/packaging/workflow red testleri çalıştırılır. Sonra:

1. Mac mini üzerinde arm64 locked local CI ve focused regression (**PASS**, `bb6ce7c`);
2. Native Intel host üzerinde x86_64 locked dependency, test, build, DMG ve mounted
   smoke (**PASS**, GitHub Actions run `34664574672`, job `103473798705`);
3. iki raporun truth matrix ve trusted pilot manifest/checksum ile doğrulanması
   (**PASS**); Phase 0 release-exit audit'i N05 ad-hoc sınırı nedeniyle ayrı açık kapıdır;
4. docs/link registry ve tam backend/frontend gate (**PASS** in the same dual run).

Release-workflow app and final-DMG smoke steps explicitly set
`KUANTRA_MARKET_DATA_ENABLED=false`; this is a test boundary, not a change to the
runtime default (`true`).

Native Intel build veya dependency kanıtı üretilemezse Intel durumu `HOST_REQUIRED/BLOCKED`
kalır; bu artık mevcut aday için geçerli değildir. Hazır x86_64 artifact sonrasında pilot
Intel Mac runtime/N03 kanıtı ayrıca kaydedilebilir. Güncel dual native evidence:

- source commit: `dd581425c2c298664512f0434fa93a726a9cacb5`;
- tracked tree SHA-256: `5c11b9b0569885db4c15319847350e00faa351e2ca4cbdaf45cc881a7ad9c24c`;
- truth-matrix SHA-256: `8c647721dc2349cc8fd99d046bf14738121ac4f9a0b7c8b87cdb9f1ccfe681ab`;
- backend/frontend lock SHA-256: `6291588602869af34e2a4db5d7244a627f4e139cbbd4b034b7cc07d890812399` /
  `396c757d5733e9618aa71f665aa3f23f5d53fcdaa8d9ff67c11d172464fcc6bc`;
- arm64 DMG/executable: `f8a4d4189ca6786f9ddb1e6d47f765ac6a3b4b11ffe8bc71a40bae8975189463` /
  `31d709963c2cb4d1ad1bea72f5e2b020423ed9b9ce151eb292f5a94ad0def2ca`;
- x86_64 DMG/executable: `786370ff03270203fc95868e7c7faa17e214059d1a2625538609d48d36347f4c` /
  `4a5991ad1cd8b98dce79aab69581542b970043d8a12894050af83c14ce419cfc`;
- smoke report SHA-256 arm64/x86_64: `c75ace0918bf48092d306c90b1ff06abc19d69c7cb06bb597e2a4dc1381d0685` /
  `12ac288398f0efcca678b7e295d498794ed9e908060a96f36b192cc6480f7c97`;
- N05 report SHA-256 arm64/x86_64: `67a97c45a7d6bacf5cdf3c908e50b2e0b32044f85e909988f2cfd958d590aa94` /
  `f923ed7ada2632691c12d73ce4044976980d7f939b4df967393a776dcaa87f9b`;
- both native jobs used Python `3.11.9`, Node `20.20.2`, PyInstaller `6.22.2`, native
  `wkwebview`, read-only mounted DMG smoke and `hdiutil verify: VALID`; N05 remains
  `BLOCKED/OWNER_REVIEW_REQUIRED` because the artifacts are ad-hoc and not notarized.
