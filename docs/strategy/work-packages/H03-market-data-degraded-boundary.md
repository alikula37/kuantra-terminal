<!-- doc-role: current-work-package -->
# H03 — Runtime Degraded/Offline Market-Data Boundary

```yaml
work_package: H03
version: 1.0.0
status: InProgress
date: 2026-09-08
baseline_commit: cc0ad94
branch: codex/p1-wp01-evidence-ledger
strategy: KPR-001@current
depends_on: N02, P0-WP02
```

## Amaç

Network erişimi olmayan veya market-data açıkça devre dışı bırakılan Mac runtime’ında
Kuantra’nın gerçek veri varmış gibi görünmesini engellemek. Local import, review ve
export akışı çalışmaya devam ederken live market-data yüzeyi açıkça `UNAVAILABLE` veya
`DEGRADED` kalacak; retry mekanizması veri uydurmayacak.

## Davranış sözleşmesi

- `KUANTRA_MARKET_DATA_ENABLED` varsayılanı `true` olarak mevcut startup davranışını korur.
- Değer `false` olduğunda Binance stream task’ı başlatılmaz ve hiçbir socket bağlantısı denenmez.
- Network failure/stream disconnect mevcut gerçek veriyi silmez; yeni veri gelmeden `LIVE`
  veya complete market context iddiası yapılmaz.
- Health, ticker, desktop snapshot ve WebSocket snapshot aynı explicit market-data durumunu
  bildirir; disabled için `UNAVAILABLE`, başlamış ama veri alınamamış bağlantı için
  `DEGRADED` kullanılır.
- Local CSV/JSON import, trade review ve Evidence Pack export network olmadan çalışmaya devam eder.
- Testler gerçek network, exchange credential veya kullanıcı verisi kullanmaz; dependency
  injection ve network-denied fixture kullanır.

## Acceptance criteria

- [ ] Disabled config Binance stream’i başlatmaz; socket connect çağrısı yapılmadığı negative test ile kanıtlanır.
- [ ] Health/ticker/desktop/WebSocket contract’ları disabled ve degraded durumunu `LIVE` yerine açıkça taşır.
- [ ] Network failure retry path’i yeni tick/candle veya sıfır değer üretmez; incomplete context complete görünmez.
- [ ] Local import, review ve export network disabled iken regression testlerinden geçer.
- [ ] P0-WP02 ve desktop/native smoke regression’ları korunur.
- [ ] Focused test, full backend/frontend suite ve Mac local CI sonucu dokümana yazılır.

## Kesinlikle kapsam dışı

Yeni connector, yeni market-data schema/event type, funding/transfer ledger, live order,
credential/keychain yazımı, sentetik fiyat, frontend redesign, historical P2 soak/promotion,
Windows/Linux host kanıtı, signing/notarization ve release/tag.

## Uygulama dosya sınırı

- `backend/app/websocket/binance_client.py`, `backend/main.py`, `backend/app/api/endpoints.py`,
  `backend/desktop/bridge.py` ve ilgili config/health types.
- `frontend/src/types/index.ts`, `frontend/src/lib/bridge.ts`, `frontend/src/hooks/useWebSocket.ts`
  ve ilgili durum/test dosyaları.
- Yeni bounded backend/frontend tests; docs ve local-CI kanıtı.
