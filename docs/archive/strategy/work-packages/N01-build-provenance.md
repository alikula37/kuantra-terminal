<!-- doc-role: archived -->
# N01 — Exact Build Provenance

```yaml
work_package: N01
version: 1.0.0
status: Complete
date: 2026-09-08
baseline_commit: 056b1ca
implementation_commit: 05e826d
branch: codex/p1-wp01-evidence-ledger
strategy: KPR-001@current
depends_on: P1-WP21, B4 audit
```

## Sonuç

Smoke ve local-CI raporları artık checkout/source tree, lock dosyaları, toolchain,
executable ve artifact kimliğini aynı provenance nesnesinde taşır. `GITHUB_SHA`
yoksa checkout `HEAD` SHA’sı alınır; tracked tree dirty ise local rapor
`DEVELOPER_DIRTY` olur ve release-facing validator bunu PASS saymaz. Local developer
metadata’sı artifact provenance ile karıştırılmaz.

## Acceptance criteria

- [x] Smoke report zorunlu provenance alanlarını deterministic biçimde üretir.
- [x] Local-CI report aynı provenance kaydını ve validator sonucunu taşır.
- [x] Checkout fallback, dirty tracked tree, eksik lock/toolchain ve hash mismatch negative testleri fail-closed geçer.
- [x] Release-facing validator eksik commit/tree/artifact bilgisini PASS saymaz.
- [x] Existing smoke, packaging ve Phase-0 truth regression’ları geçer.
- [x] Mac local CI, executable hash’i ve açık release/signing sınırı kaydedilir.

## Değişen dosyalar

- `scripts/build_provenance.py`
- `scripts/check_provenance.py`
- `scripts/smoke_desktop.py`
- `scripts/run_local_ci.py`
- `scripts/audit_phase0_exit.py`
- `.github/workflows/release.yml`
- `backend/tests/test_n01_build_provenance.py`
- `backend/tests/test_p0_wp10_phase0_exit.py`
- `backend/tests/test_packaging_spec.py`

## Kanıt

- N01 focused/workflow tests: **17 passed**.
- Full backend/local CI: **604 passed, 2 warnings**; frontend **51 passed**; i18n **480/480**; production build; PyInstaller arm64 build; native `wkwebview` smoke; packaging preflight all PASS.
- Local CI `merge_ready=true`, `provenance_status=COMPLETE`, release-facing `check_provenance.py --release` PASS.
- Source commit: `05e826dc3357665d688340ca5883c3795fbc185d`.
- Tracked source tree SHA-256: `0618895ebef86702578cb7a7565d9d61e85b08087c2acf0808b9d8e84c23e666`.
- Backend lock SHA-256: `6291588602869af34e2a4db5d7244a627f4e139cbbd4b034b7cc07d890812399`.
- Frontend lock SHA-256: `b392a59d09ade73564ce082b1a5bc1236618ebeee11703a992980cfd1812882c`.
- Executable SHA-256: `e73116e69faa61f2d13530cd7da26ef2747cd4dd7274b932922ea0d1209bf303`.
- `.app` artifact SHA-256: `99ef50a2ba7aa96610dc1564eca6447c1933d6e6142b50b3a599eb0db93058f9`.
- Host: macOS arm64, Python 3.11.16, Node v20.20.2, npm 10.8.2, uv 0.12.10, PyInstaller 6.22.2.

## Kalan sınırlar ve sonraki bağımlılık

N01 signing/notarization veya DMG-mounted executable kanıtı açmaz. N02 exact
mounted-DMG/WKWebView smoke, H03 degraded/offline boundary, Windows/Linux host
kanıtı, live execution, credentials, user migration, funding/transfer schema ve
release/tag işlemleri kapsam dışıdır. Next bounded package: **N02**.

