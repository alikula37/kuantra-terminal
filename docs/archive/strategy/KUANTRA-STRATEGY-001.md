<!-- doc-role: archived -->
> Historical reference only. Not a current work order. Unchecked acceptance items remain open;
> see [current status](../../strategy/STATUS.md). Read only for a relevant task.

# KPS-001 — Kuantra Ürün ve Mimari Stratejisi

```yaml
document_id: KPS-001
version: 1.1.0
status: Accepted
date: 2026-09-08
product_baseline: v1.4.0
commit: 2420ff9b299b69e57166f5ca7df681bc49e2f31c
requested_tag: v1.4.0-production
requested_tag_found: false
reviewed_local_tag: v1.4.0
decision_owner: Kuantra product/architecture leadership
```

> Bu belge pazarlama iddialarını değil, incelenen kodun davranışını ve dış kaynakların
> doğrulanabilir kapsamını esas alır. Rakip özellikleri bağımsız performans kanıtı değil,
> 2026-09-05 tarihinde incelenen şirket beyanlarıdır; bu sürümde yeniden web doğrulaması
> yapılmadı. Bölüm 2'deki kod audit'i `2420ff9` tarihsel baseline'ıdır, güncel açık
> hata listesi değildir. Güncel kod bulguları, kanıt sınırları ve kalan iş sırası
> [KRR-001](ROADMAP-REVIEW-2026-09-08.md) içindedir. Rekabet yüzdeleri öznel mimari
> karşılaştırma puanlarıdır; ölçülmüş pazar payı veya istatistiksel ürün yakınlığı değildir.

Faz süreleri mühendislik tahminidir, takvim taahhüdü değildir. Uygulanmış WP sayısı
faz çıkışını kanıtlamaz: bugün gerçek kullanıcı/pilot verisi yoktur; Faz 1 ve Faz 2'nin
kullanıcı exit kriterleri açık kalır. İlk değer akışı AI ve live execution olmadan
import, reconciliation, Evidence Pack ve haftalık review ile tamamlanmalıdır.

## 1. Yönetici kararı

### Tek cümlelik konumlandırma

**Kuantra, discretionary crypto/perps traderının her işlemini broker lifecycle'ı, piyasa
bağlamı, risk kararı, playbook disiplini ve kullanıcı review'u ile yeniden üretilebilir
bir Trade Evidence Pack'e dönüştüren local-first Execution Intelligence & Trade Forensics
Workstation'dır.**

Kaynak bağlı read-only AI incelemesi koşullu sonraki fazdır; ürünün ilk değer önerisi
veya güvenilirlik otoritesi değildir.

### İlk giriş pazarı

İlk pazar **Binance ve OKX kullanan aktif discretionary crypto perpetual traderlarıdır**.
İlk satılan entegrasyon canlı order entry değil; read-only API/CSV import, broker reconciliation,
kanıta dayalı replay ve haftalık karar incelemesidir.

Diğer seçenekler reddedilmiştir:

- **MT5/forex:** mevcut MT5 yüzeyi mock; terminal/Windows ve broker parçalanması yüksektir.
- **Futures/prop:** lisanslı tick/depth maliyeti ve connector/certification sayısı erken aşamada
  orantısızdır.
- **BIST:** mevcut adapter, veri anlaşması ve talep kanıtı yoktur.
- **Genel multi-asset:** güvenilir tek workflow oluşmadan kapsamı ve destek matrisini patlatır.

### Şimdi yap

1. Pazarlama ve UI'daki üretim/HFT/FIX/LLM iddialarını gerçek durumla eşleştir.
2. Normal ürün akışındaki bütün sentetik fallback'leri kaldır; `NO_DATA`, `STALE`, `SIMULATED`
   durumlarını görünür ve makinece test edilebilir yap.
3. Append-only Evidence Ledger, deterministic risk ve immutable correction modelini kur.
4. Binance/OKX read-only order/fill import ve günlük reconciliation geliştir.
5. Gerçek market context kullanan, gap'leri saklamayan deterministic replay/MAE/MFE üret.
6. Her trade için dışa aktarılabilir Trade Evidence Pack oluştur.

### Sonra yap

1. Profil sonucu gerektiriyorsa Rust/Tokio feed recorder ve sequence validator.
2. Parquet market history, DuckDB projection ve Arrow IPC bulk aktarım.
3. Kaynak bağlı, schema-constrained Local AI Auditor ve BYOK.
4. Canlı işlem kapıları kapandıktan sonra tek venue native controlled execution.
5. Ürün talebi kanıtlandıktan sonra teams/prop ve izinli plugin SDK.

### Asla yapma

- AI'a veya plugin'e doğrudan emir otoritesi verme.
- Synthetic benchmark ile HFT, institutional DMA veya sub-10µs uçtan uca iddiası üretme.
- Copy trading, flash-loan, biometrics ve “her markette terminal”i ürün çekirdeği yapma.
- Audit amacıyla blockchain ekleme; önce doğru event semantics ve imzalı root üret.
- Piyasa verisi boşken tahmini/fabricated değeri gerçek kanıt gibi gösterme.

### Dondurulacak veya Experimental yapılacak yüzeyler

`CCXT live execution`, `FIX/DMA`, internal matching/order book, AI swarm, LocalGGUF adıyla
sunulan sentetik inference, DEX/flash-loan, copy trading, biometrics, MT5, Polygon, TwelveData,
seed order-flow/heatmap ve plugin ekosistemi varsayılan UI/API'dan çıkarılmalıdır. Kod kaldırılana
kadar `Experimental — no production use` flag'i arkasında, telemetry kapalı ve gerçek para
erişimi olmadan tutulabilir.

## 2. Acımasız mevcut durum değerlendirmesi

### Doğrulama tabanı

- Local checkout temizdi; branch `main`, tag `v1.4.0`, commit
  `2420ff9b299b69e57166f5ca7df681bc49e2f31c`.
- İstenen `v1.4.0-production` tag'i repoda yoktur. Mevcut tag'ler arasında `v1.3.0-production`
  ve `v1.4.0` vardır.
