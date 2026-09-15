<!-- doc-role: archived -->
# P1-WP39 — Broker observation projection, deterministic rebuild and internal read service (A1.1)

```yaml
work_package: P1-WP39
status: Complete
branch: main
baseline: 7cfc400
```

Owner instruction (2026-09-15): apply **only A1.1** — a rebuildable broker
observation projection, separate order/fill identity contracts, deterministic rebuild
and an internal read service. A1.2 (atomic import path + user-facing API), matching,
MT4/MT5 parsing, cTrader, the XM bridge, cloud/VPS/paid data and any journal or
portfolio coupling remain unapproved. No commit/push, Release, installed-app update or
real user-data migration was performed.

## Delivery boundary

**Completed in A1.1:** a rebuildable, internal broker observation log that preserves
source observations separately from journal trades; separate order/fill source
identities; source-level idempotency (same document re-sent); explicit unverified
account-scope state with duplicate-claim counters; deterministic rebuild with a verified
ledger boundary, snapshot hash, freshness states and visible failure handling; additive
migration reachable from clean, `007` and `001` databases with existing records
preserved.

**Not completed (A1.2+ and not approved):** economic dedup/conflict classification on a
verified account scope, atomic ledger+projection import, a user-facing read API, real
broker synchronization and XM/cTrader connections.

## Finalized contracts

**Identity.** An order identity is the source order id; a fill identity is the source
fill/deal id. The order id is only the fill's relation (`related_order_id`) and is never
substituted for a fill identity; nor is the ledger event id or any content hash.

**Account scope (superseding contract, 2026-09-15).** The caller-declared local bucket
(`account_id`) is **not** a broker-verified account identity; being in the same bucket or
carrying the same symbol/fill id never proves account equality and a file hash never
substitutes for it. Current producers supply no persistent account namespace: the
read-only sync stores at most one credential per `exchange_id` and the ledger evidence
carries no account binding. Every observation is therefore projected with
`account_scope_state = UNVERIFIED` and `account_scope_reason =
ACCOUNT_SCOPE_NOT_PROVIDED_BY_PRODUCER`; each observation is stored individually with its
own lineage and **no economic merge, repeat/dedup or content conflict is declared across
observations**. Duplicate claims on the same declared scope are surfaced through
`unverified_duplicate_claim_count`/`unverified_duplicate_identity_count` with the
observations preserved. Economic grouping (repeat/conflict classification) only becomes
valid once a producer supplies a verified account namespace, which is an A1.2 obligation.
Environment/context remain independent changeable metadata (`UNKNOWN/DEMO/LIVE` x
`UNKNOWN/PERSONAL/PROP`, `PROP+DEMO` and `PROP+LIVE` valid) that is never inferred and
never part of any identity.

**Identity failures.** A producer rejection (e.g. a fill row without a fill id) creates
no ledger event and no projection row; raw-evidence retention for rejected rows is an
A1.2 obligation. A valid observation whose source scope cannot be resolved (no manifest
v2 `source_exchange_id`/`market_type`) is counted as unresolved
(`unresolved_reasons.MISSING_SOURCE_SCOPE`) and is not projected. Malformed lifecycle
payloads fail closed and abort the rebuild before any write.

**Source-level idempotency.** Re-sending the same document remains a ledger property
(same idempotency identity → no new events) and is handled separately from
cross-document economic dedup, which does not run while the account scope is unverified.

**Counters (disjoint).** `accepted_observation_count = verified_account_scope_observation_count
+ unverified_account_scope_observation_count + unresolved_source_scope_observation_count`.
`unverified_duplicate_claim_count` counts observations beyond the first per declared-scope
claim key; `unverified_duplicate_identity_count` counts claim keys with two or more
observations.

| Scenario | accepted | unverified | unresolved source | dup claims | dup identities |
|---|---|---|---|---|---|
| Single observation | 1 | 1 | 0 | 0 | 0 |
| Same document re-sent (ledger duplicate) | unchanged | unchanged | unchanged | unchanged | unchanged |
| Same bucket/fill/content in another document | 2 | 2 | 0 | 1 | 1 |
| Same bucket/fill, different content in another document | 2 | 2 | 0 | 1 | 1 (no conflict declared) |
| Missing manifest source scope | 2 | 0 | 2 | 0 | 0 |

**Determinism.** `snapshot_sha256` covers only canonical business data: observation
records (including source event identity and lineage), unresolved references and
counters. Operational values (`projected_at_utc`, duration, process id, file paths) are
excluded. The same evidence set in any processing order produces the same records,
counters and snapshot hash. Different ledgers built by different import orders may
legitimately differ in event ids and lineage hashes; that is not a determinism failure.

