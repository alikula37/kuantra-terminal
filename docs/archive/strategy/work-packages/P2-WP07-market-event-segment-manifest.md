<!-- doc-role: archived -->
> Historical reference only. Not a current work order. Unchecked acceptance items remain open;
> see [current status](../../../strategy/STATUS.md). Read only for a relevant task.

# P2-WP07 — Rotated Market Event Segments ve Manifest Recovery

```yaml
document_id: P2-WP07
version: 1.0.0
status: Active
date: 2026-09-06
baseline: 4d08d98
strategy: KPS-001@1.0.0
adr: ADR-0001, ADR-0002
depends_on: P2-WP06 Durable Market Event Segment Writer
implementation_commits: fa19c65
```

## Problem

P2-WP06 tek JSONL segmentinin fsync/recovery davranışını kanıtladı; ancak dosya
boyutu büyüdükçe rotation ve restart sonrası segmentlerin tek global hash chain
olarak doğrulanması yok. Manifest olmadan klasör tarayıp dosya sırasını tahmin
etmek canonical event history için kabul edilemez.

## Karar

1. `MarketEventSegmentSet` global `chain_sequence` ve `prev_hash` değerlerini
   segmentler arasında taşır. Yeni segment ilk envelope'ını önceki segment head'i
   ile açar; segment içi writer P2-WP06 fsync sözleşmesini korur.
2. Manifest canonical JSON + `manifest_sha256` ile segment filename, sequence/hash
   sınırları, event count, set venue ve rotation limitini kaydeder.
3. Restart yalnızca manifest'te listelenen, descriptor'ı dosyayla eşleşen
   segmentleri kabul eder. Manifest yokken yetim segmentler veya dosya silinmesi
   otomatik keşif/onarım ile telafi edilmez; strict recovery fail-closed olur.
4. Set tek-yazarlı kalır. Rotation limiti event count'tur; byte/clock policy,
   compaction ve Parquet conversion sonraki karardır.

## Teknik teslimatlar

- Base sequence/head destekli JSONL segment writer.
- Manifest-backed segment rotation ve global chain recovery.
- Missing segment, manifest tamper ve cross-segment idempotency testleri.

## Acceptance criteria

- [x] `max_events_per_segment` ile rotation deterministiktir.
- [x] Restart sonrası tüm segmentler tek global chain olarak doğrulanır.
- [x] Manifest SHA ve segment descriptor mismatch fail-closed olur.
- [x] Missing segment directory listing ile yeniden yaratılmaz.
- [x] Duplicate identity segmentler arasında idempotent kalır.
- [x] Focused suite: `5 passed`.
- [x] Full backend suite: `548 passed, 1 skipped` (Mac local CI, 2026-09-08).
- [ ] Remote CI: GitHub Actions kota/bütçe nedeniyle geçici disabled.

## Kesinlikle kapsam dışı

- Multi-process/distributed writer lock.
- Parquet/Arrow/DuckDB compaction veya query projection.
- Live Binance transport, reconnect, source verification promotion.
- Retention/deletion policy ve cloud upload.

## Risk ve sonraki sınır

Manifest ve segment dosyası arasında crash sonrası ordering farkı kalabilir;
strict recovery bunu gizlemek yerine durdurur. Bir sonraki paket durable segment
recovery drill'ini fault injection ile genişletmeli ve güvenilir bir Parquet batch
converter için ölçülebilir throughput/durability SLA belirlemelidir.

## Değişiklik geçmişi

### 1.0.0 — 2026-09-06

- Global chain'i koruyan manifest-backed segment rotation sözleşmesi tanımlandı.
