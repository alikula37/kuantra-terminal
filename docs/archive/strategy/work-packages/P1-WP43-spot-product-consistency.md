<!-- doc-role: archived -->
# P1-WP43 — Independent spot-product consistency check (gold/FX)

```yaml
work_package: P1-WP43
status: Complete
branch: main
baseline: 619f758
```

Owner instruction (2026-09-17): close the still-open WP42 blocker around instrument-product
verification. The owner selected a bounded plan-only package first: no code, no schema,
no new providers — write the contract, the product-class rules and the acceptance criteria,
then wait for explicit implementation approval.

## Problem and risk

The open-position review establishes **provider identity** per session: the candles shown
were fetched from the trade's declared free public provider and the declared provider
symbol (`identity_verified: true` means `PROVIDER_MATCH_ESTABLISHED_IN_SESSION`). What is
still a declaration is the **instrument product** behind that symbol: `biquote_public
XAUUSD` and `yahoo_public XAUUSD=X` are both *claimed* to be spot gold in USD per troy
ounce, but nothing independently checks that they price the same product. The review
currently surfaces this honestly ("source declaration, not verified"), yet the owner's
question — "is this actually the same instrument?" — stays unanswered.

Risk being addressed: a chart can look plausible while pricing a *different product class*
(a COMEX future, a tokenized metal, or a mis-scaled unit). The package adds a bounded,
independent **consistency** check for the same declared product class and makes
futures/token substitution structurally impossible — without ever claiming broker-price
equality.

## Deliverable (this package, once approved)

1. **Product-class registry** (pure data, no I/O): product keys such as
   `SPOT_METAL:XAU:USD`, `SPOT_METAL:XAG:USD`, `FX:EUR:USD`, and their allowed
   independent free-source aliases. Futures (`GC=F`, `SI=F`, `CL=F`) and tokens
   (`PAXG…`) live under distinct keys (`FUTURE:…`, `TOKEN:…`) and can never satisfy a
   spot key. Unknown symbols have no key.
2. **Pure comparator** `instrument_product` module: given the declared provider series
   and one independent same-key source series, align on identical bar timestamps,
   require `overlap_bars >= 10`, compute median (and max) relative close deviation, and
   compare against documented tolerance constants. Insufficient overlap, fetch failure
   or missing aliases return `UNVERIFIABLE` — a single source can never yield a positive
   result.
3. **Open-review integration (read-only):** the check runs only inside the existing
   **manual refresh** of the open-position review, as at most **one extra provider
   request**; its failure must not change the chart contract; the payload gains
   `instrument_product` fields; nothing is written to the database or the journal;
   `identity_verified` semantics stay exactly as they are today.
4. **Honest UI text (EN/TR/DE):** `CONSISTENT` names the independent source, the
   overlapping bar count and the measured deviation, with
   `NOT_BROKER_EXECUTION_EVIDENCE`; `DIVERGENT`/`UNVERIFIABLE` fall back to the current
   "source declaration, not verified" wording. The words "verified/doğrulandı" never
   stand alone as a product claim.
5. **Evidence:** focused tests plus one limited real credential-free run
   (`biquote_public XAUUSD 1m` vs `yahoo_public XAUUSD=X 1m` overlap) recorded under
   `artifacts/evidence/p1-wp43/`, full suites, i18n, build, docs and canonical CI.

## Ordered acceptance

- [x] Registry: spot-metal and FX product keys with their exact free-source aliases
  (biquote `XAUUSD`; yahoo `XAUUSD=X`, `XAGUSD=X`, `EURUSD=X`, …; stooq `xauusd`,
  `xagusd`, `eurusd`, … daily); `GC=F`/`SI=F`/`CL=F`/`PAXG…` carry non-spot keys and a
  `GOLD`→`GC=F`-style substitution can never compare as consistent.
- [x] Comparator: timestamp-aligned overlap only; `< 10` overlapping bars →
  `UNVERIFIABLE (INSUFFICIENT_OVERLAP)`; deviations computed on aligned closes only,
  median and max recorded; `DIVERGENT` when the median exceeds the documented
  tolerance (tolerance constants live in one place and are echoed in the payload).
- [x] Independent source selection reuses only the existing five free providers
  (no new hosts, no credentials, no paid data); no independent same-key alias →
  `UNVERIFIABLE (NO_INDEPENDENT_SOURCE)`; fetch failure → `UNVERIFIABLE` with the
  failure reason; never a silent second provider.
