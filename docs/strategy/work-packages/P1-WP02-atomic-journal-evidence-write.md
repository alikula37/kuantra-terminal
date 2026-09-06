# P1-WP02 — Atomic Journal Evidence Write Adapter

```yaml
document_id: P1-WP02
version: 1.0.0
status: Active
date: 2026-09-06
baseline: b809fa1
strategy: KPS-001@1.0.0
adr: ADR-0002, ADR-0003
depends_on: P1-WP01 canonical ledger foundation
implementation_commits: 4dc7c22
```

## Problem

`SyncPipeline` daha önce compatibility `trades` satırını SQLite'a yazıp DuckDB'ye
yansıtıyor, fakat canonical `evidence_events` ledger'a hiçbir event yazmıyordu. TradingView
webhook doğrudan `insert_trade` çağırıyor, CSV import ise ledger provenance'ı kaybediyordu.
Bu nedenle kullanıcıya dönen journal kaydı ile kanıt zinciri arasında sessiz boşluk oluşabiliyordu.

## Karar

1. Journal mutation ve canonical evidence event aynı SQLite connection üzerinde
   `BEGIN IMMEDIATE` + `synchronous=FULL` transaction'ında commit edilir.
2. Ledger append başarısız, geçersiz veya identity-conflict ise compatibility trade satırı da
   rollback edilir; başarı ACK'i yalnız iki yazı commit edildikten sonra döner.
3. DuckDB projection commit sonrasında çalışır; DuckDB arızası canonical SQLite transaction'ını
   geri açmaz.
4. Event sınıflandırması deterministiktir:
   - yeni manual/webhook kaydı → `IntentRecorded`
   - yeni CSV kaydı → `LegacyTradeImported`
   - `OPEN` → `CLOSED` geçişi → `FillRecorded`
   - diğer mevcut trade düzeltmeleri → `TradeCorrected`
5. Idempotency key, trade kimliği + event türü + volatile timestamp'ler hariç mutation
   payload'ının SHA-256 özetiyle üretilir. Aynı identity aynı canonical snapshot'ı no-op yapar;
   farklı snapshot fail-closed conflict üretir.

## Değişen yüzeyler

- `EvidenceLedgerRepository.append_event_in_transaction`: caller-owned transaction sınırı.
- `SQLiteDriver.record_trade_with_evidence`: trade snapshot ve event'i tek transaction'a bağlar.
- `SyncPipeline.record_and_sync_trade`: provenance, event sınıflandırması ve deterministic
  idempotency üretir.
- CSV importer ve TradingView webhook: artık sync pipeline üzerinden canonical yazılır.
- `test_p1_wp01_evidence_ledger.py`: atomic commit, duplicate, conflict rollback, injected
  failure rollback ve CSV provenance regression testleri.

## Acceptance criteria

- [x] Yeni journal mutation'ı trade satırı ve evidence event'i birlikte commit eder.
- [x] Ledger exception'ı sonrası trade satırı ve event birlikte yoktur.
- [x] Aynı identity tekrarında event sayısı artmaz.
- [x] Aynı identity farklı payload ile kullanılırsa trade mutation rollback olur.
- [x] CSV event'i `LegacyTradeImported` ve filename provenance taşır.
- [x] Focused ledger suite: `14 passed`.
- [x] Full backend suite: `364 passed, 1 skipped`.
- [x] `git diff --check` başarılıdır.
- [ ] Remote three-OS CI: GitHub Actions kota/bütçe nedeniyle geçici disabled; reset sonrası
  `4dc7c22` için yeniden çalıştırılacak.

## Kesinlikle kapsam dışı

- Physical delete endpoint'inin tombstone/correction UX'e dönüştürülmesi.
- CCXT cancellation ve diğer doğrudan `sqlite_driver.update_trade` execution yolları.
- CSV batch'in bütün satırlar için tek all-or-nothing transaction'a taşınması.
- DuckDB projection rebuild, Parquet/tick store, Rust data plane veya UI değişikliği.
- Live execution, FIX/DMA, AI auditor veya remote event service.

## Açık risk ve sonraki iş

Legacy `sqlite_driver.insert_trade` ve `update_trade` compatibility API'leri hâlâ doğrudan
çağrılabilir; bu paket production journal giriş noktalarını `SyncPipeline` üzerinden kapatır,
fakat bütün tarihsel çağrıları henüz yasaklamaz. Bir sonraki paket, canonical event'lerden
rebuild edilebilir projection ve physical delete yerine immutable correction/tombstone sınırını
tanımlamalıdır.

## Değişiklik geçmişi

### 1.0.0 — 2026-09-06

- İlk atomic journal/evidence write adapter ve rollback/idempotency test paketi.
