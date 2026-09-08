<!-- doc-role: archived -->
> Historical reference only. Not a current work order. Unchecked acceptance items remain open;
> see [current status](../../../strategy/STATUS.md). Read only for a relevant task.

# P1-WP14 — Versioned Playbook ve Risk Policy Events

```yaml
document_id: P1-WP14
version: 1.0.0
status: Active
date: 2026-09-06
baseline: 1665d6c
strategy: KPS-001@1.0.0
adr: ADR-0001, ADR-0002, ADR-0003
depends_on: P1-WP01 Canonical Evidence Ledger, P1-WP07 Trade Evidence Pack API, P1-WP13 Evidence Pack Export ve Backup/Restore Drill
implementation_commits: 9068afb
```

## Problem

Playbook CRUD ve `RiskGuard` kararları bugüne kadar yalnızca değişebilir SQLite
durumunu gösteriyordu. Bir trade sonradan denetlendiğinde hangi playbook kural
sürümünün kullanıldığı, risk limitinin hangi konfigürasyondan geldiği ve kararın
değiştirilmediği kanıtlanamıyordu. Bu, Trade Evidence Pack'in karar politikası
boyutunu eksik bırakıyordu.

## Karar

1. Playbook ve risk policy snapshot'ları ayrı append-only version tablolarında
   saklanır. Mevcut `playbooks`, `playbook_rules` ve settings yüzeyleri hızlı
   compatibility projection olarak kalır; geçmiş bu tablolarda güncellenmez.
2. Yeni bir evidence event type eklenmez. Mevcut schema/migration sözleşmesi
   korunarak playbook snapshot ve audit review'ları `JournalReviewAdded`, risk
   policy snapshot ve pre-execution kararları `RiskEvaluated` olarak yazılır.
3. Snapshot hash'i canonical JSON'dan üretilir. Playbook audit, açıkça seçilmiş
   `playbook_version` ile pinlenebilir; varsayılan davranış aktif sürümü kullanır.
4. `RiskGuard` deterministik yetkili olarak kalır. Policy id/version/hash ve
   ledger event id karar metadata'sına eklenir; evidence yazılamazsa karar
   fail-closed reddedilir. AI veya başka bir servis emir yetkisi kazanmaz.
5. Version/audit ve compatibility projection yazıları aynı `BEGIN IMMEDIATE`
   transaction içinde yürür. Ledger append başarısız olursa projection da
   commit edilmez.

## Teknik teslimatlar

- `RiskPolicyService` ve `risk_policy_versions` append-only schema/triggers.
- `PlaybookService` için `playbook_versions` append-only schema/triggers.
- Playbook version oluşturma/listeme ve version-pinned audit API yüzeyi.
- `RiskGuard` karar metadata'sında policy snapshot ve evidence event kimliği.
- `JournalReviewAdded` / `RiskEvaluated` ledger provenance sözleşmesi.
- Canonical snapshot hash, idempotent event identity ve rollback sınırı.
- WP14 focused regression tests.

## API / event sözleşmesi

- `POST /api/v1/playbooks/{playbook_id}/versions`
- `GET /api/v1/playbooks/{playbook_id}/versions`
- `POST /api/v1/playbooks/audit` payload'ına opsiyonel `playbook_version`
- `RiskGuard.validate_pre_execution_risk()` metadata:
  `policy_id`, `policy_version`, `policy_snapshot_sha256`, `risk_event_id`
- Snapshot event provenance `source`, `policy/playbook_id`, `version`,
  `snapshot_sha256` alanlarını taşır.

## Acceptance criteria

- [x] Playbook oluşturma ilk snapshot'ı ve `JournalReviewAdded` event'i atomik yazar.
- [x] Playbook version 1 okunabilir kalır; version 2 compatibility view'ı ilerletir.
- [x] Playbook version/audit hash'i ve event id Evidence Pack zincirinde görünür.
- [x] `playbook_versions` update/delete işlemleri append-only trigger ile engellenir.
- [x] Risk policy ilk/sonraki snapshot'ları `RiskEvaluated` ile zincire eklenir.
- [x] RiskGuard eski threshold ve compliance rejection davranışını korur.
- [x] Ledger yazılamazsa risk kararı fail-closed olur.
- [x] Focused suite: `3 passed`.
- [x] Full backend suite: `405 passed, 1 skipped`.
- [ ] Remote three-OS CI: GitHub Actions kota/bütçe nedeniyle geçici disabled;
  reset sonrası implementation commit'i için yeniden çalıştırılacak.

## Kesinlikle kapsam dışı

- Canlı broker emir gönderimi, FIX/DMA certification veya Phase 4 execution gate.
- AI'nin policy değiştirmesi ya da risk kararına doğrudan yetki verilmesi.
- Cloud policy sync, ekip/tenant policy paylaşımı veya merkezi policy server.
- Eski `trade_rule_checks` satırlarını geçmiş audit kaydı olarak yeniden yazmak;
  geçmiş kanıt ledger'da immutable kalır.

## Risk ve sonraki sınır

Ledger'a her risk değerlendirmesini yazmak SQLite write hacmini artırır. Phase 2
data-plane/replay işlerinde bu event'ler için bounded projection ve retention
telemetrisi ölçülmelidir; event silme veya zinciri kıran compaction yapılmaz.
Bir sonraki mantıklı sınır, policy/version bilgisini Evidence Pack UI'da insanın
okuyabileceği bir review paneline taşımaktır; bu panel execution authority
oluşturmayacaktır.

## Değişiklik geçmişi

### 1.0.0 — 2026-09-06

- Playbook/risk policy snapshot, hash ve version event sözleşmesi tanımlandı ve
  mevcut evidence event type seti korunarak uygulandı.
