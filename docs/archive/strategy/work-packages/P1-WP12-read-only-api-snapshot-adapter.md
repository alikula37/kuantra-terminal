<!-- doc-role: archived -->
> Historical reference only. Not a current work order. Unchecked acceptance items remain open;
> see [current status](../../../strategy/STATUS.md). Read only for a relevant task.

# P1-WP12 — Read-Only API Snapshot Adapter ve Credential Scope

```yaml
document_id: P1-WP12
version: 1.0.0
status: Active
date: 2026-09-06
baseline: 4b23405
strategy: KPS-001@1.0.0
adr: ADR-0001, ADR-0002, ADR-0003
depends_on: P0-WP07 OS keychain boundary, P1-WP11 broker lifecycle import
implementation_commits: 5aa2723
```

## Problem

P1-WP11 yerel Binance/OKX export dosyasını canonical order/fill lifecycle'a
alıyordu; ancak gerçek broker snapshot'ı için credentials, pagination ve retry
kanıtı yoktu. Bu boşluk doğrudan execution engine'i yeniden kullanarak kapatılırsa
read-only import ile order-write yüzeyi birbirine karışır ve “reconciled” raporu
eksik sayfaları gizleyebilir.

## Karar

1. İlk API connector yalnızca `binance_spot`, `binance_futures` ve `okx` için
   CCXT'nin `fetch_orders` ve `fetch_my_trades` çağrılarını kullanır. `create_*`,
   `cancel_*`, `edit_*`, `withdraw`, `transfer` ve margin/position write metotları
   proxy seviyesinde engellenir.
2. OS keychain referans metadata'sına `permission_scope=READ_ONLY` eklenir.
   Phase 4 execution gate'leri kabul edilene kadar credential manager başka bir
   scope kaydetmez; API route write-capable credential ile sync başlatamaz.
3. Pagination `since` + son timestamp + 1 kuralıyla ilerler. Rate-limit/network/
   timeout hataları sınırlı exponential backoff ile yeniden denenir; retry sayısı
   snapshot manifest'e yazılır. Cursor ilerlemiyorsa veya `max_pages` doluyorsa
   snapshot `complete=false` kalır.
4. Her sync, normalize edilmiş sayfa hash'leri, page/request/row sayıları,
   requested time bounds, scope ve stable `snapshot_sha256` taşıyan secret-free
   manifest üretir. Manifest ledger'a yalnızca summary hash ve bounded counters
   olarak girer; raw CCXT `info` veya credentials asla yazılmaz.
5. Incomplete snapshot import edilebilir bir gözlem olarak saklanabilir, fakat
   report ve reconciliation status `UNRECONCILED` olur. Partial fetch başarı gibi
   sunulmaz.
6. `POST /api/v1/broker/sync-read-only` local evidence ledger'a yalnızca
   normalized lifecycle event'leri ve manifest provenance'ını yazar; broker'a
   emir göndermez.

## Teknik teslimatlar

- `ReadOnlyBrokerSyncService` ve `ReadOnlyExchangeClient` proxy'si.
- Binance Spot/Futures ve OKX CCXT credential/config factory.
- Bounded order/fill pagination, retry/backoff, timestamp cursor ve duplicate
  page deduplication.
- `ReadOnlySnapshotManifest` hash validation ve incomplete snapshot gate'i.
- Credential reference schema migration (`permission_scope` default `READ_ONLY`).
- `/api/v1/broker/sync-read-only` route.
- Injected fake transport ile 6 focused contract testi; canlı exchange çağrısı yok.

## Acceptance criteria

- [x] Sadece read-only fetch metotları çağrılıyor; order-write proxy erişimi bloklanıyor.
- [x] Rate-limit retry/backoff bounded ve request count manifest'e yazılıyor.
- [x] Timestamp cursor ilerlemesi ve `max_pages` sınırı test ediliyor.
- [x] Snapshot digest tamper testinde fail-closed oluyor.
- [x] Credential scope SQLite metadata'sında `READ_ONLY` olarak migration-safe tutuluyor.
- [x] Incomplete snapshot `UNRECONCILED` olarak raporlanıyor.
- [x] Event provenance `broker_api_snapshot` ve manifest summary hash taşıyor.
- [x] Focused suite: `6 passed`.
- [x] Full backend suite: `397 passed, 1 skipped`.
- [x] `git diff --check` başarılıdır.
- [ ] Remote three-OS CI: GitHub Actions kota/bütçe nedeniyle geçici disabled;
  reset sonrası implementation commit'i için yeniden çalıştırılacak.

## Kesinlikle kapsam dışı

- CCXT order create/cancel/replace, withdrawal, transfer veya position mutation.
- WebSocket user-data stream, listen-key recovery ve real-time reconciliation.
- Exchange-specific historical backfill guarantees beyond the bounded CCXT API.
- Raw broker response, API key, secret, passphrase veya `info` payload'ını ledger'a
  yazmak.
- Imported snapshot'ı otomatik local intent/journal trade'ine dönüştürmek.

## Risk ve sonraki sınır

CCXT'nin exchange adapter'ı her venue için aynı pagination semantiğini garanti
etmez; bu nedenle manifest, cursor warning ve `complete=false` durumu ürünün
kanıt sözleşmesidir. Phase 4'e geçmeden önce gerçek testnet hesaplarıyla bir
connector certification matrix, position/balance reconciliation ve user-stream
sequence recovery ayrıca doğrulanmalıdır.

## Değişiklik geçmişi

### 1.0.0 — 2026-09-06

- Read-only CCXT API snapshot adapter, keychain permission scope, pagination/
  backoff ve snapshot manifest doğrulaması tanımlandı ve uygulandı.
