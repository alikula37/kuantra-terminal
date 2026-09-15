<!-- doc-role: archived -->
# P1-WP40 — MT5 HTML report safe reading and preview

```yaml
work_package: P1-WP40
status: Complete
branch: main
baseline: 5239a39
```

Owner decision (2026-09-15): pilots need to bring XM/MetaTrader gold and other trades
into Kuantra. The previous OKX A1.2.1 proposal was **not approved and is deferred**;
only this bounded MT5 HTML **preview** package is approved. Persistence/import,
migration and financial schema extensions are **not** approved. No commit/push,
Release, installed-app update, user-database access, credential request or paid service
was performed.

**Statement import is not live tracking.** This package reads one report file in memory
and shows a preview; it writes nothing to the ledger, the observation log, the journal
or the portfolio, and no price/close synchronization exists.

## Completion boundary

**Completed:** safe parsing of the defined English MT5 ReportHistory HTML format; file
selection, preview and error/uncertainty display; separation of order and deal
identities; no persistent writes anywhere; synthetic-fixture validation (not XM
compatibility evidence); EN/TR/DE UI strings and accessible modal reuse.

**Not yet verified or out of scope:** real XM report compatibility; which terminal
pilots actually use (MT4 vs MT5); the real export flow on a Mac terminal; persistent
import; live price, position or close synchronization. No "XM supported" or "broker
integration complete" claim is made.

## Supported format contract (v1, explicitly bounded)

- English MetaTrader 5 "ReportHistory" HTML export (`History → right-click → Report →
  HTML`), parsed with the standard library only [Resmî belge: MetaTrader 5 Help, Trading
  Report].
- Required section markers `Orders` and `Deals`. The known sections `Positions`,
  `Working Orders`, `Summary` and `Details` are reported as **not processed in this
  preview** instead of being silently dropped.
- Orders columns: Open Time, Order, Symbol, Type, Volume, Price, S/L, T/P, Time, State.
- Deals columns: Time, Deal, Symbol, Type, Direction, Volume, Price, Order, Commission,
  Fee, Swap, Profit, Balance.
- Order and deal identities stay separate (`SOURCE_ORDER_ID` / `SOURCE_DEAL_ID`); a
  deal's order reference is `related_order_id`, never its identity.
- Values are read exactly as reported: `time_basis = SOURCE_LOCAL_TIME_UNVERIFIED`
  (no UTC or Turkey-time conversion), `volume_unit = SOURCE_LOT` (no lot→ounce/base
  conversion), money fields carry `reported_*_source` and a parsed value only when the
  number is unambiguous; missing values stay absent, never zero.
- Fail-closed: wrong platform/template (`UNSUPPORTED_TEMPLATE`), unknown-language
  markers (`UNSUPPORTED_LANGUAGE`), missing required section (`MISSING_SECTION`),
  missing required column, per-row errors (`MISSING_DEAL_ID`,
  `MISSING_ORDER_REFERENCE`, `UNPARSED_TIME`, `UNPARSED_NUMBER`, …) and limits
  (`FILE_LIMIT_EXCEEDED`, `ROW_LIMIT_EXCEEDED`, `CELL_LIMIT_EXCEEDED`,
  `TABLE_LIMIT_EXCEEDED`).
- This is a **synthetic-fixture-validated contract**, not XM compatibility evidence.
  Until a real anonymized XM report passes, no "XM supported/verified" claim is made.

## User flow

File select → format check → safe in-memory parse → preview with problems. The entry
point is a tab inside the existing CSV import modal; the footer of MT5 mode has no
import/save action and states "Bu ekran yalnız önizlemedir; işlemler kaydedilmez."
(EN/TR/DE). Preview shows: recognized format + parser version, order/deal counts, rows
read/with problems, source date range, masked source-declared account (never the owner
name) + deposit currency, time-basis warning, order and deal tables (bounded), row
errors with reasons, unprocessed sections and validation-boundary warnings.

## Security and retention boundaries

- Nothing is persisted: no ledger/projection/journal/portfolio write; no raw file kept;
  the file is parsed from the request body in memory.
- Limits: `MAX_STATEMENT_BYTES` (10 MB), `MAX_STATEMENT_TABLES` (64),
  `MAX_STATEMENT_ROWS` (20 000), `MAX_STATEMENT_CELL_BYTES` (4 096),
  `MAX_STATEMENT_PREVIEW_ROWS` (50), `MAX_STATEMENT_ROW_ERRORS` (200).
