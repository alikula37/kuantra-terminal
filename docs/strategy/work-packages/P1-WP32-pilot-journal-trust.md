<!-- doc-role: current-work-package -->
# P1-WP32 — Pilot journal trust: trade time, editing and sizing

```yaml
work_package: P1-WP32
status: InProgress
branch: main
baseline: feec62c58dc982497a21ce37d3b37c2d1db9bfa2
```

Owner instruction (2026-09-14): pilot traders must be able to read the journal
comfortably, record and edit trades easily, and follow open positions without a
manual refresh. The standard journal's primary row action becomes **Edit**; replay
moves to a secondary action inside the edit dialog for closed trades.

## Ordered acceptance

- [x] Package 1: user-supplied trade date/time in `Europe/Istanbul` (minute
  precision), open/closed-at-entry status, UTC-aware storage, future-time
  rejection, historical open vs historical closed behavior.
- [x] Package 2: declared leverage and separated price/position/margin returns;
  quantity or supported position-size entry, no contradictory independent inputs;
  no invented contract-size, liquidation or margin claims.
- [x] Package 3: working trade edit for allowed fields with `expected_revision`
  conflict handling, correction lineage, partial-close protection and consistent
  journal/detail/tracking/analytics reads; historical open trades start local
  tracking only from the first eligible observation after recording.
- [x] Package 4: automatic open-trade quote refresh while the app is awake,
  provider-key sharing, bounded concurrency/backoff, list "refresh all" and
  detail "refresh price" with wait/success/error and LIVE/DELAYED/stale state;
  automatic close rules (LIVE, provider-event, <=60s) unchanged.
- [x] Package 5: simplified New Trade and Edit surfaces (sections, conditional
  fields, concrete errors, equal-split helper, safe preferences, EN/TR/DE).
- [x] Package 6: readability pass on core screens (>=16px primary, >=14px
  secondary, ~44px controls, contrast, focus) without a new design system; small
  screens do not clip form actions or errors.
- [x] Full backend/frontend/i18n/doc checks and canonical Mac local CI.

## Scope boundaries

- No broker order dispatch, no exchange secrets, no paid market data, no real user
  data reset/migration. Existing local TP tracking quote rules are not weakened.
- Historical candle highs/lows are not treated as realized fills; skipped closes
  while the app was closed/asleep are not invented.
- Synthetic data only for tests; installed app and GitHub Releases are untouched
  until separately approved.

## Evidence

Backend suite: `KUANTRA_DATA_DIR="$(mktemp -d)" .venv/bin/python -m pytest -q
backend/tests` → **903 passed / 2 warnings** (baseline before this package: 880).
New focused file `backend/tests/test_p1_wp32_pilot_journal_trust.py` → **23
passed**, covering Istanbul/UTC conversion, future-time rejection, historical
closed vs open behavior, tracking `armed_at > entry_time`, leverage return
separation, spot leverage rejection, notional/quantity conflict, XAUUSD unknown
contract size, revisioned edit lineage, stale-revision 409, atomic driver
revision guard, notes-only closed policy, partial-close size lock, safe plan
reset before any close, canceled immutability, identity-shared quote refresh with
stale last-known, DELAYED display-only status, Istanbul weekly-review boundary
(`2026-09-13T21:00:00Z`) and legacy default columns.

Schema revision `006_trade_time_edit_sizing` adds `leverage`, `revision`,
`entry_time_source`, `close_source`, `tracking_started_at` additively; Alembic
head, `macos_migration` classification/upgrade and the two head assertions were
updated, and H02 upgrade/restore tests stay green. Corrections append
`TradeCorrected` events whose provenance stores previous values per field; the
projection snapshot carries the new fields and rebuild/export equivalence is
covered by the existing lifecycle tests.

Frontend: `npx tsc --noEmit` clean; `npx vitest run` → **36 files / 180 tests**
(baseline: 31/154). New suites: `tradeTime.test.ts` (5), `positionMath.test.ts`
(7), `TradeEditModal.dom.test.tsx` (5), `JournalView.p1wp32.dom.test.tsx` (3),
`NewTradeModal.p1wp32.dom.test.tsx` (6). `npm run check:i18n` → **944/944/944**
EN/TR/DE; production `npm run build` passes. The New Trade form now has four
labeled sections, Turkey-time trade date/time with a visible `Türkiye saati`
label, still-open/closed-earlier selector with user-reported close fields, a
quantity-or-notional size switch, declared leverage only for long/short with a
click-to-apply previous-use suggestion, equal-split (`33.33/33.33/33.34`), and
concrete per-field errors; the summary shows the trade time, derived notional,
estimated margin and an explicit warning when the current quote already crossed
a target. The Journal's primary row action is now Edit; replay is a secondary
action inside the edit dialog for completed trades. The Journal and Dashboard
open positions show live quote status, age and stale last-known values, with
"Refresh all" / "Refresh price" controls.

