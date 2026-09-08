<!-- doc-role: archived -->
> Historical reference only. Not a current work order. Unchecked acceptance items remain open;
> see [current status](../../strategy/STATUS.md). Read only for a relevant task.

# KRR-001 — Ürün doğruluğu ve kalan geliştirme denetimi

```yaml
document_id: KRR-001
version: 1.0.0
status: Accepted
date: 2026-09-08
reviewed_commit: f746132
latest_runtime_commit: b1ceba6
branch: codex/p1-wp01-evidence-ledger
strategy: KPS-001@1.1.0
```

## Sonuç ve karar sınırı

Kuantra'nın ilk değer zinciri **import → açıklanabilir reconciliation → Trade Evidence
Pack → haftalık review → versioned kural değerlendirmesi** olarak korunur. Amaç trader'ın
karar kalitesini kanıtla değerlendirmektir; kârlılık artışı veya kanıtlanmış davranış
iyileşmesi bugün elde edilmiş sonuç değildir. Hedef kullanıcı discretionary crypto/perps
traderıdır; bir HFT terminali, genel broker terminali veya AI trading botu değildir.

P1 altyapısı uygulanmış olsa da Faz 1 ürün çıkışı tamamlanmış sayılmaz. Gerçek kullanıcı
ve pilot verisi yoktur. Spot depth/testnet geliştirmelerinin sayısı veya yeşil testler
bu boşluğu kapatmaz. Yeni P2 paketleri otomatik sıradaki iş değildir. Mevcut paketlerin
kimlikleri, kabul kriterleri ve geçmiş kanıtları korunur; kalan işlerin bağımlılık sırası
bu belgede açıklığa kavuşturulur. Hedef pazar veya ADR yetki sınırı değiştirilmez.

Bu denetim dokümantasyon değişikliğidir: aşağıdaki kod kusurları **düzeltilmedi**;
yeni broker bağlantısı, kullanıcı verisi işlemi, testnet koşusu veya release yapılmadı.

## Bugün neyi biliyoruz?

| Alan | Mevcut kanıt | Kanıtlamadığı şey / açık kapı |
|---|---|---|
| P1-WP01–10 | Ledger, atomic write, rebuild/projection, provenance, CSV ve evidence API uygulamaları kayıtlı | Her broker export'unun eksiksizliği, finansal doğruluk veya kullanıcı aktivasyonu |
| P1-WP11–15 | Lifecycle import/API snapshot, export/restore drill, policy events ve Evidence Pack UI mevcut | Uçtan uca perps accounting ve tekrarlanan haftalık review başarısı |
| Mac geliştirme | Son kayıtlı local CI: 550 backend, 51 frontend; production/desktop build ve smoke başarılı | Her OS/CPU sürümü, imzalı dağıtım, clean-machine install veya pilot başarısı |
| Public testnet | Üç adet 5 dakika ve bir 15 dakika gapsiz Spot gözlemi | USD-M/OKX SWAP account reconciliation, 24 saat süreklilik veya production source verification |
| Fault/recovery | Deterministic fault matrix 7/7; iki gerçek kontrollü disconnect gözlemi INVALID | Gerçek bağlantı kesintisinden sonra kesintisiz recovery |
| Native paket | .app smoke, DMG üretimi/preflight ve artifact hash kaydı | Hash'i alınan DMG içindeki executable'ın çalıştırıldığı iddiası |
| Faz 0 / Windows | Tarihsel üç-OS çıkış kanıtı; daha sonraki WebView2 host blocker kaydı | Bugünkü HEAD için Windows blocker'ın giderildiği veya üç-OS release-ready olduğu |
| Talep | Stratejide persona, pilot ve fiyat hipotezleri | Gerçek müşteri, ödeme, retention veya ürün-pazar uyumu |

Kanıt kaynakları: [paket kataloğu ve commit kayıtları](CATALOG-2026-09-08.md),
[testnet gözlemleri](work-packages/P2-WP14-binance-depth-testnet-soak-gate.md),
[Windows host paketi](work-packages/P0-WP11-webview2-host-diagnostics.md).
Yerel raporlar `dist/local-ci-report.json` ve `/tmp/kuantra-*-20260908/` altında
tutulmuştur; bu yollar kalıcı arşiv değildir. Bu denetim önceki koşu sonuçlarını
aktarır, yeni full CI veya yeni canlı gözlem yapıldığını iddia etmez.

## Koddan doğrulanan bulgular

### B1 — Snapshot completeness kayıt kaybını gizleyebilir (ilk öncelik)

