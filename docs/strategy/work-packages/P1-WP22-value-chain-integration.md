<!-- doc-role: current-work-package -->
# P1-WP22 — R4 Value-Chain Integration Gate

```yaml
work_package: P1-WP22
version: 1.0.0
status: InProgress
date: 2026-09-08
baseline_commit: 62921f7
branch: codex/p1-wp01-evidence-ledger
strategy: KPR-001@current
depends_on: P1-WP21, H03, R1-R3 evidence
```

## Amaç

Mevcut bounded import, reconciliation, canonical ledger, Trade Evidence Pack ve export
kapılarını tek bir temiz sentetik akışta bağlamak. Bu paket yeni broker connector, yeni
ledger schema veya haftalık review motoru eklemez; R4’ün import preview → discrepancy
görünürlüğü → correction/user decision boundary → source-linked Evidence Pack → export
uyumluluğunu kanıtlar.

## Davranış sözleşmesi

- Preview/dry-run DB’ye yazmaz; malformed veya unsupported input başarı gibi görünmez.
- Partial/unknown fee, funding, account coverage ve market context açıkça taşınır;
  sıfır veya `complete` ile doldurulmaz.
- Reconciliation discrepancy kaynağı, etkilenen ekonomik grup/trade ve çözüm durumu ile
  açıklanır; unresolved kayıt Evidence Pack’ten gizlenmez.
- Correction eski immutable event’i silmez; yeni lineage/as-of ilişkisi pack/export’a taşınır.
- Export deterministic, redacted ve canonical source-linked kalır; CSV formula injection
  veya HTML raw payload render edilmez.
- Network disabled/degraded durumunda local import, review ve export akışı çalışır;
  live market quote veya full-account PnL iddiası açılmaz.

## Acceptance criteria

- [ ] Temiz temporary data directory üzerinde supported fixture preview DB’yi değiştirmez.
- [ ] Supported fixture import/reconciliation sonucu deterministic discrepancy ve coverage özeti üretir.
- [ ] Malformed, unsupported, partial ve unknown fixture’lar fail-closed görünür; PASS/zero değer üretmez.
- [ ] Imported trade → source-linked Evidence Pack → JSON/HTML export tek akışta doğrulanır.
- [ ] Correction/re-import sonrası eski kanıt, lineage ve revision/as-of görünümü korunur.
- [ ] Network disabled fixture ile local import, evidence read ve export regression’ı geçer.
- [ ] Focused backend/frontend E2E, full suite/local CI ve Mac packaged smoke sonucu kaydedilir.

## Kesinlikle kapsam dışı

Weekly review/as-of policy UI (R5), yeni venue/connector, funding/transfer schema,
full-account PnL/tax accounting, AI recommendation/order authority, live execution,
user data migration, signing/notarization, Windows/Linux host proof, pilot ve release.

## İlk inceleme alanı

- `backend/app/services/csv_importer.py`, `broker_import_service.py`,
  `economic_evidence_propagation.py`, `trade_read_adapter.py`, evidence export ve ilgili API routes.
- `frontend/src/components/modals/CsvImportModal.tsx`, `TradeEvidencePanel.tsx`,
  stores/types ve mevcut UI/API integration tests.
- Önce red E2E tests; yalnız kanıtlanan boşluğu kapatan bounded implementation.