Canonical Mac arm64 local CI (run on the implementation tree immediately before
this evidence note):
`uv run --offline --no-project --with-requirements backend/requirements.lock
python scripts/run_local_ci.py --expected-architecture arm64 --report
dist/p1-wp32-local-ci-final2.json --smoke-timeout 90` → **MERGE READY**, 13/13
steps PASS (diff-check, compileall, release-truth, packaging-integrity,
supply-chain-audit, backend tests, frontend tests/build, PyInstaller desktop
build, native smoke, smoke contract, renderer preflight, provenance contract).
Report SHA-256 `95a096b47a9eb63ca7bb364720fb88353f1d26fc45d01c4253943ab2659c2dc5`;
smoke report `dist/local-ci-smoke.json` SHA-256
`3f25c3c8a67610b42adfa02236fe6f83cbf950e893dabe17f81d6961a8717843`; tracked
source tree SHA-256 `e38dc91cc50f836a87c8c72bb4bfc72c43a63fc81dd539602807043725b06d62`;
executable SHA-256 `e689331cbbef0c704615469cce1ff7d47827696b1d4c00c7abd820cfe0ea9db8`.
Provenance is `DEVELOPER_DIRTY` because this change is intentionally uncommitted;
this is development evidence, not release attestation. `python3.11
scripts/check_docs.py` PASS (117 documents / 161 local links / 5 startup
documents), `python3.11 scripts/check_release_truth.py` PASS and `git diff
--check` clean.

Known limits: the installed application and GitHub Releases were not changed; the
readability floor applies globally through shared primitives and small-text
utility overrides, while non-journal advanced screens were not individually
redesigned. Historical replay/backtest reconstruction, exchange-verified closes,
fee/funding accrual and real liquidation data remain out of scope.

## Independent review fixes (round 2)

Four review findings were reproduced, locked with failing tests, and fixed.

1. **Edited TP/SL did not drive the local plan.** Reproduction: a plan stop of
   `95` stayed at `95` after `PATCH` set the trade stop to `90`, so a `94` quote
   closed the trade under the stale stop. The journal stop now updates the plan
   and the trade row in one transaction; the legacy take-profit column mirrors
   TP1, a single pending target accepts a TP correction, and a multi-target or
   completed plan rejects it with `TARGETS_MANAGED_BY_PLAN`. The edit screen now
   edits the plan itself (targets editor with completed-target locks); an
   explicit plan payload carries its own `expected_revision`, plan+single-field
   orders are rejected as ambiguous, and a failed plan write rolls back the
   whole correction. After the fix a `94` observation produces no close and an
   `89` observation closes exactly once, including under a concurrent
   edit/observation race.
2. **Entry-time corrections were not saved.** `apply()` compared the new instant
   with itself, so the API returned `no_change: true`. Old and new instants are
   now normalized separately, equal instants stay idempotent (no redundant
   revision), a real change persists with `entry_time_source=USER`, and the
   correction history, re-read and projection rebuild all show the new time.
3. **A failed refresh could leave an old price looking LIVE.** The hook now
   demotes every displayed price to an explicit stale last-known value on
   transport/HTTP/malformed failures, tracks the last attempt separately from
   the last successful check, derives the displayed age from the observation
   time on a 1 s tick (no frozen age), and restores LIVE after the next
   successful response. The automatic-close freshness contract (LIVE,
   provider-event, <=60 s) is not weakened.
4. **Unknown contract sizes produced misleading money math.** `position_math`
   now withholds notional, margin and monetary P/L (`null` +
   `CONTRACT_SIZE_UNVERIFIED`) for gold, futures, provider-symbol forms and
   generic tickers instead of only warning; symbols with provider separators are
   never inferred as base-unit crypto pairs from a suffix. Local tracking
   refuses to create or edit plans for unverified instruments, legacy plans
   cannot produce close evidence, manual local close reports the boundary, a
   user-reported close of an unverified trade stores `pnl = null` (never a
   synthetic zero), and portfolio summaries exclude unknown results and count
   them (`unknown_pnl_trades`, `unverified_open_positions`). Verified base-unit
   crypto pairs keep their existing calculations.

