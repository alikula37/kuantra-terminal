# P1-WP01 — Canonical Evidence Ledger Foundation

```yaml
document_id: P1-WP01
version: 1.0.0
status: Ready
date: 2026-09-06
baseline: 129ccfa
strategy: KPS-001@1.0.0
adr: ADR-0002, ADR-0003
depends_on: P0-WP10 human release approval
implementation_authority: blocked_until_phase0_exit
```

## Karar

Phase 0 insan release approval'ı verilmeden bu work package için production kodu
değiştirilmeyecek. Onaydan sonra ilk Phase 1 implementation paketi, mevcut `trades`
CRUD'ünü bir anda kaldırmak yerine SQLite içinde ayrı ve append-only bir canonical
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

- [ ] Migration iki kez çalıştırıldığında aynı şema ve index'leri güvenle korur.
- [ ] 10.000 ardışık event append/recompute testinde zincir doğrulaması %100 başarılıdır.
- [ ] Duplicate identity aynı canonical event'i döndürür; çakışan payload fail-closed olur.
- [ ] Payload veya `prev_hash` mutation'ı verifier tarafından tespit edilir.
- [ ] Injected transaction failure sonrasında yeni event ve başarı ACK'i bulunmaz.
- [ ] Legacy backfill iki kez çalışır; her source trade için tek event üretir ve source satırını
  değiştirmez.
- [ ] `INSERT OR REPLACE` ledger write path'inde kullanılmaz; `trades` compatibility path'i
  bu pakette açıkça belgelenir.
- [ ] Yeni testler ephemeral `KUANTRA_DATA_DIR` ile çalışır; developer journal'ına yazmaz.
- [ ] Backend suite, focused ledger suite, `git diff --check` ve üç-OS CI yeşildir.

## Kesinlikle kapsam dışı

- Mevcut `trades` CRUD'ünün bu pakette tamamen kaldırılması veya UI yeniden yazımı.
- DuckDB projection rebuild/sync redesign.
- Parquet tick/order-book store, Rust/Tokio data plane, Arrow IPC/Flight.
- Broker/CSV/MT5/Polygon/TwelveData connector değişikliği.
- Live execution, FIX/DMA, reconciliation, HFT latency SLA veya kill-switch değişikliği.
- AI Auditor, local LLM, agent swarm, plugin download veya execution tool.
- Yeni remote dependency veya cloud event service.

## Migration path

1. Phase 0 exit approval ve baseline SHA doğrulanır.
2. Migration + repository + verifier önce bağımsız testlerle eklenir.
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

## Terra uygulama promptu (Phase 0 sonrası)

`docs/strategy/WORK-PACKAGE-TEMPLATE.md` kullanılarak yeni bir implementation promptu
oluşturulmalıdır. Prompt baseline olarak Phase 0'da onaylanan tam commit SHA'sını taşımalı,
bu dosyadaki kapsam dışı maddeleri aynen korumalı ve ilk adımda yalnız migration/repository
test planı sunmalıdır. Kodlama, Phase 0 approval kanıtı olmadan başlatılamaz.

