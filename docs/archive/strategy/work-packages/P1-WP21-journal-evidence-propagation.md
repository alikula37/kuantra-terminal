<!-- doc-role: archived -->
# P1-WP21 — Journal, Projection & Evidence Propagation Contract

```yaml
work_package: P1-WP21
version: 1.0.0
status: Complete
date: 2026-09-08
baseline_commit: 4f7e0f0
implementation_commit: 056b1ca
branch: codex/p1-wp01-evidence-ledger
strategy: KPR-001@current
depends_on: P1-WP20
```

## Sonuç

P1-WP20 ekonomik grup çıktısı, mevcut ledger/projection şemasını genişletmeden
canonical evidence payload içine deterministik biçimde taşındı. Açık ve eksiksiz
trade snapshot olmadan ekonomik grup journal trade olarak yazılamaz; `pnl` ve
`commission` varsayılan sıfıra indirgenmez. Account coverage `COMPLETE`, `PARTIAL`,
`UNKNOWN` ve `NOT_AVAILABLE` değerleri evidence pack içinde korunur.

Correction yeni `TradeCorrected` event’i, `causation_id`, önceki event hash’i ve
revision/as-of bilgisi ile append-only ledger’a eklenir. Projection disposable
read model olarak son canonical revision’dan yeniden kurulabilir; önceki event
fiziksel olarak silinmez. Funding/transfer için yeni event type veya schema
migration eklenmedi.

## Acceptance criteria

- [x] Önce kırmızı, sonra yeşil: aynı grouped input aynı ledger/projection/evidence pack snapshot’ını üretir; input permutation ve replay sonucu değişmez.
- [x] Economic source lineage, account coverage ve `PARTIAL`/`UNKNOWN` state downstream projection/evidence pack’te korunur; zero/complete uydurulmaz.
- [x] Correction eski event’i silmeden yeni immutable relation üretir; as-of/replay revision ve provenance görünürdür; re-import idempotent kalır.
- [x] Ledger/projection/journal atomic boundary failure injection rollback testi geçer; half-acknowledged state üretilmez.
- [x] Invalid chain, malformed group, unsupported account event ve missing coverage fail-closed raporlanır.
- [x] P1-WP17–P1-WP20 regression, focused suite, full backend suite ve Mac local CI kanıtı kaydedildi.
- [x] Exact commit, changed files, remaining accounting/schema boundaries ve sonraki UX/review integration bağımlılığı bu kayıtta yazılıdır.

## Değişen dosyalar

- `backend/app/services/economic_evidence_propagation.py`
- `backend/app/db/sqlite_driver.py`
- `backend/app/db/repositories/evidence_ledger_repo.py`
- `backend/app/services/trade_read_adapter.py`
- `backend/tests/test_p1_wp21_journal_evidence_propagation.py`

## Kanıt

- Focused P1-WP21: **6 passed**.
- P1-WP01/02/19/20 regression: **42 passed**.
- Full backend suite: **601 passed, 2 warnings**.
- Mac local CI: `merge_ready=true`; frontend 51 tests, i18n 480/480, production build, PyInstaller arm64 build, native `wkwebview` smoke and packaging preflight passed.
- Local smoke executable SHA-256: `e8124fee1ed0c666bdc5f0eb49af129da279c8b4dd1f2450ed7f27fe77ae984c`.
- Local smoke used isolated temporary data and the runtime attempted its existing public Binance WebSocket startup path; this is not runtime-offline proof.

## Kalan sınırlar ve sonraki bağımlılık

Full-account PnL/tax accounting, funding/transfer ledger schema, new connector,
live order, AI authority, market reconstruction, user migration and release/pilot
gates remain out of scope. UX/review integration waits for the provenance and
artifact identity gates. Next bounded package: **N01 exact build provenance**.

