# ADR-0002 — Evidence Ledger ve Veri Katmanları

- Durum: Accepted
- Tarih: 2026-09-05
- Karar sahibi: Ürün/Mimari liderliği
- Strateji: KPS-001 v1.0.0

## Bağlam

Mevcut SQLite `INSERT OR REPLACE`, fiziksel silme ve DuckDB'ye atomik olmayan çift yazma
yaklaşımı audit trail üretmez. DuckDB candle/trade analitiği içerir; canonical tick veya
order lifecycle store değildir. SQLite WAL aynı anda tek writer kabul eder; DuckDB çoklu
proses merkezi yazma katmanı olarak tasarlanmamıştır.

## Karar

1. Order, fill, risk ve journal değişiklikleri SQLite'ta tek-yazarlı append-only canonical
   event ledger'a yazılır.
2. Market tick/order-book verisi immutable, segmentlenmiş ve hash manifestli Parquet'te
   tutulur.
3. DuckDB yalnızca yeniden üretilebilir analytical projection/query katmanıdır.
4. Bulk prosesler arası aktarım başlangıçta Arrow IPC üzerinden yapılır; Arrow Flight
   remote/multi-host gereksinimi doğmadan eklenmez.
5. Faz 2'de data recorder ayrı Rust/Tokio prosesine ayrılabilir. Control plane, research ve
   analytics orchestration Python'da kalır.

## Event sözlüğü

`IntentRecorded → RiskEvaluated → OrderSubmitRequested → VenueAck | VenueReject →`
`FillRecorded[0..n] → CancelRequested → CancelAck | CancelReject →`
`FeeAdjusted | TradeCorrected → PositionProjectionUpdated → JournalReviewAdded[0..n]`

Her event en az şu alanları taşır: `event_id`, `account_id`, `venue`, `occurred_at`,
`received_at`, venue ve local idempotency kimlikleri, `schema_version`, `adapter_version`,
`correlation_id`, `causation_id`, raw payload hash'i, normalize edilmiş payload,
`prev_hash` ve `event_hash`. Risk, model, prompt ve tool provenance referansları olayla
ilişkilendirilir.

## Dayanıklılık ilkeleri

- Evidence transaction'larında SQLite `synchronous=FULL` kullanılır.
- Global tek zincir yerine hesap + gün/segment bazlı hash chain kullanılır.
- Hash chain kendi başına harici kurcalamayı kanıtlamaz. Günlük kök imzası veya isteğe
  bağlı güvenilir timestamp ileride eklenebilir; blockchain varsayılan çözüm değildir.
- Parquet segmenti seal edilene kadar staging log'da tutulur; seal sonrası değiştirilmez.
- DuckDB silinip canonical kaynaklardan tamamen yeniden kurulabilmelidir.

## Reddedilen alternatifler

- SQLite'a tick/order-book yığmak: tek-writer darboğazını ve DB büyümesini yanlış yerde artırır.
- DuckDB'yi event system-of-record yapmak: transaction ve multi-process write modeli uygun değildir.
- İlk günden Kafka/Redpanda/Arrow Flight: tek kullanıcı masaüstü ürünü için operasyonel yük getirir.
- Tüm backend'i Rust'a çevirmek: doğrulanmış darboğaz olmadan migration riski yaratır.
