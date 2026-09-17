<!-- doc-role: archived -->
# P1-WP42 — Read-only single-trade chart review (P1)

```yaml
work_package: P1-WP42
version: 1.0.0
status: Complete
date: 2026-09-16
```

Owner decision (2026-09-16): implement only the bounded **P1** package of the chart
trade-review plan. P2 (revision-aware playback), P3 (multi-trade view), P4 (TP4 + move
stop to break-even) and the optional hypothetical-scenario layer are **not approved** and
must not be started. This is development/test approval only: **no commit/push, Release,
installed-app update, new data provider, paid service or real order path was used.**

## Completion boundary (explicit, unchanged)

**Completed and verified:** read-only entry / SL / target view for **closed trades that
have a suitable recorded 1m candle history** in the evidence store, including the labelled
current-plan reference, recorded close marker with source declaration, provider strip and
honest empty/partial states.

**OP-01 delivered in the working tree (2026-09-17, not committed):** an open trade can now
be opened read-only on its **exact instrument's existing cache candles** without an exit
price/time; the levels, weights, current-plan reference label, manual refresh, step/seek and
the loading/empty/partial/stale/error states are implemented (details below).

**Still not completed (must not be presented as delivered):**
- **Real gold provider identity is not verified** — the review reads the existing SQLite
  cache for the exact symbol bucket and never substitutes `GOLD`/`GC=F`/`XAUUSD`; the cache
  records no provider per row, so provider identity stays UNKNOWN unless the manual refresh
  fetched in the same session. Real gold source validation remains an open blocker.
- **Historical plan revisions over time** (P2, not approved).
- **TP4 and move-stop-to-break-even** (P4, not approved).
- Multi-trade comparison (P3), candle-touch analysis, hypothetical scenarios (not approved).

