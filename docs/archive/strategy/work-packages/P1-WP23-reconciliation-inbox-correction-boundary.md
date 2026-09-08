<!-- doc-role: archived -->
> Historical reference only. Not a current work order. Unchecked acceptance items remain open;
> see [current status](../../../strategy/STATUS.md). Read only for a relevant task.

# P1-WP23 — U02 Reconciliation Inbox & Correction Boundary

```yaml
work_package: P1-WP23
version: 1.0.0
status: Complete
date: 2026-09-08
baseline_commit: ea4e12c
implementation_commit: 51ee968
branch: codex/p1-wp01-evidence-ledger
strategy: KPR-001@current
depends_on: P1-WP22, P1-WP19, P1-WP20, P1-WP21, P1-WP14
```

## Sonuç

P1-WP23, P1-WP22 import review çıktısını yeni ledger schema veya event type
eklemeden source-linked bir reconciliation inbox'a bağladı. Discrepancy, coverage,
source hash/reference ve ekonomik trade identity deterministik biçimde görünür;
`UNKNOWN`, `PARTIAL`, `NOT_AVAILABLE`, malformed ve unsupported durumlar başarıya
çevrilmez.

Kullanıcı kararları `ACKNOWLEDGE`, `REJECT` ve bounded `CORRECT` olarak ayrıdır.
ACK/REJECT mevcut journal review kanıtını; CORRECT mevcut immutable correction
lineage/as-of sözleşmesini kullanır. Eski event/evidence silinmez, correction source
event'e causation relation ile bağlanır ve duplicate/replay idempotent kalır.

Funding/transfer için yeni event type veya ledger schema eklenmedi. Full-account
PnL/tax accounting, yeni connector, live execution, AI authority ve gerçek kullanıcı
verisi bu paketin kapsamına alınmadı.

## Acceptance criteria

- [x] Temiz temporary data directory'de supported discrepancy'ler deterministic inbox'ta görünür.
- [x] Source hash/reference, economic group/trade identity, coverage ve discrepancy type UI/API'de korunur.
- [x] `UNKNOWN`/`PARTIAL`/`NOT_AVAILABLE`/unsupported kayıtlar fail-closed ve unresolved olarak kalabilir.
- [x] Acknowledge/reject/correction kararları açık state transition ve audit evidence üretir; tek “resolve” başarı kısayolu yoktur.
- [x] Correction veya re-import eski event/evidence'i silmeden lineage ve revision/as-of görünümünü korur.
- [x] Duplicate/replay ve invalid transition testleri idempotent/fail-closed davranışı kanıtlar.
- [x] Backend/frontend focused tests, full suite ve Mac local CI sonucu kaydedilir.

## Kesinlikle kapsam dışı

Funding/transfer ledger schema, full-account PnL/tax accounting, yeni venue/connector,
live broker order, AI recommendation/order authority, weekly review/R5, migration,
signing/notarization, Windows/Linux host proof, pilot ve release kararı.

## Değişen dosyalar

- `backend/app/services/reconciliation_inbox.py`
- `backend/app/db/sqlite_driver.py`
- `backend/app/services/broker_import_service.py`
- `backend/app/api/endpoints.py`
- `backend/tests/test_p1_wp23_reconciliation_inbox.py`
- `frontend/src/components/ReconciliationInbox.tsx`
- `frontend/src/components/JournalView.tsx`
- `frontend/src/components/TradeEvidencePanel.tsx`
- `frontend/src/components/__tests__/ReconciliationInbox.dom.test.tsx`
- `frontend/src/locales/en.json`
- `frontend/src/locales/tr.json`
- `frontend/src/locales/de.json`

## Kanıt

- Red testleri önce import/API ve UI modülünün bulunmadığını gösterdi; bounded
  implementation sonrası WP23 focused backend **5 passed, 2 warnings**, focused
  frontend **2 passed**, backend WP23/WP22/WP11/WP14 regression **27 passed** ve
  frontend focused regression **6 passed**.
- Full backend suite **625 passed, 2 warnings**; full frontend suite **58 passed**;
  i18n parity **512/512**; production build PASS.
- Clean Mac local CI: **MERGE READY**; diff-check, release truth, packaging
  integrity, locked backend/frontend suites, arm64 PyInstaller build, native smoke
  ve provenance contract PASS.
- Local CI source commit `51ee968e07b9463d1b6d316c7d8419f8aaf7a7c3`;
  tracked source tree SHA-256
  `25f98bc34d32ec5d1b35df9faf166618b69ce0f8183fa333367e2b41a18e4367`.
- Lock hashes: backend
  `6291588602869af34e2a4db5d7244a627f4e139cbbd4b034b7cc07d890812399`;
  frontend `b392a59d09ade73564ce082b1a5bc1236618ebeee11703a992980cfd1812882c`.
- Toolchain: macOS arm64, Python 3.11.16, Node v20.20.2, npm 10.8.2,
  uv 0.12.10, PyInstaller 6.22.2. `uv --offline` yalnız locked dependency
  hazırlama/çözümleme kanıtıdır; runtime network-offline kanıtı değildir.
- Local executable SHA-256 `0c0b609b31ff54734ad404b3936291525b9e2108d3221a6b0036b66eada1ffa0`;
  `.app` artifact SHA-256 `1ef4b6b44e779c218963030374537b561cf26f2daf64d05ec22f1941304e7b8f`.
- Exact DMG smoke: read-only mount, mount içindeki explicit `.app` executable,
  `wkwebview`, native controller ready, smoke PASS ve safe detach PASS. DMG SHA-256
  `e89ba08c2f6e07dde27d6d8a95d375fcd439e41c890fff797043e4123d11a565`; mounted
  executable SHA-256
  `0c0b609b31ff54734ad404b3936291525b9e2108d3221a6b0036b66eada1ffa0`.
- Release provenance validator PASS; provenance `COMPLETE`. Ad-hoc signing yalnız
  packaging preflight'tir; Developer ID, notarization ve Gatekeeper kanıtı değildir.

## Kalan sınırlar ve sonraki bağımlılık

U03 Trade Evidence Pack ve deterministic export boundary sonraki bounded pakettir.
Haftalık review/as-of policy, H01/H02/H04–H07 hardening, N03–N06 platform evidence,
lisans, pilot ve release-owner kararları bu paketten geçilmiş sayılmaz.

## Değişiklik geçmişi

### 1.0.0 — 2026-09-08

- Source-linked reconciliation inbox, explicit user decision/correction boundary,
  immutable lineage ve exact Mac artifact evidence kaydedildi.
