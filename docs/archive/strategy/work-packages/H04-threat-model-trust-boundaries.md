<!-- doc-role: archived -->
<!-- Historical evidence: this file is not a current implementation instruction. -->
# H04 — Threat Model & Trust Boundaries

```yaml
work_package: H04
version: 1.1.0
status: Complete
date: 2026-09-08
baseline_commit: ed689a0
completed_commit: 1cf486e
evidence_commit: 1cf486e
branch: codex/p1-wp01-evidence-ledger
strategy: KPR-001@current
depends_on: H02, H03, P1-WP22, P1-WP24, P1-WP26
```

## Amaç

Kuantra'nın local-first Execution Intelligence & Trade Forensics Workstation
sınırındaki untrusted input ve native/web trust boundary'lerini misuse testleriyle
kanıtlamak. Bu paket yeni connector, AI authority, live order, funding/transfer
schema veya genel backup capability'si eklemez.

## Davranış sözleşmesi

- CSV/JSON/HTML içeriği veri olarak işlenir; formula injection, HTML/script ve
  malformed/oversized input güvenli hata verir.
- Archive extraction absolute path, `..`, symlink, duplicate entry ve bounded
  resource limit ihlalinde fail-closed kalır; staging dışına yazmaz.
- WebView bridge yalnız allowlisted native action ve doğrulanmış payload kabul eder;
  external navigation uygulama içi güven sınırını aşamaz.
- Local gateway auth/origin boundary'si explicit test edilir; CORS veya bridge
  fallback'i fail-open olmaz.
- Redaction/export/support yüzeyleri secret, credential, token veya local path
  sızdırmaz. Unknown/unavailable sonucu production capability gibi gösterilmez.

## Red test kapsamı

- CSV formula-like cells, invalid encoding, oversized field/file, duplicate import
  ve cancel/retry sırasında DB mutation olmaması.
- JSON/HTML escaping, malformed nesting/size limit, unsafe external URL ve render
  sonucunun executable olarak yorumlanmaması.
- ZIP/TAR archive traversal, absolute path, symlink, duplicate, compression/resource
  limit ve interrupted extraction cleanup.
- WebView message schema, action allowlist, origin/source validation, malformed
  bridge payload ve gateway auth/origin negative cases.
- Redacted evidence/export/support output'ta credential, token, secret ve sensitive
  local path absence.

## Uygulama sınırı

İlk adım mevcut import/export, archive, WebView bridge ve gateway kod yollarının
trust-boundary audit'idir. Her teknik değişiklik red test → bounded implementation →
focused test → full suite/local CI → docs → ayrı commit/push sırasını izler.
Testler yalnız synthetic temporary fixture kullanır; gerçek kullanıcı verisi,
credential, migration apply ve live broker işlemi yasaktır.

## Acceptance criteria

- [x] Her trust boundary için en az bir kötüye kullanım testi red→green geçer.
- [x] Archive/import/WebView/gateway hataları fail-closed ve kullanıcıya açıklanabilir
  durumla döner; başarı veya complete sonucu uydurulmaz.
- [x] Secret/path leakage ve redaction negatif testleri PASS olur.
- [x] Full backend/frontend suite ve Mac local CI aynı source commit üzerinde PASS.
- [x] H04 kapsamı dışında kalan licensing/SBOM/privacy/performance işleri H05–H07'ye
  açık bağımlılık olarak yazılır; sessizce bu pakete alınmaz.

## Kesinlikle kapsam dışı

H05 dependency/SBOM/license, H06 privacy/keychain lifecycle, H07 performance,
N03–N06 platform/distribution proof, pilot/release, new connector, live execution,
AI order authority ve full-account PnL/tax accounting.

## Uygulama ve kanıt

- CSV, broker JSON ve webhook sınırları için byte/row/field/body limitleri, strict
  UTF-8 ve malformed payload reddi eklendi. Formula-like hücreler veri olarak kalır;
  parser veya webhook hatası 400/413 ile fail-closed döner.
- Archive verifier, member count, per-member size, toplam uncompressed size, absolute/
  traversal/symlink/duplicate sınırlarını payload okunmadan kontrol eder.
- WebView bridge yalnız allowlisted internal route/action, bounded body/file/field,
  safe filename/header/method ve doğrulanmış payload kabul eder. External URL yalnız
  geçerli credential-free `http`/`https` host ile açılır; popout/download/copy yolları
  da bounded'dir.
- CORS ve TV sync gateway origin allowlist'i explicit hale getirildi; missing veya
  external origin ile handshake fail-closed kapanır. Bu, gerçek kimlik doğrulaması
  veya remote exposure iddiası değildir; local boundary kontrolüdür.
- Evidence export secret-like değerleri ve yerel path sızıntısını reddeder; log
  redaction POSIX/Windows path, token ve credential kalıplarını maskeler.
- Red→green H04 focused/boundary suite: **60 passed, 2 warnings**. Full backend:
  **669 passed, 2 warnings**. Frontend: **17 files / 67 tests passed**.
- Mac local CI on `1cf486eefc3bf513303cb5f55902c411a21aa544`: **MERGE READY**;
  report SHA-256 `a59b1069b19d8be8986a03397cbdf13562847292f81bc46067247f0f36fb416a`,
  smoke report SHA-256 `ecaae6e90e5818e3872cf751cc88ec06f08def90e9450b199cc3a35d11355f5c`,
  tracked source tree SHA-256
  `c91d317e8c5e3b0bce726b269b753f74ab9d0a03edb03dacb8ba986d670af985`;
  Python `3.11.16`, Node `20.20.2`, npm `10.8.2`, uv `0.12.10`, PyInstaller
  `6.22.2`, macOS arm64. Local executable SHA-256
  `0bfd17e160ea693cb8bd34f9ab7f31e7d5bef04df2c37659c3dab0a641718447`;
  `.app` SHA-256 `999741169af175d2ea85095d2ac31b342daba7b19d10672d528e182ebcfe9cd7`.
  Provenance status **COMPLETE**; tracked source tree clean. `uv --offline` is
  dependency-preparation evidence only; runtime smoke is not offline proof.

## Sonraki bağımlılık

**H05 — Supply Chain, SBOM, License & Secret Boundary** aktif sıraya alınmıştır.
H06 privacy/keychain lifecycle ve H07 performance H05 sonrasında kalır. Developer
ID/notarization, Windows/Linux host evidence, pilot/release-owner kararları ayrı
host/owner kapılarıdır. Funding/transfer schema, live execution, AI order authority,
credential ve gerçek kullanıcı verisi bu pakette de kapsam dışıdır.

## Başlangıç kararı

H02 `169c446` ile schema upgrade/restore boundary'sini kapattı. H04 `1cf486e` ile
yalnız bounded synthetic misuse/negative test ve temiz Mac local-CI kanıtı üzerinden
trust-boundary kapsamını kapattı. Bu kanıt production release, signing/notarization,
remote exposure veya gerçek kullanıcı güvenliği iddiası açmaz.
