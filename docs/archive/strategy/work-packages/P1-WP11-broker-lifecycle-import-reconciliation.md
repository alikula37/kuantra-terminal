<!-- doc-role: archived -->
> Historical reference only. Not a current work order. Unchecked acceptance items remain open;
> see [current status](../../../strategy/STATUS.md). Read only for a relevant task.

# P1-WP11 — Read-Only Broker Lifecycle Import ve Reconciliation

```yaml
document_id: P1-WP11
version: 1.0.1
status: Active
date: 2026-09-06
baseline: a1f138a
strategy: KPS-001@1.0.0
adr: ADR-0001, ADR-0002, ADR-0003
depends_on: P1-WP01 canonical evidence ledger, P1-WP10 CSV import provenance
implementation_commits: 4b23405
```

## Problem

CSV import journal snapshot üretiyordu; broker'ın ayrı order/fill gözlemleri,
partial fill ve fee toplamları canonical lifecycle olarak saklanmıyordu. Bu nedenle
“journal kaydı broker fill'iyle eşleşiyor mu?” sorusu ölçülebilir değildi.

## Karar

1. İlk entegrasyon gerçek exchange bağlantısı değil, açık bir JSON export envelope'ıdır:
   `{"orders": [...], "fills": [...]}`. Binance ve OKX fixture'ları aynı normalizer
   contract'ını kullanır; API pagination, credentials ve user stream bu paketin dışındadır.
2. Normalized lifecycle record şu kimlikleri taşır: `venue`, `record_type`, external
   order/fill id, symbol, side, status, order quantity, filled quantity, price/average
   price, fee/currency, occurred-at ve source row hash/number.
3. Order gözlemleri `VenueAck` veya rejected state için `VenueReject`; fill gözlemleri
   `FillRecorded` event'i olarak append-only evidence ledger'a yazılır. Local intent
   veya order submission varsayılmaz.
4. Idempotency aynı venue/account/source-file manifest ve normalized record identity
   için garantilidir. Aynı export tekrar işlendiğinde event çoğalmaz; farklı export
   snapshot'ları ayrı immutable observations olabilir.
5. Reconciliation şunları karşılaştırır: order filled quantity ↔ fill quantity toplamı,
   average price ↔ fill-weighted price, fee toplamı, duplicate order/fill id ve orphan
   fill. Eksik/çelişkili satırlar `UNRECONCILED` olur; otomatik düzeltme yapılmaz.
6. `POST /api/v1/broker/import-json` yalnızca local JSON dosyası kabul eder, 10 MB ile
   sınırlıdır, read-only broker gözlemlerini ledger'a yazar; canlı emir göndermez.

## Teknik teslimatlar

- `BrokerImportService` typed normalization ve Binance/OKX field aliases.
- UTF-8 JSON fixture envelope ve iki venue regression corpus'u.
- Append-only lifecycle event mapping, source hash provenance ve re-import idempotency.
- Quantity/price/fee/orphan/duplicate reconciliation report.
- Bounded local upload endpoint; invalid rows raw payload göstermeden raporlanır.

## Acceptance criteria

- [x] Binance fixture order/fill kayıtları normalize edilip `RECONCILED` raporlanıyor.
- [x] OKX `ordId/instId/sz/accFillSz/avgPx/uTime` alanları aynı contract'a map ediliyor.
- [x] Aynı export yeniden işlendiğinde ledger duplicate event üretmiyor.
- [x] Quantity, weighted price, fee, orphan ve duplicate farkları explicit discrepancy
  olarak dönüyor.
- [x] Eksik timestamp veya zorunlu identity alanı receipt time ile doldurulmuyor;
  row rejected ve import `UNRECONCILED` kalıyor.
- [x] Local JSON endpoint extension/size/venue sınırlarını uyguluyor.
- [x] Focused broker import suite: `6 passed`.
- [x] Full backend suite: `392 passed, 1 skipped`.
- [x] `git diff --check` başarılıdır.
- [ ] Remote three-OS CI: GitHub Actions kota/bütçe nedeniyle geçici disabled;
  reset sonrası `4b23405` için yeniden çalıştırılacak.

## Kesinlikle kapsam dışı

- Binance/OKX REST/WebSocket connector, API key/secret veya otomatik polling.
- CCXT/FIX/DMA write path, cancel/replace, live order veya position mutation.
- Broker snapshot'ını local journal trade'ine otomatik dönüştürme.
- Reconciliation farkını otomatik düzeltme veya PnL'e sessizce yansıtma.
- Tick/order-book reconciliation, market-data sequence recovery.

## Risk ve sonraki sınır

Bu paket broker export'undaki gözlemleri kanıt zincirine alır; export'un eksik veya
yanlış olmasını tek başına çözmez. Pilot ölçümü `reconciliation_unexplained_delta=0`
ve import row rejection oranını ayrı takip etmelidir. Gerçek Binance/OKX read-only
API sınırı P1-WP12 ile aynı normalizer'a bağlandı; credential scope, pagination,
rate-limit/backoff ve snapshot manifest kapıları geçmeden live execution açılmayacaktır.

## Değişiklik geçmişi

### 1.0.0 — 2026-09-06

- İlk fixture/export tabanlı broker lifecycle normalizer, ledger mapping ve
  reconciliation report.

### 1.0.1 — 2026-09-06

- Gerçek read-only API adapter'ı ve credential/manifest sınırı P1-WP12'ye ayrıştırıldı;
  bu paketin fixture/export kapsamı korunuyor.