[`ReadOnlyBrokerSyncService._paginate`](../../../backend/app/services/exchange/read_only_broker_sync.py)
tam sayfadan sonra `cursor = max_timestamp + 1` kullanıyor. Sayfa sınırında aynı
milisaniyeye ait daha fazla kayıt varsa bu kayıtlar sonraki istekten düşebilir.
`max_timestamp >= until_ms` ve kısa/boş sayfa da genel olarak `complete=True`
üretiyor; bunlar venue'nun sıralama/cursor/history sözleşmesi olmadan evrensel
eksiksizlik kanıtı değildir. Bu, koddan çıkarılan risk olup gerçek hesapta kayıp
gözlendiği anlamına gelmez. Önce deterministic adversarial fixture ile yakalanmalıdır.

### B2 — Reconciliation kapsamı financial accounting değildir

[`BrokerImportService.reconcile`](../../../backend/app/services/broker_import_service.py)
ücretleri `sum(fill.fee or 0.0 ...)` ile topluyor; bu karşılaştırma para birimini
ayırmıyor ve eksik fill ücretini sıfır gibi ele alıyor. Float/tolerance yaklaşımı
instrument precision sözleşmesinin yerine geçmez. API normalization Binance Spot
ve Futures'ı aynı venue etiketi altında temsil ediyor; account/market/instrument
kimliklerinin uçtan uca ayrışması ayrıca doğrulanmalı.

Perps için linear/inverse, contract multiplier, settlement asset, position side/hedge
mode, funding, rebate, fee currency ve transfer/opening balance kapsamı belirlenmeden
`RECONCILED` yalnız mevcut order/fill karşılaştırması olarak yorumlanabilir; net hesap
PnL doğrulaması olarak sunulamaz. Eksik funding/fee için sıfır veya doğrulanmış sonuç
üretilmemelidir. Birden fazla export/sync gözleminin immutable saklanması ile aynı
ekonomik fill'in iki kez sayılmaması ayrı acceptance kriterleridir.

### B3 — Recovery kararı yaşayan akışta gecikebilir

[`binance_depth_transport.py`](../../../backend/app/services/market_data/binance_depth_transport.py)
içinde consumer ingestion sonuçlarını biriktiriyor; `run_once` producer/consumer
bitişini bekledikten sonra recovery/persistence sonucunu değerlendiriyor. Akış açık
kaldığında bir sequence gap session'a zamanında terminal cycle olarak ulaşmayabilir.
Bu nedenle önceki “daha uzun koşu yeterli olabilir” yorumu desteklenmez. Süreyi
uzatmadan önce bitmeyen fake source ile prompt recovery, cancellation ve bounded
shutdown testleri gerekir. Source failure'ın persistence failure'ı maskelemesi de
negative test kapsamına alınmalıdır.

Disconnect injection CLI'da opt-in testnet ile sınırlı olsa da adapter düzeyinde
environment guard, close timeout, cancellation, one-shot davranış ve requested/fired/
recovered rapor alanları ayrıca incelenmelidir. Bu iş yeni production feed açmaz.

### B4 — Offline/provenance/package kanıtı aşırı yorumlanmış

- `uv --offline` dependency cache erişimini sınırlar, uygulamanın network'ünü değil.
  [`backend/main.py`](../../../backend/main.py) lifespan public Binance client'ı başlatır.
  Runtime offline iddiası network-denied test ve açık offline davranış gerektirir.
- [`smoke_desktop.py`](../../../scripts/smoke_desktop.py) için `--artifact` hash metadata'sıdır;
  tek başına DMG'yi mount etmez veya içindeki executable'ı seçmez. Final DMG smoke,
  mount edilmiş artifact'tan explicit `--executable` ile yapılmalıdır.
- `build_commit=UNKNOWN` exact-commit provenance değildir. Hash tek başına kaynak
  commit'i veya source completeness'i kanıtlamaz.
- [`run_local_ci.py`](../../../scripts/run_local_ci.py) macOS renderer preflight'ını atlar;
  smoke renderer equality kontrolü Windows/Linux için uygulanır. Mac smoke başarılı
  olsa da bu otomatik bir fail-closed WKWebView identity gate'i değildir.

## Kalan işlerin bağımlılık sırası

Aşağıdaki R kimlikleri planlama satırıdır; ayrı ayrı uygulandı veya `Verified` değildir.
Her satır uygulamadan önce bounded WP'ye ve fixture kabul kriterlerine dönüştürülür.
İlk hazır paket [P1-WP16](../../strategy/work-packages/P1-WP16-read-only-snapshot-completeness.md).

