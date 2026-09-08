<!-- doc-role: archived -->
> Historical reference only. Not a current work order. Unchecked acceptance items remain open;
> see [current status](../../../strategy/STATUS.md). Read only for a relevant task.

# P1-WP01 — Canonical Evidence Ledger Foundation

```yaml
document_id: P1-WP01
version: 1.1.0
status: Active
date: 2026-09-06
baseline: a5ae737
strategy: KPS-001@1.0.0
adr: ADR-0002, ADR-0003
depends_on: P0-WP10 technical exit verified; release publication separately gated
implementation_authority: owner_phase_transition_directive_2026-09-06
implementation_commits: 43641e1, 25e4640, db80a77, 2f0e7d7
last_green_ci_run: 34038244922
ci_attempts_observed: 34038714552, 34038892057
```

## Karar

Phase 0 teknik exit audit’i `READY_FOR_HUMAN_RELEASE_APPROVAL` verdict’i ile doğrulandı;
gerçek GitHub release yayınlama hâlâ ayrı `publish=true` onay kapısıdır. Bu work package,
mevcut `trades` CRUD'ünü bir anda kaldırmak yerine SQLite içinde ayrı ve append-only bir canonical
`evidence_events` ledger'ı kuracak. Journal compatibility projection'ı korunacak; ledger
source-of-record olur, mevcut journal tablosu bu pakette yalnız geriye dönük okuma ve
uyumluluk yüzeyi olarak kalır.

Bu paket bir broker execution açmaz. Herhangi bir event'in ledger'a yazılması, venue'ye emir
gönderildiği anlamına gelmez.

## Problem ve risk

`backend/app/db/sqlite_driver.py` içindeki `INSERT OR REPLACE` mevcut trade satırını sessizce
değiştirebilir ve önceki değerin kanıtını kaybettirir. `backend/app/db/sync_pipeline.py`
SQLite güncellemesi ile DuckDB sync'ini tek bir canonical transaction gibi göstermektedir.
Bu durum correction, retry, import idempotency ve “bu sonuç hangi kaynaktan geldi?” sorusunu
güvenilir biçimde cevaplamayı engeller.

## Kesin kapsam

- SQLite'ta ayrı `evidence_events` tablo/repository ve güvenli, append-only append API.
- Event identity, schema/adapter version, correlation/causation/idempotency identity.
- UTC `occurred_at`/`received_at`, account/venue ve per-account + UTC-day chain scope.
- Canonical JSON serialization, raw payload SHA-256, `prev_hash` ve `event_hash`.
- Ledger write transaction'ında `BEGIN IMMEDIATE` ve `PRAGMA synchronous=FULL`.
- Aynı event identity ile tekrar gelen append'in deterministic no-op olarak doğrulanması.
- Chain verifier: payload, previous hash, sıra veya identity bozulmasını fail-closed raporlama.
- İdempotent `LegacyTradeImported` backfill komutu; mevcut `trades` satırlarını değiştirmez.
- Read-only ledger export ve test fixture'ları.

## Event sözlüğü (ilk sürüm)

`IntentRecorded`, `RiskEvaluated`, `OrderSubmitRequested`, `VenueAck`, `VenueReject`,
`FillRecorded`, `CancelRequested`, `CancelAck`, `CancelReject`, `FeeAdjusted`,
`TradeCorrected`, `PositionProjectionUpdated`, `JournalReviewAdded`, `LegacyTradeImported`.

Yeni event türü eklemek schema/version değişikliği ve test gerektirir; serbest metin event
türü kabul edilmez.

## Davranış sözleşmesi

1. Her accepted event'in `event_id`, `event_type`, `account_id`, `venue`, UTC timestamps,
   schema version, normalized payload, identity alanları ve hash alanları doludur.
2. Aynı `idempotency_key` + `account_id` + `venue` + `event_type` tekrar gelirse yeni satır
   oluşturulmaz; mevcut canonical event döndürülür. Farklı payload aynı identity ile gelirse
   işlem reddedilir ve ledger değişmez.
3. `event_hash`, canonical event gövdesi ve aynı chain scope içindeki `prev_hash` üzerinden
   hesaplanır. Hash doğrulama başarısızsa okuma/verify sonucu `invalid`, sessiz onarım yoktur.
4. Transaction rollback sonrası caller başarı ACK'i alamaz; yarım event veya hash zinciri
   boşluğu bırakılmaz.
5. Backfill tekrar çalıştırılabilir; source trade satırları ve mevcut journal API davranışı
   değişmez.
6. Raw payload'ta secret/API key/credential değeri tutulmaz; importer payload'ı redacted
   veya hash-only göndermelidir.

## Acceptance criteria

- [x] Migration iki kez çalıştırıldığında aynı şema ve index'leri güvenle korur.
- [x] 10.000 ardışık event append/recompute testinde zincir doğrulaması %100 başarılıdır.
- [x] Duplicate identity aynı canonical event'i döndürür; çakışan payload fail-closed olur.
- [x] Payload veya `prev_hash` mutation'ı verifier tarafından tespit edilir.
- [x] Injected transaction failure sonrasında yeni event ve başarı ACK'i bulunmaz.
- [x] Legacy backfill iki kez çalışır; her source trade için tek event üretir ve source satırını
  değiştirmez.