- HTML is never executed or rendered in a WebView/iframe; scripts/styles are ignored by
  the parser, external resources are never fetched, no file path is resolved from the
  upload, and the frontend renders every report value as text (no
  `dangerouslySetInnerHTML`).
- The preview response carries `source_sha256` + parser version as provenance; the hash
  is not authenticity or broker verification. A future persistence stage will require a
  fresh preview when the file or parser settings change; no approval token or import
  infrastructure exists in this package.
- Account numbers are masked (`****4321`); owner names and raw cell content are never
  returned or logged.

## Ordered acceptance

- [x] Supported synthetic MT5 EN HTML fixture parses with correct order/deal counts,
  separated identities, date range and detected format/parser version.
- [x] Order/deal identity kinds are never substituted; deal rows always carry the order
  reference separately.
- [x] MT4-like, empty, truncated, unknown-language and missing-section documents fail
  closed with distinct codes.
- [x] Mixed valid/invalid rows are split: counts, row errors with reasons, and parsed
  rows remain available.
- [x] Ambiguous time/number formats keep source text and produce row errors; no guessing.
- [x] Source times are never converted to UTC; the unverified time basis is explicit.
- [x] Missing commission/swap/profit stay absent and are never zero.
- [x] Lot quantities stay `SOURCE_LOT`; no ounce/base conversion or PnL/margin math.
- [x] Byte/table/row/cell limits are enforced with explicit errors.
- [x] Script tags, external resources and injected markup never execute, fetch or
  render as HTML.
- [x] Preview writes nothing: trade/ledger/observation tables are unchanged and logs
  contain neither the raw file content nor account/owner data.
- [x] EN/TR/DE strings are in parity; TypeScript, frontend suite and production build
  pass; the existing CSV modal behaviour is unchanged.

## Real XM sample guidance

To validate real XM compatibility, provide one **anonymized MT5 HTML report** (English
template preferred). Status: **open obligation owned by the owner/pilot**, tracked in
STATUS; it is separate from the completed preview development.

Checklist for the validation round:

- Which terminal do the pilots use: MT4 or MT5?
- Terminal build/version and report language.
- One anonymized HTML report in the supported format.
- Compare preview against the source report: order/deal counts, identity relations,
  quantities and source timestamps.
- Any unsupported or unreadable rows are explicitly explained, not silently dropped.

Anonymization rules:

- Name, account number/owner and other personal data may be changed or removed.
- Order/deal/ticket relations must stay internally consistent; do not renumber one side
  only.
- Column structure, date and number formats must remain exactly as exported.
- Do not force arithmetic equalities (e.g. `volume × price = profit`); keep financial
  values as reported.
- Never share passwords or API keys. The file is parsed locally in memory and not
  stored; only the preview response is shown.
- MT4 reports are a separate format and are not covered by this package.
- Without a real file, synthetic success is never reported as real compatibility.

## Evidence

- Red (before implementation): the new backend suite failed at import (module missing);
  frontend preview tests failed with the component missing.
- Focused backend: `backend/tests/test_wp40_mt5_statement_preview.py` **23 passed**.
- Focused frontend: `Mt5StatementPreview.dom.test.tsx` **7 passed**; existing
  `CsvImportModal.dom.test.tsx` **7 passed** unchanged.
- Related backend regressions: **112 passed**.
- Full backend suite (isolated data dir): **1026 passed / 2 warnings**.
- Frontend: **40 files / 236 tests**, TypeScript clean, i18n parity and production build
  clean.
- Canonical arm64 local CI (`KDG-002@1.1.0`): **MERGE READY**, 13/13 steps PASS, no
  failed steps, provenance `DEVELOPER_DIRTY` (uncommitted by instruction); report
  `dist/p1-wp40-preview-local-ci.json` SHA-256
  `579dd63e17284b253ea959590a33a38104ff0c572e93253cd14411d850886a8c`, executable
  `963eed4f273001afb4793b7f85648a1f1b364ffd4d19d7387688bb595cce5d84`, artifact
  `6337cee230bdec29450b832840e583fd8da90b675a80687e4b67b8164fdec5ae`.
- Frontend unchanged-surface note: the CSV import flow keeps its existing behaviour; the
  MT5 preview lives in the same modal as a separate tab.

## Scope boundaries

- No persistence/import of statement rows, no migration, no financial schema extension
  (all explicitly not approved).
- No OKX/Binance account-identity work, no cTrader, no XM EA/Wine bridge, no live
  price/close synchronization, no order sending, no cloud/VPS/paid data, no general
  multi-broker infrastructure.
- MT4, XLSX/PDF report formats and additional languages remain future work.
