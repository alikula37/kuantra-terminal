<!-- doc-role: archived -->
> Historical reference only. Not a current work order. Unchecked acceptance items remain open;
> see [current status](../../../strategy/STATUS.md). Read only for a relevant task.

# P1-WP22 — R4 Value-Chain Integration Gate

```yaml
work_package: P1-WP22
version: 1.0.0
status: Complete
date: 2026-09-08
baseline_commit: 92a2a74
implementation_commit: ea4e12c
branch: codex/p1-wp01-evidence-ledger
strategy: KPR-001@current
depends_on: P1-WP21, H03, R1-R3 evidence
```

## Sonuç

P1-WP22, temiz sentetik data directory üzerinde import preview → bounded
reconciliation/discrepancy review → source-linked Trade Evidence Pack → deterministic
JSON/HTML export akışını bağladı. CSV journal snapshot'ı broker order/fill
reconciliation olarak etiketlenmez; broker lifecycle import'u da otomatik journal trade
oluşturmaz. Accounting `pnl` veya `commission` bilinmiyorsa kayıt sıfıra çevrilmez ve
import/review açıkça fail-closed kalır. `PARTIAL`, `UNKNOWN` ve `NOT_AVAILABLE` coverage
değerleri downstream evidence pack'te korunur.

Correction/re-import akışı eski immutable kanıtı silmeden lineage, revision/as-of ve
source hash ilişkisini korur. Funding/transfer için yeni event type veya ledger schema
eklenmedi; full-account PnL/tax accounting, yeni connector, live execution ve gerçek
kullanıcı verisi bu paketin kapsamına alınmadı.

## Acceptance criteria

- [x] Temiz temporary data directory üzerinde supported fixture preview DB'yi değiştirmez.
- [x] Supported fixture import/reconciliation sonucu deterministic discrepancy ve coverage özeti üretir.
- [x] Malformed, unsupported, partial ve unknown fixture'lar fail-closed görünür; PASS/zero değer üretmez.
- [x] Imported trade → source-linked Evidence Pack → JSON/HTML export tek akışta doğrulanır.
- [x] Correction/re-import sonrası eski kanıt, lineage ve revision/as-of görünümü korunur.
- [x] Network disabled/degraded sınırında local import, evidence read ve export regression'ı geçer.
- [x] Focused backend/frontend, full suite/local CI ve Mac packaged mounted-DMG smoke sonucu kaydedildi.

## Değişen dosyalar

- `backend/app/services/csv_importer.py`
- `backend/app/services/broker_import_service.py`
- `backend/app/services/trade_read_adapter.py`
- `backend/tests/test_p1_wp22_value_chain.py`
- `frontend/src/components/modals/CsvImportModal.tsx`
- `frontend/src/components/TradeEvidencePanel.tsx`
- `frontend/src/components/__tests__/CsvImportModal.dom.test.tsx`
- `frontend/src/components/__tests__/TradeEvidencePanel.dom.test.tsx`
- `frontend/src/types/index.ts`
- `frontend/src/locales/en.json`
- `frontend/src/locales/tr.json`
- `frontend/src/locales/de.json`

## Kanıt

- Focused WP22/CSV/H03/regression tests: **23 passed, 2 warnings**.
- Full backend suite: **620 passed, 2 warnings**.
- Full frontend suite: **56 passed**; i18n check **486/486**; production build PASS.
- Clean Mac local CI: **MERGE READY**; diff-check, release truth, packaging integrity,
  backend/frontend suites, arm64 PyInstaller build, native smoke and provenance
  contract all PASS.
- Local CI source commit: `ea4e12cc60aea52c86d1318e97d90a566a3b1736`.
- Tracked source tree SHA-256: `63f224cd5cba6ce2212f01ebff39eb104217e724221379708f3d64671a5538a1`.
- Lock hashes: backend `6291588602869af34e2a4db5d7244a627f4e139cbbd4b034b7cc07d890812399`;
  frontend `b392a59d09ade73564ce082b1a5bc1236618ebeee11703a992980cfd1812882c`.
- Toolchain: macOS arm64, Python 3.11.16, Node v20.20.2, npm 10.8.2, uv 0.12.10,
  PyInstaller 6.22.2. Locked dependency preparation was used; `--offline` is not
  runtime-offline proof.
- Local executable SHA-256: `d19790e16cab9e475d51536d6dbb62e4f0e9923f20a62181ee7e305adfc145c6`.
- Exact mounted-DMG smoke: read-only mount, explicit mounted `.app` executable,
  `wkwebview`, controller ready, smoke PASS and safe detach PASS.
- DMG SHA-256: `d865310ab6fa2e3721fc524d0357fa61307b1fa9810fab136d147fcdf445b2ec`.
- Mounted executable SHA-256: `d19790e16cab9e475d51536d6dbb62e4f0e9923f20a62181ee7e305adfc145c6`.
- Release provenance validator: PASS; provenance status `COMPLETE`; ad-hoc signing is
  packaging preflight only, not Developer ID/notarization/Gatekeeper evidence.

## Kalan sınırlar ve sonraki bağımlılık

U02 reconciliation inbox ve explicit correction/user-decision boundary sonraki bounded
pakettir. R5 weekly review/as-of policy, H01/H02/H04–H07 hardening, N03–N06 platform
evidence, licensing, pilot ve release-owner kararları bu paketten geçilmiş sayılmaz.

## Değişiklik geçmişi

### 1.0.0 — 2026-09-08

- Import review, coverage/discrepancy propagation, source-linked evidence/export ve
  exact Mac artifact evidence kaydedildi.
