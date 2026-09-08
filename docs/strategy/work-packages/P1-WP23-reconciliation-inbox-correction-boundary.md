<!-- doc-role: current-work-package -->
# P1-WP23 — U02 Reconciliation Inbox & Correction Boundary

```yaml
work_package: P1-WP23
version: 1.0.0
status: Ready
date: 2026-09-08
baseline_commit: ea4e12c
branch: codex/p1-wp01-evidence-ledger
strategy: KPR-001@current
depends_on: P1-WP22, P1-WP19, P1-WP20, P1-WP21, P1-WP14
```

## Amaç

R4'te görünür hale gelen discrepancy ve coverage sonuçlarını kullanıcı kararına
bağlayan bounded bir reconciliation inbox oluşturmak. Inbox, hangi kaynağın hangi
trade/economic group üzerinde hangi belirsizliği ürettiğini gösterecek; kullanıcı
incelemesi veya düzeltme kararı kanıtı silmeden ve otomatik başarı üretmeden kaydedilecek.

## Davranış sözleşmesi

- `UNKNOWN`, `PARTIAL`, `NOT_AVAILABLE`, malformed ve unsupported sonuçlar inbox'ta
  görünür kalır; çözülmemiş kayıtlar filtreyle gizlenemez ve `PASS`/`complete` olmaz.
- Her discrepancy source event/file hash, source row/reference, economic group/trade
  identity, coverage, detected time ve current decision state ile source-linked olur;
  raw credential veya gereksiz kişisel veri UI/API'ye taşınmaz.
- Kullanıcı kararı açık bir state transition'dır: acknowledge, reject veya correction
  talebi birbirinden ayrılır. “Resolve” tek başına muhasebe doğrulaması sayılmaz.
- Correction mevcut P1-WP21 immutable relation/lineage sözleşmesini kullanır; eski event
  silinmez, yeni revision/as-of ilişkisi eklenir ve önceki Evidence Pack geçmişi korunur.
- Re-import ile fark kapanırsa yeni observation ile eski discrepancy arasında lineage
  kurulur; duplicate/replay aynı kararı veya event'i ikinci kez üretmez.
- Funding/transfer için yeni event type veya ledger schema eklenmez. Full-account PnL,
  tax accounting, live execution, AI authority ve yeni connector kapsam dışıdır.

## Red test kapsamı

- Backend: deterministic inbox query/filter, source/discrepancy/coverage projection,
  explicit decision transition, correction lineage, duplicate/replay ve invalid
  transition negative cases.
- Frontend: empty/partial/unknown/unresolved states, source reference ve decision
  confirmation; no-data sonucu success gibi görünmemeli.
- Integration: import preview → inbox → user decision/correction → evidence pack ve
  export; eski immutable evidence/as-of görünümü korunmalı.

## Acceptance criteria

- [ ] Temporary clean data directory'de supported discrepancy'ler deterministic inbox'ta görünür.
- [ ] Source hash/reference, economic group/trade identity, coverage ve discrepancy type UI/API'de korunur.
- [ ] `UNKNOWN`/`PARTIAL`/`NOT_AVAILABLE`/unsupported kayıtlar fail-closed ve unresolved olarak kalabilir.
- [ ] Acknowledge/reject/correction kararları açık state transition ve audit evidence üretir; tek “resolve” başarı kısayolu yoktur.
- [ ] Correction veya re-import eski event/evidence'i silmeden lineage ve revision/as-of görünümünü korur.
- [ ] Duplicate/replay ve invalid transition testleri idempotent/fail-closed davranışı kanıtlar.
- [ ] Backend/frontend focused tests, full suite ve Mac local CI sonucu kaydedilir.

## Kesinlikle kapsam dışı

Funding/transfer ledger schema, full-account PnL/tax accounting, yeni venue/connector,
live broker order, AI recommendation/order authority, weekly review/R5, migration,
signing/notarization, Windows/Linux host proof, pilot ve release kararı.

## İlk inceleme alanı

- P1-WP22 import review ve P1-WP21 evidence lineage servisleri ile mevcut journal
  review/correction API sözleşmeleri.
- Trade Evidence Pack read adapter/export ve mevcut discrepancy/coverage testleri.
- `CsvImportModal`, `TradeEvidencePanel`, review/inbox shell ve locale parity.
- Önce red test; yalnız bu sözleşmenin gerektirdiği bounded persistence/API/UI boşluğu
  uygulanır. Yeni ledger schema ancak mevcut sözleşme yetersizliği açık kanıtlanırsa
  ayrıca ADR/work-package kararıyla ele alınır.
