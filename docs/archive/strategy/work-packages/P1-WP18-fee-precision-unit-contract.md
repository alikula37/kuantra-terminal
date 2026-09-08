<!-- doc-role: archived -->
> Historical reference only. Not a current work order. Acceptance evidence and remaining
> boundaries are recorded here; see [current status](../../../strategy/STATUS.md).
> Read only for a relevant task.

# P1-WP18 — Fee, Precision & Unit Contract

```yaml
work_package: P1-WP18
version: 1.1.0
status: Verified
date: 2026-09-08
baseline_commit: d5d6f07
implementation_commit: 0c7d11f
branch: codex/p1-wp01-evidence-ledger
strategy: KPR-001@current
depends_on: P1-WP17
```

## Problem ve amaç

P1-WP17 source identity kaybını kapattı. Sonraki doğruluk riski, lifecycle import ve
reconciliation katmanında finansal sayıların Python `float` ile işlenmesi ve fee
semantiğinin eksik/zero/rebate/currency ayrımını her durumda açıkça taşımamasıdır.
`None` fee bilinmeyen iken `sum(fill.fee or 0.0)` ile sessizce zero gibi davranmamalıdır;
çoklu fee currency de tek bir ekonomik toplam gibi birleştirilmemelidir.

Bu paket yalnız desteklenen read-only/fixture lifecycle kayıtlarının decimal, unit ve
fee contract'ını kurar. Net account PnL, funding, opening balance, position mode veya
yeni venue desteği bu paketin sonucu değildir.

## Beklenen davranış sözleşmesi

1. Quantity, price ve fee amount için canonical decimal temsili ve deterministic
   round-trip tanımlanır; binary float yuvarlama reconciliation sonucunu belirlemez.
2. Missing, explicit zero ve signed rebate birbirinden ayrılır. Fee amount varsa fee
   currency yokluğu bilinmeyen olarak kalır; USD varsayımı yapılmaz.
3. Farklı fee currency'leri ayrı tutulur. Currency bilinmiyor veya order/fill fee
   currency'leri karşılaştırılamıyorsa sonuç `UNRECONCILED`/açık discrepancy olur;
   valid finansal eşleşme üretilmez.
4. Her numeric alanın birimi explicit olur: order quantity, fill quantity, price ve
   fee amount birbirine veya USD'ye sessizce çevrilmez.
5. Known zero, missing ve malformed/NaN/Inf input için ayrı negative testler bulunur.
   Locale-specific sayı metni veya implicit rounding reddedilir; import raw row/secret
   yazmadan bounded rejection üretir.
6. Mevcut v1 evidence/provenance ve P1-WP17 source identity korunur; gerçek kullanıcı
   DB'si, migration apply veya credential kullanılmaz.

## İlk dosya/test kapsamı

- `backend/app/services/broker_import_service.py`
- Gerekirse read-only mapper ve versioned normalized lifecycle payload'ı.
- `backend/tests/test_p1_wp11_broker_import.py`
- `backend/tests/test_p1_wp12_read_only_api_sync.py`
- Gerekirse bağımsız decimal/fee fixture'ları; mevcut venue/market desteği genişletilmez.

## Acceptance criteria

- [x] Önce kırmızı, sonra yeşil: `0.1 + 0.2`, küçük unit ve string round-trip değerleri
  exact/deterministic reconciliation üretir.
- [x] Missing fee zero sayılmaz; explicit zero bilinen zero olarak korunur.
- [x] Signed negative rebate ve pozitif fee ayrı semantik ile saklanır; fee currency
  provenance'ta korunur.
- [x] Multi-currency fee toplama, unknown currency ve order/fill currency mismatch
  explicit discrepancy üretir; sessiz netleme yoktur.
- [x] NaN, Inf, locale string, negatif quantity/price ve implicit unit dönüşümü fail-closed
  reddedilir; mevcut geçerli fixture'lar bozulmaz.
- [x] v1 source/provenance/idempotency compatibility ve P1-WP17 source identity regression
  testleri geçer; raw payload/credential ledger'a girmez.
- [x] Odak testleri `30 passed, 2 warnings`; tam backend suite `579 passed, 2 warnings`;
  Mac local CI `MERGE READY` olarak kaydedildi: frontend `51`, production build, arm64
  desktop build, WKWebView native smoke ve packaging preflight geçti.
- [x] Exact implementation commit `0c7d11f`; changed files, unsupported/unknown
  semantics ve sonraki P1-WP19 funding/accounting bağımlılığı bu kayda yazıldı.

## Kapsam dışı

Funding/corrections/opening balance/realized-unrealized PnL, economic trade grouping,
CSV formatlarının tamamını yeniden tasarlama, yeni exchange connector, live order,
AI karar/emir ve gerçek kullanıcı verisi migration'ı.

## Verified implementation notes

- Lifecycle numeric values are kept as bounded `Decimal` internally and emitted as
  canonical `DECIMAL_STRING_V1` evidence values with explicit venue-native units.
- Fee reconciliation distinguishes `NOT_PROVIDED`, `UNKNOWN`, `RECONCILED` and
  `UNRECONCILED`; missing fee data is never substituted with zero.
- This package does not establish account PnL, funding coverage or economic trade
  grouping. Those claims remain blocked behind the next bounded work packages.