| Sıra | İş / kullanıcı değeri | Çıkış kanıtı | Önkoşul |
|---|---|---|---|
| R1 | Read-only snapshot completeness: kaybolan kaydı başarı diye göstermeme | Same-timestamp/page limit/repeated page/history boundary testleri; incomplete fail-closed | P1-WP11/12 mevcut sözleşmeleri |
| R2 | Perps accounting kapsamı ve financial reconciliation | Venue/account/market kimliği; unit/precision ve fee currency testleri; unknown funding açık; duplicate/correction/re-import oracle | R1 |
| R3 | Broker lifecycle → journal/Evidence Pack bağlantısı | Partial fills, scale-in/out, flip, orphan, canceled order ve tekrar import fixture'ları; satırdan raw source'a lineage | R2 |
| R4 | İlk değer akışı: import preview → discrepancy çözümleme → pack/export | UI/API entegrasyon testi; empty/partial/error states; temiz Mac'te sentetik uçtan uca senaryo | R1–3 |
| R5 | Weekly review ve versioned rule değerlendirmesi | Review dönemi/timezone, coverage/payda, as-of rule version, before/after seçimi; no-data sonuçları; kalıcı review kaydı | R4, P1-WP14 |
| R6 | Pilot öncesi yerel güvenilirlik/dağıtım kapısı | Runtime network-denied import/review/export, exact-commit mounted-DMG smoke, Mac renderer gate, veri koruma ve redacted destek çıktısı | R4–5; Windows pilotu için P0-WP11 çözümü |
| R7 | Kullanıcı değerini ölçme | Önce 5–8 nitelikli kullanıcıyla formative kullanım; sonra 40 kişilik/8 haftalık pilot; açık consent ve yerel metrik tanımı | R6, ürün sahibinin kullanıcı/pilot organizasyonu |
| M1 | Mevcut P2 recovery kusurunun bounded bakımı | Bitmeyen source gap sonrası bounded retry; stop/cancel/persistence önceliği; injection guard testleri | B3 reproduction; yeni soak öncesi zorunlu |
| Koşullu P2 | Trade'e bağlı gerekli market context | Kullanıcının hangi kararı cevaplayamadığı belirli; coverage/no-data UI; ölçülen darboğaza göre recorder | R4–7 bulguları; M1 varsa recovery kullanımı |

R1–R6 Faz 1 değer zincirini tamamlar, kapsamı genişletmez. M1 mevcut testnet güvenilirliği
bakımıdır, primary product critical path değildir; uzun soak'a dönülecekse atlanamaz.
R2'de desteklenecek dar perps altkümesi açıkça seçilmelidir; bütün Binance/OKX türev
türleri tek seferde desteklenmiş sayılmaz. Kullanıcıya satılan capability sınırı fixture
ve uçtan uca kanıt sınırından geniş olamaz.

### Pilot ölçüm sözleşmesi

- “Import success”: desteklenen format/market ve ilan edilen aralık için eksiksiz,
  reconciliation sonucu görünür import; yalnız HTTP 200 değildir. Unsupported ve
  incomplete sonuçlar ayrı sayılır, denominator'dan sessizce çıkarılmaz.
- “Evidence completeness”: gerekli alanlar ve kaynak kapsamı önceden tanımlı trade'ler;
  bilinmeyen fee/funding/market context ayrı gösterilir. Hash validity farklı metriktir.
- “Weekly active”: dönem içindeki anlamlı tamamlanmış review; uygulamayı açmak değildir.
- “Rule change”: önceki/yeni policy version ve effective time kayıtlı kullanıcı kararı;
  AI metni veya geleceğe dönük PnL garantisi değildir.
- Before/after karşılaştırmaları trade sayısı, exposure, veri kapsamı ve dönem farklarını
  gösterir; gözlemsel ilişki nedensel iyileşme diye sunulmaz.
- Telemetry varsayılan olarak buluta gönderilmez. Pilot paylaşımı açık rıza ve redaction
  ile yapılır. Test fixture'ları gerçek credential veya gerçek kullanıcı verisi gerektirmez.

## Şimdi yapılmayacaklar ve yeniden açma koşulları