- `python -m compileall -q backend` geçti.
- Backend testleri: **230 passed, 1 skipped**, 39.27 saniye. Skip macOS GUI smoke testidir.
- Frontend: **22/22 Vitest testi geçti**, 4 test dosyası, 9.20 saniye.
- Bu sonuçlar kapsamın doğru olduğunu değil, mevcut test sözleşmesinin geçtiğini kanıtlar.
- Installer artifact checkout'ta bulunmadığından yaklaşık 198 MB iddiası yeniden ölçülmedi.

### Gerçek çalışan çekirdek

- React + FastAPI + pywebview in-process desktop dispatch mevcut:
  [`runtime.py`](../../../backend/desktop/runtime.py#L89),
  [`bridge.py`](../../../backend/desktop/bridge.py#L68).
- SQLite WAL tabanlı transaction/settings/trade saklama mevcut:
  [`sqlite_driver.py`](../../../backend/app/db/sqlite_driver.py#L17).
- DuckDB candle ve OLAP trade projection mevcut:
  [`duckdb_driver.py`](../../../backend/app/db/duckdb_driver.py#L35).
- CSV import, journal/playbook, temel analytics ve test edilebilir UI yüzeyleri mevcuttur.
- Bunlar bir journal/analytics beta çekirdeğidir; production execution veya HFT çekirdeği değildir.

### Kritik bulgular

| # | Bulgu | Kanıt | Risk / karar |
|---:|---|---|---|
| 1 | SQLite trade yazımı `INSERT OR REPLACE` kullanıyor. | [`sqlite_driver.py:112`](../../../backend/app/db/sqlite_driver.py#L112) | SQLite REPLACE çakışan satırı siler; identity/audit zinciri bozulabilir. Append-only event + projection'a geç. |
| 2 | Fiziksel trade silme var. | [`sqlite_driver.py:193`](../../../backend/app/db/sqlite_driver.py#L193) | Evidence kaybı. Tombstone/correction event kullan. |
| 3 | WAL `synchronous=NORMAL`. | [`sqlite_driver.py:20`](../../../backend/app/db/sqlite_driver.py#L20) | OS/power failure'da son committed transaction dayanıklılığı audit hedefi için yetersiz. Evidence writer `FULL` olmalı. |
| 4 | SQLite→DuckDB dual write atomik değil. | [`sync_pipeline.py:12`](../../../backend/app/db/sync_pipeline.py#L12) | Crash sonrası projection drift. DuckDB'yi yeniden üretilebilir projection yap. |
| 5 | DuckDB'de canonical tick/event store yok; candle ve trade tabloları var. | [`duckdb_driver.py:35`](../../../backend/app/db/duckdb_driver.py#L35) | Replay ve market context kanıtı eksik. Parquet recorder/manifest ekle. |
| 6 | DuckDB sync DELETE+INSERT yapıyor. | [`duckdb_driver.py:158`](../../../backend/app/db/duckdb_driver.py#L158) | Audit kaynağı olamaz; yalnız projection olarak kalmalı. |
| 7 | CSV importer “single transaction” derken kayıt başına dual write yapıyor. | [`csv_importer.py:365`](../../../backend/app/services/csv_importer.py#L365), [`csv_importer.py:410`](../../../backend/app/services/csv_importer.py#L410) | Kısmi import ve tutarsız retry riski. Import batch/event idempotency gerekir. |
| 8 | Playbook-trade ilişkisi structured key yerine notes `LIKE` ile bulunuyor. | [`playbook_service.py:126`](../../../backend/app/playbook/playbook_service.py#L126) | Yanlış eşleşme ve yeniden üretilemeyen audit. Versioned foreign key gerekir. |
| 9 | Discipline audit geçmişi silinip yeniden yazılıyor. | [`playbook_service.py:186`](../../../backend/app/playbook/playbook_service.py#L186) | Değerlendirme tarihçesi yok olur. Her değerlendirme immutable event olmalı. |
| 10 | Paper fill fiyat fallback'i `65000`. | [`ccxt_engine.py:165`](../../../backend/app/services/execution/ccxt_engine.py#L165) | Risk guard fiyatı önce reddettiği için çoğu akışta erişilemez olsa da tasarım yanlıştır. Fiyat yoksa fill yok. |
| 11 | Exchange order hemen trade'e çevriliyor; durumlar OPEN/CLOSED'a eziliyor. | [`ccxt_engine.py:203`](../../../backend/app/services/execution/ccxt_engine.py#L203), [`ccxt_engine.py:240`](../../../backend/app/services/execution/ccxt_engine.py#L240) | Partial fill/reject/cancel/fee/correction kaybı. Canlı işlem kapalı kalmalı. |
| 12 | Idempotency, user-stream lifecycle ve reconnect reconciliation yok. | [`ccxt_engine.py:203`](../../../backend/app/services/execution/ccxt_engine.py#L203) | Duplicate order ve position drift riski. Native state machine zorunlu. |
| 13 | Aynı `POST /execution/order` rotası iki kez tanımlı. | [`endpoints.py:240`](../../../backend/app/api/endpoints.py#L240), [`endpoints.py:726`](../../../backend/app/api/endpoints.py#L726) | Gölgeleme ve farklı request sözleşmesi. Faz 0'da tek route. |
| 14 | Risk compliance sonucu `status` alanından okunuyor; engine `overall_status` döndürüyor. | [`risk_guard.py:108`](../../../backend/app/quant/risk_guard.py#L108), [`compliance_engine.py:187`](../../../backend/app/services/compliance_engine.py#L187) | Compliance breach fail-open olabilir. P0 defect. |
| 15 | `get_setting(..., default=...)` çağrısı gerçek imzayla uyumsuz. | [`compliance_engine.py:18`](../../../backend/app/services/compliance_engine.py#L18), [`sqlite_driver.py:212`](../../../backend/app/db/sqlite_driver.py#L212) | Exception fallback'i 100k hesap büyüklüğünü sessizce uygular. P0 defect. |
| 16 | CCXT risk çağrısı free balance aktarmıyor. | [`ccxt_engine.py:148`](../../../backend/app/services/execution/ccxt_engine.py#L148), [`risk_guard.py:131`](../../../backend/app/quant/risk_guard.py#L131) | Bakiye kontrolü atlanıyor. |
| 17 | Binance WS multiple stream URL'si yanlış, yalnız trade/kline var. | [`binance_client.py:47`](../../../backend/app/websocket/binance_client.py#L47) | Combined stream formatı, 24h reconnect, depth sequence/gap yok. Feed kanıtı değil. |
| 18 | UI latency rastgele 8–24 ms; default last price 65000. | [`binance_client.py:22`](../../../backend/app/websocket/binance_client.py#L22), [`binance_client.py:112`](../../../backend/app/websocket/binance_client.py#L112) | Telemetry fabricated. Kaldırılmalı. |
| 19 | Replay trade yoksa fake BTC trade, candle azsa sentetik seri üretiyor. | [`replay_service.py:129`](../../../backend/app/replay/replay_service.py#L129), [`replay_service.py:150`](../../../backend/app/replay/replay_service.py#L150) | Forensics akışında sahte kanıt. Normal build'de yasak. |
| 20 | MAE/MFE candle yoksa tahmin ediyor; aggregate yol bunu sık kullanıyor. | [`mae_mfe.py:34`](../../../backend/app/quant/mae_mfe.py#L34), [`mae_mfe.py:119`](../../../backend/app/quant/mae_mfe.py#L119) | Metric evidence değil. `INSUFFICIENT_DATA` dönmeli. |
| 21 | Hardware telemetry ve GGUF cevabı hardcoded/sentetik. | [`hardware_engine.py:38`](../../../backend/app/services/ai/hardware_engine.py#L38), [`hardware_engine.py:110`](../../../backend/app/services/ai/hardware_engine.py#L110), [`hardware_engine.py:198`](../../../backend/app/services/ai/hardware_engine.py#L198) | Gerçek local inference olarak sunulamaz. Modül kaldırılmalı. |
| 22 | Agent swarm deterministic heuristic/default değerler kullanıyor. | [`agent_swarm.py:17`](../../../backend/app/services/ai/agent_swarm.py#L17), [`agent_swarm.py:124`](../../../backend/app/services/ai/agent_swarm.py#L124) | “AI swarm” etiketi yanıltıcı. Rule evaluator diye yeniden adlandır veya kaldır. |
| 23 | FIX parser checksum doğrulamıyor; sequence RAM'de ve gap recovery yok. | [`fix_gateway.py:49`](../../../backend/app/services/fix/fix_gateway.py#L49), [`fix_gateway.py:80`](../../../backend/app/services/fix/fix_gateway.py#L80), [`fix_gateway.py:166`](../../../backend/app/services/fix/fix_gateway.py#L166) | Certified FIX bağlantısı değildir. Experimental dışına çıkamaz. |
| 24 | FIX bridge `is_logged_on=True` ve simulated fill üretiyor. | [`fix_bridge.py:28`](../../../backend/app/services/execution/fix_bridge.py#L28), [`fix_bridge.py:131`](../../../backend/app/services/execution/fix_bridge.py#L131) | Gerçek transport/DMA yoktur; UI'dan kaldır. |
| 25 | Order book list scan, `min/max`, `pop(0)` ve sorting kullanıyor. | [`order_book.py:36`](../../../backend/app/services/matching/order_book.py#L36), [`order_book.py:54`](../../../backend/app/services/matching/order_book.py#L54), [`order_book.py:128`](../../../backend/app/services/matching/order_book.py#L128), [`order_book.py:233`](../../../backend/app/services/matching/order_book.py#L233) | O(1)/sub-10µs iddiasıyla uyumsuz. HFT çekirdeği olarak kullanılmamalı. |
| 26 | Order book başlangıçta fake BTC liquidity seed ediyor. | [`order_book.py:331`](../../../backend/app/services/matching/order_book.py#L331) | Ürün verisi ile demo verisini karıştırıyor. Test fixture'a taşı. |
| 27 | HFT testleri sentetik in-memory generator ve in-memory DuckDB ölçüyor. | [`hft_load_generator.py:1`](../../../scripts/hft_load_generator.py#L1), [`test_hft_stress_benchmarks.py:17`](../../../backend/tests/test_hft_stress_benchmarks.py#L17) | Exchange feed, durability, reconnect, fill lifecycle ve UI render benchmark'ı değildir. HFT iddiası kaldır. |
| 28 | Footprint/heatmap veri yokken seed output üretiyor. | [`footprint_engine.py:162`](../../../backend/app/services/orderflow/footprint_engine.py#L162) | Order flow görseli kanıt değil. No-data state zorunlu. |
| 29 | MT5 initialize kütüphane yokken bile true; quote sabit. | [`mt5_adapter.py:27`](../../../backend/app/services/data_adapters/mt5_adapter.py#L27), [`mt5_adapter.py:50`](../../../backend/app/services/data_adapters/mt5_adapter.py#L50) | Adapter demo/mock. |
| 30 | Polygon/TwelveData subscribe network bağlantısı kurmuyor. | [`polygon_adapter.py:41`](../../../backend/app/services/data_adapters/polygon_adapter.py#L41), [`twelvedata_adapter.py:42`](../../../backend/app/services/data_adapters/twelvedata_adapter.py#L42) | Connector iddiası kaldırılmalı. |
| 31 | Multi-asset manager var olmayan DuckDB metodunu çağırıyor. | [`multi_asset_manager.py:42`](../../../backend/app/services/data_adapters/multi_asset_manager.py#L42) | Yol çalışır değil; compile bunu yakalamaz. |
| 32 | Push queue dolunca en eski olayı audit gap üretmeden düşürüyor. | [`push.py:19`](../../../backend/desktop/push.py#L19) | UI telemetry kaybı olabilir. Ledger ayrı; UI drop counter/gap bildirimi zorunlu. |
| 33 | Credential passphrase hostname/platform bilgisinden türetiliyor. | Tarihsel `2420ff9` credential implementation; güncel modül: [`exchange/credentials_manager.py`](../../../backend/app/services/exchange/credentials_manager.py) | Tarihsel bulgu: OS keychain güvencesi yoktu. Güncel durum P0-WP07 kaydıyla okunur. |
| 34 | Vault default key ve fixed salt içeriyor; “zero” denilen delete yalnız `del`. | [`security.py:20`](../../../backend/app/core/security.py#L20), [`security.py:55`](../../../backend/app/core/security.py#L55) | Güvenlik iddiası yanlış. Kaldır/OS keychain kullan. |
| 35 | Gateway default webhook secret ile başlıyor, yalnız uyarıyor. | [`gateway.py:24`](../../../backend/desktop/gateway.py#L24), [`gateway.py:50`](../../../backend/desktop/gateway.py#L50) | Entegrasyon aktifse fail-closed secret zorunlu. |
| 36 | README üretim/HFT ve test iddiaları kod gerçekliğiyle uyumsuz. | [`README.md:16`](../../../README.md#L16), [`README.md:68`](../../../README.md#L68), [`README.md:135`](../../../README.md#L135) | Truth release öncesi dağıtım yapılmamalı. |

### Canlı işlem açılmadan önce zorunlu kapılar

ADR-0003'teki 15 kapı bağlayıcıdır. Özet kalite SLA'sı: 30 gün shadow mode'da sıfır
açıklanamayan order/position farkı, 10.000 testnet lifecycle, 100 reconnect, ACK verilmiş
event kaybı sıfır, duplicate order sıfır, risk bypass sıfır ve reconnect reconciliation
p99 < 60 saniye.

## 3. Rakip matrisi

### Puanlama

Örtüşme, şu sabit ağırlıklarla hesaplanmıştır: journal/behavior/risk 20, replay/market context
20, local privacy/data ownership 20, reproducible research/evidence/audit 20,
broker/execution integration 10, AI explainability/provenance 10. Her satırdaki parantez
`J/R/L/E/B/A` katkısını gösterir. Puan özellik sayısı veya kalite notu değildir.

| Ürün | Hedef kullanıcı | Güçlü taraf | Örtüşme | Kuantra ne öğrenmeli | Asla kopyalama | Kuantra'nın boşluğu |
|---|---|---|---:|---|---|---|
| [TradesViz](https://www.tradesviz.com/pricing/) | Çoklu broker kullanan aktif trader | Çok geniş analytics, import, simulator, replay, AI Coach | **56%** (20/20/0/5/8/3) | Import kapsamı ve analytics keşfedilebilirliği | Özellik kataloğu yarışına girmek | Local evidence/provenance ve deterministic risk |
| [TradeZella](https://www.tradezella.com/pricing) | Journal ve prop workflow isteyen discretionary trader | Güçlü onboarding, auto-sync, replay/backtest, ürünleşme | **58%** (20/20/0/5/10/3) | İlk değer anını kısaltan UX | Cloud dashboard klonu | Kaynak bağlı, yeniden üretilebilir Trade Evidence Pack |
| [TraderSync](https://tradersync.com/pricing/) | Risk planı ve koçluk isteyen trader | Risk planı, replay, AI coach | **56%** (20/20/0/5/8/3) | Risk planını review döngüsüne bağlamak | AI dilini kanıt yerine kullanmak | Deterministic rule verdict + immutable input |
| [Edgewonk](https://edgewonk.com/pricing) | Davranış/psikoloji odaklı trader | Tiltmeter, discipline, weekly review | **33%** (20/5/0/5/3/0) | Haftalık ritüel ve davranış metrikleri | Psychology skorunu pseudo-science'a çevirmek | Gerçek broker/market evidence ile davranış bağlantısı |
| [Chartlog](https://www.chartlog.ai/) | Düşük fiyatlı AI journal arayan trader | Basit cloud AI coach ve fiyat | **38%** (15/10/0/5/5/3) | Hızlı time-to-value | Genel LLM özetini farklılaştırıcı sanmak | Offline/BYOK, citation ve provenance |
| [Tradervue](https://www.tradervue.com/site/pricing/) | Klasik, olgun reporting isteyen trader | Güvenilir journal/reporting ve MFE/MAE | **33%** (15/5/0/5/8/0) | Sade temel rapor seti | Sadece geçmişe bakan statik journal | Event lifecycle + market context + rule evidence |
| [QuantConnect / LEAN](https://www.quantconnect.com/docs/v2/lean-cli/backtesting/deployment) | Kod yazan quant/research kullanıcıları | Local reproducible backtest/research/deploy | **73%** (5/15/20/20/10/3) | Reproducibility, artifact ve environment disiplini | Kuantra'yı developer-only IDE yapmak | Discretionary kararın reproducible evidence'ı |
| [Freqtrade](https://docs.freqtrade.io/en/latest/) | Crypto bot geliştiricisi | Açık kaynak, backtest, dry-run, live | **60%** (5/10/20/15/10/0) | Dry-run-first güvenlik kültürü | Bot execution'ı ana persona yapmak | İnsan kararları için forensics ve review |
| [Bookmap](https://bookmap.com/packages-comparison) | Order-flow/liquidity traderı | Heatmap, historical liquidity, replay | **53%** (5/20/15/5/8/0) | Görsel context ve veri lisansı ayrımı | Pahalı market-data terminali olmak | Trade'e bağlı seçili context ve evidence pack |
| [Quantower](https://help.quantower.com/quantower/getting-started/license-comparison) | Çoklu broker execution/order-flow traderı | DOM, footprint, chart execution | **55%** (5/20/15/5/10/0) | Modüler workspace ve connector yüzeyi | Her venue/widget matrisini kopyalamak | Review/risk/audit'i execution UI'dan üstün tutmak |
| [AmiBroker](https://www.amibroker.com/products.html) | Local desktop teknik analiz/backtest kullanıcısı | Hızlı local scan/backtest/optimization | **48%** (3/5/20/15/5/0) | Yerel çalışma ve uzun ömürlü basitlik | Eski desktop UX'ini taklit etmek | Modern evidence workflow + broker reconciliation |

**Okuma:** En yakın GTM rakipleri TradeZella ve TradesViz'dir. QuantConnect'in %73 çıkması onu
aynı satış kategorisi yapmaz; local/reproducible research ekseninde mimari yakınlığı gösterir.

## 4. Hedef mimari

### Korunacaklar

- React UI ve FastAPI sözleşmeleri, yüzey küçültülerek.
- Python research, analytics ve control plane.
- SQLite: settings, metadata, küçük projection ve canonical evidence ledger.
- DuckDB: yalnız read-heavy analytical projection/query.
- Local-first veri dizini, açık export ve backup yaklaşımı.
- Mevcut pywebview shell; Windows WebView2 için Accepted ADR-0004, macOS WKWebView.

### Radikal yeniden yazılacaklar

- Trade-row CRUD → append-only order/fill/risk/journal event ledger + projection.
- CCXT order-to-trade shortcut → explicit venue lifecycle ve reconciliation state machine.
- Candle/synthetic replay → sequence-aware real market recorder ve deterministic replay.
- Tahmini MAE/MFE → verified context veya `INSUFFICIENT_DATA`.
- Fake GGUF/swarm → gerçek sidecar ve read-only AI Auditor.
- String/notes ilişkileri → versioned typed IDs.

### Gereksiz karmaşıklık

- İlk günden Kafka/Redpanda, Arrow Flight, service mesh veya Kubernetes.
- Tüm Python backend'in Rust'a taşınması.
- Blockchain audit zinciri.
- Generic FIX/DMA veya cross-venue smart router.
- Hot-loaded in-process plugin ve biometrics.

### Proses sınırı

Mevcut uygulama **tek mantıksal uygulama prosesi** olarak kalır. Faz 2 tek başına
rewrite yetkisi değildir. Profiler gerçek kullanıcı workload'unda darboğaz gösterirse
ayrı bounded karar ile aşağıdaki proses ayrımı değerlendirilebilir:

1. Thin desktop host + React UI.
2. Python control/research/analytics prosesi.
3. Rust data recorder/normalizer prosesi.

Ledger'ın tek sahibi vardır. UI queue kaybı canonical event kaybı sayılmaz. Prosesler supervisor
tarafından izlenir; recorder veya AI sidecar düşerse journal read-only çalışmaya devam eder.

### Karar/maliyet/risk/validation tablosu

| Karar | Risk | Tahmini maliyet | Migration path | Validation SLA |
|---|---|---:|---|---|
| SQLite append-only ledger, tek writer, `FULL` | Schema migration ve projection bug'ı | 4–6 mühendis-hafta | Mevcut trade'leri `LegacyTradeImported` event'ine dönüştür; eski DB read-only backup | write ack p99 <20 ms; 10k crash testinde ACK event kaybı 0; projection rebuild %100 |
| Parquet market store + manifest | Segment corruption, küçük dosya patlaması | 6–10 hf | Staging log → hour partition → seal/hash/manifest; eski candles ayrı legacy source | 50k event/s sustained; gap saklama 0; flush <2 s; corrupt segment açık hata |
| DuckDB disposable projection | Query/schema drift | 3–5 hf | View'ları Parquet + ledger projection'dan üret; DB delete/rebuild command | 10M satır standard query p95 <1 s; clean rebuild %100 |
| Çoklu proses sınırı | IPC/supervision hata yüzeyi | 4–6 hf temel | Önce interface ve contract test; sonra recorder'ı ayır | child restart <5 s; journal degraded mode; canonical loss 0 |
| Rust/Tokio yalnız data plane | FFI/skill/migration maliyeti | 10–16 hf | Önce gerçek Python profiler/soak baseline; aynı golden stream'i iki implementasyonda çalıştır | 24h soak; unexplained gap 0; drop <0.01%; duplicate 0 |
| Arrow IPC, control için JSON | Schema compatibility | 4–6 hf | Versioned RecordBatch schema, named pipe/Unix socket; golden compatibility fixture | local throughput >200 MB/s; batch p95 <50 ms; backward fixture pass |
| Arrow Flight'i ertele | Gelecekte remote migration | Şimdi 0 | Yalnız remote/multi-host ve auth/service discovery gerektiğinde Flight | Faz 5 öncesi Flight dependency 0 |
| llama.cpp/OpenAI-compatible sidecar | Model variability, hallucination | 6–8 hf | Fake engine'i kaldır; health/capability discovery; versioned prompt/tool contracts | schema valid ≥99%; source coverage %100; p95 local response <8 s |
| AI Auditor read-only | Kullanıcı AI önerisini emir sanabilir | Dahil | Execution tool hiç tanımlama; UI'da evidence/confidence/counterexample | unsupported numeric <1%; source trace %100; risk bypass 0 |
| WebView2 ADR-0004; Tauri 2 ertelenmiş | Renderer/host uyumsuzluğu | Ayrı ölçüm gerekir | Mevcut pywebview Windows Evergreen host; macOS WKWebView; Tauri ancak ölçümle | Exact-artifact renderer smoke; boyut/activation hedefleri henüz kanıt değil |
| Native canlı venue adapter | Venue API değişimi ve para kaybı | 12–16 hf/venue | CCXT read-only; Binance USD-M shadow → testnet → canary | 30 gün fark 0; recon p99 <60 s; duplicate/risk bypass 0 |

### Arrow Flight kararı

Proses ayrımı gerekirse önce **Arrow IPC değerlendirilir**; bugün zorunlu dependency değildir.
Flight, uzak endpoint, auth, discovery, network backpressure
ve multi-host teams gerektirdiğinde değerlendirilir. Tek makinede Flight sunucusu çalıştırmak ürün
değeri üretmeden deployment yüzeyi ekler.

### WebView2 kararı

Windows renderer kararı [ADR-0004](../../strategy/adr/ADR-0004-windows-webview2-renderer.md) ile
WebView2 Evergreen olarak kabul edilmiştir; önceki “şimdi geçilmez” ifadesi geçersizdir.
Bu, Tauri veya multi-process rewrite kararı değildir. Windows host blocker'ı kendi
host'unda doğrulanmalıdır. Tauri ancak ölçülmüş install/crash sorunu ve ayrı kapsam
kararıyla değerlendirilir; macOS mevcut WKWebView kullanır.

## 5. Fazlandırılmış yol haritası

### Faz 0 — Truth & Safety Release — 3–4 hafta

- **Amaç:** Ürün iddiası ile çalışan kodu eşitlemek; para/veri güvenliği için kırmızı bayrakları kapatmak.
- **Kullanıcı değeri:** Kullanıcı gerçek, simüle ve eksik veriyi ayırt eder; yanlış güven oluşmaz.
- **Teknik teslimatlar:** duplicate route düzeltmesi; risk/compliance contract fix; `get_setting`
  düzeltmesi; Binance combined URL; fake fallback'lerin normal build'den çıkarılması; no-data/stale/
  simulated state; OS keychain; zorunlu gateway secret; CI truth matrix; README/release claim temizliği;
  Windows/macOS/Linux clean-install smoke.
- **Kapsam dışı:** Rust, LLM, live execution, yeni broker, yeni analytics widget.
- **Risk:** UI demo akışları boş görünebilir; bu doğru davranıştır.
- **Başarı metrikleri:** normal build fabricated market/fill/telemetry = 0; duplicate routes = 0;
  açık P0 security = 0; claim→test matrisi %100; üç OS smoke pass.
- **Exit criteria:** ürün `Production HFT/DMA/LLM` iddiası taşımıyor; read-only/journal beta olarak
  dürüstçe dağıtılabiliyor.
- **Bağımlılıklar:** feature flag ve test fixture ayrımı.
- **Kaldır/experimental:** FIX/DMA, live CCXT, order book, AI swarm/GGUF, DEX, copy, biometrics,
  MT5/Polygon/TwelveData, seed order flow.

### Faz 1 — Evidence Ledger ve Reliable Journal Core — 6–8 hafta

- **Amaç:** Her trade'i yeniden üretilebilir ve düzeltilebilir kanıt zincirine çevirmek.
- **Kullanıcı değeri:** “Bu sonuç hangi broker kaydı, risk kuralı ve nottan çıktı?” sorusunun cevabı.
- **Teknik teslimatlar:** append-only SQLite ledger; event schema/version/idempotency/hash chain;
  projection rebuild; tombstone/correction; versioned playbook/risk policies; file/source hash'li CSV;
  Binance/OKX read-only order/fill import; reconciliation report; Evidence Pack JSON/HTML; backup/restore.
- **Kapsam dışı:** tick recorder, AI, canlı order entry.
- **Risk:** legacy trade migration ve connector field mapping.
- **Başarı metrikleri:** import success ≥%90; normalized fill doğruluğu ≥%99.5; evidence completeness
  ≥%95; pack generation p95 <2 s; rebuild sonucu %100 aynı.
- **Exit criteria:** pilotta kullanıcıların ≥%60'ı üç haftada en az iki weekly review tamamlar.
- **Bağımlılıklar:** Faz 0, canonical schema, broker fixture corpus.
- **Kaldır/experimental:** eski direct CRUD read-only compatibility adapter'a iner.

### Faz 2 — Data Plane ve Replay/Research Core — 8–12 hafta

- **Amaç:** Trade kararını gerçek, gap-aware piyasa bağlamında deterministik yeniden oynatmak.
- **Kullanıcı değeri:** gerçek MAE/MFE, karar anı liquidity/context ve tekrar edilebilir analiz.
- **Teknik teslimatlar:** Parquet/manifest/checksum; Binance snapshot+delta order-book sequence;
  deterministic replay clock; verified MAE/MFE; DuckDB views; Arrow IPC; profiler eşiği geçilirse
  Rust/Tokio recorder, bounded ring buffer ve micro-batch.
- **Kapsam dışı:** HFT order entry, multi-venue smart routing, generic FIX.
- **Risk:** market-data lisansı, disk büyümesi, sequence gap.
- **Başarı metrikleri:** 24h soak silent gap = 0; aynı input replay hash'i %100 aynı; context coverage
  ≥%95; 10M satır standard query p95 <1 s; bütün gap'ler UI'da görünür.
- **Exit criteria:** pilotun ≥%40'ı haftalık replay kullanır; ≥%30'u bir rule/playbook değişikliği kaydeder.
- **Bağımlılıklar:** Faz 1 event identity, retention policy, data license.
- **Kaldır/experimental:** synthetic replay ve seed footprint tamamen test fixture'a taşınır.

### Faz 3 — Local AI Auditor ve Decision Intelligence — 6–8 hafta

- **Amaç:** Evidence Pack'i özetleyen değil, kanıta bağlayarak sorgulayan read-only auditor.
- **Kullanıcı değeri:** Kullanıcı her AI cümlesinin kaynağını, güvenini ve karşı örneğini görür.
- **Teknik teslimatlar:** llama.cpp/OpenAI-compatible sidecar; model/prompt/tool hash; schema-constrained
  response; citation resolver; observation/evidence/confidence/counterexample şeması; BYOK; golden eval;
  prompt injection/red-team; AI kapalıyken eksiksiz ürün.
- **Kapsam dışı:** signal generation, order tool, autonomous strategy changes.
- **Risk:** hallucination, latency, donanım uyumsuzluğu, bulut gizliliği.
- **Başarı metrikleri:** citation coverage %100; unsupported numeric <1%; schema valid ≥%99;
  weekly review completion uplift ≥10 puan; evaluator precision ≥%85.
- **Exit criteria:** AI kapalı kontrol kohortuna göre ölçülebilir review/rule-adherence artışı.
- **Bağımlılıklar:** Faz 1–2 evidence API, consent/BYOK ve eval corpus.
- **Kaldır/experimental:** `hardware_engine` ve `agent_swarm` yerini gerçek auditor contract'ına bırakır.

### Faz 4 — Controlled Execution / Broker Reconciliation — 12–16 hafta/venue

- **Amaç:** Kanıtlanmış journal/reconciliation çekirdeğine sınırlı, fail-closed execution eklemek.
- **Kullanıcı değeri:** Karar, risk verdict, venue lifecycle ve son reconciliation aynı pakette.
- **Teknik teslimatlar:** Binance USD-M native adapter; persistent idempotency/state machine; user stream;
  REST reconciliation; partial/reject/cancel/replace/fee/correction; max notional; stale block; confirmation;
  independent kill switch; shadow/testnet/canary rollout.
- **Kapsam dışı:** AI order, bot portfolio, copy, FIX/DMA, multi-venue router.
- **Risk:** finansal kayıp, venue outage/API drift, mevzuat ve destek yükü.
- **Başarı metrikleri:** unexplained order/position delta = 0; duplicate order = 0; risk bypass = 0;
  ACK event loss = 0; reconnect reconciliation p99 <60 s.
- **Exit criteria:** ADR-0003'teki 15 kapının tamamı ve 30 günlük shadow dönemi.
- **Bağımlılıklar:** bağımsız security review, hukuki ürün matrisi, on-call/runbook.
- **Kaldır/experimental:** generic CCXT canlı yol kapalı; yalnız read-only/import kullanımı kalır.

### Faz 5 — Teams / Prop Desk / Plugin Ecosystem — 12+ hafta

- **Amaç:** Bireysel kanıt modelini desk policy ve denetlenebilir review workflow'una taşımak.
- **Kullanıcı değeri:** Koç/desk yöneticisi trader verisini ele geçirmeden rule adherence görebilir.
- **Teknik teslimatlar:** signed policy packs; RBAC review; team adherence; privacy-preserving aggregates;
  retention; signed export; out-of-process plugin SDK; permission manifest; signature ve resource quota.
- **Kapsam dışı:** social copy, pooled funds/custody, autonomous AI, in-process sınırsız plugin.
- **Risk:** GDPR/KVKK, tenant isolation, support ve procurement.
- **Başarı metrikleri:** 3 ücretli design partner; ≥%70 weekly desk review; permission bypass = 0;
  export/audit acceptance = %100.
- **Exit criteria:** üç partnerin 90 gün kullanması ve en az ikisinin yıllık sözleşmeye geçmesi.
- **Bağımlılıklar:** Faz 4 zorunlu değil; Faz 1–3 ve legal/DPA zorunlu.

## 6. Ticari model

Bu bölümün fiyatları ve paket içerikleri **teklif hipotezidir**, satışa hazır veya
uygulanmış capability listesi değildir. MIT lisansı private repo'yu otomatik olarak
public yapmaz; yayınlama ve ticari paket kararı ürün sahibinindir. Güvenilir import ve
AI'sız review doğrulanmadan ücretli AI/connector vaadi verilmez.

### Karar: açık çekirdek + ücretli automation/operasyon

MIT local core stratejik niyettir; `package.json` MIT dese de bu checkout'ta `LICENSE`
dosyası yoktur. Lisans metni/third-party notices dağıtım öncesi ürün sahibince çözülmelidir.
Audit bütünlüğü, veri taşınabilirliği veya basic risk doğruluğu paywall
arkasına konmaz. Ücret, tekrarlanan connector operasyonu, gelişmiş workflow, destek ve team
yönetişiminden alınır.

| Teklif | Fiyat hipotezi | Dahil |
|---|---:|---|
| Community | Ücretsiz / MIT | Local ledger, manual entry, unlimited CSV, temel journal/MAE-MFE/risk, Evidence Pack export, backup, veri silme/taşıma, bir read-only community connector, local/BYOK API |
| Desktop Pro Global | **$129/yıl** veya $15/ay | Advanced replay, multi-account, scheduled review, custom evidence template, advanced rules, polished local AI UX, signed builds/support |
| Desktop Pro AB | **€119/yıl + KDV** veya €14/ay | Global Pro ile aynı |
| Desktop Pro Türkiye | **₺3.990/yıl** veya ₺449/ay | 12 ay fiyat koruması; satın alma gücüne göre bölgesel fiyat |
| Connector | **$79/yıl/exchange family** | Bakımı yapılan auto-sync/reconciliation; Binance+OKX paket hipotezi $119/yıl |
| Managed Cloud AI | **$12/ay**, kredi limiti açık | Tamamen opt-in; local/BYOK ücretsiz kalır |
| Teams / Prop | **$39/kullanıcı/ay**, min. 5 veya $390/yıl | Policy packs, RBAC review, team metrics, support |

- Deneme: kart istemeyen 14 gün; Community'ye veri kaybetmeden düşüş.
- Market data ürün fiyatına gömülmez; kullanıcı lisansı veya pass-through maliyet ayrı gösterilir.
- Canlı execution ayrı bir “daha çok trade et” upsell'i yapılmaz. Güvenlik kapısı ticari baskıyla açılmaz.
- Bookmap ve Quantower'ın data/platform ayrımı piyasa emsalidir.

## 7. Talep doğrulama planı

### İlk persona

Binance/OKX perps üzerinde ayda en az 100–200 discretionary trade yapan; Excel/Notion veya cloud
journal kullanan; haftalık review disiplini zayıf; en az bir risk ihlali yaşamış; bot geliştiricisi
olmayan ve trade verisinin buluta gitmesine hassas trader.

### 40 kullanıcılık, 8 haftalık pilot

- 15 Türkiye, 15 Avrupa, 10 global İngilizce kullanıcı.
- Tamamı ilk crypto/perps personasına uygun olmalı; farklı journal deneyimleriyle
  çeşitlendirilir. Geleneksel futures/prop kitlesi için hedef pazar genişletilmez.
- Önce 5–8 nitelikli kullanıcıyla formative uçtan uca kullanım; R1–R6 kapıları sonrası
  40 kişilik pilot. Kullanıcı bulma/iletişim ve veri paylaşımı ayrı ürün sahibi sürecidir.
- Ücretsiz kalabalık beta yerine depozito veya zaman taahhüdü olan design partner seçimi.
- Her kullanıcı için baseline: mevcut import süresi, haftalık review, rule breach ve kullandığı araç maliyeti.

### Interview script başlıkları

1. Son üç trade'i hangi kanıtlarla yeniden kurabiliyor?
2. Son import/sync hatasında ne oldu ve bunu nasıl fark etti?
3. Bir risk kuralına uyduğunu nasıl kanıtlıyor?
4. MAE/MFE veya replay değerine hangi durumda güvenmiyor?
5. Journal'ı en son neden bıraktı?
6. Hangi verinin buluta çıkmasını kabul etmiyor?
7. Son büyük ihlali hangi deterministic kural durdurabilirdi?
8. Bir AI cümlesine inanmak için hangi kaynak ve karşı örneği görmek ister?
9. Read-only auto-sync için ne öder?
10. Üründe sadece üç şey kalacaksa hangileri kalmalı?

Önce geçmiş davranış sorulur; özellik listesi gösterilip niyet beyanı toplanmaz.

### Fake-door testleri

| Kapı | Başarı eşiği |
|---|---:|
| Trade Evidence Pack | qualified visit → waitlist ≥%12 |
| Local auto-reconciliation | waitlist → interview ≥%30 |
| Source-linked Local AI Review | fake-door CTR ≥%8 ve interview'da kaynak talebi |
| Deterministic Rule Review (emir durdurma vaadi yok) | pilot invite → install ≥%60 |
| Ücretli connector rezervasyonu | refundable deposit ≥%15 |

Execution butonuna tıklama tek başına talep kanıtı değildir; kullanıcı güvenilir import/review
workflow'unu tekrar kullanmıyorsa execution yatırımı yanlış olur.

### Funnel ve retention hedefleri

- Install → ilk import: ≥%70; median <10 dakika.
- Import success: ≥%90.
- İlk gün Evidence Pack görüntüleme: ≥%60.
- Week-1 weekly review: ≥%55; Week-4: ≥%40; Week-8 aktif: ≥%35.
- En az bir deterministic rule yapılandırma: ≥%60.
- Weekly rule-adherence workflow kullanımı: ≥%45.
- 14 günlük trial → paid: global ≥%15; Türkiye ≥%10 (fiyatlandırmayla aynı süre hipotezi).
- 90 günlük paid retention: ≥%80.

### Yatırımı durdurma kuralları

İki ardışık kohortta aşağıdakilerden biri olursa execution yatırımı durur ve Faz 1'e dönülür:

- import success <%85;
- Week-4 review <%30 veya Week-8 active <%25;
- Evidence Pack weekly use <%25;
- paid connector niyeti/depozitosu <%15;
- broker reconciliation doğruluğu <%99.5.

AI yatırımı şu durumda durur:

- fake-door CTR <%8;
- review completion uplift <5 yüzde puan;
- unsupported numeric >%2;
- kullanıcıların >%20'si AI cümlesinin kaynağını bulamıyor;
- inference maliyeti Pro brüt marjının >%20'si.

Pilot go/no-go için üç koşul birlikte gerekir: 40 kullanıcının en az 16'sı sekizinci
haftada weekly active, en az 6'sı ücretli ve açıklanamayan fill farkı sıfır. Herhangi
biri sağlanmazsa veya ölçüm yoksa Faz 3/4'e geçilmez. AI numeric hedefi <%1;
>%2 yatırım durdurma eşiğidir, %1–2 aralığı kabul/production izni değildir.

## 8. Dış kaynaklar ve karar dayanakları

### Veri ve mimari

- [SQLite WAL — tek writer davranışı](https://www.sqlite.org/wal.html)
- [SQLite ON CONFLICT — REPLACE'in satır silmesi](https://sqlite.org/lang_conflict.html)
- [SQLite PRAGMA synchronous — NORMAL/FULL dayanıklılığı](https://sqlite.org/pragma.html)
- [DuckDB concurrency](https://duckdb.org/docs/current/connect/concurrency)
- [Apache Arrow use cases](https://arrow.apache.org/use_cases/)
- [Arrow IPC Python API](https://arrow.apache.org/docs/python/api/ipc.html)
- [Arrow Flight specification](https://arrow.apache.org/docs/format/Flight.html)
- [llama.cpp server — OpenAI-compatible ve constrained output](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)
- [Binance Spot WebSocket stream formatı](https://github.com/binance/binance-spot-api-docs/blob/master/web-socket-streams.md?plain=1)
- [Microsoft WebView2 distribution](https://learn.microsoft.com/microsoft-edge/webview2/concepts/distribution)

### Ürün/compliance sınırı

- [ESMA copy trading supervision guidance](https://www.esma.europa.eu/press-news/esma-news/esma-provides-guidance-supervision-copy-trading-services)
- [MiCA — Regulation (EU) 2023/1114](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32023R1114)
- [GDPR Article 9 dahil tam metin](https://eur-lex.europa.eu/eli/reg/2016/679/2016-05-04/eng)
- [KVKK özel nitelikli kişisel veriler](https://www.kvkk.gov.tr/Icerik/2051/Ozel-Nitelikli-Kisisel-Veriler)

### Rakip/resmî ürün ve fiyat sayfaları

- [TradesViz pricing](https://www.tradesviz.com/pricing/)
- [TradeZella pricing](https://www.tradezella.com/pricing)
- [TraderSync pricing](https://tradersync.com/pricing/)
- [Edgewonk pricing](https://edgewonk.com/pricing)
- [Chartlog](https://www.chartlog.ai/)
- [Tradervue pricing](https://www.tradervue.com/site/pricing/)
- [QuantConnect pricing](https://www.quantconnect.com/pricing)
- [Freqtrade docs — backtest/dry-run uyarısı](https://docs.freqtrade.io/en/stable/strategy-101/)
- [Bookmap package comparison](https://bookmap.com/packages-comparison)
- [Quantower license comparison](https://help.quantower.com/quantower/getting-started/license-comparison)
- [Quantower — market data dahil değildir](https://www.quantower.com/faq)
- [AmiBroker editions/pricing](https://www.amibroker.com/products.html)

## Değişiklik geçmişi

### 1.1.0 — 2026-09-08

- KRR-001 ile güncel backlog/kanıt sınırı ayrıldı; P1 değer zinciri önceliklendirildi.
- WebView2 ADR çelişkisi, zorunlu Rust/proses yorumu, pilot persona ve trial süresi düzeltildi.
- Tarihsel audit/rekabet ve ticari hipotezler güncel production iddiasından ayrıldı.

### 1.0.0 — 2026-09-05

- v1.4.0 local checkout audit'i, rakip matrisi, hedef mimari, beş fazlı yol haritası,
  fiyatlandırma hipotezi ve talep doğrulama kapıları kabul edildi.
