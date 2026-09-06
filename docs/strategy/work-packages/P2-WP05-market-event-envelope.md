# P2-WP05 — Canonical Market Event Envelope ve Hash Chain

```yaml
document_id: P2-WP05
version: 1.0.0
status: Active
date: 2026-09-06
baseline: d2a68e6
strategy: KPS-001@1.0.0
adr: ADR-0001, ADR-0002
depends_on: P2-WP02 Binance Snapshot + Delta Sequence Validator, P2-WP04 Binance Depth Payload Normalization ve Venue Projection
implementation_commits: pending
```

## Problem

Depth payload'ı process içinde normalize edilip book projection'a uygulanabiliyor;
ancak restart, replay ve audit için canonical event identity, deterministic
payload hash ve append-only ordering kaydı yok. Trade Evidence Ledger'dan farklı
olarak market event hacmi daha yüksek olacağı için bu paket yalnızca envelope
kontratını ve in-memory chain doğrulamasını kurar; disk storage kararını tek
proses yazıcıya bağlamaz.

## Karar

1. Snapshot ve sequence-approved delta event'leri `MARKET_EVENT_V1` envelope'ına
   çevrilir. Normalize payload, source identity, provenance ve `payload_sha256`
   birlikte tutulur.
2. Chain `GENESIS_HASH`, `prev_hash`, monoton `chain_sequence` ve `event_hash`
   üretir. Aynı source identity aynı payload ile tekrar gelirse idempotent
   sonuç döner; farklı payload identity conflict olarak reddedilir.
3. `GAP_DETECTED`, `REJECTED` veya `STALE_IGNORED` sequence sonucu canonical
   applied update olarak yazılamaz. Gap telemetry'si sonraki event-observation
   tablosunun işidir; sentetik update zincire giremez.
4. Offline fixture/normalizer kullanıldığı için envelope `source_verified=false`
   kalır. Hash bütünlüğü transport gerçekliği veya durable persistence iddiası
   değildir.

## Teknik teslimatlar

- `MarketEventEnvelope` ve `MarketEventChain`.
- Snapshot/update source identity ve idempotency conflict kontrolü.
- Payload SHA-256 + prev/event hash zinciri.
- Read-only `verify()` integrity raporu.
- Canonical JSON, provenance ve sequence decision bağlama regression suite'i.

## Acceptance criteria

- [x] Snapshot ve APPLIED update deterministik envelope/hash üretir.
- [x] Duplicate source identity idempotent, farklı içerik conflict olur.
- [x] APPLIED dışı sequence canonical chain'e giremez.
- [x] Payload/prev/event hash mutasyonu verifier tarafından görünür.
- [x] `source_verified=false` offline kapsamda zorunludur.
- [x] Focused suite: `6 passed`.
- [ ] Full backend suite: implementation commit sonrası yeniden çalıştırılacak.
- [ ] Remote CI: GitHub Actions kota/bütçe nedeniyle geçici disabled.

## Kesinlikle kapsam dışı

- SQLite/Parquet/DuckDB durable market-event writer.
- Websocket/REST transport, reconnect ve real-feed validation.
- Rust/Tokio data plane veya Arrow IPC.
- Source verification promotion, UI veya live execution.

## Risk ve sonraki sınır

In-memory chain restart sonrası kaybolur ve yüksek hacim benchmark'ı yapmaz.
Bir sonraki paket envelope'ı bounded append-only local segment writer'a veya
Parquet batch sink'e bağlamalı; tek writer, fsync/durability ve recovery drill'i
ayrı ölçülebilir kapılar olarak ele alınmalıdır.

## Değişiklik geçmişi

### 1.0.0 — 2026-09-06

- Canonical market event envelope, source identity/idempotency ve in-memory hash
  chain sözleşmesi tanımlandı.
