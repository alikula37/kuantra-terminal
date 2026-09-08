<!-- doc-role: archived -->
> Historical reference only. Not a current work order. Unchecked acceptance items remain open;
> see [current status](../../../strategy/STATUS.md). Read only for a relevant task.

# P1-WP07 — Trade Evidence Pack API

```yaml
document_id: P1-WP07
version: 1.0.0
status: Active
date: 2026-09-06
baseline: 9eb9950
strategy: KPS-001@1.0.0
adr: ADR-0002, ADR-0003
depends_on: P1-WP06 bulk OLAP sync evidence gate
implementation_commits: 65e4b71
```

## Problem

Kuantra'nın yeni kimliği trade sonucunu yalnızca PnL satırı olarak değil, kararın
kanıt paketi olarak göstermeyi gerektiriyor. Projection read adapter mevcut snapshot'ı
güvenli taşıyordu; fakat kullanıcı veya gelecekteki AI auditor için event sırası,
hash/provenance ve ledger bütünlüğü tek read-only sözleşmede yoktu.

## Karar

1. `GET /api/v1/trades/{trade_id}/evidence` tek bir read-only Trade Evidence Pack
   döndürür.
2. Paket; mevcut trade snapshot'ı, `read_source`, projection coverage, ledger
   integrity özeti ve trade ile eşleşen immutable event'leri taşır.
3. Event çıktısı `event_id`, tip, UTC zamanlar, chain sequence, `prev_hash`,
   `event_hash`, `raw_payload_sha256`, normalized payload ve provenance içerir;
   raw payload byte'ları dışarı verilmez.
4. Coverage hazır değilse paket bunu `read_source=compatibility_legacy` ve
   `coverage.ready=false` ile açıkça belirtir; adapter projection ile legacy veriyi
   karıştırmaz.
5. Bu API AI'ya emir verme, broker çağırma veya risk kararı yetkisi vermez. İleride
   AI auditor yalnız bu kaynak-linked paketi okuyarak açıklama üretebilir.

## Teknik teslimatlar

- `EvidenceLedgerRepository.list_events_for_trade`: correlation ID ve legacy snapshot
  source ID eşleştirmesi.
- `TradeReadAdapter.get_evidence_pack`: coverage-gated snapshot + verified ledger
  integrity + safe event projection.
- `GET /api/v1/trades/{trade_id}/evidence` endpoint'i.
- Raw payload dışlama, event sırası, ledger validasyonu ve endpoint regression testleri.

## Acceptance criteria

- [x] OPEN → CLOSED lifecycle'ı event sırası ile tek pakette görülebilir.
- [x] Ledger hash/provenance alanları kaynak-linked olarak döner.
- [x] Raw payload alanı response'a sızmaz.
- [x] Coverage/read source durumu response'ta açıkça bulunur.
- [x] Bilinmeyen trade için endpoint 404 döner.
- [x] Focused evidence/projection suite: `12 passed`.
- [x] Full backend suite: `377 passed, 1 skipped`.
- [x] `git diff --check` başarılıdır.
- [ ] Remote three-OS CI: GitHub Actions kota/bütçe nedeniyle geçici disabled;
  reset sonrası `65e4b71` için yeniden çalıştırılacak.

## Kesinlikle kapsam dışı

- Event ledger'a yeni event yazmak veya mevcut event'i değiştirmek.
- AI prompt/model inference, local LLM sidecar veya execution tool-call.
- Broker reconciliation, FIX/DMA, live order lifecycle veya market-data replay.
- Frontend Evidence Pack ekranı; API sözleşmesi önce stabilize edilecek.

## Sonraki iş

Evidence Pack schema'sı sabitlendikten sonra P1-WP08 olarak deterministic replay/
market-context attachment ele alınmalıdır. AI auditor bu paketi kaynak gösterebilen
bir consumer olarak ancak replay ve provenance completeness ölçümleri sağlandığında
devreye alınmalıdır.

## Değişiklik geçmişi

### 1.0.0 — 2026-09-06

- İlk source-linked, raw-payload-free Trade Evidence Pack read API.
