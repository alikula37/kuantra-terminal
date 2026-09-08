<!-- doc-role: current-work-package -->
# H04 — Threat Model & Trust Boundaries

```yaml
work_package: H04
version: 1.0.0
status: Ready
date: 2026-09-08
baseline_commit: ed689a0
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

- [ ] Her trust boundary için en az bir kötüye kullanım testi red→green geçer.
- [ ] Archive/import/WebView/gateway hataları fail-closed ve kullanıcıya açıklanabilir
  durumla döner; başarı veya complete sonucu uydurulmaz.
- [ ] Secret/path leakage ve redaction negatif testleri PASS olur.
- [ ] Full backend/frontend suite ve Mac local CI aynı source commit üzerinde PASS.
- [ ] H04 kapsamı dışında kalan licensing/SBOM/privacy/performance işleri H05–H07'ye
  açık bağımlılık olarak yazılır; sessizce bu pakete alınmaz.

## Kesinlikle kapsam dışı

H05 dependency/SBOM/license, H06 privacy/keychain lifecycle, H07 performance,
N03–N06 platform/distribution proof, pilot/release, new connector, live execution,
AI order authority ve full-account PnL/tax accounting.

## Başlangıç kararı

H02 `169c446` ile schema upgrade/restore boundary'sini kapattı. H04 başlamadan
untrusted-input veya WebView/gateway production-ready iddiası yoktur.
