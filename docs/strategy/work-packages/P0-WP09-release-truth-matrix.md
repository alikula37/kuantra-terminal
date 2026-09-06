# P0-WP09 — Release Truth Matrix ve Current Claims

```yaml
document_id: P0-WP09
version: 1.0.0
status: Active
date: 2026-09-06
baseline: 110add6
strategy: KPS-001@1.0.0
adr: ADR-0001, ADR-0003
canonical_contract: KTR-001@1.0.0
```

## Karar

v1.4.0 için release-facing iddiaların tek kaynağı
[`docs/release/truth-matrix.v1.4.0.json`](../../release/truth-matrix.v1.4.0.json) olur.
`README.md`, paket metadata'sı, Linux desktop metadata'sı, workflow'lar ve manifest üretimi bu
contract ile doğrulanır. `RELEASE_NOTES.md` içindeki eski notlar repository audit arşivinde kalır;
GitHub Release body'si yalnız marker-delimited current bölümünden üretilir.

Bu paket ürün kabiliyetini genişletmez. Live broker execution, FIX/DMA, HFT/order-flow SLA,
AI/model authority, DEX/DeFAI, biometrics ve remote plugin marketplace hâlâ
`EXPERIMENTAL_DISABLED` durumundadır.

## Problem ve risk

Önceki release notları ve `package.json` kurumsal HFT, zero-mock, canlı CCXT ve AI swarm gibi
artık desteklenmeyen iddiaları current release metadata'sında taşıyordu. Release workflow bütün
`RELEASE_NOTES.md` dosyasını body olarak gönderdiği için tarihsel metin yeni release'e de sızabilirdi.
Bu, kullanıcı beklentisi, compliance ve güvenilirlik açısından doğrudan risktir.

## Teslimatlar

- KTR-001 canonical matrix: capability status, provenance, authority boundary, release-facing file
  listesi ve dar forbidden-pattern sözleşmesi.
- Dependency-free `scripts/check_release_truth.py`: matrix/schema, version sync, exact tag,
  marker, required truth phrases ve current claim taraması.
- `scripts/render_current_release_notes.py`: GitHub Release için yalnız current body render'ı.
- `generate_release_manifest.py` içine matrix kimliği ve SHA-256 provenance kaydı.
- CI ve tagged release workflow'unda truth gate; release body artık
  `dist/CURRENT_RELEASE_NOTES.md`.
- README, root package description/keywords ve Linux desktop comment truth-safe ürün kimliğine
  taşındı; eski release testleri current-vs-history sınırını ölçüyor.

## Kapsam dışı

- Yeni broker/venue adapter'ı, live order submission veya reconciliation.
- Rust/Tokio data plane, Arrow/Parquet ledger, WebView2 geçişi.
- AI inference, plugin signing/marketplace veya yeni UI feature'ı.
- Historical release text'inin silinmesi; arşiv Git history ile birlikte korunur.

## Acceptance criteria

- [x] Matrix product version, Python/package versions ve kabul edilen tag ile eşleşiyor.
- [x] Current release notes marker'ları tekil; renderer historical claim'leri üretmiyor.
- [x] Forbidden claim checker current release-facing dosyalarda fail-closed çalışıyor.
- [x] CI ve release workflow checker'ı backend/frontend/paketleme öncesi çalıştırıyor.
- [x] Release MANIFEST.json matrix document/version/hash taşıyor.
- [x] Yerel truth, packaging ve ilgili regression testleri geçiyor.
- [ ] Üç OS push/PR CI kanıtı ve Phase 0 exit audit kaydı tamamlanacak.

## Validation commands

```text
python scripts/check_release_truth.py
python scripts/render_current_release_notes.py --output <temp>/CURRENT_RELEASE_NOTES.md
python scripts/verify_packaging.py
python -m pytest backend/tests/test_p0_wp09_release_truth.py backend/tests/test_ci_workflow_contract.py backend/tests/test_ci_cd_workflows.py backend/tests/test_release_manifest.py backend/tests/test_phase18_documentation_packaging.py -q
```

## Risk ve geri dönüş

Checker bilinçli olarak `docs/strategy/**`, `docs/superpowers/**` ve historical release archive'ı
tarama dışı bırakır; aksi halde tarihsel iddialar current contract'ı yanlış bloke eder. Yeni bir
release-facing dosya eklenirse matrix listesine eklenmeden release gate'i geçemez. Matrix veya
renderer hatası release'i durdurur; ürün runtime'ını değiştirmez.
