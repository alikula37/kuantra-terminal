<!-- doc-role: archived -->
# H03 — Runtime Degraded/Offline Market-Data Boundary

```yaml
work_package: H03
version: 1.0.0
status: Complete
date: 2026-09-08
baseline_commit: cc0ad94
implementation_commit: 62921f7
branch: codex/p1-wp01-evidence-ledger
strategy: KPR-001@current
depends_on: N02, P0-WP02
```

## Sonuç

`62921f7` ile `KUANTRA_MARKET_DATA_ENABLED` varsayılanı `true`, explicit `false` ise
Binance stream task/socket başlatılmıyor. Stream gerçek veri almadan ve network failure
sonrasında `DEGRADED`, disabled durumda `UNAVAILABLE`, gerçek tick/candle alındığında
`LIVE` bildiriyor; retry path fiyat/candle üretmiyor. Health, ticker, WebSocket,
desktop bridge ve frontend header aynı durumu taşıyor; stale fiyatla pozisyon close
edilmesi `LIVE` dışında reddediliyor. Status-only push event'i reconnect/degraded
geçişini UI'a taşırken finansal/market event uydurmuyor.

## Acceptance criteria

- [x] Disabled config Binance stream’i başlatmaz; socket connect çağrısı yapılmadığı negative test ile kanıtlanır.
- [x] Health/ticker/desktop/WebSocket contract’ları disabled ve degraded durumunu `LIVE` yerine açıkça taşır.
- [x] Network failure retry path’i yeni tick/candle veya sıfır değer üretmez; incomplete context complete görünmez.
- [x] Local import, review ve export network disabled iken regression testlerinden geçer.
- [x] P0-WP02 ve desktop/native smoke regression’ları korunur.
- [x] Focused test, full backend/frontend suite ve Mac local CI sonucu dokümana yazılır.

## Kanıt

- H03 focused backend: **7 passed**.
- Full backend: **615 passed, 2 warnings**.
- Frontend: **54 passed**; i18n **480/480**; TypeScript ve production build **PASS**.
- Mac local CI: **MERGE READY**; packaging preflight, arm64 PyInstaller ve native
  `wkwebview` smoke/controller readiness **PASS**.
- Source commit: `62921f72df12c3bf50cf10c05e903ad463d3ec00`; provenance `COMPLETE`;
  release-facing validator **PASS**.
- Executable SHA-256: `91308c4b60a0b9f5685fd3392d319a29e15b73189a56a1a96364f0e71d36a521`.
- `.app` artifact SHA-256: `1631e5e38d7b3f773567e7635d5055ea26b3893fab1b09aa58d0e9adc7c2b921`.
- Network/credential/user-data boundary: no credential, real user data or live order;
  network-denied behavior was fixture/DI tested, not treated as a public-network soak.

## Kalan sınırlar ve sonraki bağımlılık

H03 Mac runtime boundary is closed. Windows/Linux host behavior, signing/notarization,
second-host install, long P2 recovery soak, funding/transfer schema and live execution
remain out of scope. Next bounded package is **P1-WP22 R4 value-chain integration**;
weekly review/as-of rule work is R5 and remains separate.