Round-2 evidence: `backend/tests/test_p1_wp32_review_fixes.py` **11 passed**;
full backend **914 passed / 2 warnings**; frontend **37 files / 192 tests**
(new stale/recovery/age tick, unverified tracking/money gating, plan editor and
open-position gating suites); `npx tsc --noEmit` clean; i18n
**956/956/956** EN/TR/DE. The first red runs are reproduced in the review test
design: before the fix the stop plan stayed at 95, `entry_time` returned
`no_change`, `XAUUSD` returned `notional 4000 / margin 400 / gross 200`, and the
hook kept `LIVE` on a failed transport refresh.

Canonical Mac arm64 local CI on the fixed tree (docs note follows the run):
`uv run --offline --no-project --with-requirements backend/requirements.lock
python scripts/run_local_ci.py --expected-architecture arm64 --report
dist/p1-wp32-review-local-ci-final.json --smoke-timeout 90` -> **MERGE READY**,
13/13 steps PASS, native WKWebView smoke. Report SHA-256
`7f5b6d4513ff3df217b9517a231c6da3304d87d6b4779d8ee6fcc421dd39a2eb`; smoke
report `dist/local-ci-smoke.json` SHA-256
`4d4b1b334ca752463fff806ad995b9cc4119fcf04a23171eb65301a867e93beb`; tracked
source tree `245b63db3791e5a2f6c1e7107c721b3a4aefb5ee156a3449e3e85759fb88c563`;
executable `f0c867c3e2db7a1f6451d705b26a9ce78794f20c9c41c508f8dc436fdb70d29a`;
provenance `DEVELOPER_DIRTY` (uncommitted). One earlier CI run transiently failed
the backend step without a reproducible test failure; three consecutive clean
full-suite runs (914 passed each) and the final gate run above passed. No commit,
release or installed-app change was made.

## Round-3 fixes (plan-only edits and unit verification)

1. **Plan-only edits were skipped.** Changing only TP2/TP3, target percentages
   or the tracking enabled flag returned `no_change: true` because the decision
   compared only the mirrored trade columns. `TradeEditService` now compares the
   entire plan payload (enabled, source identity, stop, targets and plan
   revision) and records a `tracking_plan` revision marker in the correction
   history when nothing else changed; a stale plan revision still returns 409.
   Red first: a TP2-only PATCH answered `no_change: true` and left the plan at
   revision 1; now it answers `no_change: false`, saves plan revision 2 and the
   trade revision, while an identical payload stays idempotent.
2. **Symbol suffixes no longer grant verified base-unit status.** Monetary math
   now requires a provider-confirmed instrument identity (`binance_public` /
   `bybit_public` with the exact provider symbol) or an explicit
   `qty_unit=BASE` contract stored on the trade (schema revision
   `007_trade_qty_unit`). `EURUSD`, `GBPUSD`, `FAKEUSD` and manual symbols
   without a declaration produce no notional, margin or money P/L, cannot open
   a local plan and store `pnl=null` on a user-reported close; verified crypto
   pairs keep their existing math. The New Trade form exposes the explicit unit
   checkbox plus the verification source; the edit screen can declare it later
   through a revisioned correction. Red first: suffix-only EURUSD/GBPUSD/FAKEUSD
   returned notional/margin/gross figures; now they return `UNAVAILABLE` with
   `notional=null`, while `qty_unit=BASE` or a matching provider identity
   returns the correct 1100/20 math.

Round-3 evidence: `backend/tests/test_p1_wp32_round3_fixes.py` **10 passed**;
full backend **924 passed / 2 warnings**; frontend **37 files / 198 tests**;
`npx tsc --noEmit` clean; i18n **964/964/964**. Canonical Mac arm64 local CI on
the fixed tree (docs note follows the run):
`uv run --offline --no-project --with-requirements backend/requirements.lock
python scripts/run_local_ci.py --expected-architecture arm64 --report
dist/p1-wp32-round3-local-ci.json --smoke-timeout 90` -> **MERGE READY**, 13/13
steps PASS. Report SHA-256
`6a7a1bc79832fc70be12eaf9b423632e021a9c293a33b275dab9cd0e424f45ce`; smoke
report `dist/local-ci-smoke.json` SHA-256
`09e8b996fec8179765e975a3019ef471c4cbdda01c708fc043cec37b987a8272`; tracked
source tree `5d8f7b13c3ca08b67a6d5ed638597b376f1b67f9d709e42dcca271f00261f3df`;
executable `d43c8f9b99c9feb8232f88047d81c71921e67b23adbc19e9239142953339b9f4`;
provenance `DEVELOPER_DIRTY` (uncommitted).