- [x] Manual-refresh integration: exactly one additional request attempt, bounded
  timeout, executed only after the declared fetch succeeded; the refresh result and
  chart rendering are unchanged when the check fails; no DB/schema writes (payload
  only); reviewed state includes `checked_at`.
- [x] Frontend: instrument panel shows the product-check line for gold first (then
  other mapped products); states localized EN/TR/DE; no new buttons; existing refresh
  CTA unchanged; `data-product-status` hook for tests.
- [x] Tests: synthetic comparator cases (aligned, skewed timestamps, divergent,
  insufficient overlap, wrong product class, fetch failure), request-cap and
  no-write assertions, review payload contract tests, frontend state rendering;
  full backend/frontend suites, i18n parity and production build.
- [x] Evidence: one limited real run for XAUUSD recorded as JSON (both sources,
  overlap bars, measured deviations, tolerance) plus a review screenshot with the
  real check result; honest note that a `DIVERGENT` real result ships as `DIVERGENT`.
- [x] Docs: this package's evidence section filled, STATUS updated, canonical local CI
  **MERGE READY** on the implementing commit.
- [ ] **Real independent-source verdict (CONSISTENT/DIVERGENT):** blocked on a reachable
  independent free same-product source for spot gold/FX. Probed 2026-09-17: yahoo
  `XAUUSD=X` answers HTTP 404 in the free public path and stooq answers HTTP 200 with a
  JavaScript browser-verification challenge instead of CSV (both `xauusd` and `eurusd`);
  the check honestly reports `UNVERIFIABLE (FETCH_FAILED)` until such a source exists.
- [ ] **Real pilot-data visual acceptance** of the product-check surface (an owner-host
  obligation, like the other pilot visual reviews).

## Product-class rules (contract)

| Product key | Class | Free source aliases (same product only) |
| --- | --- | --- |
| `SPOT_METAL:XAU:USD` | spot metal | `biquote_public XAUUSD` (1m–1w), `yahoo_public XAUUSD=X` (1m), `stooq_public xauusd` (daily) |
| `SPOT_METAL:XAG:USD` | spot metal | `yahoo_public XAGUSD=X`, `stooq_public xagusd` (daily) |
| `FX:<BASE>:<QUOTE>` | FX spot | `yahoo_public <PAIR>=X`, `stooq_public <pair>` (daily) |
| `FUTURE:GC` / `FUTURE:SI` / `FUTURE:CL` | futures | never comparable with spot keys |
| `TOKEN:PAXG` (and any crypto pair) | token | never comparable with spot or futures keys |

Default tolerances (median relative close deviation on aligned bars): metals **0.5 %**,
FX **0.2 %**. Both are echoed in the payload; if real overlap exceeds them the result is
honestly `DIVERGENT` and is never tuned to pass.

## Scope boundaries

- Reuses only the existing five free public sources and their exact symbols; no new
  network hosts, no credentials, no paid feeds, at most one extra request per manual
  refresh.
- Read-only: no journal, plan, ledger or database writes, no schema change, no
  background/automatic fetching.
- The existing close contract, the closed-trade review and the open-review chart
  contract are untouched; `identity_verified` keeps its current meaning.
- Money math stays where it is: contract-size/unit decisions remain the manual
  declaration (P1-WP37) and the crypto spot catalog (P1-WP34). The product check never
  unlocks or changes monetary results.

## Non-goals

- No futures integration, no spot-vs-futures basis analysis, no tokenized-metal
  (PAXG) equating.
- No session/holiday calendar modeling; gaps are reported, not classified.
- No broker API, no broker price-equality claim, no "XM supported" implication.
- No new dependency, no schema/migration, no UI redesign.

## Approved decisions (owner, 2026-09-17)

1. **Trigger:** the check runs automatically inside the existing manual refresh as
   exactly **one additional provider request**; a failed check leaves the chart
   rendering unchanged and reports `UNVERIFIABLE`.
2. **Tolerances:** metals ≤ **0.5 %**, FX ≤ **0.2 %** median relative close deviation on
   aligned overlapping bars; both echoed in the payload; real results beyond tolerance
   ship honestly as `DIVERGENT`.
