<!-- doc-role: archived -->
# P1-WP41 — Journal bulk CSV export and readable PDF reports

```yaml
work_package: P1-WP41
version: 1.0.0
status: Complete
date: 2026-09-16
```

Owner request (2026-09-16): add a visible **Export** flow to the trade journal (CSV for
spreadsheets; a readable PDF list plus a short period summary), with explicit scope
(filtered results vs all records), a date range and monthly reports, and a direct PDF save
on the single-trade Evidence Pack. Data accuracy rules: reuse existing calculation
services, show Europe/Istanbul dates and the report period/basis explicitly, separate open
/ closed / canceled records, never treat unknown PnL or fees as zero, never sum money
across unverified currencies, keep local TP/SL estimates separate as an "estimated gross
result", and keep CSV and PDF on the same filter/snapshot. This message is development and
test approval only: **no commit/push, Release, installed-app update, migration or MT5
persistence was performed.**

## Completion boundary

**Implemented and tested (synthetic fixtures):** backend `journal_export` service (one
snapshot → CSV + PDF), `/api/v1/journal/export` + `/api/v1/journal/export/preview`,
Evidence Pack `pdf` artifact, JournalView "Export" modal with scope/period/basis/format
controls and honest cancel/limit/error states, Evidence Pack PDF button, EN/TR/DE strings,
vendored Bitstream Vera fonts (Turkish coverage) for offline PDF rendering, and PDF
visual inspection (page numbers, repeating table headers, wrapped notes).

**Not yet verified / out of scope:** real pilot-data reports, real XM/MT5 compatibility,
commit/push/Release/installed-app update, any persistent MT5 import, and any new audit
beyond the targeted dependency/license checks recorded in
`security-report/dependency-audit.md`.

## User flow

- Journal toolbar → **Export**: scope **Filtered results** (every record matching the
  current filters, explicitly not the loaded page) or **All records**; date range with
  entry/close basis selection and a month preset; format CSV (Excel-compatible, UTF-8 BOM,
  formula-safe cells) or PDF (list + period summary, page numbers).
- Export button → single-record Evidence Pack now offers **JSON / HTML / CSV / PDF**;
  the PDF is a readable summary, the JSON remains the full payload artifact.

## Accuracy contract

- Dates are rendered and filtered on **Europe/Istanbul** calendar days; the artifact states
  the time zone, the period and the date basis (entry vs close).
- OPEN / CLOSED / CANCELED are separated; CANCELED records never join performance figures.
- Unknown PnL stays unknown: counted and excluded from totals, never zero-filled.
- Money totals are produced only inside one **server-verified quote asset** (instrument
  catalog); records without a verified quote asset are counted and excluded, and no
  conversion is applied.
- Local TP/SL tracking results (`basis = LOCAL_ESTIMATE`, gross, fees excluded) are shown in
  a separate "estimated gross result" section and never added to realized results.
- CSV and PDF share one snapshot object and one snapshot SHA-256 for the same filter input.
- Limits fail closed (`MAX_EXPORT_TRADES = 2000`, `MAX_EXPORT_BYTES = 8 MiB` below the
  desktop bridge cap): exceeding a limit raises an explicit error, never a silent truncation.

## Verification

- Backend `backend/tests/test_journal_export.py` — 33 tests: empty/single/multi-page PDF,
  entry/close monthly bounds, filtered-vs-all scope, canceled/unknown/unverified-currency/
  local-estimate separation, CSV↔PDF snapshot and row consistency, Turkish headers and
  glyphs, long notes, formula-safe cells, record/byte limits, endpoint status mapping,
  Evidence Pack PDF plus JSON/HTML/CSV regressions.
- Frontend `JournalExportModal.dom.test.tsx` (10), `JournalView.dom.test.tsx` (+1 export
  entry test), `TradeEvidencePanel.dom.test.tsx` (+2 PDF/limit tests); i18n parity, tsc and
  production build.
- PDFs rendered to PNG (Quartz) and inspected: numbered pages, repeating table headers,
  wrapped long notes, correct Turkish/German glyphs, no empty trailing page.
- Full suites and canonical local CI results are recorded in STATUS.

## Unchecked criteria

- [ ] Real pilot-data CSV/PDF review on this Mac (counts, totals, month boundaries).
- [ ] Pilot acceptance of the report layout and wording (EN/TR/DE).
- [x] Commit/push and installed-app update (owner approved 2026-09-16; evidence in STATUS).