**Rebuild and freshness.** Rebuild materializes one consistent ledger read snapshot,
captures the processed-through boundary as verifiable `event_id`/`event_hash` (event
ids are not treated as sortable), stores an evidence digest and never mixes events
appended while it runs. Coverage reports `NEVER_BUILT`, `CURRENT` or `STALE` plus
`newer_events_pending` and `last_attempt_status`/`last_failure_reason`; freshness
describes the local ledger scope, not the broker's live account state. A failed rebuild
keeps the previous successful snapshot and records the failure in a separate transaction
so the rollback cannot hide it.

## Closure review (2026-09-15)

**1. Changeable metadata is not economic identity.** The first draft had
`account_environment`/`account_context` in the projection primary key, so learning that an
account is `LIVE`/`DEMO` or `PERSONAL`/`PROP` later would have created a second record
for the same source fill. Environment/context are now changeable row metadata and are
excluded from the claim key (see the superseding account-scope closure below);
environment/context remain on the row as changeable classification metadata (still
`UNKNOWN` because no producer supplies them) and never fork the identity. Proven by a
contract test that constructs the same observation with `UNKNOWN`, `LIVE/PERSONAL`,
`DEMO/PROP` and `LIVE/PROP` metadata and receives one identity, while a different
account or source market produces a different identity. Conflicting or unverified
metadata can never be silently selected: there is no metadata ingestion path in A1.1 and
an explicit negative test shows unverified provenance metadata is ignored. Ingesting
declared versus broker-verified metadata, with provenance and conflict visibility, is an
A1.2 producer obligation.

**2. Account scope basis.** Traced producer → ledger → projection: `account_id` is
created by the caller (`/broker/sync-read-only` query parameter, default
`local-broker-api`) or by the local import default (`local-broker-import` in
`BrokerImportService.import_records`), is free text up to 128 characters and has no
broker-verified relationship; no producer field carries a broker account number or
server namespace. A caller can therefore place different real accounts into the same
local bucket. A1.1 does not invent a broker identity: coverage now reports
`account_scope_basis = CALLER_DECLARED` and
`account_metadata_basis = NOT_PROVIDED_BY_PRODUCER`, observations without a resolved
source scope remain unresolved, and different declared accounts/source markets never
merge. A broker-verified account namespace/server is recorded as an A1.2 obligation.

**3. Supported head upgrade could duplicate evidence.** With revision `008`, a database
already on revision `007` with canonical evidence is classified as needing the staged
upgrade (only the broker tables are missing). The staged flow ran
`backfill_legacy_trades`, which appended a `LegacyTradeImported` event for every trade
that had no legacy backfill yet — including trades already represented by canonical
`IntentRecorded`/`FillRecorded`/`TradeCorrected` events. The projection rebuild then
produced a second `legacy`-venue row for the same trade and the coverage preflight
correctly refused promotion (`PROJECTION_COVERAGE_INCOMPLETE`). This was a real, safely
refused but blocking defect on the supported `007 → 008` path. Fix:
`backfill_legacy_trades` now skips trades already represented by canonical journal
events (`already_evidenced` counter, `list_events_for_trade` lineage check) so no second
evidence lineage or projection row is created; true legacy rows still backfill and re-runs
stay idempotent. The earlier artificial test (a modern database force-stamped as legacy
being counted as migration evidence) was replaced by this real `007 → 008` scenario; the
underlying inconsistency is reproducible through the supported staged-stamp flow, so it
was fixed rather than hidden.

## Account-scope closure (2026-09-15, superseding)

The second closure review found a contradiction: `account_id` was described as a
caller-declared local bucket, yet the projection used it as an economic account scope, so
two different real accounts imported into the same bucket could be merged (same content)
or declared conflicting (different content) without proof. Producer trace confirmed the
gap: `exchange_credential_refs` is keyed by `exchange_id` only, the sync endpoint accepts
a free-text `account_id`, the ledger evidence carries no account or server binding, and a
file hash is not an account identity. Fix: every observation is projected individually
with `account_scope_state = UNVERIFIED`, no economic merge/dedup/conflict runs while the
scope is unverified, duplicate claims on the same declared scope are counted and
preserved with lineage, and source-level idempotency stays a separate ledger property.
The rows table was renamed to `broker_observation_log` so databases that already hold the
unreleased first-draft table (dev profiles only; the owner database has no broker tables
— read-only inspected and not modified; the closure task did not re-access it) cannot
collide; no table or row was dropped. Verified `007 → 008`
upgrade, backfill and journal behavior are unchanged.

## Scope boundaries

- No import-path change and no ledger+projection atomicity (A1.2); no user-facing API
  or UI (A1.2+).
