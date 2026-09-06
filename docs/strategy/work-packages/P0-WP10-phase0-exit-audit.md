# P0-WP10 — Three-OS Packaging, Final Artifact Smoke ve Phase 0 Exit Audit

```yaml
document_id: P0-WP10
version: 1.0.0
status: Verified
date: 2026-09-06
baseline: df46f27
strategy: KPS-001@1.0.0
adr: ADR-0001, ADR-0003
candidate_run: 34035766242
release_publication: NOT_RUN_PUBLISH_FALSE
```

## Karar

P0-WP10 yeni ürün kabiliyeti açmaz. Phase 0’ın “truth/safety release” sınırını, üç OS CI
kanıtından dağıtılabilir installer/DMG/AppImage smoke kanıtına taşır. Final artifact smoke ve
immutable audit raporu olmadan ürün `production-ready` veya canlı işlem ürünü olarak etiketlenmez.

## Problem ve risk

Mevcut CI PyInstaller’ın unpacked çıktısını smoke ediyor; ancak NSIS installer, DMG ve AppImage
üretildikten sonra dağıtılan artefaktın içinden uygulamayı çalıştırmıyordu. Ayrıca smoke JSON’u
ürün versiyonu, platform/arch, executable/artifact hash’i ve KTR-001 provenance’ını taşımıyordu.
Bu iki boşluk, “build geçti” ile “kullanıcıya dağıtılan artifact çalıştı” arasındaki farkı görünmez
kılıyordu.

## Teslimatlar

- `scripts/smoke_desktop.py`: schema v2 report; product version, platform/arch, executable ve
  distributed artifact SHA-256, commit, timestamp ve KTR-001 matrix digest.
- `scripts/audit_phase0_exit.py`: WP00–WP09 (WP06A/WP06B ayrımıyla) Verified, truth/workflow/packaging static gates ve
  üç final artifact smoke report’unu fail-closed doğrulayan stdlib-only audit.
- `backend/tests/conftest.py`: pytest başlamadan önce ephemeral `KUANTRA_DATA_DIR` ve singleton risk
  state restore; testler gerçek kullanıcı journal’ına yazamaz ve suite order bağımlılığı azalır.
- Release workflow’da Package adımından sonra OS’a özgü final artifact smoke:
  NSIS silent install, mounted DMG app binary ve extracted AppImage.
- Publish job’da üç report birleştirilerek `READY_FOR_HUMAN_RELEASE_APPROVAL` verdict’i üretilir;
  bu verdict otomatik canlı işlem veya production authority vermez.
- `docs/strategy/PHASE-0-EXIT-AUDIT.md`: exact commit, matrix digest, CI run/job IDs, artifact
  hash’leri, residual riskler ve insan onayı için immutable kayıt.

## Kapsam dışı ve açık ertelemeler

- Canlı broker execution, broker certification, FIX/DMA, HFT SLA ve reconciliation.
- Rust/Tokio data plane, canonical tick ledger, Arrow/Parquet migration ve WebView2.
- AI inference/execution authority, DEX/DeFAI, biometrics ve signed/sandboxed plugin ecosystem.
- macOS notarization ve AppImageTool supply-chain pinning; release audit bunları açık residual
  risk olarak gösterecek, “verified” diye gizlemeyecek.

## Acceptance criteria

- [x] Üç OS release-candidate package job’ı final installer/DMG/AppImage’ı üretir.
- [x] Her final artifact kendi içinden smoke ile beş required check’i ve version/hash provenance’ını
  başarıyla raporlar.
- [x] Publish audit job’ı üç farklı platform report’unu ve aynı product/matrix version’ını doğrular;
  eksik, false veya mismatch report non-zero döner.
- [x] Current release notes + MANIFEST yalnız truth-gated publish adımından çıkar.
- [x] Residual riskler ve release-owner approval ayrımı `P0-EXIT-AUDIT.md` içinde kayıtlıdır.
- [x] Push/PR CI, backend/frontend/build/unpacked smoke regression’larını yeşil tutar.
- [x] Yerel full backend suite izole veri diziniyle `350 passed, 1 skipped`.

## Final artifact kanıtı

Release candidate [34035766242](https://github.com/alikula37/kuantra-terminal/actions/runs/34035766242)
`df46f27afb91d80b39425a6140f8302aabb33886` commit’i için üç OS package/final smoke job’ını
başarıyla tamamladı. Publish audit job `101495589738` `READY_FOR_HUMAN_RELEASE_APPROVAL`
verdict’i verdi. Windows `101493428000`, Ubuntu `101493427995` ve macOS `101493427867`
raporlarında aynı KTR-001 canonical digest’i ve `ok: true` bulundu. Workflow `publish=false`
olduğu için bu doğrulama yeni GitHub Release/tag yayımlamadı.

## Validation commands

```text
python scripts/audit_phase0_exit.py --json
python -m pytest backend/tests/test_p0_wp10_phase0_exit.py -q
```
