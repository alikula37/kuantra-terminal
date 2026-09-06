# P0-WP06A — Replay ve Excursion Veri Doğruluğu

```yaml
work_package: P0-WP06A
status: Verified
phase: Phase 0 - Truth & Safety Release
strategy: KPS-001@1.0.0
baseline_commit: 1326e5ecc3503cc8b08d12dc64a15a7413399213
owner: Axiom
implementer: lead + gpt-5.6-terra
```

## Problem ve karar

`replay_service.py:129-159` bulunmayan trade için 65.000 fiyatlı işlem ve rastgele mum üretir.
Kayıtlı mum varken de işlem zamanıyla ilgisiz son 300 mumu sabit entry/exit indekslerine bağlar.
`mae_mfe.py:44-55,146-149` piyasa geçmişini sorgulamadan SL/TP ve yüzdelik tahminlerle excursion
üretir. Stop-loss yokken iki modül de giriş fiyatının %1'ini 1R sayar. Replay exit sonrasındaki
mumlardan excursion üretmeye devam eder. UI, eksik hedef ve survival değerlerini 2,5R/%94 ile
doldurur. Mevcut testlerin bir kısmı bu davranışları beklemektedir.

Faz 0 kararı: yalnız kaydedilmiş, işlem zaman aralığını eksiksiz kapsayan 1m mumlar kullanılır.
Sonuçlar **mum bazlı yaklaşık** olarak etiketlenir. Mevcut DuckDB şeması venue/feed provenance
taşımadığı için kaynak doğrulandı iddiası kurulmaz. Broker fill veya tick replay kanıtı değildir.
Hedef önerisi optimizasyon doğrulaması gelene kadar `null` kalır.

## Kapsam

- `backend/app/db/duckdb_driver.py`: bounded time-range candle read; mevcut schema/write değişmez.
- `backend/app/db/sqlite_driver.py`: evidence örneklemesinde ISO-offset timestamp'leri UTC sıralama
  için opt-in read seçeneği; diğer çağrıların davranışı ve kayıtlar değişmez.
- Yeni `backend/app/quant/candle_evidence.py`: UTC zaman, OHLC, gap/duplicate ve risk doğrulaması.
- `backend/app/replay/replay_service.py`, `backend/app/quant/mae_mfe.py`.
- `backend/app/api/endpoints.py`: optimal-exits provenance/status aktarımı ve gerektiğinde replay hata sözleşmesi.
- `backend/app/ai/ai_auditor.py`: nullable excursion tüketicisinin uyumu ve uydurma hedef
  direktifinin kaldırılması; diğer legacy coaching hesapları bu pakette doğrulanmış sayılmaz.
- İlgili replay/MAE testleri + yeni veri aralığı regresyonları.
- `frontend/src/components/TradeReplayCanvas.tsx`, `MaeMfeVisualizer.tsx`, ilgili types ve
  yalnız gerekli test/helper/çeviri dosyaları.
- Gerçek React fetch/render/effect regresyonları için yalnız dev dependency `jsdom@27.4.0`;
  production bundle'a girmez. Varsayılan Node Vitest ortamı korunur, DOM testleri dosya bazlıdır.

## Davranış sözleşmesi

1. Replay, bilinmeyen trade/eksik geçmişte `NO_DATA` veya `UNAVAILABLE`, `reason`, `message`,
   `session_id:null`, boş mumlar ve `trade:null` döndürür; session kaydetmez. Başarılı durum `READY`.
2. Trade yalnız geçerli symbol/side/pozitif sonlu fiyat+qty ve entry/exit zamanlarıyla incelenir.
   Faz 0 replay kapalı işlemler içindir. Legacy timezone'suz zaman UTC kabul edilir ve açıklanır.
3. Zaman sorgusu [başlangıç, bitiş) aralığını kullanır; son 300 mum yerine ilgili trade penceresi.
   İşlem süresi en çok 20.000 dakika; bunun üzeri açık `WINDOW_TOO_LARGE` durumu.
4. Mumlar 1m zamanına hizalı, pozitif sonlu tutarlı OHLC olmalı. Aynı timestamp aynı OHLCV ise
   tekilleştirilir; çelişkili duplicate veya trade penceresinde tek bir eksik bar bile reddedilir.
5. Intrabar entry/exit belirsizliği `BAR_APPROXIMATION`, `source:DUCKDB_CANDLES`,
   `source_verified:false`, `timeframe:1m` provenance'ıyla açıklanır.
