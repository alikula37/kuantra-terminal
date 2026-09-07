# P2-WP06 — Durable Market Event Segment Writer

```yaml
document_id: P2-WP06
version: 1.0.0
status: Active
date: 2026-09-06
baseline: 62a21d2
strategy: KPS-001@1.0.0
adr: ADR-0001, ADR-0002
depends_on: P2-WP05 Canonical Market Event Envelope ve Hash Chain
implementation_commits: 3696fae
```

## Problem

P2-WP05 canonical envelope'ı yalnızca process belleğinde tutuyor. Gerçek data
plane bağlanmadan önce fsync, restart recovery ve yarım/bozuk segment davranışı
ölçülmezse “durable market event” iddiası yine test edilemez kalır.

## Karar

1. İlk durable sınır Parquet değil, tek-yazarlı append-only JSONL segmentidir.
   Her satır canonical envelope JSON'u ve newline ile yazılır; `flush + fsync`
   başarılı olmadan memory index güncellenmez.
2. Writer açılırken tüm satırlar sequence, `prev_hash`, payload/event hash ve
   source identity açısından taranır. Hatalı/yarım son satır otomatik truncate
   edilmez; strict modda açılış fail-closed olur.
3. Writer aynı source identity + payload için idempotent döner; farklı payload
   conflict'tir. Yeni satırın chain position'ı segment head ile birebir ardışık
   olmak zorundadır.
4. Bu paket single-process/single-writer sözleşmesidir. Multi-process lock,
   Parquet compaction, DuckDB hydration ve cross-segment manifest sonraki
   paketlerdir.

## Teknik teslimatlar

- `MarketEventSegmentWriter` ve `recovery_report()`.
- Canonical JSONL newline record, fsync sonrası memory commit.
- Restart replay, duplicate/idempotency ve chain position validation.
- Corrupt hash ve incomplete final line fail-closed drill'i.

## Acceptance criteria

- [x] Segment yazımı newline + fsync ile tamamlanır.
- [x] Restart sonrası valid segment head ve event count yeniden bulunur.
- [x] Duplicate identity idempotent, farklı içerik conflict olur.
- [x] Yanlış chain position yazılmadan reddedilir.
- [x] Hash corruption veya incomplete line otomatik onarılmaz.
- [x] Focused suite: `5 passed`.
- [x] Full backend suite: `548 passed, 1 skipped` (Mac local CI, 2026-09-08).
- [ ] Remote CI: GitHub Actions kota/bütçe nedeniyle geçici disabled.

## Kesinlikle kapsam dışı

- Multi-process writer lock/lease veya distributed coordination.
- Parquet/Arrow/DuckDB sink ve compaction.
- Binance transport/reconnect ve live source verification.
- UI, execution, HFT latency veya retention policy.

## Risk ve sonraki sınır

JSONL segment yüksek hacimli OLAP formatı değildir; tek writer ve tek dosya
ölçeğinde tutulur. Bir sonraki paket segment rotation, manifest/recovery drill
ve Parquet batch conversion kararını gerçek disk benchmark'ı ile vermelidir.

## Değişiklik geçmişi

### 1.0.0 — 2026-09-06

- Fsync-backed single-writer JSONL segment ve fail-closed restart recovery
  sözleşmesi tanımlandı.
