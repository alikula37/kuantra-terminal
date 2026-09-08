<!-- doc-role: archived -->
# N02 — Exact macOS DMG ve WKWebView Smoke

```yaml
work_package: N02
version: 1.0.0
status: Complete
date: 2026-09-08
baseline_commit: 05e826d
implementation_commit: cc0ad94
branch: codex/p1-wp01-evidence-ledger
strategy: KPR-001@current
depends_on: N01
```

## Sonuç

`cc0ad94` ile `scripts/smoke_macos_dmg.py` DMG’yi read-only mount edip mount içindeki
explicit executable üzerinde smoke çalıştırır; release-facing provenance doğrulaması
ve güvenli detach fail-closed uygulanır. N02 focused testleri **3 passed**; sonraki
temiz Mac local CI **608 backend**, **51 frontend**, **480/480 i18n**, production build,
PyInstaller arm64, standalone native smoke ve packaging preflight ile `MERGE READY`
oldu.

## Acceptance criteria

- [x] Mac DMG packaging preflight PASS olur.
- [x] Read-only mounted DMG içinden explicit executable smoke PASS olur.
- [x] WKWebView identity/controller readiness raporda doğrulanır.
- [x] DMG ve mounted executable hash/provenance ilişkisi doğrulanır.
- [x] Detach ve failure cleanup test edilir; mounted path yanlışsa PASS olmaz.
- [x] Mac local CI ve exact DMG smoke kanıtı commit’e yazılır.

## Kanıt

- DMG SHA-256: `5a0010a919ba8a6a296531486918379d5bd58257b86445a76fb14a02089e09e6`
- Mounted executable SHA-256: `2d53c4c2c0b894a43127c34be76c53726fe2130d0dbcc9583282dba776fa9f44`
- Source commit: `cc0ad948d4eee6b5b0a74f4e2101aa048d34473d`
- `provenance_status=COMPLETE`; `check_provenance.py --release`: **PASS**
- `renderer_actual=wkwebview`; `renderer_controller_ready=true`
- `mount_mode=readonly`; `executable_from_mount=true`; `mount_detached=true`; smoke **PASS**
- `hdiutil imageinfo` DMG format/checksum preflight ve `.app` ad-hoc
  `codesign --verify --deep --strict` **PASS**
- Ortam: macOS arm64, Python 3.11.16, Node v20.20.2, npm 10.8.2, uv 0.12.10,
  PyInstaller 6.22.2

## Kalan sınırlar ve sonraki bağımlılık

Bu kanıt Developer ID signing/notarization/ticket, Gatekeeper, ikinci temiz host/profile,
Windows/Linux artifact veya release onayı değildir. Smoke başlangıcında public Binance
WebSocket bağlantısı denenmiştir; explicit `KUANTRA_MARKET_DATA_ENABLED=false`,
degraded health/UI ve network-denied davranışı H03 paketinde ele alınacaktır. Next
bounded package: **H03**.