6. R ölçüleri yalnız doğru taraftaki pozitif stop-loss'tan hesaplanır. Eksik/yanlış stop'ta
   `risk_unit`, `r_multiple`, `mae_r`, `mfe_r` null olur; varsayılan %1 yoktur.
7. Replay pre-entry PnL/R/excursion göstermez. Exit sonrası excursion exit barında sabitlenir;
   `unrealized_pnl:null` ve mevcutsa kayıtlı `realized_pnl` gösterilir.
8. MAE/MFE aggregate yalnız doğrulanmış pencereyi kullanır. Atlanan trade'ler reason ile
   `excluded_trades` içinde; `total_candidates`, `total_analyzed`, `total_r_analyzed` ayrı verilir.
   Empty state ortalamaları ve `recommended_target_r` null; recommendation hiçbir zaman
   hardcoded/default değere dönmez. Survival oranı yalnız tarihsel betimleyici dağılımdır.
9. Replay/MAE UI HTTP/error/no-data durumunu açık gösterir; eski trade yanıtları güncel trade'i
   ezemez; istek hatası eski metriği görünür bırakmaz. Playback istekleri çakışmaz. Chart, async
   başarılı session render edildikten sonra kurulur ve cleanup yapılır.
10. Null ölçüler `—`; R grafiği yalnız sonlu MAE/MFE çiftlerini çizer. Hedef/insight uydurulmaz.
11. `r_multiple` brüt yönlü fiyat hareketi / geçerli kayıtlı stop mesafesidir; net PnL veya
    içe aktarılmış R değildir. Replay exit'te kayıtlı PnL'yi gösterir, bilinmiyorsa null kalır.
    Unrealized PnL yalnız lineer fiyat farkı × kayıtlı base quantity varsayımıdır; inverse/contract
    multiplier değerlemesi değildir. Eski store'da initial-stop history bulunmadığı açıklanır.
12. Aday seçimi en son 1.000 kapalı işlemi UTC entry time sırasıyla alır; candidate limit ve
    selection metadata'sı response'a taşınır. Stop dağılımında eşik teması ihlal sayılır (`<`).
13. Replay snapshot cache 32 session ile sınırlıdır; en eski UI snapshot çıkarılır, bu session'ın
    sonraki isteği 404 alır. Kaynak journal/evidence kaydı silinmez.

## Acceptance

- [x] Bilinmeyen trade, boş DB, DB unavailable, eski/alakasız mumlarda no-data ve session yok.
- [x] Gerçek temp DuckDB'de zaman aralığı/limit, UTC offset, gap ve duplicate testleri.
- [x] Long/short MAE/MFE elle hesaplanan fixture ile doğrulanır.
- [x] Eksik stop, NaN/Inf/invalid OHLC, ters zamanlar fail-closed.
- [x] Replay entry/exit zaman indeksleri ve post-exit excursion freeze; deterministic replay.
- [x] Eksik örnekler aggregate/recommendation içine sızmaz; sayımlar doğru.
- [x] UI null/error/provenance davranışı ve async chart kurulumu jsdom ile doğrulanır.
- [x] Locked backend suite, frontend test/build, audit ve 3-OS CI/smoke geçer.

## Migration / rollback / kapsam dışı

DB migration veya veri silme yoktur. API'ye status/provenance ve nullable ölçüler eklenir; UI aynı
committe taşınır. Önceki üretilmiş metrikler persisted değildir. Kayıtlı kullanıcı trade'leri korunur.
Order-flow/FIX/DMA bulguları P0-WP06B'de, canonical event ledger Faz 1'de; tick replay Faz 2'dedir.
Yeni broker/data aboneliği, canlı order, AI otoritesi veya store rewrite bu pakete dahil değildir.

## Local gate kanıtı

- Locked Python 3.11: `328 passed, 1 skipped` (full backend suite).
- Frontend: `42 passed` / 9 test files; i18n 478/478; production build successful.
- `npm audit --omit=dev --audit-level=moderate`: 0 vulnerabilities.
- `git diff --check`: clean.
- Remote PR CI run `34018288308` passed on Windows, macOS and Ubuntu; every OS completed
  backend tests, frontend tests/audit/build, desktop build and smoke test.

## Remote kanıt

- Implementation commit: `d517c340e31a222bc00c685d6c94f16688c03054`.
- PR run: `34018288308` — all three OS jobs successful.
- Matching push run: `34018286678` — triggered for the same SHA.
- This package does not authorize live execution, tick replay, or a validated target optimizer.