## Round-4 fix (provider labels are not verification)

A client-supplied `price_source`/`price_source_symbol` pair was still accepted as
provider verification, so an isolated API test could record
`FAKEUSD + binance_public + FAKEUSD` and receive `PROVIDER_INSTRUMENT` / `READY`.
The backend cannot prove the instrument exists, is the same product, or uses
base-unit quantity, and price discovery alone does not establish a contract
multiplier.

The provider path is therefore closed: until a server-verified instrument
catalog exists, the only accepted basis for monetary math is an explicit user
`qty_unit=BASE` declaration (schema revision `007_trade_qty_unit`), reported as
`verification: EXPLICIT_QTY_UNIT` with
`verification_source: USER_DECLARATION`. `price_source`/`price_source_symbol`
remain price provenance only. The same rule is applied by `position_math`,
create/close P/L gating, portfolio open-risk/volume aggregation, the local
tracking gate (`observe`/`edit`/`list unit_status`) and the frontend, which now
always exposes the explicit declaration checkbox plus the verification label.

API-level evidence (before -> after):

- `FAKEUSD` + `binance_public`/`FAKEUSD` label: provider verification rejected;
  sizing `UNAVAILABLE`, `notional=null`, close `pnl=null`, local plan `422` with
  full rollback.
- Real symbol (`BTCUSDT`) with a provider label and no declaration:
  `UNAVAILABLE` (a price or label cannot stand in for contract knowledge).
- Explicit `qty_unit=BASE` on the same symbol: `READY`, labeled
  `EXPLICIT_QTY_UNIT / USER_DECLARATION`, with correct notional and gross math;
  a revisioned edit can revoke the declaration and the gate re-applies while
  stored close evidence is untouched.

Round-4 evidence: `backend/tests/test_p1_wp32_round4_fixes.py` **5 passed**;
full backend **929 passed / 2 warnings**; frontend **37 files / 198 tests**;
`npx tsc --noEmit` clean; i18n **963/963/963**. Canonical Mac arm64 local CI on
the fixed tree (docs note follows the run):
`uv run --offline --no-project --with-requirements backend/requirements.lock
python scripts/run_local_ci.py --expected-architecture arm64 --report
dist/p1-wp32-round4-local-ci.json --smoke-timeout 90` -> **MERGE READY**, 13/13
steps PASS. Report SHA-256
`d4bb14afb05b3d2f9eb292196cd7ba4f905137d01b058450c59a8e38f4ae0e72`; smoke
report `dist/local-ci-smoke.json` SHA-256
`5b9f534e692e840267d6802aab4991fdb0160447546af11436dae039d458f7d4`; tracked
source tree `daa3e351d1b00a6715cea14fd562719035675c7a88aa32193ba085ce2e8e75d9`;
executable `4135267d55212772452b555dd2327566379d71e005fda53ae7b92b6a88d852eb`;
provenance `DEVELOPER_DIRTY` (uncommitted).

## Clean-source commit and distribution validation