- No broker account verification system, no new importer account/namespace fields, no
  declared-account mapping flow: those are A1.2 obligations, not implemented here.
- Broker observations are never converted into journal trades, never matched to journal
  trades and never added to portfolio PnL; local estimated closes remain estimates.
- Existing ledger, projection and correction lineage are extended, not
  rewritten; the legacy economic-grouping service is untouched and still unused.
- Additive migration only (`008_broker_observation_projection`, still uncommitted and
  never applied outside isolated tests), exercised in isolated test databases; no real
  user-data migration or destructive operation.
- A1.2 producer obligations: broker-verified account namespace/server, verified-versus-
  declared metadata ingestion with provenance and conflict visibility, economic grouping
  keyed on the verified scope, atomic import path and the user-facing read API.
- MT4/MT5 parser, cTrader, XM bridge, cloud/VPS/paid data and order dispatch are out of
  scope.

## Ordered acceptance

- [x] Order and fill identities are separate: one order plus two fills produces three
  individual observation rows; a fill without a source fill id is rejected by the
  producer, is never keyed on the order id and fails closed in the pure builder.
- [x] A valid observation without a resolvable source scope stays unresolved and
  unprojected instead of being silently dropped or counted as malformed.
- [x] `PROP+DEMO` and `PROP+LIVE` are valid; no producer value is fabricated.
- [x] Re-sending the same document leaves ledger and projection counters unchanged
  (source-level idempotency, separate from cross-document dedup).
- [x] Two documents in the same declared bucket with the same fill id and content stay
  two unverified observations - never one economic fill plus a repeat.
- [x] Two documents in the same declared bucket with the same fill id and different
  content stay two unverified observations - no `UNRESOLVED_CONFLICT` variants.
- [x] The counter examples match the documented disjoint arithmetic.
- [x] Events appended during a rebuild do not enter the snapshot; coverage turns
  `STALE`.
- [x] Failure injection keeps the previous snapshot, records the failure visibly and
  leaves the state correct.
- [x] Repeated rebuild is deterministic for the same evidence set and leaves the ledger
  and export unchanged.
- [x] The additive migration preserves existing rows and creates the new tables.
- [x] Journal, portfolio and local tracking results are unchanged.
- [x] Changeable environment/context metadata is not part of any identity and is never
  inferred from unverified sources.
- [x] The account scope basis and the unverified scope state are explicit in every row
  and in coverage; the producer gap is recorded for A1.2.
- [x] The supported `007 → 008` upgrade with canonical evidence does not duplicate
  ledger events, projections or trades; the re-run reports `CURRENT`.

## Evidence

- Red (first implementation): all focused tests failed (missing modules); the mandated
  account-scope scenarios were reproduced against the previous grouping logic: two
  documents, same declared bucket and same fill id produced **one merged record plus a
  repeat** (same content) and **one `UNRESOLVED_CONFLICT`** (different content) — the
  behavior this closure removes. The previous A1.1 files were never committed and are
  overwritten, so the legacy outcome is demonstrated by a differential reproduction over
  the same ledger rather than a literal old-code test run.
- Green: `backend/tests/test_a1_wp39_broker_observations.py` **20 passed** (two mandated
  scenarios, order/fill separation, metadata separation, source idempotency, counters,
  determinism, rebuild boundary, failure visibility, migration paths).
- Related regressions: ledger/H02/macOS-migration/broker-import/read-only-sync/
  trade-projection/H01/A0/economic-grouping **106 passed**; local tracking, WP32 review
  fixes, H07 performance, security DB, system sync, portfolio, journal propagation,
  reconciliation inbox, maintenance **121 passed**.
- Full backend suite (isolated data dir): **1003 passed / 2 warnings**.
- `python3.11 scripts/check_docs.py` PASS (124 documents / 171 local links / 5 startup);
  `git diff --check` clean.
- Canonical arm64 local CI (`KDG-002@1.1.0`) on the account-scope closure tree: **MERGE
  READY**, 13/13 steps PASS, no failed steps, provenance `DEVELOPER_DIRTY` (uncommitted
  by instruction; the earlier pre-closure reports are superseded); report
  `dist/p1-wp39-account-scope-local-ci.json` SHA-256
  `8ab45595e7918a34e8f14c8165d805463ceea81216db273aa9a9a21d87819e5d`, executable
  `485b960495a849b98bf760bad3f7dbfd05a01e6c829354f6a1ae2b10dd471b8e`, artifact
  `06048c7b4a3b8715b073f17abb9c117b9f7dc012a32eef6364066f395a3dce68`.
- Frontend unchanged: no frontend files touched; existing 229 tests, TypeScript, build
  and i18n were exercised by the canonical gate only.