- [x] Ledger write path'inde `INSERT OR REPLACE` kullanılmaz; legacy `trades` compatibility
  upsert'i `ON CONFLICT DO UPDATE` ile foreign-key tag ilişkilerini korur.
- [x] Yeni testler ephemeral `KUANTRA_DATA_DIR` ile çalışır; developer journal'ına yazmaz.
- [ ] Latest implementation SHA için backend suite, focused ledger suite, `git diff --check`
  ve üç-OS CI yeşildir.

## Implementation record

- `backend/app/db/evidence_schema.py`: runtime/Alembic ortak DDL, unique identity/chain
  index'leri ve append-only update/delete trigger'ları.
- `backend/alembic/versions/002_evidence_ledger.py`: idempotent head migration; destructive
  downgrade bilerek desteklenmiyor.
- `backend/app/db/repositories/evidence_ledger_repo.py`: canonical JSON, secret-bearing field
  rejection, `BEGIN IMMEDIATE` + write-only `synchronous=FULL`, hash-chain append/verifier,
  deterministic duplicate no-op, conflict/failure rollback, JSONL export ve legacy backfill.
- `backend/app/cli.py`: yalnız explicit local komutlar:
  `python backend/app/cli.py evidence-ledger backfill --apply|--dry-run`, `verify`, `export`.
- `backend/alembic/env.py`: explicit test/user database URL’si artık dinamik varsayılanla
  ezilmiyor; migration gerçekten hedef DB’ye uygulanıyor.
- Focused suite: `10 passed`.
- Full backend suite: `360 passed, 1 skipped`.
- Code commits: `43641e1`, `25e4640`, `db80a77`, `2f0e7d7`; Phase 0 evidence baseline:
  `a5ae737`.
- Last green three-OS push CI: [34038244922](https://github.com/alikula37/kuantra-terminal/actions/runs/34038244922)
  success for `a103a06`; Windows job `101500164796`, macOS `101500164772`, Ubuntu `101500164652`.
- Latest hardening commit `2f0e7d7` local full suite: `360 passed, 1 skipped`; CI attempts
  [34038714552](https://github.com/alikula37/kuantra-terminal/actions/runs/34038714552) and
  [34038892057](https://github.com/alikula37/kuantra-terminal/actions/runs/34038892057) could
  not start any job because GitHub account billing/spending-limit protection blocked runner
  allocation. This is an external validation blocker, not a test failure; acceptance remains
  open until a fresh green run covers `2f0e7d7`.

## Değişiklik geçmişi

### 1.1.0 — 2026-09-06

- Legacy journal upsert path `INSERT OR REPLACE` yerine `ON CONFLICT DO UPDATE` kullanır;
  aynı trade yeniden yazıldığında `trade_tags` foreign-key ilişkileri korunur.
- Regression testi eklendi; focused suite `10 passed`, full backend suite `360 passed,
  1 skipped`.

## Kesinlikle kapsam dışı

- Mevcut `trades` CRUD'ünün bu pakette tamamen kaldırılması veya UI yeniden yazımı.
- DuckDB projection rebuild/sync redesign.
- Parquet tick/order-book store, Rust/Tokio data plane, Arrow IPC/Flight.
- Broker/CSV/MT5/Polygon/TwelveData connector değişikliği.
- Live execution, FIX/DMA, reconciliation, HFT latency SLA veya kill-switch değişikliği.
- AI Auditor, local LLM, agent swarm, plugin download veya execution tool.
- Yeni remote dependency veya cloud event service.

## Migration path

1. Phase 0 technical exit ve baseline SHA doğrulanır; release publication ayrıca gated kalır.
2. Migration + repository + verifier bağımsız testlerle eklendi ve `43641e1` ile kaydedildi.
3. `LegacyTradeImported` backfill dry-run/export ile ölçülür; yazma ayrı explicit komuttur.
4. Journal/import akışları compatibility adapter üzerinden event append etmeye alınır; eski
   projection aynı commit içinde kaldırılmaz.
5. İki pilot cycle boyunca ledger doğrulama ve duplicate/error metriği gözlemlenir.
6. Sonraki WP, canonical ledger'dan projection rebuild ve immutable correction UX'ini açar.

## Metrikler ve çıkış kapısı

- Append success rate ≥ %99.9 (known validation rejects ayrı raporlanır).
- Duplicate identity yanlış çoğaltma = 0.
- Hash verification false negative = 0; mutation detection = %100 test coverage.
- Backfill source coverage = %100 veya her exclusion için explicit reason.
- Pilot journal read latency p95 mevcut baseline'dan kötüleşmez (hedef ≤ +10%).

Bu metrikler iki ardışık pilot veri setinde sağlanmadan WP `Verified` yapılmaz. Phase 1'in
projection/replay paketleri bu çıkıştan önce başlamaz.

## Terra uygulama promptu (uygulandı)

`docs/strategy/WORK-PACKAGE-TEMPLATE.md` sınırlarıyla Terra bounded review alındı; review,
normal desktop startup’ta migration/bootstrap drift riskini ve ledger’ın bağımsız repository
olması gerektiğini doğruladı. Kod yalnız bu work package kapsamındaki dosyalara dokundu;
DuckDB, connector, UI, AI, broker/FIX ve live execution kapsam dışı kaldı.