Implementation commit `bfd52b3a724f3de0dc24646a3276b1e1a564f947`
("feat: add Turkey-time journal trust, revisioned editing and unit-declared
sizing") contains the complete P1-WP32 work. The tracked tree is clean
(`git status --porcelain --untracked-files=no` empty); only the preserved
untracked `.codex/` and P1-WP27 evidence directories remain outside this change.

Canonical Mac arm64 local CI on that commit
(`uv run --offline --no-project --with-requirements backend/requirements.lock
python scripts/run_local_ci.py --expected-architecture arm64 --report
dist/p1-wp32-clean-local-ci.json --smoke-timeout 90`): **MERGE READY**, 13/13
steps PASS, provenance **COMPLETE**, `source_commit_sha = bfd52b3a…`, tracked
tree `7e66cf0e8fc1c834d27bdefc9888e9ea0cfc367e8cd93483c803ccff87f1d5e9`;
backend **929 passed / 2 warnings**, frontend **37 files / 198 tests**, i18n
**963/963/963**. Report SHA-256
`91bfd4bfb6555e699c23d409cf4b9e784aced452d437f5a617dd32bb6863b6b4`; local CI
smoke report `d1ad0628049654db650a0cd04acf80424e09292f79a9fe9c499bc9f06b1b9df6`;
built executable `afde5274beda8b097d834ffbaabc9362e7149db7ad8e6b7a18f9d488d6f19a9f`.

Distribution validation from the same clean source (local artifacts only):

- DMG `dist/Kuantra-Terminal-1.0.0-arm64.dmg` built with `PYTHON_BIN=python3.11
  scripts/package_macos.sh --architecture arm64 --app "dist/Kuantra Terminal.app"`;
  `hdiutil verify` = **VALID**; DMG SHA-256
  `04416ce65504338db764a43d562410ccf11d7c10934884774761a414173df47d`;
  mounted executable SHA-256 `afde5274…` (matches the CI build).
- Exact read-only mounted-DMG smoke (`scripts/smoke_macos_dmg.py`, isolated temp
  data dir, `KUANTRA_MARKET_DATA_ENABLED=false`): **PASS**, native arm64,
  `wkwebview` controller ready, `COMPLETE` provenance; report SHA-256
  `97a1de2d663731c182cdc5a90e4e514d7e125e2a5175b5f4c8e2af6e8665d428`.
- N05 preflight: `BLOCKED` as designed (ad-hoc artifact, no Developer
  ID/notarization); report SHA-256
  `fc905f6bd44ba8c83c3dcd5eaba57bbc5d72a440e96698959d00c758a332a64b`.
- Pilot package `dist/p1-wp32-clean-pilot-package/`: `TRUSTED_MACOS_PILOT_ARM64`,
  status `AD_HOC_TRUSTED_PILOT_ONLY_ARM64`, bound to `bfd52b3a…` with the clean
  tree hash; `shasum -a 256 -c SHA256SUMS` passed for all five payload files;
  `SHA256SUMS` SHA-256
  `c76dcce8c2e45983ff39d82c1018cbac6869b59c576e07651c883d5a1143c6f2`; manifest
  SHA-256 `c818938a4dc89e6b9550c3d6ba24d5a88cb1b15605da7bfda7f0fa50d9d6ff0b`.

No GitHub Release asset or installed application was changed by this validation;
both remain behind separate owner approval. The package is ad-hoc and
trusted-pilot-only, not notarized or production evidence, and Intel remains
outside this local arm64 chain.

## v1.1.0 pilot prerelease

Owner-authorized pilot publication of the P1-WP32 train. GitHub Actions candidate run
[`34946454427`](https://github.com/alikula37/kuantra-terminal/actions/runs/34946454427)
(`workflow_dispatch`, `release_tag=v1.1.0`, `publish=false`, source
`122b6bef522f3e2ed9872f82e3bed5cf98f25a58`) passed both native build jobs: arm64 on
`macos-latest` and x86_64 on `macos-15-intel`, each with the locked backend/frontend
suites, native desktop smoke including the synthetic local TP lifecycle, exact read-only
mounted-DMG smoke and `COMPLETE` provenance. The trusted pilot package artifact verified
with `shasum -a 256 -c SHA256SUMS` for all eight payload files, and both downloaded DMGs
passed `hdiutil verify` locally.

Private prerelease:
[`pilot-v1.1.0`](https://github.com/alikula37/kuantra-terminal/releases/tag/pilot-v1.1.0)
(tag at `122b6be`, `PRERELEASE`, `AD_HOC_TRUSTED_PILOT_ONLY`) carries exactly two assets
whose GitHub digests match the CI reports:

| Architecture | DMG SHA-256 | Mounted executable SHA-256 |
|---|---|---|
| arm64 | `ce0cc652e6d57d38dc6d6e06aa9d9fde2131f480cfe92c18be1e827c764df803` | `4b3013e44b0ef143e2f24a8b638c21525a84f9d0ddb72a9ad24b740fecc2d808` |
| x86_64 | `09e27a31bbbd929b061d2c21da2d3bca4e4fa7c0050e5eb0770532f67656ef1c` | `45e58975eccaa5119b95e06cc4267dc1c28d9a84ed287629e1e0ea5aa0ccc13e` |

Two earlier candidate runs failed before publication: the workflow's npm-audit tolerance
was pinned to the previous tag (`1fd0030`) and the native tracking smoke created its
synthetic plan before the explicit `qty_unit=BASE` declaration existed (`122b6be`). Both
were fixed and re-validated; the failure logs are retained in the run history. N05 remains
`BLOCKED` (ad-hoc, no Developer ID/notarization) and the installed application was not
modified.

## Round-5: note-style status editing, form overflow and header cleanup

Owner feedback after pilot use (2026-09-15):

1. **A canceled trade can be edited and brought back.** The journal is a personal note
   system, not a ledger with terminal states. The edit surface now exposes an explicit
   Open / Closed / Canceled control for every trade:
   - Canceled → Open: the record is restored and can immediately receive a local TP/SL plan
     again; `is_tombstone` clears on rebuild.
   - Canceled → Closed: requires user-reported exit price/time; P/L is computed only for an
     explicitly declared base unit, otherwise it stays unknown.
   - Closed → Open (reopen): clears the stored exit result on the row; the append-only
     ledger keeps the previous price/time/PnL in the correction provenance, and the trade
     leaves the closed-trade aggregates.
   - Open → Closed from the editor: requires the realized exit price/time and records
     `close_source=USER_REPORTED`.
   - Completed trades keep their evidence protection: without a status change only notes
     can be edited, and canceling a completed trade is status+notes only.
   Every transition is revision-checked (409 on stale editors) and appears in the revision
   history (`status`, `exit_price`, `exit_time`, `pnl` with previous values).

2. **New Trade overflow fixed.** `margin_source_UNVERIFIED_CONTRACT_SIZE` and
   `reason_TIME_IN_FUTURE` translation keys were missing, so raw keys rendered and
   overran the derived-value grid. The keys are added in EN/TR/DE, and the derived panel
   now stacks on narrow windows (`grid-cols-1 sm:grid-cols-2 xl:grid-cols-4`) with
   `min-w-0`/`break-words` cells so long labels or currencies cannot overlap a neighbor.

3. **Top header boxes removed.** The portfolio telemetry cards (total equity, open risk,
   realized), the market-status badge and the event-age badge were removed from the top
   bar. The header now carries only the brand plus functional controls (persona/LITE,
   language, theme, API keys, GPU/vision when active, New Trade); it no longer polls the
   portfolio endpoint. Portfolio numbers remain on the Dashboard.

Evidence: backend `test_p1_wp32_trade_status_edits.py` **9 passed**; full backend
**938 passed / 2 warnings**; frontend **37 files / 199 tests** (new status-control,
reopen-notice, exit-required, canceled-restore and slim-header tests); `npx tsc --noEmit`
clean; i18n **976/976/976**. Canonical Mac arm64 local CI on the working tree is
**MERGE READY** (13/13), report `dist/p1-wp32-ui-round-local-ci.json` SHA-256
`b2b9ab40dad3d9d76b544e22fc290cf855abf45d1be5ef8108b1ca00f4bf6f3a`, provenance
`DEVELOPER_DIRTY` (uncommitted). The installed app and GitHub Releases were not changed by
this round.

### Round-5 clean build and installed-app update

Per the owner standing instruction (AGENTS.md, 2026-09-15), the verified round-5 change was
committed (`8719b27`, pushed) and the Mac's installed application was updated from the clean
commit:

- Canonical Mac arm64 local CI on `8719b27`: **MERGE READY**, provenance **COMPLETE**, tree
  clean, backend **938 passed / 2 warnings**, frontend **199 tests**, i18n **976/976/976**;
  report `dist/p1-wp32-round5-clean-local-ci.json` SHA-256
  `d633827c2f5bf301e6f759a7b3f32833d692e9cda78d9f78fbe237b7c65e1327`, built executable
  `eeb16e89f3c4418678df79aaa0266d42b640b1a036453d749ffc083ac6c27287`.
- Exact arm64 DMG `dist/Kuantra-Terminal-1.1.0-arm64-round5.dmg` built from that app:
  `hdiutil verify` **VALID**, DMG SHA-256
  `1ad8123c9ffa5835e3d930cdd8f4c210c3876636c5ff6b19abdc2e94890129ed`; exact read-only
  mounted-DMG smoke **PASS** (report `dist/p1-wp32-round5-dmg-smoke.json` SHA-256
  `acddbaafb5357913e4157fae2c3dd6b318fd1bf271b1ef6ccb32144117e624bc`).
- `/Applications/Kuantra Terminal.app` replaced after a graceful quit; installed executable
  SHA-256 matches the CI/DMG executable, `codesign --verify --deep --strict` passes, version
  `1.1.0`, launched PID `38584`, local runtime `{"status":"online","gateway":true,"version":"1.1.0"}`.
  User data under `~/Library/Application Support/Kuantra Terminal` was preserved.
- The GitHub pilot prerelease was not changed by this local update; a Release refresh remains a
  separate owner decision.
