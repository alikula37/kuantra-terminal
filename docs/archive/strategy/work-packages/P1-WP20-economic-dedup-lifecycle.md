<!-- doc-role: archived -->
> Historical reference only. Not a current work order. Acceptance evidence and remaining
> boundaries are recorded here; see [current status](../../../strategy/STATUS.md).
> Read only for a relevant task.

# P1-WP20 — Economic Dedup & Lifecycle Trade Grouping Contract

```yaml
work_package: P1-WP20
version: 1.0.0
status: Verified
date: 2026-09-08
baseline_commit: c1f131f
implementation_commit: 5d691b9
branch: codex/p1-wp01-evidence-ledger
strategy: KPR-001@current
depends_on: P1-WP19
```

## Problem ve amaç

CSV ve read-only API gözlemleri aynı ekonomik fill’i farklı source identity’lerle
taşıyabilir. Tersine, aynı external ID farklı account/venue/market scope’larında
geçerli olabilir. Bu gözlemler doğrudan trade sayılırsa duplicate fill, late
correction, partial fill, scale-in/out veya flip durumları yanlış ekonomik sonuç
üretir. P1-WP20’nin amacı source observation identity ile economic trade identity’yi
ayıran, deterministic ve lineage-preserving bir grouping contract kurmaktır.

Bu paket yeni connector, live order veya tam PnL hesaplaması değildir. P1-WP19’un
funding/account coverage sınırları korunur; eksik finansal kapsam grouping sonucu ile
complete account state olarak sunulmaz.

## Beklenen davranış sözleşmesi

1. Aynı ekonomik fill farklı CSV/API source’larında tekrarlandığında tek ekonomik
   contribution üretilir; source observations ve provenance kaybolmaz.
2. Aynı external ID farklı account, source exchange veya market type scope’larında
   çakışmaz. Scope eksik veya çelişkili ise group `UNRESOLVED`/`PARTIAL` kalır.
3. Partial fill’ler order lifecycle’dan ayrılır; scale-in/out, flip, cancel/reject,
   orphan fill ve late correction için açık lifecycle state ve discrepancy üretilir.
4. Correction yeni immutable observation/event olarak ilişkilendirilir; önceki
   observation silinmez veya sessizce yeniden yazılmaz. As-of grouping deterministic
   kalır ve correction lineage taşır.
5. Aynı input sırası, batch bölme/birleştirme veya tekrar import ekonomik group
   sonucunu değiştirmez; gerçek correction sonucu açıkça değiştirir.
6. Grouping yalnız read-only/fixture gözlemlerinde çalışır. AI, risk motoru veya
   execution katmanı order authority alamaz.

## İlk dosya/test kapsamı

- `backend/app/services/` içinde ayrı bounded economic grouping service/model.
- P1-WP11 lifecycle records, P1-WP17 source identity ve P1-WP18 Decimal payload
  contract’larıyla adapter; P1-WP19 account event’leri trade grouping’e sessizce
  karıştırılmaz.
- `backend/tests/` overlapping source, duplicate fill, partial/scale/flip,
  cancellation/orphan, late correction, multi-account collision ve permutation
  fixtures.
- Mevcut evidence ledger’a yeni schema event type ekleme ayrı onaylı migration
  olmadan yapılmaz; canonical correction/lineage sınırı korunur.

## Acceptance criteria

- [x] Önce kırmızı, sonra yeşil: aynı economic fill overlapping CSV/API source’larında
  tek contribution ve iki source lineage ile görünür.
- [x] Same external ID farklı account/source/market scope’larında ayrılır; eksik veya
  çelişkili identity `UNRESOLVED`/`PARTIAL` olur.
- [x] Partial fill, scale-in/out, flip, cancel/reject ve orphan fill state/discrepancy
  sözleşmeleri deterministic olarak test edilir.
- [x] Late correction yeni immutable lineage üretir; eski observation korunur ve
  re-import idempotent kalır.
- [x] Sıralama, batch partition ve tekrar import ekonomik sonucu değiştirmez; gerçek
  correction açıkça değiştirir.
- [x] P1-WP17/P1-WP18/P1-WP19 regression, focused suite `8 passed`, full backend
  suite `595 passed, 2 warnings` ve Mac local CI `MERGE READY` kanıtı kaydedildi:
  frontend `51`, i18n `480/480`, production build, arm64 desktop build, WKWebView
  native smoke ve packaging preflight geçti.
- [x] Exact implementation commit `5d691b9`; changed files, unsupported/unknown semantics ve sonraki P1-WP21
  journal/evidence propagation bağımlılığı bu kayda yazılır.

## Verified implementation notes

- `EconomicGroupingService` source observation identity’yi account, venue, source
  exchange, market type, source document ve row hash ile scope’lar; economic group
  identity’yi bu source kimliğinden ayrı tutar.
- Aynı explicit economic key veya aynı source-scoped fill ID farklı CSV/API
  observations arasında tek contribution üretir; source lineage listesi korunur.
  Quantity/price conflict sessizce netlenmez ve `UNRESOLVED` kalır.
- Order lifecycle partial/canceled/rejected/orphan durumlarını ayrı state olarak
  raporlar. One-way position mode açıkça verilmeden scale-in/out/flip semantics
  üretilmez; bu paket PnL hesaplamaz.
- Late correction eski group snapshot’ını silmez; effective contribution ve correction
  lineage birlikte taşınır. Ledger/projection write propagation P1-WP21’e bırakılmıştır.

## Kapsam dışı

Tam exchange statement accounting, tax/accounting advice, cross-currency conversion,
new connector, live order, execution routing, AI decision/order, market-data tick
reconstruction, user migration ve funding/transfer için yeni ledger schema migration.
