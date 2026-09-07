# P2-WP01 — Sequence Gap-Aware Market Context

```yaml
document_id: P2-WP01
version: 1.0.1
status: Active
date: 2026-09-06
baseline: 89f2430
strategy: KPS-001@1.0.0
adr: ADR-0001, ADR-0002
depends_on: P1-WP08 Deterministic Replay ve Market-Context Attachment, P1-WP09 Market-Data Provenance Schema, P1-WP15 Trade Evidence Pack UI
implementation_commits: 623fbda
```

## Problem

Replay'in candle zaman aralığı contiguous olsa bile feed provenance sequence'inde
gaps veya kısmi coverage bulunabiliyordu. Önceki özet yalnızca sequence alanının
varlığını raporluyor, `source_verified` kararı sequence sürekliliğini test etmiyordu.
Bu, gerçek feed recovery ve Phase 2 replay öncesinde ölçülemeyen sessiz gap riski
oluşturuyordu.

## Karar

1. `source_sequence` değerleri context candle zaman sırasına göre strict +1
   ilerlemiyorsa context `sequence_coverage=GAPPED` olur ve `source_verified=false`
   kalır. Aradaki eksik sequence sayısı ve ilk 20 gap aralığı raporlanır.
2. Bazı candle'larda sequence olup bazılarında yoksa durum `PARTIAL` olur;
   bu da verified sayılamaz. Sequence hiç yoksa mevcut `NONE` sözleşmesi korunur.
3. Sequence sürekliliği bar timestamp coverage'dan ayrıdır. Trade window candle'ları
   mevcut olsa bile feed gap'i açıklanır; mevcut bar-approximation replay sessizce
   “tam verified market truth” iddiasına yükselmez.
4. Binance public kline event'inde gerçek monotonic sequence bulunmadığı için bu
   paket yeni sequence üretmez ve mevcut Binance kline adapter'ını yapay şekilde
   verified yapmaz.

## Teknik teslimatlar

- `candle_evidence._provenance_summary` strict sequence continuity evaluator.
- `sequence_contiguous`, `sequence_gap_count`, `sequence_gaps` market-context alanları.
- `provenance()` içinde sequence-gap policy açıklaması.
- Gap/partial/clean sequence regression tests.
- Evidence Pack UI'nın nested market-context verification alanını okuması.

## Acceptance criteria

- [x] Contiguous sequence `COMPLETE` ve tüm diğer provenance alanları geçerliyse verified olabilir.
- [x] Atlanan sequence `GAPPED` ve `source_verified=false` üretir.
- [x] Kısmi sequence `PARTIAL` ve `source_verified=false` üretir.
- [x] Gap raporu sınırsız büyümez; en fazla 20 aralık ve bounded count taşır.
- [x] Mevcut candle timestamp gap rejection ve replay fingerprint davranışı korunur.
- [x] Focused suite: `49 passed`.
- [x] Full backend suite: `548 passed, 1 skipped` (Mac local CI, 2026-09-08).
- [ ] Remote CI: GitHub Actions kota/bütçe nedeniyle geçici disabled.

## Kesinlikle kapsam dışı

- Binance kline payload'ına gerçekte olmayan sequence numarası eklemek.
- Tick/order-book recorder, snapshot+delta synchronization veya Rust/Tokio data plane.
- Gap'leri doldurmak için synthetic candle/tick üretmek.
- `source_verified` bayrağını UI veya kullanıcı override'ı ile yükseltmek.

## Risk ve sonraki sınır

Sequence semantiği venue/feed'e göre değişebilir; generic `+1` kuralı yalnızca
monotonic sequence sözleşmesi ilan eden feed'lerde kullanılmalıdır. Bir sonraki
Phase 2 paketi gerçek Binance snapshot+delta order-book sequence/reconnect
boundary'sini ayrı bir adapter contract'ı olarak ele almalıdır.

## Değişiklik geçmişi

### 1.0.0 — 2026-09-06

- Sequence gap truth contract, market-context provenance alanları ve regression
  coverage uygulandı.

### 1.0.1 — 2026-09-08

- Mac temiz ortamında sequence-gap, candle provenance ve deterministic replay
  ilişkili focused suite `62 passed` olarak yeniden doğrulandı.
- P2-WP01 sonrası tam local CI `548 passed, 1 skipped` ile merge-ready oldu;
  remote CI kanıtı GitHub Actions kota/bütçe kısıtı nedeniyle hâlâ beklemede.
