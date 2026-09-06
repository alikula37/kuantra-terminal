# P1-WP10 — CSV Import Evidence Provenance ve Fail-Closed Validation

```yaml
document_id: P1-WP10
version: 1.0.0
status: Active
date: 2026-09-06
baseline: 2573bb6
strategy: KPS-001@1.0.0
adr: ADR-0002, ADR-0003
depends_on: P1-WP01 canonical evidence ledger, P1-WP02 atomic journal evidence write
implementation_commits: d62db79
```

## Problem

CSV importer geçersiz veya eksik timestamp'i mevcut zaman ile dolduruyor, sembol ve
side eksikliğinde varsayılan değer seçiyor, generic qty eksikliğini `1.0` yapıyor ve
import edilen satırı hangi dosyanın hangi satırından geldiğini canonical event'te
taşımıyordu. Bu davranış import'u “başarılı” gösterse bile Trade Evidence Pack'in
kaynak kanıtını zayıflatıyordu.

## Karar

1. Timestamp artık zorunludur. Explicit timezone yoksa UTC varsayımı açıkça uygulanır;
   parse edilemeyen veya eksik değer satırı reddeder. Receipt time hiçbir zaman trade
   zamanı olarak yazılmaz.
2. Symbol, side, entry price ve qty zorunlu/pozitif alanlardır. Closed trade için
   valid exit price gerekir. Eksik alanlar `BTCUSDT`, `BUY`, `1.0` veya benzeri
   sentetik varsayılanlara dönmez.
3. Import edilen byte dizisinin `source_file_sha256` özeti ve normalize raw CSV row'un
   `source_row_sha256` özeti üretilir. Satır numarası, format ve dosya adı ile birlikte
   `LegacyTradeImported` event provenance'ına girer; ham CSV veya credential ledger'a
   yazılmaz.
4. Preview ve import response dosya hash'ini taşır. Böylece kullanıcı aynı dosyanın
   tekrar import'unu ve Evidence Pack'teki kaynak bağını kontrol edebilir.
5. Duplicate semantic trade'ler mevcut fingerprint ile atlanmaya devam eder; yeni
   provenance alanı duplicate'i zorla ikinci bir trade/event yapmaz.

## Teknik teslimatlar

- `CsvTradeImporterService.parse_timestamp()` fail-closed UTC normalizer.
- Strict symbol/side/numeric/closed-exit validation ve no-default parser contract.
- `SyncPipeline.record_and_sync_trade(provenance_extra=...)` ile source metadata'nın
  atomik journal/evidence write'a taşınması.
- CSV file hash, row hash, row number ve format provenance'ı.
- Parser, preview, ledger provenance ve legacy regression testleri.

## Acceptance criteria

- [x] Eksik/unparseable timestamp current time ile doldurulmuyor; row reddediliyor.
- [x] Eksik symbol/side/qty/closed exit fail-closed kalıyor.
- [x] File SHA-256 ve row SHA-256 canonical `LegacyTradeImported` event'te okunabiliyor.
- [x] Preview raw payload göstermeden hash ve row identity taşıyor.
- [x] Aynı semantic CSV trade'i ikinci kez import edildiğinde duplicate olarak atlanıyor.
- [x] Focused import/provenance suite: `25 passed`.
- [x] Full backend suite: `386 passed, 1 skipped`.
- [x] `git diff --check` başarılıdır.
- [ ] Remote three-OS CI: GitHub Actions kota/bütçe nedeniyle geçici disabled;
  reset sonrası `d62db79` için yeniden çalıştırılacak.

## Kesinlikle kapsam dışı

- Binance/Bybit API üzerinden otomatik read-only sync veya yeni credential yüzeyi.
- CSV satırlarını broker fill/order lifecycle olarak doğrulama.
- Exit price veya realized PnL çıkarımı için sentetik piyasa verisi.
- Canlı order entry, CCXT write path, FIX/DMA ve reconciliation engine.
- Raw CSV içeriğini ledger'a veya cloud'a yükleme.

## Risk ve sonraki sınır

Parser artık veri uydurmuyor; bunun bedeli kötü formatlı export'larda import success
oranının düşebilmesidir. Pilotta `import_success_rate >= 90%` ölçülmeli, ancak bu eşik
geçersiz satırları sessizce kabul ederek sağlanmamalıdır. Sonraki bounded iş, Binance/OKX
read-only order/fill connector'ını aynı event/provenance contract'ına bağlamak ve import
reconciliation raporu üretmektir. Bu paket tek başına broker verisini “reconciled” ilan etmez.

## Değişiklik geçmişi

### 1.0.0 — 2026-09-06

- İlk fail-closed CSV parser, source hash provenance ve canonical event integration.
