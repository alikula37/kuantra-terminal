<!-- doc-role: archived -->
# P1-WP38 — A0 data-accuracy findings verification and fix

```yaml
work_package: P1-WP38
status: Complete
branch: main
baseline: ed6eabc
```

Owner instruction (2026-09-15): apply **only** package A0 — verify the two reported
data-accuracy findings and fix them if real. This is **not** approval for A1, an MT4/MT5
statement parser, cTrader, an XM bridge, a new cloud service or a new broker identity
schema. No commit/push, Release, installed-app update, real user data change or migration
apply. The pre-existing "A→B→C→D order" does not exist in any current repository document;
only A0 is approved and no competing roadmap entry was created.

## Finding 1 — broker `FillRecorded` events vs. trade projection rebuild

**Verified.** Production path: `BrokerImportService.import_records` appends ledger events
(`broker_import_service.py:739-743`) — fills become `FillRecorded` with payload
`{"broker_lifecycle": ...}` on `local-broker-import` / `local-broker-api`
(`read_only_broker_sync.py:633`); account reconciliation appends `TradeCorrected` with
`{"account_event": ...}` (`account_reconciliation.py:479-506`). `PROJECTABLE_EVENT_TYPES`
matched by event type only and `_projection_from_event` required `payload["trade"]`, so
`EvidenceTradeProjectionRepository.rebuild()` aborted with
`EvidenceProjectionError: event ... has no trade snapshot` for any database containing
such observations. Active rebuild callers: `kuantra-cli evidence-ledger
projection-rebuild` (`cli.py:130-135`), the H07 bounded-performance worker
(`desktop/h07_worker.py:142-159`), and the macOS migration restore path
(`macos_migration.py:1016`).

**Fix (narrowest correct):** rebuild and the atomic upsert classify each projectable-type
event explicitly: a `trade` snapshot is projected; the validated non-trade payload
contracts (`broker_lifecycle`, `account_event`) are counted as
`non_trade_lifecycle_events` and skipped for this projection; any other payload without a
trade snapshot still raises before the projection table is touched (fail closed). The
broker/account events, their provenance and the ledger chain are unchanged.

## Finding 2 — DuckDB `pnl or 0.0` unknown-to-zero conversion

**Verified.** Production path: DuckDB is a locked dependency; every journal mutation is
written to `olap_trades` (`sync_pipeline.py:69-70`), the shadow hydrator rebuilds the same
table (`duckdb_hydrator.py:111-128`), and `/analytics/overview`, `/analytics/symbols` and
`/analytics/equity` read it (`endpoints.py:1027,2107,2123`). `float(pnl or 0.0)` stored a
NULL result as 0.0, so an unknown outcome appeared as a breakeven, inflated the win-rate
denominator, and `is_winner` became `False`. The SQLite/portfolio contract excludes
unknown results and reports the count instead (`portfolio_service.py:109-115,243-245`).

**Fix:** OLAP write paths preserve NULL (`is_winner` NULL for unknown);
`get_aggregated_stats` reports `known_pnl_trades` / `unknown_pnl_trades` and computes the
win rate over known results only; `get_symbol_breakdown` adds `known_pnl_count` /
`unknown_pnl_count` and a known-only win rate; `get_equity_curve` skips unknown results,
matching the portfolio equity curve.

## Closure review (2026-09-15)

### 1. Is the unknown PnL visible to the user?

**Verified, with one real gap fixed.** The DuckDB counts reach the user through
`/analytics/symbols`: `AnalyticsView.tsx` now shows a per-symbol `(N unknown)` marker, an
unknown-result note when any unknown result exists, and a dedicated "all closed trades
have an unknown result" state instead of the generic "awaiting trades" empty state. A
fully known book shows no unknown note, and a book with no records keeps the existing
empty state — so no data, all-unknown and real zero are visually distinct. The dashboard
already showed `dashboard.unknown_pnl_note` while `unknown_pnl_trades > 0`
(`DashboardView.tsx:251-253`) and the portfolio equity curve skips unknown results.
`/analytics/overview` and `/analytics/equity` have no frontend consumer and remain
API-only; that is reported here rather than silently presented as UI coverage. Local
estimated closes (`PositionProjectionUpdated`, `local-journal`) never enter `trades`,
portfolio or analytics (existing tests `test_local_tracking.py`).

**Gap found (red before the fix):** AnalyticsView ignored `known_pnl_count` /
`unknown_pnl_count`; an all-unknown book looked like "no data" and a mixed book presented
known-only totals and win rate without any notice. Fix: the type and response guard
require the counts, the note/all-unknown state/per-row marker were added, and EN/TR/DE
keys were added in parity.

### 2. Is the projection event classification strict enough?

**Verified, and tightened.** The first A0 classifier accepted any object under
`broker_lifecycle` or `account_event` regardless of event type or producer fields. It now
validates against the actual producer contracts:

