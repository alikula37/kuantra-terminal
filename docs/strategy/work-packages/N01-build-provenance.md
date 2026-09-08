<!-- doc-role: current-work-package -->
# N01 — Exact Build Provenance

```yaml
work_package: N01
version: 1.0.0
status: InProgress
date: 2026-09-08
baseline_commit: 056b1ca
branch: codex/p1-wp01-evidence-ledger
strategy: KPR-001@current
depends_on: P1-WP21, B4 audit
```

## Amaç

Smoke ve local-CI raporlarında checkout, tracked source tree, lock dosyaları,
toolchain ve executable/artifact hash’lerini aynı provenance sözleşmesine bağlamak.
`GITHUB_SHA` yoksa checkout commit’i `git rev-parse HEAD` ile deterministik alınır;
local developer metadata’sı release artifact provenance olarak gösterilmez.

## Sözleşme

- source commit SHA ve checkout karşılaştırması raporlanır;
- tracked source tree durumu ve digest’i raporlanır; untracked kullanıcı dizinleri
  source tree’yi sessizce release-clean göstermez;
- backend/frontend lock hash’leri ve Python, Node, npm, uv, PyInstaller/toolchain
  bilgileri raporlanır;
- OS/architecture, executable SHA-256 ve artifact SHA-256 raporlanır;
- provenance alanlarından biri eksikse release-facing validator fail-closed olur;
- local developer build’i ile release artifact’i arasında `provenance_status` ayrımı
  korunur; bu paket signing/notarization iddiası açmaz.

## Acceptance criteria

- [ ] Smoke report zorunlu provenance alanlarını deterministic biçimde üretir.
- [ ] Local-CI report aynı provenance kaydını ve validator sonucunu taşır.
- [ ] Checkout fallback, dirty tracked tree, eksik lock/toolchain ve hash mismatch
  negative testleri fail-closed geçer.
- [ ] Release-facing validator eksik commit/tree/artifact bilgisini PASS saymaz.
- [ ] Existing smoke, packaging ve Phase-0 truth regression’ları geçer.
- [ ] Mac local CI, executable hash’i ve açık release/signing sınırı kaydedilir.

## Kapsam dışı

DMG içi mounted executable smoke (N02), WKWebView identity/degraded runtime (H03),
signing/notarization, Windows/Linux host kanıtı, live execution, credentials, user
data migration, funding/transfer schema ve release/tag işlemleri.