3. **Initial scope:** **XAUUSD first** plus the FX majors where a daily overlap exists;
   XAGUSD is included only if it comes through the same code path without extra work;
   futures and tokens remain structurally non-comparable.

Implementation starts only on an explicit owner instruction; until then this package
stays `Ready` and no code is written.

## Evidence

**Implemented:** `backend/app/quant/instrument_product.py` (product registry + pure
comparator), integrated into `ReplayService.create_open_review_session` as exactly ONE extra
free-source request after a successful declared fetch, surfaced in
`OpenReviewBlock.instrument_product` and rendered by `TradeReplayCanvas` with a localized,
non-claiming line (`data-product-status`).

**Tests:**
- `backend/tests/test_instrument_product.py` **12 passed**: registry classification
  (spot/FX/futures/unknown), candidate selection (different provider, same-granularity
  preference, daily-declared gets a daily fetch, futures/tokens never receive a candidate),
  exact-bar alignment and the >=10 overlap gate, divergence measurement, skewed timestamps
  never align, millisecond normalization, UTC-day alignment with the latest partial day
  excluded, invalid/zero closes dropped, single-source or missing key never positive,
  fetch-failure and not-run payloads.
- `backend/tests/test_open_position_review.py` **21 passed** (4 new): the refresh contacts
  exactly the declared provider + one independent candidate; consistent and divergent
  outcomes carry the measured overlap/deviation/tolerance; an independent failure keeps the
  chart READY and reports `UNVERIFIABLE/FETCH_FAILED` with the candidate named; a futures
  declaration (`yahoo_public GC=F`) gets no candidate and no extra request.
- Full backend **1158 passed**; frontend **41 files / 280 tests** (3 new: consistency
  rendering with `data-product-status`/`data-product-provider`, divergent and unverifiable
  states, unknown-reason fallback); i18n parity **1213/1213/1213** with matching
  interpolation parameters; `npx tsc --noEmit` clean; production build clean;
  `check_docs` PASS; `git diff --check` clean.

**Limited real runs (credential-free, 2 requests each; JSON and screenshots in
`artifacts/evidence/p1-wp43/`):**
- `service-refresh-biquote-xauusd-20260917T102639.json`: a real open gold trade declared
  `biquote_public XAUUSD` refreshed to **READY** with 301 real 1m bars
  (2026-09-17 05:26-10:26 UTC); the product check honestly returned
  **`UNVERIFIABLE / FETCH_FAILED`** because the single independent candidate
  `yahoo_public XAUUSD=X` answered HTTP 404 (probed directly).
- `biquote-vs-yahoo-xauusd-20260917T102447.json`: the direct comparator run for the same pair.
- `free-source-availability-2026-09-17.json`: yahoo `XAUUSD=X` 404 (1m and 1d); stooq
  JavaScript challenge (xauusd, eurusd); `GC=F` daily works but printed **4349.20** against
  spot ~4314 — the basis that must never be equated; biquote serves 1m/1d.
- Screenshots: `01-unmatched.png` (manual-refresh state), `02-product-check-real.png`
  (bar 301/301, real candles, product-check line in place), `03-undeclared.png`.
- Honest note: the real verdict today is `UNVERIFIABLE`, not a consistency claim; a real
  CONSISTENT/DIVERGENT verdict is tracked as an unchecked item above. The mechanism is
  pinned by synthetic tests, and "CONSISTENT" would only ever mean independent-source
  agreement within the recorded tolerance — never broker execution evidence. The
  implementing commit, canonical CI report hash and installed-app hash are recorded in
  `docs/strategy/STATUS.md`.

## Non-goals

**Shipped in `v1.1.4` (2026-09-17, owner-approved release):** tag `pilot-v1.1.4` on the
release train commit `ab2c933`; GitHub prerelease with the verified arm64/x86_64 DMGs
(arm64 SHA-256 `ad3fd146bbf2b4f6c5a50dba4761d2ef6032e37e8bf9234756b83b0ae4a09dc3`, x86_64
`05ea2367c56b923e80b8e4f354683e411ebc13c0d8b6a922ef1e15c43ca218be`); the arm64 executable
`42ef84c426004bb6e24b404c93e72757184ccff35e0b71682cdc6af582e00fab` matches the app installed
and verified on the owner's Mac. `pilot-v1.1.3` is marked superseded and directs users here.
