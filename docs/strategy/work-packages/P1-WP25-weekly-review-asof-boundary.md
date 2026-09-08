<!-- doc-role: current-work-package -->
# P1-WP25 — U04 Weekly Review & As-of Determinism Boundary

```yaml
work_package: P1-WP25
version: 1.0.0
status: Ready
date: 2026-09-08
baseline_commit: afedb70
branch: codex/p1-wp01-evidence-ledger
strategy: KPR-001@current
depends_on: P1-WP24, P1-WP23, P1-WP21, P1-WP14
```

## Amaç

U04 weekly review akışını, belirli period/timezone ve evidence snapshot'ı üzerinden
tekrar üretilebilir hale getirmek. Kullanıcı, o hafta hangi canonical evidence'ın
mevcut olduğunu, hangi coverage/discrepancy/rule durumlarının review'ü sınırladığını
ve sonradan gelen correction'ın eski değerlendirmeyi nasıl etkilediğini açıkça görür.

Bu paket haftalık review'ü measured financial success, tax/accounting completeness,
AI recommendation veya trading authority olarak sunmaz. Yeni ledger schema/event,
funding/transfer modeli, connector, live execution veya gerçek kullanıcı verisi
eklenmez; mevcut immutable review/correction event sözleşmeleri kullanılır.

## Davranış sözleşmesi

- Review period başlangıç/bitişi ve IANA timezone explicit input'tur; aynı input,
  canonical source ve rule snapshot aynı review id/snapshot üretir.
- As-of cutoff açıkça kaydedilir. Cutoff sonrasında gelen event/correction eski
  snapshot'ı sessizce değiştirmez; yeni revision veya `STALE_REVIEW` uyarısı üretir.
- Rule effective time review cutoff'a göre değerlendirilir; hindsight rule veya
  sonradan değişen playbook geçmiş haftaya geriye dönük uygulanmaz.
- Empty, partial, unknown, not-available, unsupported ve malformed evidence review
  durumunu `NOT_READY`/`LIMITED` olarak gösterebilir; hiçbir no-data durumu `PASS`,
  `COMPLETE` veya finansal başarıya yükselmez.
- Kullanıcı notu ve review tamamlanma kararı açık user action olarak evidence'e
  bağlanır; “complete” düğmesi veri doğruluğu veya kârlılık onayı değildir.
- Replay/duplicate aynı review snapshot'ını üretir; correction eski pack/review
  evidence'ini silmez.

## Red test kapsamı

- Backend: timezone boundary, DST/period determinism, as-of cutoff, late correction,
  rule effective time, no-data/partial/unknown propagation, duplicate/replay ve
  invalid period/unsupported timezone negative cases.
- Frontend: empty/limited/not-ready/ready review states, evidence coverage/rule
  warning, stale revision warning, explicit note/completion confirmation ve locale
  parity.
- Integration: import → reconciliation decision/correction → Evidence Pack → weekly
  review snapshot; aynı source ile reopen aynı snapshot'ı üretmeli.

## Acceptance criteria

- [ ] Period, timezone, as-of cutoff ve rule snapshot review/API/export'ta explicit ve deterministic'tir.
- [ ] Late correction/re-import eski review snapshot'ını silmez; stale/revision lineage görünür.
- [ ] `UNKNOWN`/`PARTIAL`/`NOT_AVAILABLE`/unsupported/malformed evidence no-data sonucunu PASS göstermez.
- [ ] Rule effective time hindsight uygulamasını engeller; applicable rule provenance korunur.
- [ ] User note ve completion kararı açık audit evidence üretir; completion financial validation değildir.
- [ ] Duplicate/replay, DST/timezone ve invalid-boundary testleri aynı snapshot/fail-closed davranışı kanıtlar.
- [ ] Focused red→green tests, full backend/frontend suite ve Mac local CI sonucu kaydedilir.

## Kesinlikle kapsam dışı

Full-account PnL/tax accounting, funding/transfer ledger schema, yeni venue/connector,
live broker order, AI recommendation/order authority, migration, signing/notarization,
Windows/Linux host proof, pilot, release ve kullanıcı başarı iddiası.

## İlk inceleme alanı

- P1-WP24 canonical Evidence Pack snapshot/export ve P1-WP23 decision/correction
  lineage.
- Existing review event/API boundary, timezone utilities, playbook/risk policy
  effective-time fields ve current locale states.
- Önce red test; yalnız U04 determinism ve bounded review state sözleşmesinin
  gerektirdiği implementation yapılır. Yeni ledger schema/event ancak ayrı ADR ve
  work-package kararıyla ele alınır.