Dağıtım için ek belge blocker'ı: `package.json` MIT beyan ediyor ancak checkout'ta
`LICENSE` yok. Lisans metni ve third-party notices ürün sahibince netleştirilmeli;
bu audit lisans eklemez veya hukuki izin varsaymaz. Root `ARCHITECTURE.md`,
`CONTRIBUTING.md` ve `global.md` içindeki eski AI/biometric, ModStore ve doğrudan
main push direktifleri de güncel ürün/yetki sınırlarıyla hizalanmıştır.

- **Rust/Arrow IPC/multi-process rewrite:** yalnız ölçülmüş gerçek workload darboğazı,
  Python baseline ve kullanıcı değerine bağlanan karşılaştırmalı benchmark sonrası.
- **Yeni attestation/bundle/soak katmanı:** mevcut kanıtın hangi kararı engellediği
  belirtilmeden eklenmez. 24 saat soak; M1, bounded shutdown, disk bütçesi, rapor saklama
  ve takip planı hazır olmadan başlatılmaz. Gapsiz kısa koşu yerine geçmez.
- **AI:** güvenilir evidence ve AI'sız review önce; kaynak/abstention eval ve consent
  sonra. AI risk motorunun veya kullanıcının yerine emir veremez.
- **Live execution/FIX/DEX/plugins/teams:** ayrı talep ve güvenlik kapıları; ADR-0003,
  açık kullanıcı onayı ve ilgili faz çıkışları olmadan açılmaz.
- **Ticari fiyat/rekabet iddiaları:** KPS-001'deki 2026-09-05 araştırması tarihsel
  hipotezdir. Bu denetimde web araştırması yapılmadı; güncel fiyat/pazar payı iddiası yok.
  Ücretli teklif veya mevzuat kararı öncesi güncel birincil kaynaklar yeniden doğrulanır.

## İş bitirme disiplini ve açık blocker'lar

Her WP: failing fixture → bounded uygulama → ilgili suite → riskine uygun full local
gate → docs/claim kontrolü → commit/push. `Active`, implementasyon geçmişi olan açık
kayıt anlamına gelebilir; sıradaki iş veya bütün acceptance maddelerinin geçtiği anlamına
gelmez. `Verified` kanıt commit'i/platformu/senaryosu ile sınırlıdır. Faz çıkışı ayrıca
kullanıcı metriği ve ürün sahibi kararı gerektirir. Main merge/release/tag ayrı onaylıdır.

Bugün açık olanlar: B1/B2 doğruluk işleri, B3 gerçek recovery, B4 kanıt sertleştirme,
uçtan uca review/pilot kanıtı ve Windows host doğrulaması. Bunlar docs değişikliğiyle
kapanmaz. Mevcut Mac geliştirme ortamı bounded geliştirmeye engel değildir; ticari
ve cross-platform release-ready sonucu çıkarılamaz. GitHub quota/disabled kayıtları
tarihsel olup bu denetimde mevcut hesap/billing durumu yeniden sorgulanmamıştır.

## Bu doküman değişikliğinin doğrulaması

Push sonrası güvenlik kontrolü (2026-09-08): GitHub varsayılan branch için 5 açık
Dependabot uyarısı bildirdi. Read-only alerts API, frontend dev dependencies için
Vitest `<3.2.6` critical, Vite `<=6.4.2` high/medium, Vite `<=6.4.1` medium ve
esbuild `<=0.24.2` medium aralıklarını döndürdü. Bu feature branch lock'u Vitest
`3.2.7`, Vite `6.4.3`, esbuild `0.25.12` içeriyor; listelenen beş aralığa girmiyor.
Bu, yeni kapsamlı dependency/security audit'i değildir. Default branch uyarıları
silinmedi/kapatılmadı; main'e otomatik merge yapılmadı. Release öncesi default branch
ve yayınlanacak lock için güvenlik durumu yeniden doğrulanmalıdır.

- `git diff --check`: PASS.
- `python3.11 scripts/check_release_truth.py`: PASS.
- `python3.11 scripts/verify_packaging.py`: PASS; 480 locale token parity korunuyor.
- Değişen 14 Markdown dosyasında yerel bağlantı hedefleri: 165 kontrol, kırık hedef yok.
  Bu kontrol dış URL'lerin güncelliğini veya tarihsel satır anchor'larını doğrulamaz.
- Runtime kodu değişmediğinden bu tur backend/frontend/full local CI yeniden çalıştırılmadı.
  Önceki 550/51 sonuçları yeni doküman commit'inin test koşusu olarak sunulmaz.

## Değişiklik geçmişi

### 1.0.0 — 2026-09-08

- P1 ürün değerine bağlı sıra, kod bulguları, kanıt sınırları ve koşullu yatırımlar ayrıldı.
