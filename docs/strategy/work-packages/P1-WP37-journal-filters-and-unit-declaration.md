<!-- doc-role: current-work-package -->
# P1-WP37 — Multi-select journal filters and one-click unit declaration

```yaml
work_package: P1-WP37
status: InProgress
branch: main
baseline: c694712
```

Owner report (2026-09-15): "işlem günlüğü sayfasında filtreler çoklu seçilebilsin" and,
with a screenshot of the open XAUUSD position showing "Sözleşme büyüklüğü doğrulanmadı —
parasal K/Z hesaplanmaz", "bir de ekteki gibi hatayı yine veriyor. nasıl giderilir?"

Root cause of the second report: the server-verified instrument catalog (P1-WP34) covers
free provider **spot crypto** metadata (Binance/Bybit). XAUUSD is a commodity quoted by
Biquote; no public provider publishes a contract size for it, so the truth rules forbid
inventing one. The honest path is the owner's own `qty_unit=BASE` declaration — which
existed in the editor but was not discoverable from the position row that shows the
warning.

## Ordered acceptance

- [x] Journal symbol and status filters are multi-select checkbox dropdowns: selecting
  several values filters with OR inside a filter and AND across filters, the trigger
  shows the selected count, the panel has a clear action, and it closes on outside
  click.
- [x] Missing-data honesty is preserved: an empty selection means "all", symbols list
  derives from the loaded journal, and status options stay OPEN/CLOSED/CANCELED.
- [x] The open-positions row turns the unverified-unit warning into an action:
  when money math is unavailable and the row is editable, a "Birim beyan et" button
  opens the trade editor with a tooltip explaining that declaring BASE enables
  monetary P/L. Verified rows show no such button.
- [x] EN/TR/DE strings for the filter controls and the declaration action; i18n parity.
- [x] Tests: journal DOM test covers multi-symbol + multi-status selection and clearing;
  open-positions DOM tests cover the declaration CTA and its absence for verified rows.

## Scope boundaries

- No automatic contract-size inference for commodities/forex: only the owner's
  declaration or a provider's own spot metadata enables money math (P1-WP34 rule).
- The journal filter UI stays client-side over the loaded page set; no new backend
  query parameters.
- The editor remains the single write path for `qty_unit`; no new endpoint.

## Evidence

- Frontend **39 files / 226 tests** (new: multi-select filtering across symbols and
  statuses with clearing, declaration CTA calls the editor, no CTA once verified).
- i18n **1032/1032/1032**; `npx tsc --noEmit` clean.
- The owner's XAUUSD trade (`TRD-1789469630309`, SELL 1000 XAUUSD, quote LIVE via
  `biquote_public`) can now be resolved in one click from the dashboard row; declaring
  `qty_unit=BASE` makes its open P/L and R compute from the live quote.

### Clean build and installed-app update

Per the owner standing instruction, the verified change was committed and the Mac's
installed application was rebuilt from the clean commit (details appended after the run).
