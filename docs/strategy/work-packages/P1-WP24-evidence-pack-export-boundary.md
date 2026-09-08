<!-- doc-role: current-work-package -->
# P1-WP24 — U03 Trade Evidence Pack & Deterministic Export Boundary

```yaml
work_package: P1-WP24
version: 1.0.0
status: Ready
date: 2026-09-08
baseline_commit: 51ee968
branch: codex/p1-wp01-evidence-ledger
strategy: KPR-001@current
depends_on: P1-WP23, P1-WP22, P1-WP15, P1-WP13, P1-WP14
```

## Amaç

P1-WP22 ile bağlanan source-linked Evidence Pack akışını U03 ürün sözleşmesiyle
tamamlamak: timeline, fee/funding ve market-context coverage, applicable rule,
redaction ve deterministic export aynı canonical read adapter'dan üretilecek.
Kullanıcıya gösterilen pack ile JSON/HTML/tabular export arasında sessiz alan veya
coverage farkı oluşmayacak.

Bu paket yeni ledger schema/event, funding/transfer modeli, connector veya execution
capability eklemez. `UNKNOWN`, `PARTIAL` ve `NOT_AVAILABLE` downstream'de `complete`,
`PASS` veya sıfır değere dönüşmez. Analytics unavailable ise açıkça unavailable kalır.

## Davranış sözleşmesi

- Timeline ve özet alanları canonical evidence/projection read adapter'dan gelir;
  frontend yalnızca yeniden etiketleyebilir, finansal gerçek üretemez.
- Fee/funding/context coverage, source event hash, provenance, correction lineage ve
  as-of/revision ilişkisi UI ve export'ta korunur.
- Export deterministiktir: aynı canonical snapshot ve export seçenekleri byte-stable
  JSON/HTML/tabular çıktı üretir. Kullanıcı veya local path bilgisi gereksiz yere
  dışarı taşınmaz; credential, raw secret ve redacted alanlar çıkmaz.
- HTML output'ta escaping zorunludur. CSV/tabular output destekleniyorsa formula
  injection karakterleri veri olarak güvenli biçimde yazılır; export edilen değer
  executable spreadsheet formula olamaz.
- Boş/partial/unknown/unavailable analytics açık durum olarak gösterilir; no-data
  sonucu başarılı review, tam coverage veya finansal doğrulama gibi görünmez.
- Correction sonrası eski evidence korunur; yeni revision/as-of ve source lineage
  pack içinde görünür. Funding/transfer için yeni event type veya ledger schema yoktur.

## Red test kapsamı

- Backend: canonical pack snapshot ile UI/API/export alan eşitliği, deterministic
  serialization, HTML escaping, tabular formula-injection boundary, redaction,
  unavailable coverage ve correction/as-of lineage.
- Frontend: timeline/coverage/rule/export states; empty/partial/unknown/unavailable
  sonuçları; source/evidence linkleri ve export error/retry; EN/TR/DE parity.
- Integration: import → reconciliation decision/correction → Evidence Pack → export;
  replay/duplicate aynı snapshot'ı üretir ve eski kanıt silinmez.

## Acceptance criteria

- [ ] Trade Evidence Pack timeline, coverage ve applicable rule alanları canonical read adapter ile UI/API/export arasında tutarlıdır.
- [ ] `UNKNOWN`/`PARTIAL`/`NOT_AVAILABLE`/unsupported analytics fail-closed görünür; `complete` veya zero'a dönüşmez.
- [ ] Source hash, provenance, correction lineage ve as-of/revision ilişkileri export'ta korunur.
- [ ] JSON/HTML ve desteklenen tabular export deterministic, redacted ve injection-safe'tir.
- [ ] Empty/partial/unknown/unavailable state'leri no-data sonucunu PASS gibi göstermez.
- [ ] Correction/replay sonrası eski evidence korunur ve aynı input aynı pack snapshot'ını üretir.
- [ ] Focused red→green tests, full backend/frontend suite ve Mac local CI sonucu kaydedilir.

## Kesinlikle kapsam dışı

Funding/transfer ledger schema, full-account PnL/tax accounting, yeni venue/connector,
live broker order, AI recommendation/order authority, weekly review/R5, migration,
Developer ID signing/notarization, Windows/Linux host proof, pilot ve release kararı.

## İlk inceleme alanı

- `backend/app/services/trade_read_adapter.py` ve
  `backend/app/services/evidence_pack_export.py` canonical boundaries.
- `TradeEvidencePanel`, mevcut export/download yüzeyi ve locale parity.
- P1-WP22 import/reconciliation review ile P1-WP23 decision/correction lineage
  fixture'ları.
- Önce red test; yalnız U03 sözleşmesinin gerektirdiği bounded UI/API/export boşluğu
  uygulanır. Yeni ledger şeması veya funding/transfer event'i bu pakette açılmaz.
