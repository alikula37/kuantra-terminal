<!-- doc-role: archived -->
> Historical reference only. Not a current work order. Acceptance evidence and remaining
> boundaries are recorded here; see [current status](../../../strategy/STATUS.md).
> Read only for a relevant task.

# P1-WP19 — Funding, Corrections & Account Reconciliation Contract

```yaml
work_package: P1-WP19
version: 1.0.0
status: Verified
date: 2026-09-08
baseline_commit: e4ca324
implementation_commit: f67e732
branch: codex/p1-wp01-evidence-ledger
strategy: KPR-001@current
depends_on: P1-WP18
```

## Problem ve amaç

Order/fill lifecycle kanıtı tek başına hesabın açılış bakiyesini, funding akışını,
transferleri, düzeltmeleri veya realized/unrealized ayrımını kanıtlamaz. Bu alanlar
trade reconciliation içine sessizce katılırsa Kuantra yanlış bir net PnL veya account
state üretebilir. P1-WP19’un amacı desteklenen dar read-only/fixture sınırında bu olay
türlerini açıkça sınıflandırmak ve veri eksikliğini `UNKNOWN`/`NOT_AVAILABLE` olarak
korumaktır.

Bu paket tam hesap muhasebesi veya yeni venue desteği değildir. Kullanıcı verisi,
credential, canlı emir ve migration apply kullanılmaz.

## Beklenen davranış sözleşmesi

1. Funding, trade fee, transfer, rebate, liquidation/ADL ve manual correction ayrı
   event türleri olarak normalize edilir; biri diğerinin yerine varsayılmaz.
2. Opening balance/position veya account coverage yoksa zero/flat account state
   uydurulmaz. Rapor `NOT_AVAILABLE`/`PARTIAL` ve coverage reason taşır.
3. Realized PnL, unrealized PnL ve cash movement ayrıdır. Transfer, funding veya fee
   otomatik olarak realized PnL’ye eklenmez; currency ve signed Decimal semantiği
   P1-WP18’ten devralınır.
4. Correction eski kanıtı silmez veya yeniden yazmaz; source lineage, effective time
   ve correction relationship ayrı taşınır. Geç gelen düzeltme yeni immutable event’tir.
5. Liquidation/ADL veya venue’ye özgü hesap olayı için yeterli kaynak yoksa explicit
   `UNSUPPORTED`/`UNKNOWN` sonucu üretilir; valid account PnL claim’i verilmez.
6. Account/source/market identity P1-WP17 sözleşmesine bağlı kalır; aynı external id
   farklı account veya source arasında çakışmaz.

## İlk dosya/test kapsamı

- `backend/app/services/broker_import_service.py` ve gerekirse ayrı bounded account
  reconciliation service/model.
- Evidence event normalization/provenance; mevcut ledger schema’nın dışına taşan
  migration ancak ayrı onaylı iş olarak ele alınır.
- `backend/tests/` funding, transfer, correction, coverage ve negative fixtures.
- P1-WP18 decimal/fee tests ve P1-WP17 source identity regression korunur.

## Acceptance criteria

- [x] Önce kırmızı, sonra yeşil: funding/transfer/fee/correction event’leri ayrı
  normalize edilir ve signed Decimal/currency korunur.
- [x] Opening balance veya position coverage eksik olduğunda zero/flat PnL üretilmez;
  explicit coverage state ve discrepancy/report reason döner.
- [x] Funding ve transfer realized/unrealized PnL’ye sessizce karışmaz; aynı currency
  içinde bile event türü kaybolmaz.
- [x] Correction yeni immutable evidence ve lineage üretir; eski event/provenance
  silinmez; late correction yeniden importta idempotent kalır.
- [x] Liquidation/ADL/venue-specific unsupported event’ler fail-closed görünür;
  desteklenmeyen account claim’i production capability olarak açılmaz.
- [x] Multi-account, source identity ve market type collision negative testleri geçer;
  P1-WP17/P1-WP18 regression yeşil kalır.
- [x] Odak testleri `8 passed`; tam backend suite `587 passed, 2 warnings`; Mac local CI
  `MERGE READY` olarak kaydedildi: frontend `51`, production build, arm64 desktop build,
  WKWebView native smoke ve packaging preflight geçti.
- [x] Exact implementation commit `f67e732`; changed files, accounting limitations ve sonraki P1-WP20 economic
  dedup/lifecycle bağımlılığı bu kayda yazılır.

## Verified implementation notes

- `AccountReconciliationService` funding, transfer, trade fee, rebate, liquidation/ADL
  ve manual correction kayıtlarını ayrı `account_event_kind` değerleriyle normalize eder.
- Numeric amount değerleri P1-WP18 ile aynı `DECIMAL_STRING_V1` ve explicit currency
  unit sözleşmesini kullanır; bilinmeyen currency aggregation'a dahil edilmez.
- Mevcut ledger event sözlüğünde funding/transfer için ayrı event type bulunmadığı için
  bu gözlemler `SCHEMA_EVENT_TYPE_PENDING` olarak raporlanır ve kanonik ledger'a yazılmaz.
  Fee/rebate `FeeAdjusted`, manual correction `TradeCorrected` olarak append-only
  yazılabilir; correction hedefi `causation_id` ve provenance lineage ile korunur.
- Bu paket realized/unrealized PnL hesaplamaz; opening/account/mark coverage yoksa
  `NOT_AVAILABLE` veya `PARTIAL` döner ve zero/flat değer uydurmaz.

## Kapsam dışı

Tam exchange statement coverage, tax/accounting advice, cross-currency conversion,
leverage/margin modelinin tamamı, historical balance reconstruction without source,
economic trade grouping, yeni connector, live order, AI karar/emir ve gerçek kullanıcı
verisi migration’ı.
