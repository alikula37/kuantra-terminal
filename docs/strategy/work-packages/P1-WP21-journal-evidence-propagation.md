<!-- doc-role: current-work-package -->
# P1-WP21 — Journal, Projection & Evidence Propagation Contract

```yaml
work_package: P1-WP21
version: 1.0.0
status: Ready
date: 2026-09-08
baseline_commit: 5d691b9
branch: codex/p1-wp01-evidence-ledger
strategy: KPR-001@current
depends_on: P1-WP20
```

## Problem ve amaç

P1-WP20 deterministic economic groups üretir; ancak bu sonuçların canonical evidence
ledger, rebuildable trade projection, journal/evidence pack ve correction lineage
katmanlarına atomik ve tekrar üretilebilir biçimde taşınması ayrı bir doğruluk
problemidir. Projection’a erken veya parçalı yazım UI’da group ile ledger’ı ayırabilir;
correction eski kanıtı silebilir veya incomplete coverage complete görünebilir.

P1-WP21’in amacı canonical ledger → typed projection → read/evidence pack zincirinde
aynı input için aynı sonucu, correction için immutable lineage’ı ve transaction
rollback sınırını doğrulamaktır. Funding/transfer için yeni ledger event type veya
schema migration bu paket tarafından sessizce eklenmez.

## Beklenen davranış sözleşmesi

1. Aynı normalized observation/group input aynı projection ve evidence pack’i üretir;
   event order yalnızca canonical chain order ile belirlenir, process/hash-map sırası
   sonucu değiştirmez.
2. Economic group source lineage ve P1-WP19 account coverage downstream’de korunur;
   `UNKNOWN`/`PARTIAL` downstream’de complete/zero değer olarak düzleştirilmez.
3. Correction yeni immutable ledger/evidence relation üretir; önceki event, source
   row ve projection history fiziksel olarak silinmez. As-of/replay görünümü açıkça
   revision veya correction lineage taşır.
4. Ledger append + projection update + compatibility journal mutation transaction
   sınırında birlikte commit/rollback olur; injected failure ACK edilmiş yarım state
   bırakmaz.
5. Rebuild disposable projection’ı yalnız valid canonical events’tan deterministic
   üretir; corrupted chain, malformed group veya unsupported account event fail-closed
   olur.
6. Read-only evidence pack source event hash/provenance gösterir; raw payload, secret,
   AI authority veya live execution capability eklenmez.

## İlk dosya/test kapsamı

- `backend/app/db/repositories/evidence_ledger_repo.py`, `evidence_projection_repo.py`
  ve gerektiğinde `sqlite_driver.py` transaction boundary.
- `backend/app/services/trade_read_adapter.py` evidence pack/coverage propagation.
- P1-WP20 economic group output adapter; P1-WP19 funding/transfer pending schema
  boundary korunur.
- `backend/tests/` deterministic replay/rebuild, correction lineage, incomplete
  coverage, rollback ve malformed/unsupported negative fixtures.
- Yeni schema migration, live connector, user data migration ve UI capability promotion
  kapsam dışıdır.

## Acceptance criteria

- [ ] Önce kırmızı, sonra yeşil: aynı grouped input aynı ledger/projection/evidence
  pack snapshot’ını üretir; input permutation ve replay sonucu değişmez.
- [ ] Economic source lineage, account coverage ve `PARTIAL`/`UNKNOWN` state downstream
  projection/evidence pack’te korunur; zero/complete uydurulmaz.
- [ ] Correction eski event’i silmeden yeni immutable relation üretir; as-of/replay
  revision ve provenance görünürdür; re-import idempotent kalır.
- [ ] Ledger/projection/journal atomic boundary failure injection rollback testi geçer;
  half-acknowledged state üretilmez.
- [ ] Invalid chain, malformed group, unsupported account event ve missing coverage
  fail-closed raporlanır.
- [ ] P1-WP17–P1-WP20 regression, focused suite, full backend suite ve uygun Mac
  local CI kanıtı kaydedilir.
- [ ] Exact commit, changed files, remaining accounting/schema boundaries ve sonraki
  UX/review integration bağımlılığı bu kayda yazılır.

## Kapsam dışı

Funding/transfer için yeni ledger schema migration, full account PnL/tax accounting,
new connector, live order, AI decision/order, market-data reconstruction, user
migration, release/signing ve pilot go/no-go.
