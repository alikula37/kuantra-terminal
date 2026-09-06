# Phase 0 Exit Audit — Pending Final Artifact Evidence

```yaml
document_id: KPS-P0-EXIT
version: 1.0.0
status: Active
decision: STATIC_GATES_PASS_REPORTS_PENDING
product_version: 1.4.0
canonical_contract: KTR-001@1.0.0
```

## Karar

Statik truth/safety kapıları geçiyor; Phase 0 henüz insan release approval’ı ile kapanmış
sayılmaz. `READY_FOR_HUMAN_RELEASE_APPROVAL` verdict’i yalnız üç OS’tan final artifact smoke
raporları aynı publish audit job’ında doğrulandığında üretilebilir. Bu kayıt canlı execution,
AI authority veya “production-ready” iddiası vermez.

## Zorunlu kanıt

- P0-WP00–P0-WP09: `Verified` ve commit referansları `docs/strategy/PHASE-0-STATUS.md` içinde.
- `KTR-001` matrix, app/package version ve exact release tag eşleşmesi.
- Windows NSIS installer, macOS DMG ve Linux AppImage içinden smoke; her raporda:
  `smoke_schema_version: 2`, beş required check, product version, platform/arch,
  executable SHA-256, artifact SHA-256 ve matrix digest.
- Publish audit sonucu ve push/PR CI run/job kimlikleri.
- Backend test suite kullanıcı journal’ından ayrıdır: pytest kendi ephemeral data directory’sini
  kullanır ve singleton risk konfigürasyonunu test sonunda geri yükler (`350 passed, 1 skipped`).

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

Bu komut yalnız static gates için `STATIC_GATES_PASS_REPORTS_PENDING` döner. Final artifact
raporları olmadan exit verdict’i yükseltilemez.