A trader inspecting an **open** position is served only to the extent that the exact symbol
already has cached candles (Market Charts or the review's manual refresh); no candle source
is invented and no provider equivalence is claimed.

## Scope delivered (working tree)

- Journal row action **"Grafikte incele"** (open/closed trades; hidden for canceled trades)
  routes to the existing replay surface; no new chart or replay architecture.
- The replay session payload now carries a labelled, read-only plan reference and close
  provenance; the chart draws the level lines on the recorded 1m candles.
- Entry (recorded) is solid; SL and targets are dashed **current-plan reference** lines and
  the panel always states that it is not verified that these levels applied at that time.
- Levels come from the local tracking plan when its entry matches the recorded trade, else
  from the recorded trade row; missing levels are omitted and a single recorded TP never
  receives an invented percentage.
- Price, side (LONG/SHORT) and, when the local plan provides them, target weights are
  labelled; the recorded close appears as a marker **only once the cursor reaches the exit
  bar**, classified as user report / imported file (not broker-verified) / simulation /
  broker-verified only if the field literally says so / unknown.
- Provider strip: symbol, venue, feed, timeframe, data-gap note and the explicit statement
  that recorded candles are not broker execution evidence (1m bar approximation).
- Honest states: open trades and missing candle history are localized and explained, never
  silently hidden; unknown server reasons fall back to a generic localized line plus the raw
  reason code; no synthetic candles and no fallback to another instrument.
- Dark/light theme, keyboard-accessible controls, EN/TR/DE strings.
- Read-only guarantee: no journal, plan, ledger or portfolio write anywhere in the review
  path (regression test compares trades and ledger event counts before/after).

## Fixes found by the implementation and visual check

- Origin lookup used `trade_read_adapter.list_events_for_trade`, which does not exist on the
  adapter, so imported trades always read "origin unknown"; the service now uses the
  adapter's scoped ledger repository (regression test).
- `NO_CANDLE_HISTORY` (and the other emitted candle-evidence reasons) were not localized and
  the raw English message leaked into localized states; reasons are now localized and the raw
  message only appears for genuinely unknown codes.
- Light theme: the replay chrome used dark fallback surfaces with theme-remapped text,
  leaving prices/ids unreadable; standard palette classes and control icon colors were
  applied and re-verified visually.
- **Close-source verification claim:** the label previously promoted the raw string
  `BROKER_VERIFIED` to a "broker-verified" label. The producer check confirmed that no API
  payload can write `close_source` today (only the server writes `USER_REPORTED`), and no
  broker-verification infrastructure exists, so that claim depended on a string value alone.
  The label now reports any unrecognised explicit value as **source declaration (not
  verified)** with the raw value kept visible, and `broker_verified` is always `false`;
  negative tests pin that forged values (`BROKER_VERIFIED`, `BROKER_CONFIRMED`, ...) cannot
  open a verified label.

## Next package plan — OP-01 open position chart review (NOT approved, do not start)

**Need:** the trader selects an open trade and sees entry, SL and targets on the exact
instrument's available candles; opening the chart must not modify the trade or produce a
close.

**Architecture decision:** do **not** weaken the closed-trade replay contract (it requires
`status=CLOSED` and a complete entry→exit window). Add a separate read-only builder
`backend/app/quant/open_position_evidence.py` that reuses the candle-store reader, the
duplicate/conflict rules and the provenance helper, plus the existing plan-reference code,
and extend `GET /api/v1/replay/session/{trade_id}` to branch by trade status
(`review_mode: "OPEN"`); the closed branch stays byte-compatible (regression-pinned).

**Bounded behaviour:**
- Window `[entry_bar .. last recorded bar]` (no exit time/price required), bounded by a
  bar ceiling; payload carries `review_mode`, `as_of`, `last_candle_time_utc`,
  `last_candle_age_seconds`, `data_freshness` (`CURRENT`/`STALE`/`UNKNOWN`), `history_status`
  (`FULL_SINCE_ENTRY`/`PARTIAL_SINCE_ENTRY`/`EMPTY`), `history_note`, no `close_evidence`,
  no realised PnL; plan stays the dashed **current-plan reference**; MAE/MFE/unrealized may
  reuse the existing excursion helper with `closed=false`.
- States: loading; offline/read error; no candles (same honest gold-style state); partial
  history shown with an explicit "tam geçmiş yok; gösterilen aralık X–Y" note; stale data
  with an age banner; provider/identity strip unchanged ("not broker execution evidence").
- No synthetic candles, no fallback to another instrument, no provider substitution.
- Refresh: manual only in OP-01; a later auto-refresh would need a bounded interval
  (≥60 s), hidden-tab skip, in-flight guard and exponential backoff on errors.
- Read-only guarantees tested: trades, `local_tracking_projections` and `evidence_events`
  unchanged, no local-tracking `observe()`/close-engine call, no plan mutation.
- Frontend reuses `TradeReplayCanvas` with a mode branch (no close marker, as-of watermark,
  freshness state), existing i18n/theme/keys.

**Gold note (open blocker, not solvable by chart work):** free XAUUSD candles exist through
`public_fetcher` (Biquote exact XAUUSD preferred; Yahoo/Stooq fallback) but are cached in
the SQLite UI cache, while the review reads the DuckDB `market_candles` evidence store that
the current free ingestion path does not feed for gold; `GOLD` maps to `GC=F` (futures) and
must never be treated as XAUUSD spot. OP-01 therefore requires an approved ingestion-bridge
decision (free source → evidence store with explicit venue/feed and
`source_verified=false`) or it will keep showing the honest no-candle state for gold.

**Decisions needed before OP-01:** freshness threshold (proposed: STALE > 5 min for 1m
bars, UNKNOWN without a last candle); playback offered for open trades (proposed: yes, up to
the last recorded bar, no auto-advance); manual-only refresh in v1 (proposed); minimum
history (proposed: show from the first bar covering the entry, otherwise PARTIAL/EMPTY); the
gold ingestion bridge above.

## Verification

- Backend `backend/tests/test_replay_plan_reference.py` — 14 tests (level source rules,
  created-after-entry flag, plan mismatch fallback, close-source classes, ledger-origin
  lookup, close marker future-leak guard, read-only guarantee); existing replay/candle
  suites unchanged (1122 backend tests pass).
- Frontend `TradeReplayCanvas.dom.test.tsx` — 16 tests (reference banner, level labels and
  dashed/solid styles, trade-row fallback without weight, chart/line replacement on trade
  change, close-marker gating and localization, light theme palette, provider/gap strip,
  localized open/no-data states, playback request isolation); `JournalView.dom.test.tsx`
  covers the new row action and its absence on canceled trades (264 frontend tests pass).
- i18n 100% parity, `tsc` and production build clean.
- Visual check with synthetic data (isolated `KUANTRA_DATA_DIR`, Chrome + puppeteer-core,
  no user data): dark TR levels/close marker, light TR levels, open-trade state and
  gold-without-candles state captured in `artifacts/evidence/p1-wp42/`.

## OP-01 implementation record (working tree, 2026-09-17)

**Data path (decision):** the open review reads the **existing SQLite market cache**
(`market_candles_cache`) for the trade symbol's own bucket, read-only; the DuckDB evidence
store and the closed replay contract are untouched, and no new table/migration was added.
Provider provenance is only reported when the **in-session manual refresh** fetched data
(the cache itself has no provider column); pre-existing rows are honestly UNKNOWN, and the
UI states that the same symbol text does not prove the provider.

**Backend:** `backend/app/quant/open_position_evidence.py` (exact-symbol read, entry-optional
window `[entry_bar .. last recorded bar]`, partial/empty handling, duplicate/conflict rules,
bar ceiling with explicit truncation, delay indicator, gaps → `RANGE_NOT_ASSESSABLE`, no
writes); `replay_service.py` OPEN branch (`review_mode: "OPEN"`, `OpenReviewSession`,
step/seek reuse, no close evidence, no performance numbers) plus
`create_open_review_session(refresh=True)` where the manual refresh may update the market
cache and can never write evidence; the endpoint accepts `?refresh=true`.

**Freshness contract:** separate fields for the last candle time and state
(`OPEN`/`CLOSED`/`UNKNOWN`), last successful in-session download, provider latency (always
`UNKNOWN` until a provider declares it), coverage range, missing-before-entry minutes and gap
ranges; the 5-minute threshold is a **delay indicator only** and no field claims live data.
No touch/topic analysis and no performance metrics are produced for open positions.

**Frontend:** open badge and review panel (freshness, provider, identity, partial-history
range, gap note), manual **Refresh** with in-flight guard that keeps the previous chart and
shows a retry error on failure, no automatic refresh, close marker hidden, performance row
replaced by an explicit out-of-scope note, existing i18n/theme/keyboard surfaces reused.

**Fixes found during this step (real defects):**
- Open-review candles were emitted with the cache key `timestamp` instead of the chart's
  `time`, which crashed the replay component into a blank screen; the payload now uses the
  replay candle shape (backend test pins it).
- `NO_CACHED_CANDLES` (and the sibling open-review reasons) were not localized and leaked the
  raw English message into the localized state; all emitted reasons are now localized in
  EN/TR/DE.

**Verification:** backend `test_open_position_review.py` (14 tests: open trade without exit,
partial/empty history, exact identity vs GOLD/GC=F, delayed indicator, gaps wording, bar
ceiling, session payload without close/perf numbers, candle shape, closed-path regression,
manual-refresh-only behavior and read-only guarantees) — full backend **1139 passed**;
frontend open-review tests (badge/levels/no close marker/no performance, delay indicator,
partial+gap wording, manual refresh with retained chart and retry, late refresh ignored, no
automatic refresh) — full frontend **41 files / 270 tests**; i18n parity and production build
clean. Visual check with synthetic cache data (isolated data dir, Chrome) captured in
`artifacts/evidence/p1-wp42/op01/` — dark/light open review, delayed/partial gold panel,
GOLD identity refusal and the refresh failure state; real provider access is **not** claimed.

## OP-01 provider-match hardening and edit-flow fixes (2026-09-17, working tree)

**Matched-chart contract (supersedes cache display):** the open review no longer presents
cache rows of unknown provenance as the trade's chart. A chart is shown only from a
**manual fetch against the trade's declared free public provider and exact provider
symbol** (`price_source` + `price_source_symbol`); the snapshot fetched in that session is
what the chart displays, the market cache may be updated as a side effect but is never read
back as proof, and the rows of a fresh download are never relabelled onto older rows.
- `public_fetcher.fetch_declared_provider_candles(provider, provider_symbol, ...)` calls
  exactly one provider (Binance, Bybit, Yahoo, Stooq, Biquote — no fallback) and raises
  `ProviderFetchError` with an explicit reason (`PROVIDER_NOT_SUPPORTED`,
  `PROVIDER_NOT_DECLARED`, `PROVIDER_INSTRUMENT_UNSUPPORTED`, `PROVIDER_FETCH_FAILED`).
  Symbol mappings that change the product (for example `GOLD` → `GC=F`) are rejected
  instead of substituted.
- Evidence identity: `identity_verified: true` now means "fetched from the declared
  provider for the declared provider symbol in this session"; the payload still states
  `NOT_BROKER_EXECUTION_EVIDENCE`, and `GOLD` / `GC=F` / `XAUUSD` are never equated.
- A session created without refresh stays unmatched and asks for the manual refresh
  (`PROVIDER_MATCH_REQUIRED`, with the declared provider shown); a trade without a declared
  provider explains that a match cannot be established (`PROVIDER_NOT_DECLARED`).
- Fixed during this work: provider payloads are millisecond epochs while the review math is
  in seconds; timestamps are now normalized (`_normalize_seconds`) and the boundary note in
  the header is mode-aware (it no longer claims "DuckDB candles" on the provider path).

**Limited real-provider evidence (credential-free):** one Biquote XAUUSD 1m request
(61 candles, 2026-09-17 08:19–09:19 UTC, last close 4312.764, fetched at 09:19:24Z) recorded
in `artifacts/evidence/p1-wp42/provider-match/biquote-xauusd-20260917-091922.json`; the
matched-chart screenshot with the real candles is in the same directory. This is a real
source/instrument/time-range/freshness check, **not** broker price equality or execution
evidence. An earlier attempt failed inside the local evidence script (millisecond timestamp
misuse); the provider itself answered on retry.

**Trade edit-flow fixes (real defects reproduced in isolated synthetic data):**
- **Entry seconds were silently truncated**: saving any unrelated field rewrote the stored
  entry time to minute precision (10:00:15Z → 10:00:00Z) because the dirty check compared a
  seconds-carrying ISO string with the minute-precision form value. The comparison is now
  minute-precision; an unchanged entry time is never sent.
- **Invalid/cleared entry time was silently skipped**: the save proceeded without the field
  and reported no error. A non-empty unparsable value (or cleared value) now shows
  `journal_edit.reason_time_invalid` and aborts the save.
- **Entry time was over-locked after a partial close**: the backend allows correcting the
  entry time before/after a partial close (price and quantity stay locked), but the editor
  disabled the field. It is now editable; the price/quantity lock and its reason remain.
- The canceled/closed/partial edit contracts were probed end-to-end (UI → API →
  persistence → reopened form) and preserved: an explicit cancel stays a note-style
  editable record with status restore/close transitions (as pinned by the WP32 tests); an
  initial attempt to lock canceled records in place was **reverted** after the pinned
  contract showed it was wrong.

**Verification:** full backend **1142 passed**, frontend **41 files / 277 passed**,
i18n parity and production build clean; screenshots and provider evidence under
`artifacts/evidence/p1-wp42/` (`op01/`, `provider-match/`).

## Unchecked criteria

- [x] Commit/push of this working tree (commit `7b6c379` / `71a3640`).
- [x] **OP-01 commit/push and installed-app update** (arm64 package installed from the clean commit; evidence in STATUS).
- [ ] **Instrument-product verification for gold/FX** (open blocker: the session establishes
  the declared provider identity, but spot `XAUUSD` has no verified catalog entry and the
  product never equates `GC=F` futures with spot; the manual refresh needs network access).
- [ ] Durable import marker on journal trades so "imported file" close provenance survives
  without ledger-origin inference (decision for the next plan).
- [ ] P2–P4 and hypothetical scenarios (not approved).
- [ ] Real pilot-data visual acceptance of the review surface.

**Shipped in `v1.1.4` (2026-09-17, owner-approved release):** tag `pilot-v1.1.4` on the
release train commit `ab2c933`; GitHub prerelease with the verified arm64/x86_64 DMGs
(arm64 SHA-256 `ad3fd146bbf2b4f6c5a50dba4761d2ef6032e37e8bf9234756b83b0ae4a09dc3`, x86_64
`05ea2367c56b923e80b8e4f354683e411ebc13c0d8b6a922ef1e15c43ca218be`); the arm64 executable
`42ef84c426004bb6e24b404c93e72757184ccff35e0b71682cdc6af582e00fab` matches the app installed
and verified on the owner's Mac. `pilot-v1.1.3` is marked superseded and directs users here.