- `broker_lifecycle` is valid only on `FillRecorded` (the only projectable event type the
  broker importer emits for fills; order observations use `VenueAck`/`VenueReject`), and
  requires non-empty `record_type` (fill/order), `external_order_id`, `symbol`,
  `occurred_at`, `external_fill_id` for fills, and a payload venue that matches the event.
- `account_event` is valid only on `TradeCorrected` (the only projectable type the account
  reconciler emits; fee/rebate kinds use `FeeAdjusted`), and requires non-empty
  `account_event_kind`, `account_event_status`, `storage_status`, `external_event_id`, and
  a payload account/venue that match the event.
- Both payload keys at once raise a conflicting-payload error.
- Payloads without a lifecycle key and without a trade snapshot still raise
  `no trade snapshot`; malformed lifecycle payloads are never silently skipped.
- Rebuild and the atomic upsert share the same classification function.

## Ordered acceptance

- [x] The rebuild failure is reproduced with an isolated fixture of the supported broker
  import flow plus a real account-event observation (red test before the fix).
- [x] Broker/account lifecycle observations no longer abort the rebuild; they are reported
  as `non_trade_lifecycle_events` and create no trade projection row.
- [x] An unknown projectable payload still fails closed (`no trade snapshot`) and leaves the
  projection table unchanged.
- [x] Repeated rebuild is idempotent: same counts, no duplicate projections, ledger event
  count and chain unchanged.
- [x] Unknown PnL stays NULL in `olap_trades` (and `is_winner` NULL) and is excluded from
  totals, win rate, breakeven count and the equity curve.
- [x] A real zero stays a valid breakeven value; positive/negative results are unchanged.
- [x] DuckDB analytics and the portfolio summary apply the same unknown-PnL contract on
  identical input.
- [x] Focused tests, related regressions and the full backend suite pass.
- [x] The frontend consumes the unknown-result counts: mixed, all-unknown, fully-known and
  no-data states are distinct, with EN/TR/DE parity.
- [x] The classifier is producer-scoped: event type ↔ payload type, required fields and
  types, account/venue identity consistency, and conflicting payloads are rejected.
- [x] Negative tests cover empty and wrong-type `broker_lifecycle`, malformed
  `account_event`, wrong event type, conflicting keys, missing identifiers and mid-rebuild
  rollback without partial projection changes.
- [x] Rebuild and the atomic upsert apply the same classification rules.

## Scope boundaries

- A0 only: no A1 work, no MT4/MT5 parser, no cTrader/XM bridge, no cloud service, no new
  broker identity schema or venue expansion.
- No schema migration and no new dependency; new analytics fields are additive.
- **Broker observations are not converted into journal trades.** Making broker events
  directly create or alter journal trades is not approved; a future design must use a
  separate broker view, explicit matching and double-count prevention.
- `/analytics/overview` and `/analytics/equity` were not removed and remain API-only.
- Plugin-gated engines that still coalesce unknown PnL inside their own paths
  (`pivot_engine.py:85`, `psychology_engine.py`, `execution_drift.py:25`) were **not**
  changed; they are recorded as an open follow-up, not silently fixed or hidden.
- No commit/push, Release or installed-app change; the selected next package is P1-WP29
  (owner-host obligations only) and A1 is not approved.

## Evidence

- Red (before the fixes):
  - `EvidenceProjectionError: event 215092a3-… has no trade snapshot`
    (`evidence_projection_repo.py:96`);
  - `assert 0.0 is None` for the unknown-PnL row;
  - 12 failed classifier/rollback backend tests and 2 failed AnalyticsView DOM tests
    (unknown note and all-unknown state) in the closure review.
- Focused: `backend/tests/test_a0_data_accuracy_findings.py` **17 passed**;
  `frontend/src/components/__tests__/AnalyticsView.dom.test.tsx` **6 passed**.
- Frontend: **39 files / 229 tests**, TypeScript clean, production build PASS, i18n
  **1036/1036/1036**.
- Related backend regressions: **160 passed** (broker import, projection, account
  reconciliation, journal propagation, reconciliation inbox, local tracking, portfolio,
  H07 performance, macOS migration, system sync, security DB).
- Full backend suite (isolated data dir): **983 passed / 2 warnings**.
- Canonical arm64 local CI (`KDG-002@1.1.0`) on the closure-review tree: **MERGE READY**,
  13/13 steps PASS, no failed steps, provenance `DEVELOPER_DIRTY` (uncommitted by
  instruction); report `dist/p1-wp38-closure-local-ci.json` SHA-256
  `ebd133133d33ade353a7811a9c8019f2aa406549452d61ad6091df76f124d1f8`, executable
  `9f9caf2933df6fb201867c688b820d0f142e0b927b715140c9a4082c50a2fee3`, artifact
  `e821bc4f6baede75723f38d1ddcbd1f4113e3c2555da863435c673354a0d46b2`.
- `python3.11 scripts/check_docs.py` PASS (123 documents / 170 local links / 5 startup);
  `git diff --check` clean.
