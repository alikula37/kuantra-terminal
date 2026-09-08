<!-- doc-role: archived -->
> Historical reference only. Not a current work order. Unchecked acceptance items remain open;
> see [current status](../../../strategy/STATUS.md). Read only for a relevant task.

# P0-WP02 — Market Data Truth Contract ve Fabricated Fiyat/Latency Temizliği

```yaml
work_package: P0-WP02
status: Verified
phase: Phase 0 - Truth & Safety Release
strategy: KPS-001@1.0.0
adr: ADR-0003
baseline_commit: ab5a2cf03e1593a80de55fe54a4fb25107d6dabb
owner: lead-agent
implementer: gpt-5.6-terra
verified_by: lead-agent
```

## Problem ve risk

Binance stream başlamadan backend fiyatı `65000`, latency'yi `12ms`; frontend store ise fiyatı
`65420.50`, latency'yi `12ms` ve tick volume'ünü `0.5` olarak üretir. Tick geldiğinde latency
rastgele 8–24ms seçilir. Bağlantı hatası logu “simulated live feed” der. Binance iki stream için
yanlış raw URL kullanır ve combined envelope parse etmez. Dashboard veri yokken pozisyonu `0.0`
exit price ile kapatabilir.

## İstenen sonuç

İlk gerçek tick gelene kadar fiyat, event timestamp ve event age `null` olmalı; durum açıkça
`NO_DATA` olmalıdır. Gerçek trade event'inden sonra `LIVE` durumuna geçilmeli ve yalnız
`receive_wall_clock - exchange_event_time` ile hesaplanan, doğru adı verilmiş `event_age_ms`
yayınlanmalıdır. Bağlantı kaybı veri simüle etmemeli. UI null state'i göstermeli ve fiyat yokken
pozisyon kapatma isteği backend'e gönderilmemelidir. Paper order'a fiyat verilmemişse hiçbir trade
yazmadan açık reject dönmelidir.

## Dosya kapsamı

Değiştirilebilir:

- `backend/app/websocket/binance_client.py`
- `backend/app/services/execution/ccxt_engine.py` — yalnız paper fallback/no-price davranışı
- `backend/app/api/endpoints.py` — market ticker, compliance ve websocket snapshot uyumu
- `backend/desktop/bridge.py` — snapshot uyumu
- `frontend/src/stores/marketStore.ts`
- `frontend/src/hooks/useWebSocket.ts`
- `frontend/src/lib/bridge.ts`
- `frontend/src/types/index.ts`
- `frontend/src/components/Header.tsx`
- `frontend/src/components/DashboardView.tsx` — yalnız no-price close fail-closed davranışı
- İlgili backend/frontend testleri

Kapsam dışı:

- Order/fill lifecycle veya Evidence Ledger
- Depth/order-book sequence recorder
- Replay/MAE/MFE ve order-flow fake data
- WebView/IPC mimarisi
- UX redesign veya yeni component sistemi
- Canlı execution açılması

## Davranış sözleşmesi

1. `BinanceStreamClient` başlangıçta `last_price`, `last_tick_time` ve `event_age_ms` için `None`
   taşır; hardcoded fiyat/latency yoktur.
2. Binance combined URL `/stream?streams=<trade>/<kline>` formatındadır; combined `{stream,data}`
   envelope ile doğrudan event payload ikisi de parse edilir.
3. Trade event age, receive wall-clock milliseconds eksi exchange event time'dır; negatif değer
   clock skew nedeniyle sıfıra clamp edilebilir. Rastgele sayı kullanılmaz.
4. Reconnect yolu tick/candle üretmez ve “simulated feed” iddia etmez.
5. `/market/ticker` ilk tick öncesi `status: NO_DATA`, `price: null`, `event_age_ms: null`,
   `timestamp: null` döner. Tick sonrası `status: LIVE` ve gerçek değerleri döner.
6. Desktop/browser snapshot nullable fiyatı güvenle taşır. Fiyat yokken open positions kaybolmaz;
   PnL/current price alanları `null` ve market-data durumu `NO_DATA` olur.
7. Frontend store fabricated başlangıç fiyatı/age/time/volume içermez. Header ilk veri öncesi
   `AGE: —`, gerçek tick sonrası ölçülen event age'i gösterir.
8. Dashboard, market price yokken `exit_price: 0` göndermez ve pozisyonu yerel listeden çıkarmaz;
   kullanıcıya açık bir hata gösterir.
9. Paper order price yok/0/non-finite ise risk reject olur; `65000` fallback kullanılmaz ve
   `sync_pipeline.record_and_sync_trade` çağrılmaz.
10. İç isimlendirmede `latency_ms` yerine `event_age_ms` kullanılır; bu ölçüm round-trip latency
    olarak pazarlanmaz.

## Acceptance criteria

- [x] Backend initial/no-data contract testi.
- [x] Combined URL ve envelope parse regression testi.
- [x] Deterministic event-age hesabı testi; random bağımlılığı yok.
- [x] Reconnect wait sırasında market event üretilmediği testli.
- [x] `/market/ticker`, websocket ve desktop snapshot no-data testleri.
- [x] Paper no-price reject ve zero persistence testleri.
- [x] Frontend store başlangıç durumu ve gerçek tick güncellemesi testi.
- [x] Header no-data görünümü ve dashboard close fail-closed testi.
- [x] `rg` ile production scope'ta ilgili fabricated başlangıç/fallback değerleri yok.
- [x] Tam backend ve frontend test suite geçer; TypeScript/Vite build geçer.
- [x] `git diff --check` temizdir.

## Teslim raporu

Terra commit/push yapmaz. Değişen dosyaları, exact test/build komutlarını, acceptance eşlemesini,
bilinen riskleri ve `git status --short` çıktısını lead agent'a gönderir.

## Doğrulama kaydı — 2026-09-05

- Lead-agent temiz ve izole `KUANTRA_DATA_DIR` ile tam backend suite: `257 passed, 1 skipped`
  (`36.09s`).
- Tam frontend suite: 6 dosyada `29 passed` (`3.74s`).
- i18n kontrolü: TR/EN/DE dillerinde 478 anahtar, eksik/bozuk anahtar yok.
- TypeScript ve Vite production build: exit `0`; 1.913 modül işlendi.
- Production-scope fabricated değer taraması: eşleşme yok.
- `git diff --check`: exit `0`; Windows checkout için yalnız line-ending uyarıları.
- Lead review düzeltmesi: trade side fiyat hareketinden türetilmez. Binance `m` flag'i gerçek
  aggressor side'a çevrilir; eksik/geçersiz değer `UNKNOWN` olur.
