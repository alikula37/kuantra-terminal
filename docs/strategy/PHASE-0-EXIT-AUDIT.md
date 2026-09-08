<!-- doc-role: historical-reference -->
> Historical Phase 0 evidence, retained at this path for audit tooling. Not current release status.
> See [current status](STATUS.md).

# Phase 0 Exit Audit — Final Artifact Evidence Recorded

```yaml
document_id: KPS-P0-EXIT
version: 1.0.0
status: Verified
decision: READY_FOR_HUMAN_RELEASE_APPROVAL
product_version: 1.4.0
canonical_contract: KTR-001@1.0.0
candidate_run: 34035766242
candidate_commit: df46f27afb91d80b39425a6140f8302aabb33886
release_publication: NOT_RUN_PUBLISH_FALSE
```

## Karar

Statik truth/safety kapıları ve üç OS final artifact smoke kanıtı geçti. Publish audit job’ı
`READY_FOR_HUMAN_RELEASE_APPROVAL` verdict’ini üretti. Bu kayıt teknik Phase 0 çıkışını
doğrular; release yayınlama hâlâ ayrı bir insan onayıdır. Aday koşusu `publish=false` ile
çalıştırıldığı için yeni tag/release oluşturulmadı ve bu kayıt canlı execution, AI authority
veya “production-ready” iddiası vermez.

## Zorunlu kanıt

- P0-WP00–P0-WP09: `Verified` ve commit referansları `docs/strategy/PHASE-0-STATUS.md` içinde.
- `KTR-001` matrix, app/package version ve exact release tag eşleşmesi.
- Windows NSIS installer, macOS DMG ve Linux AppImage içinden smoke; her raporda:
  `smoke_schema_version: 2`, beş required check, product version, platform/arch,
  executable SHA-256, artifact SHA-256 ve matrix digest.
- Publish audit sonucu ve push/PR CI run/job kimlikleri.
- Backend test suite kullanıcı journal’ından ayrıdır: pytest kendi ephemeral data directory’sini
  kullanır ve singleton risk konfigürasyonunu test sonunda geri yükler (`350 passed, 1 skipped`).

## Kanıt kaydı

- Release candidate workflow: [run 34035766242](https://github.com/alikula37/kuantra-terminal/actions/runs/34035766242)
- macOS package/final smoke job: `101493427867` — success
- Ubuntu package/final smoke job: `101493427995` — success
- Windows package/final smoke job: `101493428000` — success
- Publish audit job: `101495589738` — success; `Audit Phase 0 exit evidence` geçti
- Final smoke artifact’ları: `final-smoke-windows.json`, `final-smoke-macos.json`,
  `final-smoke-linux.json`; üç raporun `ok: true`, `smoke_schema_version: 2`, build commit’i
  `df46f27` ve KTR-001 canonical matrix digest’i aynıdır.
- Kanıt artifact’ı: `phase0-exit-evidence`; audit verdict’i
  `READY_FOR_HUMAN_RELEASE_APPROVAL`, `external_execution_enabled: false`.
- Normal push CI: [run 34035432817](https://github.com/alikula37/kuantra-terminal/actions/runs/34035432817) — üç OS success.

## Onay ayrımı

`publish=false` aday koşusu teknik çıkış kapılarını doğrular. Gerçek GitHub Release/tag
yayımlamak için ayrıca `publish=true` workflow dispatch ve ürün sahibinin açık release onayı
gerekir. Bu karar Phase 1 Evidence Ledger geliştirmesini veya güvenli local-first kullanımı
otomatik olarak canlı broker execution yetkisine dönüştürmez.

## Bu fazda hâlâ kapalı olanlar

Canlı broker/venue execution, FIX/DMA, HFT latency SLA, AI/model execution authority,
DEX/DeFAI, biometrics, remote plugin download/hot-mount ve canonical tick/data-plane migration
Phase 0 exit ile açılmaz. Bunlar ayrı acceptance gates ve ayrı work package ister.

## Residual risk kayıtları

- Windows/Linux PyQt6-WebEngine paketleme maliyeti devam eder; WebView2 geçişi yapılmadı.
- macOS imzası ad-hoc; notarization yoktur.
- Linux AppImageTool indirmesi henüz pinned digest ile doğrulanmamaktadır.
- Bundled experimental plugin tree runtime’da fail-closed olsa da signed/sandboxed plugin izolasyonu
  sonraki faza ertelenmiştir.

## Audit command

```text
python scripts/audit_phase0_exit.py --json
```

Bu komut yerelde rapor dosyaları yoksa `STATIC_GATES_PASS_REPORTS_PENDING` döner. CI publish
audit’inin kanıt artifact’ı üç final raporunu doğruladı ve yukarıdaki verdict’i üretti.
