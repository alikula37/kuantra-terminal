<!-- doc-role: current-status -->
# Current development status

Updated: 2026-09-17. Branch: `main` (latest owner instruction).

**Selected work: [P1-WP29 trusted macOS pilot package](work-packages/P1-WP29-trusted-macos-pilot-package.md).**
The package is selected for its still-open owner-host obligations (N03/N05/H05/pilot
access); no development proceeds under it without owner approval. Owner instruction
(2026-09-17): traders size positions in USD, not base units — the bounded
[P1-WP45 USD position value package](../archive/strategy/work-packages/P1-WP45-usd-position-value.md)
retired the base-quantity entry, made USD value the only sizing (stored as `qty` with
`qty_unit=USD`), derived money math from the value with an explicit approximate label for
non-USD quotes, and — by explicit owner instruction ("hepsini sil. mantık hatalıydı") —
deleted all existing trade records after a full backup, shipping as `v1.1.5`.

**P1-WP45 implementation evidence (this change, uncommitted):** entry/edit now have a single
USD position-value field (payload `size_input_mode=NOTIONAL`, `qty_unit=USD`; the base pair the
old model proved is retired); the backend prices from the value (`USD_NOTIONAL` basis:
notional = value, margin = value/leverage, PnL = price-return × value, R from the price-risk
fraction) and labels non-USD-quoted pairs `QUOTE_NOT_USD_APPROXIMATE`; local tracking stores
the unit and prices USD closures from the value; portfolio risk/margin/unrealized/volume use
the value; journal, open positions, edit modal, tracking panel and exports state the USD
unit. Legacy `BASE`/`UNKNOWN` rows remain readable and are never rewritten automatically (a
notes-only edit keeps them; a changed value declares USD). Evidence: `test_wp45_...` **9
passed**, full backend **1173 passed**, frontend **41 files / 286 tests**, i18n
**1228/1228/1228**, `tsc`/build clean. The trade-domain wipe and the v1.1.5 release/install
evidence are recorded below once executed.

**v1.1.5 release train (2026-09-17, owner-approved):** the USD position-value sizing change
ships as `v1.1.5` (`truth-matrix.v1.1.5.json`, `pilot-v1.1.5` prerelease with the tag on the
verified build commit); `pilot-v1.1.4` keeps its historical packages and redirects users to
v1.1.5. **Trade-domain wipe complete (owner instruction):** full data-directory backup at
`~/Documents/Kuantra-Backups/backup-20260917-155320` first; then trades, evidence events,
trade projections, local tracking plans and the OLAP trade table were emptied (all verified
0), the append-only triggers were restored, and preferences, playbooks, the instrument
verification cache and the 17,424-row market candle cache were kept. Release run id, DMG
and mounted-executable hashes and the installed-app verification are recorded below.

**v1.1.5 release and install evidence (2026-09-17):** train commit `592e04c` (tag
`pilot-v1.1.5` on it); candidate release run `35223913627` **success**; all artifact
checksums re-verified locally (`sha256sum -c SHA256SUMS` OK); DMG SHA-256 arm64
`b6efc5758aeb9d9891d032eb3c6dae050118d432d4dd5d595ad40e2ffd031184`, x86_64
`99a770d89c5f9436c5c1e8dbfc62014d152a69c8f2fd169103b466e291b184e3`; mounted executables
arm64 `1e38bc5bf641f0e94899ef451c8ed8139bfe30edf75b296c19ea22a04d837391`, x86_64
`93c62ff12b0a7d8a128bf7d1c6a70a4da3ed444cac597b291b7a1817b4333ea0`; exact mounted-DMG
smoke **PASS** on both lanes; N05 ad-hoc `BLOCKED / OWNER_REVIEW_REQUIRED` as expected. The
arm64 artifact was installed over `/Applications/Kuantra Terminal.app` (backup at
`/tmp/kuantra-v115-update.dsIlgF`): installed executable matches the CI build, codesign OK,
version 1.1.5, launch verified and the journal confirmed intentionally empty
(trades/events/tracking 0 after launch). GitHub prerelease `pilot-v1.1.5` and the
`pilot-v1.1.4` supersede notice follow this commit; app backup and data backup paths are
recorded above.

**Live test trade and post-release fixes (2026-09-17, owner-requested):** a simulated
BTCUSDT LONG was opened at the live 76,601.0 quote with a $500 USD position value, 10x
leverage and a ±0.05 % SL/TP bracket. The local plan **auto-closed via SL** at 76,531.48
(gross -0.4538 USD, `LOCAL_ESTIMATE`, provider event 13:31:23.99Z) while the external record
correctly stayed OPEN; the portfolio's real aggregates stayed untouched and only the
simulation counters moved. The cross-screen check (journal, dashboard open positions, local
tracking panel, edit modal, portfolio tiles) found and fixed two gaps: the dashboard
open-positions table now loads server-side open positions (it previously showed nothing
after a restart) and the open PnL column shows the mark-to-market value instead of the
stored zero. Commits `9dbde34` (fix + tests: frontend 41 files / **287 tests**, backend
**1173 passed**); canonical arm64 local CI on the clean commit **MERGE READY** (report
`dist/p1-wp45-postfix-local-ci.json`, executable
`add409088cfb7eea2e8550f0f507cbf6809866e737033d0bce48190af305fd4c`). arm64 DMG
`dist/Kuantra-Terminal-1.1.5-postfix-arm64.dmg` SHA-256
`775cbeba122134e4d6a0235304f7b017241f1c2eb6b21aeff7f49d597120b387` (exact-DMG smoke PASS)
was installed over `/Applications/Kuantra Terminal.app` (backup
`/tmp/kuantra-postfix-update.Gd40oc`): installed executable matches the CI build, codesign
OK, version 1.1.5, launch verified. The test trade remains in the journal for the owner's
inspection; evidence `artifacts/evidence/p1-wp45-test/`. GitHub Release/tag for these
post-release fixes awaits a separate owner decision.
Owner instruction (2026-09-17): the three real-UI-test findings on the installed app were
reproduced, diagnosed and fixed in isolated synthetic data under
[P1-WP44 confirmed identity, simulation separation and reachable journal actions](../archive/strategy/work-packages/P1-WP44-identity-sim-separation-journal-actions.md)
(complete and archived). (1) A hand-typed entry price no
longer erases the confirmed provider identity: creation now sends the confirmed
provider/symbol separately from `price_origin=MANUAL`, so the journal quote refresh returns
LIVE, the chart review resolves the declared provider and the local plan keeps the same
identity (backend end-to-end tests; real `binance_public BTCUSDT` run returned LIVE 76362.0
and `PROVIDER_MATCH_REQUIRED`; no provider is ever inferred from symbol text and legacy rows
are untouched). (2) Simulation records are labelled in the journal and open-positions table,
journal rows show the local plan state/remaining quantity with an explicit "local completion
is an estimate; the external trade is still open" notice while the lifecycle stays OPEN, and
simulation records no longer enter real monetary aggregates (portfolio summary, asset
breakdown, equity curve, daily heatmap) which now expose explicit simulation counters.
Verified finding: they previously did mix; `/analytics/overview` and the pivot grid remain
unchecked (OLAP projection lacks `record_mode`; owner decision needed) along with the pivot
seed-data fallback. (3) Row actions are pinned to the right edge at 1229×768 (measured inside
the viewport and keyboard-focusable despite `scrollWidth 1717 > clientWidth 971`), with no
font-size change; DOM and visual regressions added. Full suites: backend **1164 passed**,
frontend **41 files / 284 tests**, i18n **1221/1221/1221**, `tsc`/build clean. Working
behaviours preserved: quantity/leverage/TP edit saves, local automatic closes, the LIVE +
provider-event + <=60s contract and the real-vs-local split. Evidence:
`artifacts/evidence/p1-wp44/`.

**P1-WP44 delivery verification (2026-09-17):** commits `789d3e1` (backend), `88ee5ea`
(frontend), `a36fcdd` (docs; WP44 archived Complete with 2 tracked unchecked items). Clean
commit `a36fcdd` canonical arm64 local CI: **MERGE READY**, provenance **COMPLETE**, clean
tree; report `dist/p1-wp44-committed-local-ci.json` SHA-256
`b91e1b906be211ee7093117cf137fc4eb93ba046be05afd7c8540ba4ebb4565d`, executable
`302455ee63adc51c2e93a99b6230532d33bd1971876c4377200610c410a4cba8`. arm64 DMG
`dist/Kuantra-Terminal-1.1.3-wp44-arm64.dmg` SHA-256
`19cc416c7400d2df8647b9551f69623e46c0a3311ac4f0d6ab56eba41035dc16`; exact read-only
mounted-DMG smoke **PASS** (`dist/p1-wp44-exact-dmg-smoke.json`). `/Applications/Kuantra
Terminal.app` was replaced and verified: installed executable matches the CI build,
`codesign --verify --deep --strict` passes, version 1.1.3, launch path and clean quit
verified, user data preserved. GitHub Releases and tags were untouched for the bounded fix itself.

**v1.1.4 release train (2026-09-17, owner-approved):** the chart review (P1-WP42), the
independent product-consistency check (P1-WP43) and the identity/simulation/journal-action
fixes (P1-WP44) ship as `v1.1.4` (`truth-matrix.v1.1.4.json`, `pilot-v1.1.4` prerelease
with the tag on the verified build commit). The former `pilot-v1.1.3` release keeps its
historical 1.1.3 packages and redirects users to `pilot-v1.1.4`; the canonical product
Release/tag is not moved. **v1.1.4 release evidence (2026-09-17):** train commit `ab2c933` (tag `pilot-v1.1.4` on
it); candidate release run `35216823564` (`workflow_dispatch`, `publish=false`) **success**;
all artifact checksums re-verified locally with `sha256sum -c SHA256SUMS` (OK). DMG SHA-256:
arm64 `ad3fd146bbf2b4f6c5a50dba4761d2ef6032e37e8bf9234756b83b0ae4a09dc3`, x86_64
`05ea2367c56b923e80b8e4f354683e411ebc13c0d8b6a922ef1e15c43ca218be`; mounted executables:
arm64 `42ef84c426004bb6e24b404c93e72757184ccff35e0b71682cdc6af582e00fab`, x86_64
`c6995532b85811e468a79baa373f2897c18c988ed616652ac8033923de433bed`. Exact mounted-DMG smoke
**PASS** on both native lanes; N05 ad-hoc status `BLOCKED / OWNER_REVIEW_REQUIRED` as
expected (no Developer ID/notarization). The GitHub prerelease `pilot-v1.1.4` is created
with the two DMGs and `pilot-v1.1.3` is marked superseded; the arm64 DMG was mounted, its
checksum verified, and `/Applications/Kuantra Terminal.app` was replaced with the verified
artifact: installed executable SHA-256 matches the CI build, `codesign --verify --deep
--strict` passes, version 1.1.4, launch/quit verified, user data preserved.
The owner-host obligations of the selected
[P1-WP29 trusted macOS pilot package](work-packages/P1-WP29-trusted-macos-pilot-package.md)
(N03/N05/H05/pilot access) remain tracked there and are unchanged.
Owner instruction (2026-09-17): the WP42 instrument-product blocker was closed with the
bounded [P1-WP43 spot-product consistency package](../archive/strategy/work-packages/P1-WP43-spot-product-consistency.md),
now complete and archived. The open review refresh now runs exactly ONE extra independent
free-source request and reports `CONSISTENT`/`DIVERGENT`/`UNVERIFIABLE` with the declared
product key, the independent source, the aligned overlap and the measured deviation —
futures (`GC=F`) and tokens are structurally non-comparable, and "consistent" is only
independent-source agreement within the recorded tolerance, never broker execution
evidence. Implementation evidence: backend **1158 passed** (12 comparator + 4 integration
tests), frontend **41 files / 280 tests**, i18n **1213/1213/1213**, `tsc`/build clean.
Real runs (2026-09-17, 2 credential-free requests each, evidence in
`artifacts/evidence/p1-wp43/`): a real biquote XAUUSD refresh returned 301 real 1m bars
(05:26-10:26 UTC) and the honest **UNVERIFIABLE/FETCH_FAILED** product check because
yahoo's `XAUUSD=X` spot route answers HTTP 404 and stooq now serves a JavaScript challenge
instead of CSV — so **no reachable independent free source exists for spot gold/FX today**
and a real CONSISTENT/DIVERGENT verdict remains an unchecked item in the archived package.
Remaining WP43 unchecked items: the real independent-source verdict and real pilot-data
visual acceptance.

**P1-WP43 delivery verification (2026-09-17):** commits `4a6d44b` (backend), `a17fc5a`
(frontend), `f6286a5` (docs; WP43 archived Complete with 2 tracked unchecked items). Clean
commit `f6286a5` canonical arm64 local CI: **MERGE READY**, provenance **COMPLETE**, clean
tree; report `dist/p1-wp43-committed-local-ci.json` SHA-256
`acd10378f4fdb6e99bf06caf07180dae71196cd9ee11e9b6e943a52918f21c90`, executable
`b86bbd742144e923bbbb49263ea103e4fa3a9e3356334dde28298700a10d9af7`. arm64 DMG
`dist/Kuantra-Terminal-1.1.3-wp43-arm64.dmg` SHA-256
`3d5b02387df969909fb25568d37651d0b3fd9b753899d59a6cf8244890dfe52e`; exact read-only
mounted-DMG smoke **PASS** (`dist/p1-wp43-exact-dmg-smoke.json`). `/Applications/Kuantra
Terminal.app` was replaced after a graceful quit: installed executable matches the CI build,
`codesign --verify --deep --strict` passes, version 1.1.3, launched and quit cleanly, user
data preserved. GitHub Releases and tags were untouched (no version train approved).
[P1-WP42 read-only chart review](../archive/strategy/work-packages/P1-WP42-chart-trade-review-p1.md)
remains complete and archived (commits `7b6c379` / `71a3640`).
[P1-WP42 read-only chart review](../archive/strategy/work-packages/P1-WP42-chart-trade-review-p1.md)
is complete and archived: the closed-trade chart review, the provider-matched open position
review and the trade-editor time fixes shipped in commits `7b6c379` / `71a3640` (remaining
unchecked items are tracked in the archived package). The still-open owner-host obligations of
[P1-WP29 trusted macOS pilot package](work-packages/P1-WP29-trusted-macos-pilot-package.md)
(N03/N05/H05/pilot access) remain tracked there and are unchanged; no development proceeds
under WP29 without owner approval, and
**A1.2 (including the deferred OKX identity work) and every other integration package
remain unapproved**.
[P1-WP41 journal bulk CSV export and readable PDF reports](../archive/strategy/work-packages/P1-WP41-journal-bulk-export-and-pdf-reports.md)
is complete and archived: the journal export flow, the readable PDF reports and the
single-trade Evidence Pack PDF shipped in `v1.1.3` (real pilot-data review and layout
acceptance remain open obligations).
[P1-WP40 MT5 HTML report preview](../archive/strategy/work-packages/P1-WP40-mt5-html-report-preview.md)
is complete and archived: safe parsing of the defined English MT5 ReportHistory HTML
format with a preview-only UI, separated order/deal identities and no persistent writes.
Owner decision (2026-09-15): pilot users need to bring XM/MetaTrader trades into
Kuantra; only this bounded **preview** package was approved. **Persistence/import,
migration and financial schema extensions are not approved.** Statement import is not
live tracking: the preview reads one report in memory and writes nothing.
**Open obligation (owner/pilot):** real anonymized XM report validation — terminal
(MT4/MT5), build/language, then a preview-vs-source comparison of counts, identity
relations, quantities and timestamps; no "XM supported" claim until then.
[P1-WP39 broker observation projection (A1.1)](../archive/strategy/work-packages/P1-WP39-broker-observation-projection.md)
completed its account-scope closure and is complete and archived.
[P1-WP38 A0 data-accuracy findings](../archive/strategy/work-packages/P1-WP38-a0-data-accuracy-findings.md)
is complete and archived with its evidence (including the closure review). Owner
instruction (2026-09-15): apply **only** A0 — verify the two reported data-accuracy
findings and fix them if real. Both findings were reproduced and fixed; the closure
review additionally verified user-visible unknown-PnL reporting and tightened the
projection lifecycle-event classifier: full backend **983 passed / 2 warnings**,
frontend **39 files / 229 tests**, focused A0 tests **17 passed**, i18n
**1036/1036/1036**. Broker observations are not converted into journal trades; a future
design must use a separate broker view, explicit matching and double-count prevention.
[P1-WP37 multi-select journal filters and one-click unit declaration](work-packages/P1-WP37-journal-filters-and-unit-declaration.md)
is complete with its evidence below.
Owner report (2026-09-15): the journal filters must allow multi-selection, and the open
XAUUSD position still shows "contract size not verified — monetary P/L is not
calculated". The package makes the symbol/status filters multi-select dropdowns and turns
the unverified-unit warning in each position row into a "Birim beyan et" action that
opens the trade editor, where the owner declares the unit for commodity/CFD instruments
that no public provider metadata can verify. [P1-WP36 dashboard terminal redesign](work-packages/P1-WP36-dashboard-terminal-redesign.md)
is complete with its evidence below.
Owner report (2026-09-15): the dashboard is "çok basit ve anlaması zor"; it must be more
effective. Owner decisions: the top of the page shows live cash + open P/L + risk at one
glance, in a professional trading-terminal style. The package adds a dense hero row and
metric rail, compact exposure/margin metrics from the backend, formula tooltips, a
sparkline, a localized title and a rebalanced layout. [P1-WP35 refresh and sync button
truth](work-packages/P1-WP35-refresh-and-sync-truth.md) is complete with its evidence
below.
Owner report (2026-09-15): "check the refresh / refresh-all buttons on every page; some
seem not to work." Every refresh control was traced to its handler; the Settings
"full dual-DB sync" button was a pure `setTimeout` placebo that claimed success without
any request, and the Dashboard refresh never reached the open-position quotes. The
package wires the real sync (`POST /system/sync/full` with honest outcomes) and makes
the dashboard refresh cascade into the quote refresh. [P1-WP34 server-verified
instrument catalog](work-packages/P1-WP34-verified-instrument-catalog.md) remains a
reference package.
Owner report (2026-09-15): the open ETHUSDT position still shows "contract size not
verified — monetary P/L is not calculated" even though the backend can check the
instrument at the exchange. The package makes the server verify free provider spot
metadata itself (Binance/Bybit, cached in the app database) so a directly verified spot
instrument enables monetary math without a manual declaration. [P1-WP33 bounded
market-chart history](work-packages/P1-WP33-market-chart-history.md) is complete with its
evidence below; [P1-WP32 pilot journal trust](work-packages/P1-WP32-pilot-journal-trust.md)
remains a reference package.

Owner instruction (2026-09-14): pilot traders need a readable journal with
user-supplied Turkey-time trade dates, working edit/correction with revision
control, declared leverage with separated price/position/margin returns, automatic
open-trade quote refresh and a simplified New Trade/Edit form. The standard
journal's primary row action becomes Edit; Replay moves to a secondary action for
closed trades. Prior package [P1-WP29 trusted pilot obligations](work-packages/P1-WP29-trusted-macos-pilot-package.md)
remains open for N03/N05/H05/pilot-access owner-host obligations.

**P1-WP32 implementation evidence (this change, uncommitted):** Trade time is now
user-supplied in `Europe/Istanbul` and stored as timezone-aware UTC
(`entry_time_source=USER|SERVER`), future realized times are rejected, and a
historical entry explicitly declares still-open vs closed-earlier; closed-at-entry
requires exit price/time and never enables live tracking. Historical open entries
arm local tracking after recording (`armed_at > entry_time`), so the untracked gap
cannot close a position. Corrections append `TradeCorrected` events with previous
values per field and an atomic `expected_revision` guard (409 on stale editors);
quantity/entry edits reset an existing local TP plan only before any close
evidence and are locked after a partial close, while completed trades accept notes
only and canceled tombstones are immutable. Declared leverage is journal metadata:
price return, position return and margin return stay separate, PnL is never
multiplied by leverage, spot rejects leverage, notional/quantity inputs cannot
conflict, and unknown contract sizes (XAUUSD) never produce a margin/liquidation
claim. Open-trade quotes refresh automatically and on demand through one batched
endpoint keyed to the exact confirmed provider identity, with shared requests,
concurrency 4, exponential backoff, visible LIVE/DELAYED/stale states and a
stale-only "last known" fallback; the LIVE + provider-event + <=60s automatic
close contract is unchanged. Schema revision `006_trade_time_edit_sizing` is
additive; Alembic head, migration classification and the two head assertions were
updated. Backend **903 passed / 2 warnings** (23 new focused tests), frontend
**36 files / 180 tests** (26 new), i18n **944/944/944** EN/TR/DE, TypeScript and
production build clean, docs/release-truth/`git diff --check` PASS. Canonical Mac
arm64 local CI is **MERGE READY** with 13/13 steps and native WKWebView smoke;
report `dist/p1-wp32-local-ci-final2.json` SHA-256
`95a096b47a9eb63ca7bb364720fb88353f1d26fc45d01c4253943ab2659c2dc5`, tracked tree
`e38dc91cc50f836a87c8c72bb4bfc72c43a63fc81dd539602807043725b06d62`, provenance
`DEVELOPER_DIRTY` (uncommitted development evidence). Installed application and
GitHub Releases are untouched; the read-only replay, fee/funding accrual and
exchange-verified close boundaries remain open.

**P1-WP32 independent-review fixes (round 2):** Four reproduced findings are
fixed with red-first tests. (1) A journal stop correction now updates the local
plan and the trade row in one transaction; the legacy TP column mirrors TP1, a
single pending target accepts a TP correction, multi-target/completed plans
reject it (`TARGETS_MANAGED_BY_PLAN`), the edit screen edits the plan itself
with completed-target locks and its own plan `expected_revision`, and a failed
plan write rolls the correction back. Before: plan stop stayed `95` after the
trade stop became `90`, and a `94` quote closed the trade; now `94` produces no
close and `89` closes exactly once. (2) `entry_time` edits persist (old/new
instants normalized separately, equal instants idempotent, `entry_time_source`
set to `USER`, history/rebuild consistent); before, the API returned
`no_change: true`. (3) A failed quote refresh now demotes every displayed price
to an explicit stale last-known value, tracks last attempt and last success
separately, ages the price from its observation time each second, and recovers
to `LIVE` on the next success; the automatic-close freshness contract is
unchanged. (4) Unknown contract sizes (gold/futures/provider-symbol/generic)
produce no notional, margin or money P/L (`null` +
`CONTRACT_SIZE_UNVERIFIED`), local tracking refuses plans for them, legacy plans
cannot close, unverified user-reported closes store `pnl = null` (never a
synthetic zero) and portfolio aggregates exclude/count unknown results; verified
base-unit crypto pairs keep their existing math. Evidence: focused
`test_p1_wp32_review_fixes.py` **11 passed**, full backend **914 passed / 2
warnings**, frontend **37 files / 192 tests**, TypeScript clean, i18n
**956/956/956**. Canonical Mac arm64 local CI on the fixed tree is **MERGE
READY** (13/13) with native WKWebView smoke; report
`dist/p1-wp32-review-local-ci-final.json` SHA-256
`7f5b6d4513ff3df217b9517a231c6da3304d87d6b4779d8ee6fcc421dd39a2eb`, tracked tree
`245b63db3791e5a2f6c1e7107c721b3a4aefb5ee156a3449e3e85759fb88c563`, provenance
`DEVELOPER_DIRTY`. One earlier gate run transiently failed the backend step with
no reproducible failure; three consecutive clean full-suite runs and the final
gate run passed. No commit, release or installed-app change was made.

**P1-WP32 round-3 fixes:** Plan-only corrections (TP2/TP3, allocations, enabled
flag) were previously answered as `no_change` because only the mirrored trade
columns were compared; the whole plan payload is now compared, plan-only edits
save with their own revision and a `tracking_plan` history marker, and a stale
plan revision still conflicts. Symbol suffixes no longer grant verified
base-unit status: monetary math, local tracking and close P/L require a
provider-confirmed instrument identity (Binance/Bybit exact symbol) or an
explicit `qty_unit=BASE` contract (schema revision `007_trade_qty_unit`);
`EURUSD`, `GBPUSD`, `FAKEUSD` and undeclared manual symbols produce no money
figures, while verified crypto pairs keep their math. Round-3 focused tests
**10 passed**; full backend **924 passed / 2 warnings**; frontend **37 files /
198 tests**; i18n **964/964/964**; TypeScript clean. Canonical Mac arm64 local
CI is **MERGE READY** (13/13) with native WKWebView smoke; report
`dist/p1-wp32-round3-local-ci.json` SHA-256
`6a7a1bc79832fc70be12eaf9b423632e021a9c293a33b275dab9cd0e424f45ce`, tracked tree
`5d8f7b13c3ca08b67a6d5ed638597b376f1b67f9d709e42dcca271f00261f3df`, provenance
`DEVELOPER_DIRTY`. No commit, release or installed-app change was made.

**P1-WP32 round-4 fix:** A client-supplied provider label was still treated as
instrument verification (`FAKEUSD + binance_public + FAKEUSD` produced
`PROVIDER_INSTRUMENT`/`READY`). The provider path is closed: monetary math,
local tracking, close P/L and portfolio aggregation now require an explicit
`qty_unit=BASE` user declaration, labeled
`EXPLICIT_QTY_UNIT / USER_DECLARATION`; provider fields remain price provenance
only, and the frontend exposes the declaration checkbox plus the label. Round-4
focused tests **5 passed** (fake symbol + fake provider label, real symbol
without declaration, valid explicit declaration, revocation, plan gate); full
backend **929 passed / 2 warnings**; frontend **37 files / 198 tests**; i18n
**963/963/963**; TypeScript clean. Canonical Mac arm64 local CI is **MERGE
READY** (13/13) with native WKWebView smoke; report
`dist/p1-wp32-round4-local-ci.json` SHA-256
`d4bb14afb05b3d2f9eb292196cd7ba4f905137d01b058450c59a8e38f4ae0e72`, tracked tree
`daa3e351d1b00a6715cea14fd562719035675c7a88aa32193ba085ce2e8e75d9`, provenance
`DEVELOPER_DIRTY`. No commit, release or installed-app change was made.

**P1-WP32 clean-source commit and distribution validation:** Implementation
commit `bfd52b3a724f3de0dc24646a3276b1e1a564f947` contains the complete package;
the tracked tree is clean. Canonical Mac arm64 local CI on that commit is
**MERGE READY** (13/13) with provenance **COMPLETE** and
`source_commit_sha = bfd52b3a…`; backend **929**, frontend **37 files / 198
tests**, i18n **963/963/963**; report
`dist/p1-wp32-clean-local-ci.json` SHA-256
`91bfd4bfb6555e699c23d409cf4b9e784aced452d437f5a617dd32bb6863b6b4`, tracked tree
`7e66cf0e…`. Distribution validation from the same clean source: arm64 DMG
`hdiutil verify` VALID (`04416ce65504338db764a43d562410ccf11d7c10934884774761a414173df47d`),
exact read-only mounted-DMG smoke PASS with native `wkwebview` and COMPLETE
provenance (report `97a1de2d…`), N05 correctly `BLOCKED` ad-hoc (report
`fc905f6b…`), and pilot package `TRUSTED_MACOS_PILOT_ARM64` /
`AD_HOC_TRUSTED_PILOT_ONLY_ARM64` with all `SHA256SUMS` verified
(`SHA256SUMS` `c76dcce8…`, manifest `c818938a…`). The clean commit is local;
pushing and any Release/installed-app change await separate owner approval. No
GitHub Release asset or installed app was modified.

[P1-WP31 local TP tracking](../archive/strategy/work-packages/P1-WP31-local-tp-tracking.md)
is bounded complete and archived. Source `4298acdbfa2e7de0028dcaf7a1c3780b4f69c1d0`
passed canonical Mac CI: **880 backend / 154 frontend / 813-key i18n**, all 13 steps
PASS, COMPLETE provenance. Local exact-DMG synthetic TP lifecycle also passed.
Native GitHub run `34721385803` passed on both architectures: each **879 backend /
1 skipped / 2 warnings**, **154 frontend**, **813-key i18n**, build and exact mounted
DMG/WKWebView/local-tracking smoke. Original reports/manifest/checksums are retained
in `artifacts/evidence/p1-wp31/4298acd/`; remote dependency setup/audit required network.

Current pilot DMG SHA-256: arm64
`03671ca814ba9299fcf47429cb0c585fbccd550e6201e747c5f2c2e5c32c5e93`, Intel
`e43e0026c118bff9ed338e9e8560dc3758c64fa9052de83d1a23977e906240c2`.
The existing private Release was refreshed with exactly those two DMGs; GitHub digests
match. This Mac's installed arm64 executable is
`ee5683af6c5571fb3da6797faac50bf5fd0cf7dc1840c360d46a98dd032b05b6`, verified and launched.
User data was not reset/deleted/migrated; the previous app remains in
`/tmp/kuantra-tp-update.A5TXWE/Kuantra Terminal.app.previous` until OS temporary cleanup.

Local plans, partial/full closes and gross estimates remain separate from external
fills/analytics. Binance/Bybit provider-event quotes must match instrument and be <=60s
old; Yahoo/Stooq/Biquote currently remain display-only for automatic tracking.
No eligible quote means WAITING, not an assumed fill. Historical/imported trades stay off.
N03 clean-profile, N05 signing/notarization, H05 commercial/dependency disposition and
pilot access/outcomes remain separate owner/host obligations, not closed by this package.
Roadmap: [KPR-001](PRODUCTION-READINESS-PLAN.md), current planning source, still Proposed
for new scope/estimates. Selecting one roadmap does not approve its commercial assumptions.

**Owner decision (2026-09-10):** İlk production sürümü macOS-only olacak ve macOS 12
Monterey veya üzeri için ayrı native arm64 ve x86_64 DMG’ler olarak doğrudan Developer ID
imzalı/notarize biçimde dağıtılacaktır. Intel desteği, fiziksel Intel Mac erişimi olmadan
native Intel host/runner build + exact mounted-DMG smoke kanıtıyla kapatılacaktır. Üç
kişilik pilot ekipten native Intel Mac sahibi olan kişi, hazır x86_64 artifact üzerinde
runtime ve N03 install-lifecycle kanıtı sağlayabilir; istenirse aynı Mac kontrollü native
build hostu da olabilir. Pilot host kanıtı build commit/tree/lock/provenance zincirini
yerine geçmez. Windows ve Linux v1 claim’i değildir. Apple Developer üyeliği ve gerçek
signing/notarization erişimi Release Candidate aşamasına kadar ertelenmiştir.

**Pilot host decision (2026-09-10):** Pilot ekip yalnızca indiren kullanıcı olarak
değil, kontrollü teknik doğrulama grubu olarak kullanılabilir. Native Intel Mac, x86_64
DMG’nin gerçek cihaz açılışı, architecture, Gatekeeper gözlemi ve sentetik
import→review→export→close/reopen akışını doğrulayabilir. Temiz profil attestation'ı
varsa N03 kanıtına da bağlanır; normal kullanıcı profili yalnız runtime pilot kanıtıdır.

**Pilot distribution decision (2026-09-10, current evidence 2026-09-13):** Apple Developer
ID üyeliği satın alınmayacak. Üç kişilik kapalı pilot için iki native DMG'li dual paket
hazırlandı: Apple Silicon için `arm64`, Intel için `x86_64`. Paket ve her iki exact
mounted-DMG smoke zinciri GitHub Actions run `34721385803` üzerinde native hostlarda PASS
oldu; package checksum doğrulaması da PASS. Her iki ad-hoc artifact manual Gatekeeper
approval gerektirir ve yalnızca trusted-pilot-only olarak sınıflandırılır. Bu seçim public
download, commercial support, production veya notarized-artifact claim'i açmaz. Pilot
kullanıcılarının repository read erişimi owner tarafından ayrıca verilmelidir. Private
prerelease Release [`pilot-v1.0.0-arm64`](https://github.com/alikula37/kuantra-terminal/releases/tag/pilot-v1.0.0-arm64)
aynı tag korunarak iki DMG ile güncellendi; GitHub asset digest'leri final DMG hash'leriyle
eşleşiyor. JSON/MD evidence dosyaları Release asset'i
yapılmayıp repository/local audit paketinde tutulacaktır. Canonical `v1.0.0` product
tag'i/release'i oluşturulmayacaktır.

**Release cleanup decision (2026-09-11, current refresh 2026-09-12):** Owner isteğiyle
güncel olmayan tüm GitHub Release kayıtları ve sürüm tag'leri kaldırıldı. GitHub Releases
sayfasında yalnızca private `pilot-v1.0.0-arm64` prerelease/tag ve iki exact DMG asset'i
bulunuyor: arm64 ve x86_64. JSON/MD kanıt dosyaları indirme alanında tutulmuyor.
Eski v1.4.0/v1.3.0/v1.2.0 ve institutional sürüm referansları repository içindeki
tarihsel audit/truth belgelerinde kalabilir; bunlar indirme kaynağı, güncel ürün tanımı
veya production kanıtı değildir. Canonical `v1.0.0` product Release yayımlanmayacaktır.

**Journal/quote scope decision (2026-09-11):** Yeni işlem girişi artık dışarıda
gerçekleştirilmiş işlemi kaydeden `EXTERNAL` journal akışını varsayılan kabul eder;
Kuantra bu akışta hiçbir broker emri göndermez. `SIMULATION` yalnızca açık seçimle
kullanılabilir ve otomatik fallback değildir. Sembol alanı herhangi bir varlık için
kullanılabilir; otomatik fiyat yalnızca ücretsiz ve exact sembol kimliğini koruyan
Binance/Bybit public crypto, Yahoo/Stooq public kaynağı veya XAUUSD için exact Biquote
public kaynağından alınır. Kaynak yoksa `UNAVAILABLE` gösterilir ve gerçek fiyat manuel
istenir. Ücretli veri servisi/API key eklenmez; TradingView alert'i fill değil, kullanıcı
onayına kadar `PENDING_REVIEW` immutable observation'dır. Biquote erişiminin ücretsiz
olması, gelecekteki ticari yeniden dağıtım/lisans şartlarının otomatik olarak onaylandığı
anlamına gelmez; bu dış kaynak H05 ticari notices/terms kapısında yeniden doğrulanacaktır.
Yeni işlem ve Piyasa Grafikleri sembol araması aynı katalog kimliğini kullanır: arama
sonucu seçilip ayrıca onaylanmadan sembol etkinleşmez, fiyat/mum isteği başlatılmaz ve
serbest metin Enter ile başka bir ürüne dönüştürülmez. Katalogda doğrulanmayan semboller
sessizce eklenmez; bu sınır kapsam dışı veri sağlayıcısı/yanlış eşleşme riskini önler.

**Version train decision (2026-09-15):** The P1-WP32 journal-trust feature set moves
the pilot artifact train to `v1.1.0`. The release truth matrix
[`truth-matrix.v1.1.0.json`](../release/truth-matrix.v1.1.0.json) is the accepted
matrix for that feature set and `pilot-v1.1.0` is the private prerelease transport carrying
the native arm64 and x86_64 DMGs. The canonical product Release/tag remains unpublished and the
ad-hoc/trusted-pilot-only boundary is unchanged.

**Security patch train (2026-09-15):** the security follow-up (dependency OSV scan, crafted-ZIP
validation, migration manifest ceiling) advances the trusted pilot artifacts to `v1.1.1`.
[`truth-matrix.v1.1.1.json`](../release/truth-matrix.v1.1.1.json) is the current accepted
matrix; the pilot prerelease is `pilot-v1.1.1`, whose tag points at the verified build commit,
and the canonical product Release/tag stays unpublished.

**v1.1.0 pilot prerelease published (2026-09-15, owner-authorized):** GitHub Actions
candidate run `34946454427` (`workflow_dispatch`, `publish=false`, source `122b6be`)
passed both native jobs — arm64 (`macos-latest`) and x86_64 (`macos-15-intel`) — with the
locked backend/frontend suites, native desktop smoke including the synthetic local TP
lifecycle, and exact read-only mounted-DMG smoke; provenance `COMPLETE` on both. The
trusted pilot package artifact also passed its checksums locally (all eight entries). The
private prerelease [`pilot-v1.1.0`](https://github.com/alikula37/kuantra-terminal/releases/tag/pilot-v1.1.0)
was created at `122b6be` with exactly two DMGs and GitHub asset digests matching the CI
reports: DMG SHA-256 arm64
`ce0cc652e6d57d38dc6d6e06aa9d9fde2131f480cfe92c18be1e827c764df803`, x86_64
`09e27a31bbbd929b061d2c21da2d3bca4e4fa7c0050e5eb0770532f67656ef1c`; mounted executables
arm64 `4b3013e44b0ef143e2f24a8b638c21525a84f9d0ddb72a9ad24b740fecc2d808`, x86_64
`45e58975eccaa5119b95e06cc4267dc1c28d9a84ed287629e1e0ea5aa0ccc13e`. Both artifacts are
ad-hoc (`AD_HOC_TRUSTED_PILOT_ONLY`) and not notarized; N05 stays `BLOCKED` by design.
Two earlier candidate runs failed on a version-pinned npm-audit tolerance and on the
native tracking smoke missing the new explicit `qty_unit=BASE` declaration; both were
fixed (`1fd0030`, `122b6be`) before the successful run. The prior `pilot-v1.0.0-arm64`
prerelease remains as historical transport. The installed application on this Mac was not
changed.

**P1-WP32 round-5 pilot feedback (2026-09-15):** The journal now behaves like a personal
note system: canceled trades are editable and can be restored to open or closed, completed
trades can be reopened (the row's exit result is cleared while the ledger keeps the previous
values), and an open trade can be closed from the editor with user-reported exit price/time
(unknown P/L stays unknown for unverified units). Completed-trade evidence protection remains
for edits without a status change. New Trade raw-key overflow was fixed by adding the missing
`margin_source_UNVERIFIED_CONTRACT_SIZE` and `reason_TIME_IN_FUTURE` translations and making
the derived panel responsive with `min-w-0`/`break-words`. The top header telemetry cards,
market badge and age badge were removed; the header keeps only functional controls and no
longer polls the portfolio endpoint. Evidence: focused status-edit tests **9 passed**, full
backend **938 passed / 2 warnings**, frontend **37 files / 199 tests**, i18n
**976/976/976**; local CI `MERGE READY` report
`dist/p1-wp32-ui-round-local-ci.json` SHA-256
`b2b9ab40dad3d9d76b544e22fc290cf855abf45d1be5ef8108b1ca00f4bf6f3a` (`DEVELOPER_DIRTY`).
Uncommitted; installed app and Releases unchanged.

**Owner standing instruction (2026-09-15):** recorded in
[AGENTS.md](../../AGENTS.md); after every successful bounded development the change is
committed and pushed, and the installed application on this Mac is rebuilt from the clean
commit and replaced while preserving user data. GitHub Release refreshes stay a separate
owner decision. Round-5 followed it: source `8719b27`, clean arm64 local CI `MERGE READY`
with `COMPLETE` provenance (report `d633827c…`), arm64 DMG `1ad8123c…` with `hdiutil verify`
VALID and mounted-DMG smoke PASS (`acddbaaf…`), installed executable `eeb16e89…` matching the
CI build, launched with runtime `{"status":"online","version":"1.1.0"}`; the journal database
was preserved.

**P1-WP32 round-6 pilot report fix (2026-09-15):** A completed trade that was
closed without an explicit base-unit declaration stored an unknown P/L, portfolio
aggregates exclude unknown results, and the editor blocked the declaration afterwards
(422), so the Dashboard appeared not to change after an edit/close. Completed trades now
accept `qty_unit`, `exit_price` and `exit_time` corrections while entry/quantity stay
locked; each correction recomputes the user-reported gross P/L and R for a declared base
unit, keeps previous values in the correction provenance, and revoking the unit returns
the result to unknown. The Dashboard shows an explicit unknown-result count. Evidence:
focused status-edit tests **12 passed**, full backend **941 passed / 2 warnings**,
frontend **37 files / 200 tests**, i18n **979/979/979**, TypeScript clean.

**P1-WP33 market-chart history (2026-09-15):** Market Charts were limited to one
provider page and the cache-freshness gate never expired, so the 8-second refresh could
freeze on the first window. Crypto history now walks Binance klines backwards in bounded
pages (max 10 x 1000, stops on short page/reached start, dedup by timestamp) for an
explicit `start_time`; macro/equity history uses Yahoo `period1/period2` with the
documented intraday window (1m=7d, 5m-30m=60d, 1h=730d) and daily+ keeps the requested
lookback; a full cache is reused only while at most two bars old. The chart requests 1000
bars, has a "load older data" control that prepends one bounded chunk while keeping the
visible window, disables itself at the provider's history start, and the live refresh
merges instead of wiping loaded history. Evidence: `test_market_candle_history.py`
**6 passed**, full backend **947 passed / 2 warnings**, frontend **38 files / 204 tests**,
i18n **984/984/984**, TypeScript clean.

**P1-WP33 clean build and install (2026-09-15):** Source `7e785a1` passed canonical
arm64 local CI with `COMPLETE` provenance and a clean tree (backend **947**, frontend
**38/204**, i18n **984/984/984**; report `46ecf223…`). The arm64 DMG
`55f93dc1…` passed `hdiutil verify` and the exact mounted-DMG smoke; `/Applications`
was replaced (installed executable `38a59ad1…`, runtime
`{"status":"online","version":"1.1.0"}`, user data preserved).

**P1-WP32 round-7 dashboard truth (2026-09-15):** Owner review found misleading
dashboard values. Average R is `null` when no closed trade has an R observation (KPI shows
"—" + "no R data", not `+0.00R`); open risk carries an explicit
`open_risk_basis = COMPLETE|PARTIAL|NOT_AVAILABLE` and shows "risk not calculated" for
unverified units instead of `0.0R ($0.00)`; drawdown renders `0.00%` without a negative
zero; infinite profit factor is labeled "No losses yet"; the equity curve starts with an
explicit INITIAL baseline point; asset breakdown marks partial volume; and the dashboard
validator accepts a null average R. Evidence: `test_portfolio_service.py` **12 passed**,
`PortfolioKpiGrid.p1wp33` DOM tests **3 passed**, full backend **948 passed / 2 warnings**,
frontend **39 files / 207 tests**, i18n **989/989/989**.

**Round-7 clean install (2026-09-15):** Source `878f699` passed canonical arm64 local
CI with `COMPLETE` provenance and a clean tree (backend **948**, frontend **39/207**, i18n
**989/989/989**; report `0586dfb4…`); arm64 DMG `d73843fc…` passed `hdiutil verify` and
the exact mounted-DMG smoke; `/Applications` was replaced (installed executable
`23fcf253…`, runtime `{"status":"online","version":"1.1.0"}`, user data preserved).

**Version reset decision (2026-09-10):** Kullanılamaz durumdaki v1.4.0 yayın kaydı geri
çekilmişti; 2026-09-11 cleanup kararıyla GitHub release/tag/assets kaldırıldı. Eski truth
matrix ve audit belgeleri repository içinde yalnızca tarihsel kanıt olarak tutulur. Güncel
canonical release train `v1.0.0`'dır; canonical product Release yayımlanmamıştır. Güncel
private pilot transport ise aynı `pilot-v1.0.0-arm64` prerelease üzerinde iki native DMG
taşır; bu transport production release değildir.
Kapalı pilot taşıma kanalı olan `pilot-v1.0.0-arm64` ayrı bir private prerelease'tir ve
güncel dual asset seti `4298acd` source commit'ine bağlıdır. Aşağıdaki v1.4.0 ad-hoc
hash'leri yalnızca pre-reset historical evidence'tir; güncel release kanıtı olarak
kullanılamaz.
Eski kök `UAT_AUDIT_REPORT.json` raporu geri çekilmiş tarihsel kayıt olarak arşivlendi;
güncel UAT çıktısı yalnızca ignore edilen `artifacts/evidence/uat/` altında tutulur.
Son güvenli çalıştırmada 2 temel senaryo `PASSED`, 3 deneysel senaryo `DISABLED` oldu;
komutun yüzde-100 dışı sonucu bilinçli bir release engelidir ve production PASS değildir.

**P1-WP34 server-verified instrument catalog (2026-09-15):** Money math previously
required an explicit `qty_unit=BASE` declaration; a client `price_source` label was never
proof (round-4 decision) and the server had no verification path of its own. The new
`InstrumentCatalog` queries Binance spot exchange info (Bybit spot fallback) and stores
the result in a `verified_instruments` table in the same SQLite database as trades:
24-hour cache reuse, 7-day honesty horizon, silent UNVERIFIED on provider errors or
unknown symbols. `EXPLICIT_QTY_UNIT` and `PROVIDER_CATALOG` enable money math, `NONE`
stays unknown; trade creation, open-position summaries, portfolio open risk/volume,
local-tracking plans and trade-edit close recomputation all consult the catalog, and
`GET /api/v1/market-data/instrument?symbol=` exposes one symbol's verification. New
Trade/Edit verify the confirmed symbol once and hide the manual checkbox when the server
confirms it; the open-positions table asks once per unverified symbol and then shows
monetary K/Z. Evidence: `test_instrument_catalog.py` **9 passed**, full backend
**957 passed / 2 warnings**, frontend **39 files / 209 tests**, i18n **990/990/990**,
TypeScript clean.

**P1-WP34 clean install (2026-09-15):** Source `2d0106e` passed canonical arm64 local
CI with `COMPLETE` provenance and a clean tree (backend **957**, frontend **39/209**, i18n
**990/990/990**; report `8d380b2c…`, executable `9d492a41…`); arm64 DMG `204887dc…`
passed `hdiutil verify` and the exact mounted-DMG smoke; `/Applications` was replaced
(installed executable matches the CI build; runtime
`{"status":"online","gateway":true,"version":"1.1.0"}`, user data preserved). Live check:
the installed app verified the owner's open ETHUSDT position at startup
(`verified_instruments` row `ETHUSDT | binance_spot | ETH | USDT`) and an isolated copy
of the owner database reports `PROVIDER_CATALOG` / money **READY** for
`TRD-1789460532666` without rewriting the trade.

**P1-WP35 refresh and sync button truth (2026-09-15):** All refresh controls were
audited; every one except the Settings dual-DB sync was already wired to a real
request. That button only started a 600ms timer and printed "sync completed
successfully" — no endpoint existed. `SyncPipeline.full_sync_report()` now reports
DuckDB availability, the evidence coverage gate and the synchronized count, exposed
via `POST /api/v1/system/sync/full`; the Settings button disables while running and
shows synced count / DuckDB-unavailable / coverage-blocked / failed honestly. The
Dashboard refresh now also bumps a nonce consumed by the open-positions table, so
prices, ages and unrealized K/Z refresh together with the KPI cards instead of
waiting for the 20s poll. Evidence: `test_system_sync.py` **3 passed**, full backend
**960 passed / 2 warnings**, frontend **39 files / 214 tests**, i18n **993/993/993**,
TypeScript clean.

**P1-WP35 round 2 — live (mark-to-market) equity (2026-09-15):** Owner decision after
"açık işlemdeki zarar/kâr toplam kasayı etkilemiyor; sence bu doğru mu?": the total-cash
card now moves with open positions. `total_equity` stays the realized ledger;
`live_equity` adds the mark-to-market result of open positions using only quotes the
server already fetched (`QuoteRefreshService.cached_quote`, no network on the summary
path), with `live_equity_basis` `COMPLETE|PARTIAL|NOT_AVAILABLE`, `unrealized_pnl_usd/pct`,
`live_positions_unpriced`, `live_quotes_stale` and the oldest quote age; a position
without a fetched quote is never valued at its entry price. The dashboard card shows
"TOPLAM KASA (CANLI)" with the realized/open breakdown, price age or stale notice,
partial-coverage count, and an explicit fallback note when nothing can be priced.
Evidence: `test_portfolio_service.py` **15 passed** (three new mark-to-market tests),
full backend **963 passed / 2 warnings**, frontend **39 files / 217 tests**, i18n
**999/999/999**, TypeScript clean. Live check on a copy of the owner database: before a
quote refresh `live_equity: null`; after it `live_equity: -3448.50` (COMPLETE,
unrealized -8520.00).

**P1-WP35 round-2 clean install (2026-09-15):** Source `25dcf88` passed canonical arm64
local CI with `COMPLETE` provenance and a clean tree (backend **963**, frontend
**39/217**, i18n **999/999/999**; report `ef174524…`, executable `09e5195f…`); arm64 DMG
`d481e4b8…` passed `hdiutil verify` and the exact mounted-DMG smoke; `/Applications` was
replaced after a graceful quit (installed executable matches the CI build, PID `54668`,
runtime `{"status":"online","gateway":true,"version":"1.1.0"}`, user data preserved).

**P1-WP35 clean install (2026-09-15):** Source `ef89ae6` passed canonical arm64 local
CI with `COMPLETE` provenance and a clean tree (backend **960**, frontend **39/214**, i18n
**993/993/993**; report `7903e040…`, executable `a51f290f…`); arm64 DMG `66ae08f1…`
passed `hdiutil verify` and the exact mounted-DMG smoke; `/Applications` was replaced
(installed executable matches the CI build; runtime
`{"status":"online","gateway":true,"version":"1.1.0"}`, user data preserved). Live check
on a copy of the owner database: `POST /system/sync/full` →
`{available: true, coverage_ready: true, synced: 5}` and the quote refresh returned
`LIVE 2481.13` for the open ETHUSDT trade.

**P1-WP36 dashboard terminal redesign (2026-09-15):** The dashboard now opens with a
five-block hero row — live equity (realized/open breakdown, price freshness, equity
sparkline), open P&L, open risk, exposure (notional + margin from recorded leverage,
coverage notes) and today's activity — followed by a compact rail (win rate, profit
factor with gross profit/loss, average R, max drawdown, active positions with
verification state, unknown results) and a tighter layout with the 90-day heatmap
moved beside the asset breakdown. The backend adds verified-only exposure metrics
(`open_notional_usd`, `open_margin_usd`, `open_margin_positions`,
`open_exposure_basis`, `open_exposure_unpriced`); every cell reuses the established
truth bases (no fabricated values). The hardcoded mixed-language dashboard title is
now EN/TR/DE. Evidence: `test_portfolio_service.py` **16 passed**, full backend
**964 passed / 2 warnings**, frontend **39 files / 220 tests**, i18n **1022/1022/1022**,
TypeScript clean.

**P1-WP36 clean install (2026-09-15):** Source `4b874ad` passed canonical arm64 local
CI with `COMPLETE` provenance and a clean tree (backend **964**, frontend **39/220**, i18n
**1022/1022/1022**; report `59dd43d9…`, executable `903c713b…`); arm64 DMG `f92f2285…`
passed `hdiutil verify` and the exact mounted-DMG smoke; `/Applications` was replaced
after a graceful quit (installed executable matches the CI build, PID `57042`, runtime
`{"status":"online","gateway":true,"version":"1.1.0"}`, user data preserved).

**P1-WP36 round 2 — research-driven design fix (2026-09-15):** The owner rejected the
first pass ("çok kötü") and asked for design research. Root causes: a hardcoded dark
hero color the light-theme shim did not remap while it did remap the text color; 9–10px
rail labels inflated to the 14px readability floor, breaking the six-cell layout; and a
flex-column scroller whose `min-h` let the chart row shrink so the positions card painted
over the heatmap. Round 2 applies published dashboard practice (inverted pyramid, fixed
card anatomy, one metric per meaning, semantic tokens instead of hardcoded colors) and
migrates Tailwind to theme CSS variables (`elevated`, `ink`, `muted`, `warn` +
alpha-capable accent/gain/loss/border), rewrites the KPI hero/strip on new `.k-kpi`
primitives, theme-resolves the chart colors, fixes the scroller flow and formats negative
money correctly. Both themes were verified with headless-Chrome screenshots and a
DOM-measured overlap check. Frontend **39/220**, i18n **1022/1022/1022**, TypeScript
clean.

**P1-WP36 round-2 clean install (2026-09-15):** Source `ffa3a77` passed canonical arm64
local CI with `COMPLETE` provenance and a clean tree (backend **964**, frontend
**39/220**, i18n **1022/1022/1022**; report `f13e3c4a…`, executable `fa00cd73…`); arm64
DMG `9c779575…` passed `hdiutil verify` and the exact mounted-DMG smoke; `/Applications`
was replaced after a graceful quit (installed executable matches the CI build, PID
`61170`, runtime `{"status":"online","gateway":true,"version":"1.1.0"}`, user data
preserved).

**P1-WP36 round 3 — Sharpe on the dashboard (2026-09-15):** Owner asked where the Sharpe
ratio is and to add it. It lived only in the plugin-gated Analytics page (invisible in
Lite mode) and used the engine's default capital. `portfolio/summary` now reports
`sharpe_ratio`/`sharpe_basis`/`sharpe_trades` (annualized mean/std × √252 of realized
returns scaled by the configured balance; fewer than two varying results stay
`NOT_AVAILABLE`, never `0.00`), the Analytics endpoint uses the same configured capital
for one-number consistency, and the KPI strip gained a "SHARPE" cell with the formula
tooltip and the closed-trade count. Evidence: `test_portfolio_service.py` **18 passed**,
full backend **966 passed / 2 warnings**, frontend **39/221**, i18n **1026/1026/1026**,
TypeScript clean.

**P1-WP36 round-3 clean install (2026-09-15):** Source `43a3c06` passed canonical arm64
local CI with `COMPLETE` provenance and a clean tree (backend **966**, frontend
**39/221**, i18n **1026/1026/1026**; report `a08edaa4…`, executable `01dc9eef…`); arm64
DMG `c1d47fb7…` passed `hdiutil verify` and the exact mounted-DMG smoke; `/Applications`
was replaced after a graceful quit (installed executable matches the CI build, PID
`63300`, runtime `{"status":"online","gateway":true,"version":"1.1.0"}`, user data
preserved).

**P1-WP36 round 4 — per-metric hide (2026-09-15):** Owner asked for a hover ✕ on every
KPI box with layout re-alignment when boxes are closed or reopened. Each hero card and
rail cell now carries an ✕ that appears on hover/focus and hides that metric; the
choice is stored in `localStorage` (`kuantra_dashboard_metrics_hidden`) with an
in-memory fallback. The hero grid recomputes its column count from the remaining cards
(live equity keeps a double slot) and the rail keeps auto-fit cells, so any combination
stays aligned without gaps. A "Metrikler · N gizli" control appears only while
something is hidden and opens a per-metric checkbox panel plus "show all", so closing
is reversible. Evidence: frontend **39/223**, i18n **1030/1030/1030**, full backend
**966**, TypeScript clean, screenshot-verified with three metrics hidden.

**P1-WP36 round-4 clean install (2026-09-15):** Source `3ad50ed` passed canonical arm64
local CI with `COMPLETE` provenance and a clean tree (backend **966**, frontend
**39/223**, i18n **1030/1030/1030**; report `c495e26d…`, executable `b1419395…`); arm64
DMG `b3c07ce3…` passed `hdiutil verify` and the exact mounted-DMG smoke; `/Applications`
was replaced after a graceful quit (installed executable matches the CI build, PID
`65266`, runtime `{"status":"online","gateway":true,"version":"1.1.0"}`, user data
preserved).

**P1-WP36 round 5 — remove the "unknown results" cell (2026-09-15):** The owner asked
what the cell meant and then asked to remove it entirely. The strip cell and its two
unused locale keys are gone; the truth guard remains — the summary still reports
`unknown_pnl_trades`, the amber warning line still appears while the count is above zero,
and unknown-result trades stay excluded from monetary aggregates rather than counted as
zero. The rail now has six cells and keeps the hide/reflow behaviour. Evidence:
frontend **39/223**, i18n **1028/1028/1028**, TypeScript clean.

**P1-WP36 round-5 clean install (2026-09-15):** Source `1906625` passed canonical arm64
local CI with `COMPLETE` provenance and a clean tree (backend **966**, frontend
**39/223**, i18n **1028/1028/1028**; report `84dfffb2…`, executable `5902efbd…`); arm64
DMG `1eae1302…` passed `hdiutil verify` and the exact mounted-DMG smoke; `/Applications`
was replaced after a graceful quit (installed executable matches the CI build, PID
`67360`, runtime `{"status":"online","gateway":true,"version":"1.1.0"}`, user data
preserved).

**P1-WP37 multi-select filters and unit declaration (2026-09-15):** Journal symbol and
status filters are now multi-select checkbox dropdowns (OR within a filter, AND across
filters, selected-count trigger, clear action, outside-click close). The open-positions
row turns the "contract size not verified" state into an action: "Birim beyan et" opens
the editor with a tooltip explaining that declaring `qty_unit=BASE` enables monetary P/L;
verified rows keep no button. This is the honest resolution path for commodity/CFD
instruments such as XAUUSD, whose contract size no free provider metadata can verify
(P1-WP34 covers only spot crypto). Evidence: frontend **39 files / 226 tests**, i18n
**1032/1032/1032**, TypeScript clean.

**P1-WP37 clean install (2026-09-15):** Source `03c447e` passed canonical arm64 local CI
with `COMPLETE` provenance and a clean tree (backend **966**, frontend **39/226**, i18n
**1032/1032/1032**; report `f6319e1d…`, executable `fb571fb5…`); arm64 DMG `22e51a2c…`
passed `hdiutil verify` and the exact mounted-DMG smoke; `/Applications` was replaced
after a graceful quit (installed executable matches the CI build, PID `69084`, runtime
`{"status":"online","gateway":true,"version":"1.1.0"}`, user data preserved).

**P1-WP38 A0 data-accuracy findings — complete and archived (2026-09-15, uncommitted):**
Broker and account lifecycle observations (`FillRecorded` with a `broker_lifecycle`
payload, `TradeCorrected` with an `account_event` payload) previously aborted
`EvidenceTradeProjectionRepository.rebuild()` with `event … has no trade snapshot`, which
broke the `kuantra-cli evidence-ledger projection-rebuild` maintenance path, the H07
performance worker and the macOS migration restore rebuild for any database containing
broker observations. Rebuild and the atomic upsert now project trade snapshots, count the
validated non-trade payload contracts as `non_trade_lifecycle_events`, leave the source
events, provenance and chain untouched, and still fail closed on unknown projectable
payloads. The DuckDB OLAP path no longer converts an unknown PnL to 0.0: NULL is preserved
(`is_winner` NULL), `known_pnl_trades`/`unknown_pnl_trades` are reported, the win rate uses
known results only, the symbol breakdown carries known/unknown counts, and the equity
curve skips unknown results, matching the portfolio summary contract.

**Closure review (2026-09-15):** (1) User-visible unknown PnL: AnalyticsView now consumes
the known/unknown counts — a mixed book shows an unknown-result note and per-symbol
unknown counts, an all-unknown book gets its own labelled state instead of the generic
"awaiting trades" empty state, and a fully known book shows no note; the dashboard already
showed `dashboard.unknown_pnl_note` while unknown results exist. `/analytics/overview` and
`/analytics/equity` remain API-only (no frontend consumer) and are reported as such.
(2) Classifier strictness: lifecycle payloads are validated against the producer
contracts — `broker_lifecycle` only on `FillRecorded` with record type, order/fill
identity, symbol, occurrence and matching venue; `account_event` only on `TradeCorrected`
with kind/status/storage/identity and matching account/venue; both keys at once is a
conflict; malformed, mismatched or unknown payloads fail closed and never partially
change the projection. Evidence: focused A0 tests **17 passed** with red-first proof
(`EvidenceProjectionError: … has no trade snapshot`; `assert 0.0 is None`; two frontend
DOM failures before the visibility fix), frontend **39 files / 229 tests**, i18n
**1036/1036/1036**, related backend **160 passed**, full backend **983 passed / 2
warnings**, TypeScript clean and production build PASS. Canonical arm64 local CI
(`KDG-002@1.1.0`) on the closure-review tree is **MERGE READY** with 13/13 steps and
provenance `DEVELOPER_DIRTY` (uncommitted by instruction; report
`dist/p1-wp38-closure-local-ci.json` SHA-256
`ebd133133d33ade353a7811a9c8019f2aa406549452d61ad6091df76f124d1f8`, executable
`9f9caf29…`). Plugin-gated engines that still
coalesce unknown PnL in their own paths (pivot/psychology/execution-drift) are recorded as
an open follow-up. No commit, Release or installed-app change was made; A1 and every
integration package remain unapproved. **Broker observations are not converted into
journal trades; a future design must use a separate broker view, explicit matching and
double-count prevention.**

**P1-WP39 broker observation projection (A1.1) — complete and archived (2026-09-15,
uncommitted):** Broker lifecycle observations now have a rebuildable observation log
(`broker_observation_log` and `broker_projection_state`, additive revision
`008_broker_observation_projection`): order and fill identities are separate (a fill
identity is the source fill/deal id, never the order id, ledger event id or a content
hash), and valid observations without a resolvable source scope stay unresolved and are
not projected. **Account-scope closure (2026-09-15):** the caller-declared local bucket
(`account_id`) is not a broker-verified account identity — credential refs are per
`exchange_id`, `account_id` is free text and file hashes are not identities — so every
observation is stored individually with `account_scope_state = UNVERIFIED`, no economic
merge/dedup/content conflict runs while the scope is unverified, duplicate claims on the
same declared scope are counted
(`unverified_duplicate_claim_count`/`unverified_duplicate_identity_count`) and preserved
with lineage, and source-level idempotency (same document re-sent) stays a separate
ledger property. The two mandated scenarios (same bucket/fill/content and same
bucket/fill/different content across two documents) now stay two unverified observations
instead of one merged record plus repeat or an `UNRESOLVED_CONFLICT`. Environment/context
remain changeable metadata and are never inferred. The earlier metadata/identity and
`007 → 008` migration closures stand (metadata is not identity; the legacy backfill skips
trades with canonical evidence via `already_evidenced`). Rebuild materializes one
evidence snapshot with a verified processed-through boundary and an evidence digest,
never mixes concurrently appended events, excludes operational fields from
`snapshot_sha256`, and keeps the previous snapshot on failure while recording the failure
in a separate transaction. Internal read service only: no user API, no journal
conversion, no portfolio PnL. The additive migration was exercised only in isolated test
databases and preserves existing rows; the rows table was renamed to
`broker_observation_log` so unreleased first-draft tables in dev profiles cannot collide
(no table or row was dropped; the owner database was read-only inspected and not
modified, and was not re-accessed by this task). Evidence: `test_a1_wp39_broker_observations.py` **20 passed**, related
regressions **106 + 121 passed**, full backend **1003 passed / 2 warnings**; frontend
unchanged. Canonical arm64 local CI (`KDG-002@1.1.0`) on the account-scope closure tree is
**MERGE READY** with 13/13 steps and provenance `DEVELOPER_DIRTY` (uncommitted by
instruction; report `dist/p1-wp39-account-scope-local-ci.json` SHA-256
`8ab45595e7918a34e8f14c8165d805463ceea81216db273aa9a9a21d87819e5d`, executable
`485b9604…`). No commit, Release or installed-app change; A1.2 and every other
integration package remain unapproved.

**P1-WP40 MT5 HTML report preview — complete and archived (2026-09-15,
uncommitted):** The CSV import modal
gained an **MT5 HTML preview** tab: the user selects an English MT5 "ReportHistory" HTML
export and sees a safe, in-memory preview — recognized format + parser version,
order/deal counts, rows read/with problems, source date range, masked source-declared
account (never the owner name), deposit currency, time-basis warning, bounded order and
deal tables with separate `SOURCE_ORDER_ID`/`SOURCE_DEAL_ID` kinds, row errors with
reasons and unprocessed sections. The footer states "Bu ekran yalnız önizlemedir;
işlemler kaydedilmez." and has no import/save action. The parser fails closed for
wrong platform/template, unsupported language, missing sections/columns, ambiguous
time/number formats and limit overruns; it never converts timezones, lots or money,
never turns missing values into zero and never executes or fetches HTML resources.
**Nothing is persisted** (no ledger/projection/journal/portfolio writes; no raw file
retention; logs carry no file content or personal data), and this is a
synthetic-fixture-validated contract, not XM compatibility evidence: until a real
anonymized XM report passes, no "XM supported" claim is made. Evidence: backend
`test_wp40_mt5_statement_preview.py` **23 passed**, frontend
`Mt5StatementPreview.dom.test.tsx` **7 passed** plus the unchanged `CsvImportModal`
tests **7 passed**, related regressions **112 passed**, full backend **1026 passed / 2
warnings**, frontend **40 files / 236 tests**, TypeScript/i18n/production build clean.
Canonical arm64 local CI (`KDG-002@1.1.0`) was **MERGE READY** with 13/13 steps
on the committed tree (`2c961fe`, pushed; clean-commit provenance `COMPLETE`).
Persistence/import, migration and financial schema extension remain unapproved. **Open
owner/pilot obligation:** the
real anonymized XM report validation (terminal MT4/MT5, build/language, preview-vs-source
comparison of counts, identity relations, quantities and timestamps) is tracked here and
separate from this completed preview package.

**P1-WP41 journal bulk CSV export and readable PDF reports — complete and archived
(2026-09-16; owner-approved commit/push, shipped as `v1.1.3`):** the journal toolbar now has an **Export**
flow (scope **filtered results** = every record matching the current filters, explicitly
not the loaded page, or **all records**; date range with **entry/close basis** and a month
preset; **CSV** for spreadsheets or a **PDF** report) and the single-trade Evidence Pack
offers a direct **PDF** artifact next to JSON/HTML/CSV. One snapshot object feeds both CSV
and PDF (same records, totals and snapshot SHA-256); dates are Europe/Istanbul with the
period and basis stated in the artifact; OPEN/CLOSED/CANCELED are separated and CANCELED
never joins performance; unknown PnL is counted, never zero-filled; money totals are only
produced inside one server-verified quote asset (unverified records counted and excluded;
no conversion); local TP/SL estimates (`LOCAL_ESTIMATE`, gross) are reported separately as
"estimated gross result". Limits fail closed (`MAX_EXPORT_TRADES = 2000`,
`MAX_EXPORT_BYTES = 8 MiB` below the desktop bridge cap) with honest UI states for cancel,
limit and failure. **Evidence:** backend **1108 passed** (33 new journal-export tests
including HTTP endpoints and Evidence Pack PDF, with JSON/HTML/CSV regressions intact);
frontend **41 files / 253 tests** (new export modal + journal entry + evidence PDF/limit
tests); i18n 1110 keys parity, `tsc` and production build clean; generated PDFs rendered to
PNG (Quartz) and visually inspected (numbered pages, repeating table headers, wrapped long
notes, correct Turkish/German glyphs, no empty trailing page — two real layout defects were
found and fixed this way). Canonical arm64 local CI is **MERGE READY** 13/13 with provenance
`DEVELOPER_DIRTY` (report `dist/p1-wp41-local-ci.json` SHA-256
`1439ff09509409d9bf35b7faf471303e912634df3189f0dbe04944586714ec03`, executable
`86ae3a55…`, artifact `e21095b7…`); the frozen packaged smoke now includes a
`journal_export` check that proved both artifacts render offline in the app bundle
(`PIL` exclusion removed, `app/assets/fonts/*.ttf` collected). New dependencies:
`reportlab 5.0.1` (BSD-3-Clause) and its `pillow 12.3.0` (MIT-CMU) at runtime, `pypdf
6.19.0` (BSD-3-Clause) test-only; a targeted OSV query returned no advisories and the lock
was regenerated. Real pilot-data review and layout acceptance remain open obligations.

**P1-WP42 read-only single-trade chart review — implemented and verified (2026-09-16,
working tree; no commit/push):** the journal row now has **"Grafikte incele"** (hidden for
canceled trades) which opens the existing replay surface with a labelled plan reference:
entry solid, SL/targets dashed and clearly marked as the **current plan reference** ("geçmişte
bu seviyelerin geçerli olduğu doğrulanmadı"), levels from the local tracking plan when its
entry matches the trade (else the recorded trade row, missing levels omitted, no invented
weights), price/side/target-weight labels, and the recorded close marker with its provenance
(user report / imported file — explicitly **not** broker-verified / simulation / unknown)
disclosed only once the cursor reaches the exit bar. Open trades and missing candle history
show localized honest states (gold without recorded candles: "Bu işlemi kapsayan kayıtlı 1m
mum geçmişi yok; yerine başka veri konulmadı"), provider strip shows symbol/venue/feed/
timeframe/gaps plus the "not broker execution evidence" line, and the review path performs
**no writes** (regression test compares trades and ledger events before/after). The visual
check with synthetic data (isolated data dir, Chrome) found and fixed one real backend bug
(adapter origin lookup always returned UNKNOWN), the unlocalized `NO_CANDLE_HISTORY` state
with raw English leakage, and a light-theme contrast failure; screenshots are in
`artifacts/evidence/p1-wp42/`. Evidence: backend `test_replay_plan_reference.py` (14 tests,
full backend **1122 passed**), frontend `TradeReplayCanvas.dom.test.tsx` (16 tests) plus the
JournalView action test (full frontend **41 files / 264 tests**), i18n 100% parity and
production build clean. **Completion boundary (do not overstate):** completed = read-only
entry/SL/TP view for **closed** trades with suitable recorded 1m candle history; **not
completed** = open position chart review (tracked as OP-01 with an approved-ready plan in
WP42), real gold/FX candle coverage in the evidence store (free gold candles currently live
only in the SQLite UI cache; GC=F must not substitute XAUUSD spot), historical plan
revisions (P2), TP4/break-even stop (P4) and multi-trade/scenario work. A trader wanting to
inspect an open position is not fully served yet and that obligation stays visible.
**Close-source label hardening (2026-09-16):** tracing the producer showed no API payload can
write `close_source` (only the server writes `USER_REPORTED`) and no broker-verification
infrastructure exists, so the previous string-based "broker-verified" promotion was removed:
unrecognised explicit values now render as **source declaration (not verified)** with the raw
value kept visible and `broker_verified` always false; negative tests pin that forged
`BROKER_VERIFIED`/`BROKER_CONFIRMED` values cannot open a verified label. Full backend
**1125 passed** (17 label/review tests), frontend **41 files / 265 tests**, i18n/build clean.

**OP-01 open position review delivered in the working tree (2026-09-17, not committed):**
an open trade is now shown read-only on its **exact instrument's existing SQLite cache
candles** without exit data: labelled current-plan levels and weights, manual **Refresh**
(updates only the market cache; keeps the chart on failure with a retry error), step/seek,
and honest loading/empty/partial/stale/error states (delay is an indicator only; gaps say
"this range cannot be assessed"; no touch analysis, no PnL/MAE/MFE). The closed replay
contract is untouched, no new table/migration was added, and the open path performs no
journal/plan/ledger writes. The visual check with synthetic cache data found and fixed two
real defects (cache `timestamp` vs chart `time` blank-screen crash; unlocalized
`NO_CACHED_CANDLES`) and captured the delayed/partial gold panel, the GOLD identity refusal
(no XAUUSD substitution) and the refresh failure state in
`artifacts/evidence/p1-wp42/op01/`. Evidence: backend **1139 passed** (14 new open-review
tests), frontend **41 files / 270 tests**, i18n/build clean. **Provider-match hardening (2026-09-17):** cache rows of unknown provenance are no longer
presented as the trade's chart. A matched chart now requires a manual fetch from the trade's
**declared free public provider + exact provider symbol** (single-provider fetch, no
fallback; `GOLD`→`GC=F`-style product substitutions are rejected), the fetched snapshot is
what is displayed, and the market cache may be updated but is never read back as proof.
Sessions without a match ask for the refresh (`PROVIDER_MATCH_REQUIRED`) or explain the
missing declaration (`PROVIDER_NOT_DECLARED`). A limited credential-free Biquote XAUUSD 1m
check succeeded (61 real candles, 2026-09-17 08:19–09:19 UTC, last close 4312.764) and is
recorded in `artifacts/evidence/p1-wp42/provider-match/` together with the real matched-chart
screenshot — provider identity is established per session, but the **instrument product
remains source-declared** (spot XAUUSD has no verified catalog entry and futures are never
equated); this stays the open blocker, and no broker-price-equality claim is made.
**Edit-flow fixes (same change):** a notes-only save no longer rewrites the stored entry
seconds (minute-precision dirty check), a cleared/unparsable entry time now shows a
validation error instead of being skipped silently, and the entry time is editable after a
partial close while price/quantity stay locked. Canceled records keep their pinned
note-style editing contract (an initial lock was reverted after the WP32 tests showed it was
wrong). Evidence: backend **1142 passed**, frontend **41 files / 277 tests**, i18n/build
clean. A durable import marker on journal trades would still remove the ledger-origin
inference, and P2–P4/scenario work remains unapproved.

**v1.1.3 artifacts built, released and installed (2026-09-16, owner-approved):** commits
`142dc79` (feature) and `3e64572` (train) on `main`; build commit
`3e64572343d1117953ea2592448d13826c23ec69` (clean tree). Canonical arm64 local CI is
**MERGE READY** 13/13 with provenance `COMPLETE` (report
`dist/p1-wp41-committed-local-ci.json` SHA-256
`2c690143fa70de7152d8f2a10fe64cfaf4f189fcd469e2bedf950eff29da30d3`, executable
`1e920d0b…`, artifact `0674dcd0…`). Release run `35150481616` built both native DMGs from
the same commit (arm64 executable `d1649078…`, x86_64 `24d66761…`) with native and exact
mounted-DMG smoke PASS; the pilot-package `SHA256SUMS` verified locally; a local native
arm64 exact-DMG smoke passed (`dist/v113-arm64-exact-dmg-smoke.json` SHA-256
`2efe647369f85966f16c2852371e50c8896171f448a2e001848606ea017699eb`). The
`pilot-v1.1.3` prerelease (tag on the build commit above) carries exactly two assets —
`Kuantra-Terminal-1.1.3-arm64.dmg` SHA-256
`76a1345945b9dc1a6cba207000827193b69720dd8931ed0a3997e60c75840869` and
`Kuantra-Terminal-1.1.3-x86_64.dmg` SHA-256
`3ac3bd6d67530b83e4d07b5a7179266e42d2d2edc23866f4146711fcbc1eb7e4` — both downloaded back
after upload and re-hashed; `pilot-v1.1.2` was superseded in place (title/body redirect) and
**keeps its historical 1.1.2 packages**; no tag was moved.
`/Applications/Kuantra Terminal.app` was replaced with the verified arm64 artifact
(installed executable `d1649078…`, version 1.1.3, `codesign` structure OK, launch verified,
user data preserved); the bundled frontend contains the export UI (`journal-export-open`)
and the update button still targets `https://github.com/alikula37/kuantra-terminal/releases`.
Previous-version app backups and old local DMG artifacts were removed from this Mac per the
owner's instruction; rollback is available by re-downloading the historical DMGs from the
superseded GitHub prereleases. The installed signature remains ad-hoc
(`TeamIdentifier=not set`): Developer ID signing/notarization is still **absent** and
remains an open pilot/distribution gate; `codesign` OK is not Apple approval.

**Security review (`ersinkoc/security-check` v1.2.0, deep profile, whole repository,
sandboxed local checks) — complete and remediated (2026-09-15):** Independent hunt and
verification passes produced 21 confirmed findings (4 High, 10 Medium, 7 Low) and 3
rejected hunter claims; the full report is
[security-report/SECURITY-REPORT.md](../../security-report/SECURITY-REPORT.md) with its
coverage ledger, dependency notes and per-skill candidate records alongside. Confirmed
fixes: the panic switch no longer fabricates closing trades and requires
`KUANTRA_PANIC_DISARM_SECRET`; the integrations gateway exposes webhook ingest only and
refuses non-loopback binds; copy signals require a shared-secret HMAC and broadcast fails
closed; model artifact names are contained under `MODELS_DIR`; webhook bodies are streamed
under a 64KB cap with constant-time secret comparisons; the execution-mode guard covers
cancel/open routes; correction/close/list inputs are bounded; `update_trade` columns are
allowlisted; broker-import review output is capped; migration archive reads stream under
byte ceilings; generated Python literals are escaped; exchange errors are generic; workflow
actions are SHA-pinned with `persist-credentials: false`, a validated `release_tag` and no
silent `appimagetool` download. Pinned by 33 new tests in
`backend/tests/test_security_review_fixes.py` (full backend **1059 passed**); committed as
`a235da2` and pushed. The clean-commit canonical arm64 local CI is **MERGE READY** 13/13
with provenance `COMPLETE` (report `dist/p1-security-review-committed-local-ci.json`
SHA-256 `b8e2898a1b8f943acd6af9077548bd94a80734b3959697cc2f998b7d4f11c1d4`, executable
`0b2b044278…`, artifact `41d7e4e8c4…`). The release workflow was then dispatched on
`a235da2` (`release_tag=v1.1.0`, `publish=false`, run `35017352321`): both native runners
built and exact-DMG-smoked their artifacts (arm64 executable `4cf92f1f…`, x86_64
`aaed049c…`), the SHA-pinned actions executed cleanly and the trusted pilot package
checksums verified locally. `Kuantra-Terminal-1.1.0-arm64.dmg` SHA-256
`96fc311e76583b4b2a8506f9b432381966ac0221d747f55bfbd81eb78a84a41f` and
`Kuantra-Terminal-1.1.0-x86_64.dmg` SHA-256
`2b344a4f2538b5bfd9040a7b7d2dda33eddbc93e0b4261606735ba8aa24a14b2` were re-uploaded to
the existing `pilot-v1.1.0` prerelease (tag not moved; exactly two DMGs; digests match the
package `SHA256SUMS`); a local native arm64 exact-DMG smoke passed
(`dist/security-arm64-exact-dmg-smoke.json` SHA-256
`9cef33a45ee14484fa7861cbda4dc5c1c7db155dd5f6e57e4c5ce5acd2b57502`); and
`/Applications/Kuantra Terminal.app` was replaced with the verified arm64 artifact
(installed executable `4cf92f1f…`, codesign structure verified, launch verified, previous
bundle retained temporarily, user data preserved). `security-report/` is repository
documentation only and was not added to the Release. **Needs validation (no severity):**
dependency CVE freshness (no local scanner; external audit services not used) and the
crafted-zip false-central-directory regression; macOS signing/notarization and the real XM
sample remain separate open obligations. (Both former follow-up items — dependency CVE freshness
and the crafted-zip regression — were closed by the 2026-09-15 follow-up below.)

**Security follow-up validations complete (2026-09-15):** (1) **Dependency scan** — an
OSV.dev `querybatch` received only `{ecosystem, name, version}` triples for the 82 installed
Python lock packages and all 289 npm lock packages; **Python: 0 vulnerabilities**. npm returned
a single dev-only advisory (`GHSA-82fw-gwwq-j7x9`, vitest/@vitest/mocker 3.2.7, fixed only in a
vitest 4 major) which is not shipped; the production `npm audit --omit=dev` cross-check from
release run `35017352321` reports 0. No dependency, lock or version changes were made. Evidence:
`security-report/dependency-scan-2026-09-15.json`, updated `security-report/dependency-audit.md`.
(2) **Crafted-ZIP validation** — 14 synthetic-archive tests
(`backend/tests/test_security_crafted_zip.py`) cover central-directory falsification, declared
vs actual size mismatch, member/total/count ceilings, symlink/traversal/duplicate/unlisted
members, corrupt central directories and restore atomicity under interruption. The validation
found one real Medium issue — `_read_manifest` decompressed `manifest.json` without a manifest
ceiling — fixed with `MAX_ARCHIVE_MANIFEST_BYTES` (1MB, streamed) and pinned by
`test_oversized_manifest_is_bounded_before_parsing`; full backend **1073 passed**. Because the
fix is binary-affecting, the trusted pilot artifacts advance to `v1.1.1`
(`truth-matrix.v1.1.1.json`); the transport release stays `pilot-v1.1.0` (assets refreshed in
place, tag not moved). Build/CI/install hashes are recorded in the follow-up evidence commit.

**v1.1.1 security-patch artifacts built and installed (2026-09-15):** build commit
`6c1e03c9c8a42f2e32d8c730beab828482338506` (clean tree). Canonical arm64 local CI is
**MERGE READY** 13/13 with provenance `COMPLETE` (report
`dist/p1-security-followup-committed-local-ci.json` SHA-256
`582b14a168f7b1de5adf58b4b5a829e28f1415e7cea298ed6a25a75588585a8d`, executable
`cf6b9b5d…`, artifact `ae148d76…`). Release run `35023961123` built both native DMGs from
the same commit (arm64 executable `a9db9c46…`, x86_64 `77b692e9…`) with native and
exact mounted-DMG smoke PASS; the pilot-package `SHA256SUMS` verified locally; a local native
arm64 exact-DMG smoke passed (`dist/security-followup-arm64-exact-dmg-smoke.json` SHA-256
`446e894cc69e61ead37ceefd76ff977657d3cca899000f330200742f3594d0bd`). The two assets were
first attached to the `pilot-v1.1.0` prerelease; the later release-identity correction below
moved them to a dedicated `pilot-v1.1.1` release.
`/Applications/Kuantra Terminal.app` was replaced with the verified arm64 artifact (installed
executable `a9db9c46…`, `codesign` structure OK, launch verified, previous bundle retained at
`/tmp/kuantra-v111-update.kUez7y`, user data preserved). The installed signature remains
ad-hoc (`TeamIdentifier=not set`): Developer ID signing/notarization is still **absent** and
remains an open pilot/distribution gate.

**Release-identity correction (2026-09-15, owner-authorized):** the 1.1.1 DMGs had been
attached to the `pilot-v1.1.0` prerelease whose tag targets the older `122b6bef…` commit,
leaving a Release–tag–package mismatch. Corrected by creating the lightweight tag
`pilot-v1.1.1` on the verified build commit `6c1e03c9c8a42f2e32d8c730beab828482338506` and a
new prerelease `pilot-v1.1.1` carrying exactly the two already-verified DMGs (arm64
`df4656bc…`, x86_64 `a541ce7d…`, downloaded back and re-hashed after upload). Only after that
verification, the `pilot-v1.1.0` prerelease was marked superseded (title/body redirect, no
downloads) and its wrongly-attributed 1.1.1 assets were removed; the old tag was not moved and
no history was rewritten. **Binary-affecting follow-up found:** the app's update button opens a
hardcoded URL (`frontend/src/components/updater/UpdateNotifier.tsx` →
`releases/tag/pilot-v1.0.0-arm64`), so the installed 1.1.1 app still points at the oldest
pilot release and does **not** yet find `pilot-v1.1.1`. Fixing this requires a frontend change,
i.e. a new binary; per instruction the 1.1.1 packages were not replaced. Bounded patch plan
(not started): update the update-mechanism URL (prefer a stable pointer such as the releases
index or the current pilot tag), rebuild both DMGs from one clean commit, re-run
native/exact-DMG smoke, publish as `pilot-v1.1.2`, then update the installed app.

**Vitest advisory assessment (2026-09-15):** `GHSA-82fw-gwwq-j7x9` / `CVE-2026-84373`
(`@vitest/mocker` redirect-mock path traversal, CVSS 5.9 moderate) was reviewed from the
official advisory. The unauthenticated path requires a third-party dev server using the public
`mockerPlugin`/`interceptorPlugin` on a reachable Vite HMR socket; `vitest` itself does not
load that plugin in this repository (no `@vitest/mocker` imports, no browser mode, no
`--api`/`--host`, `vitest run` with the node environment in ephemeral CI). No reachable
exploit path exists in the current developer/CI usage; the finding stays open as a
**dev-toolchain** item because the fix exists only in vitest 4.1.11+ (3.x is unmaintained and
will not receive it). Bounded fix (not started): upgrade the dev-only vitest dependency to
4.1.11 and run the full frontend suite; no app/runtime binary impact. Details:
`security-report/dependency-audit.md`.

**v1.1.2 update-flow and dev-toolchain patch train (2026-09-16):** two bounded changes.
(1) **Update flow:** `frontend/src/components/updater/UpdateNotifier.tsx` no longer pins
`releases/tag/pilot-v1.0.0-arm64`; it opens the repository Releases list
(`.../releases`) with explicit EN/TR/DE labels stating that the screen does not check the
version automatically, and failure paths keep showing an error (never "up to date"). Tests
were written first (6 failing cases incl. locale-label assertions) and now pass
(11 UpdateNotifier tests). (2) **Vitest:** the dev-only toolchain is upgraded to the patched
`vitest@4.1.11` (`@vitest/mocker@4.1.11`) from the unmaintained 3.x line, clearing
`GHSA-82fw-gwwq-j7x9` (`npm audit` = 0, production and full); frontend suite **40 files /
240 tests** green plus typecheck/i18n/production build on the upgraded runner. Artifact
release: this is a source + dev-toolchain change, so the trusted pilot artifacts advance to
`v1.1.2` (`truth-matrix.v1.1.2.json`); build, Release and installed-app evidence are recorded
in the post-build evidence section below.

**v1.1.2 artifacts built, released and installed (2026-09-16):** build commit
`5ea112fbe1db0801f564ee63c0cf1bf973db5694` (clean tree). Canonical arm64 local CI is
**MERGE READY** 13/13 with provenance `COMPLETE` (report
`dist/p1-v112-committed-local-ci.json` SHA-256
`7ec87db20ad104c832bc1e97140fe40951d87db12f0afb91231c3eb13557e570`, executable
`5575d0d2…`, artifact `c56fd881…`). Release run `35065925107` built both native DMGs from
the same commit (arm64 executable `936ee7f8…`, x86_64 `a17f7629…`) with native and exact
mounted-DMG smoke PASS; the pilot-package `SHA256SUMS` verified locally; a local native
arm64 exact-DMG smoke passed (`dist/v112-arm64-exact-dmg-smoke.json` SHA-256
`78a59cc09c45cbfcfcaa132d3ffdc2b587ad2168f48650e3930213bf5f516421`). The
`pilot-v1.1.2` prerelease (tag on the build commit above) carries exactly two assets —
`Kuantra-Terminal-1.1.2-arm64.dmg` SHA-256
`bdc5f43693695740d2e26db2606e193cdfdf20bd107d26481db21f8373f15d9a` and
`Kuantra-Terminal-1.1.2-x86_64.dmg` SHA-256
`a95336f8d290e7519b149c9403d0f29414e7ba6862e902deeaddc56e559219bf` — both downloaded back
after upload and re-hashed; `pilot-v1.1.1` was superseded in place (title/body redirect) and
**keeps its historical 1.1.1 packages**; no tag was moved. `/Applications/Kuantra Terminal.app`
was replaced with the verified arm64 artifact (installed executable `936ee7f8…`, version 1.1.2,
`codesign` structure OK, launch verified, previous bundle retained at
`/tmp/kuantra-v112-update.dmnlQX`, user data preserved). The bundled update target was
verified inside the installed app: `Contents/Resources/frontend/index.html` contains
`https://github.com/alikula37/kuantra-terminal/releases` and no longer contains
`pilot-v1.0.0-arm64`. The installed signature remains ad-hoc (`TeamIdentifier=not set`):
Developer ID signing/notarization is still **absent** and remains an open pilot/distribution
gate; `codesign` OK is not Apple approval.

## Selected next work

**Previous spot/search UX evidence (2026-09-12; superseded by WP31 above):** New Trade now separates
the empty provider-search field from the committed instrument, keeps an already-selected
non-catalog symbol (including literal `LINK`) intact, and requires explicit selection
and confirmation before quote/submission. Aborted or late quote responses cannot write
the previous instrument's price; switching instruments clears price/stop/target values.
`SPOT` / `LONG` / `SHORT` is persisted as `position_type` in compatibility SQLite,
canonical snapshots, rebuilt projections and Evidence Pack CSV/JSON. Spot is a BUY
purchase; contradictory directions fail validation and historical entries stay UNKNOWN.
New Trade no longer invents stop/target prices or an equity percentage from a hardcoded
$10,000 account. Chart OHLC values no longer claim USD and retain small-price precision.
Schema revision 005 is additive; stamped/unstamped v3/v4 classification and synthetic
upgrade tests pass without changing a real user's database. The prior unstamped-schema
finding below is corrected by these bounded classification tests.
Focused New Trade DOM: **13 passed**; backend full suite before the final UI-only
changes: **853 passed / 2 warnings**; spot close/cancel/CSV/rebuild regression passed.
That UI scope was included in the previous dual-native candidate. GitHub Actions run
`34664574672` from source `dd581425c2c298664512f0434fa93a726a9cacb5` passed native
arm64 and `x86_64` backend/frontend/build/package/smoke jobs; each backend reported
**852 passed / 1 skipped / 2 warnings**, each frontend **29 files / 148 tests**, and
EN/TR/DE parity **771/771**. The final DMGs and their exact read-only mounted-DMG
evidence supported the previous private Release refresh; N03, N05, H05 and pilot
read access remain open separately.

**Superseded owner-requested UX / Intel implementation evidence (2026-09-11):** Work was on
`codex/p1-wp01-evidence-ledger`, following the current session branch instruction;
the existing `main` checkout was the baseline. The full requested scope remains:
New Trade provider search/confirmation parity, explicit spot journaling, periodic
screen flicker and related usability defects, and a native Intel pilot build path.
In this change, Dashboard no longer replaces valid cards with loading placeholders
on every four-second poll, overlapping background reads are skipped, and failed
refreshes retain the last validated snapshot with an EN/TR/DE stale-data notice.
Market Charts no longer cover the canvas or reset user zoom on every eight-second
successful refresh. Three new regression scenarios reproduced the defects before
the fixes; focused tests are **13 passed**, full frontend **29 files / 141 passed**,
and i18n **763/763**. Source `bea2bab` passed native arm64 build/WKWebView smoke
with `COMPLETE` provenance; full local CI was `MERGE BLOCKED` by two historical
Release-title assertions left behind by the previous download-page simplification.
Those assertions now check the current M-series pilot title and scope. Intel probe
tests also exposed a native-host classification defect: Apple's documented
`sysctlbyname` `ENOENT` case is native, whereas other probe errors remain unknown.
The shared Python probe now reads errno directly; packaging and hosted workflow
use that same guard. Focused architecture/packaging/workflow/release tests are
**43 passed**; the real Mac mini accepts arm64 and rejects an x86_64 request.
Combined source `957c328` passed canonical arm64 local CI (`MERGE READY`, all gates,
frontend **141**, i18n **763/763**, native WKWebView, provenance `COMPLETE`). Report
`dist/ux-intel-guard-local-ci-arm64.json` SHA-256:
`e2ca4189f0694e85312f802e6fea41e7d6ea33b22b66f33b41f478cca5973d2a`.
Exact read-only DMG smoke and `hdiutil verify` passed for
`dist/Kuantra-Terminal-1.0.0-arm64-ux-intel-guard.dmg`, SHA-256
`eccee8c4f571cd50c9e3d81de8ba7dd567d0be7bdacbaca3ab508035a9778b73`;
mounted executable SHA-256
`5b0ef8bbabaa576ee4d1590358dc743da9fb2bb90ee1d8e7c231cf3fc1c23e34`.
DMG smoke used isolated data with market data/gateway disabled; local CI retained
default network behavior. `uv --offline` describes dependency resolution only.
Installed application and published Release remain unchanged pending the full UX package.
The installed app was inspected read-only: its active chart shows `ARCLK.IS` prices
with hardcoded dollar signs, another currency-display defect to resolve in this
continuation. Spot persistence, New Trade UX, currency display and Intel work are
still open. GitHub read-only inspection found the existing Release workflow active,
CI manually disabled, and no newer native Intel run than the failed historical
`34463755562`; this does not establish current billing eligibility.

**Superseded pilot UI correction evidence (this change):** The standard journal now has a visible, confirmed
`İptal et` action for an existing trade. The action calls the bounded DELETE endpoint,
which records a `CANCELED` tombstone; it does not physically remove the canonical row or
its evidence chain. Failed or malformed responses leave the confirmation open. Canceled
tombstones remain in journal/evidence history but are excluded from the dashboard asset
performance breakdown; canceling an OPEN row also removes it from the in-memory
open-position list. The Light/Dark control now applies theme tokens to the existing
dark-first shell, updates the native root `color-scheme`, and updates chart canvas colors
when the theme changes. The chart page is named and translated as `Market Charts` /
`Piyasa Grafikleri` / `Marktcharts`; visible OHLCV and error content is localized in all
three locales. The page now supports a persistent symbol watchlist, provider-backed
search with explicit result selection and confirmation, an exact-symbol manual fallback,
and per-symbol remove controls. XAUUSD now
uses an exact free Biquote OHLC fallback when Yahoo/Stooq cannot provide spot gold; it
never becomes GC=F or PAXGUSDT. A typed `LINK` returns the explicit `LINKUSDT` Chainlink
candidate, but Enter alone neither activates it nor starts a data request. Focused
Journal/Chart DOM tests are `13 passed`, the portfolio regression is `11 passed`, full
frontend tests are `29 files / 138 tests`, and i18n parity is `762/762`. The new arm64
local candidate from source `0a5b8aa` is built and exact-mounted-smoke validated. The
private pilot Release was refreshed in place from the newer `876efe0` package after this
candidate evidence was recorded. No trade or user data was changed by the tests.

**Manual update page (this change):** Settings now opens the fixed private arm64 pilot
Release in the system browser through the desktop bridge. The old timer-based false
"up to date" result is removed. Seven focused DOM tests and frontend build/i18n
(742 keys per locale) pass. The final arm64 DMG, exact mounted smoke and native browser
click-through also pass; Release asset replacement follows from this evidence.
No version comparison, automatic installer or data migration is added.

**Local schema compatibility finding — IMPLEMENTED / USER DATA UNCHANGED:** Read-only inspection
of the existing developer-profile SQLite returned integrity `ok`, but the migration
classifier rejected the unstamped pre-004 schema with ledger/projection tables and seven
missing quote fields as `SQLITE_SCHEMA_INCOMPLETE`. Runtime initialization and explicit
upgrade classification differed. The 2026-09-12 schema classification handles the intact
unstamped pre-004 layout and the additive pre-005 layout with synthetic upgrade tests.
No user-data migration/reset was performed.

**P1-WP29 — IN PROGRESS: trusted macOS pilot package preparation.** The current
bounded distribution package binds the refreshed source to two native architecture DMGs,
exact mounted smoke, manifest/checksums and pilot instructions; the active work package is
[P1-WP29](work-packages/P1-WP29-trusted-macos-pilot-package.md).

The private Release is the trusted-pilot transport for the clean dual package identified
in the current evidence at the top of this document. It carries exactly one arm64 DMG
and one x86_64 DMG. N03, N05, H05 and pilot read access remain separate obligations;
the native x86_64 build/evidence blocker is closed.

**Previous dual native pilot candidate evidence (2026-09-12; not current downloads):** GitHub Actions run
`34664574672`, source commit `dd581425c2c298664512f0434fa93a726a9cacb5`, passed the
native `macos-latest/arm64` and `macos-15-intel/x86_64` jobs. Each host completed the
locked backend suite with **852 passed / 1 skipped / 2 warnings**, the frontend with
**29 files / 148 tests**, EN/TR/DE i18n parity **771/771**, TypeScript, production build,
PyInstaller build, desktop smoke, exact read-only mounted-DMG smoke and artifact upload.
The dual trusted-pilot package and its `SHA256SUMS` verification also passed.

The exact artifacts are arm64 DMG `f8a4d4189ca6786f9ddb1e6d47f765ac6a3b4b11ffe8bc71a40bae8975189463`
with executable `31d709963c2cb4d1ad1bea72f5e2b020423ed9b9ce151eb292f5a94ad0def2ca`, and
x86_64 DMG `786370ff03270203fc95868e7c7faa17e214059d1a2625538609d48d36347f4c` with
executable `4a5991ad1cd8b98dce79aab69581542b970043d8a12894050af83c14ce419cfc`. Both
reports show native matching architecture, `wkwebview`, `COMPLETE` provenance and
`hdiutil verify: VALID`; N05 remains `BLOCKED/OWNER_REVIEW_REQUIRED` because both are
ad-hoc and unsigned/notarized. This is dual native trusted-pilot evidence, not a
production or Apple-trusted claim. That private Release refresh used the title `Kuantra Terminal
v1.0.0 — Trusted macOS Pilot (arm64 + x86_64)` and the two DMGs above. Current downloads
are identified by WP31 evidence, not these historical hashes.

**P1-WP30 — BOUNDED COMPLETE / ARCHIVED:** The external-default journal, explicit
simulation, exact free quote provenance, unavailable→manual boundary and TradingView
pending-observation confirmation are implemented and archived with their evidence in
[P1-WP30](../archive/strategy/work-packages/P1-WP30-free-multi-asset-journal.md). No
paid data, broker order path or broad account reconciliation claim was opened.

**P1-WP30 implementation boundary:** The backend exposes a free-only single-quote
endpoint with `LIVE`, `DELAYED`, `EOD` and `UNAVAILABLE` statuses. Exact crypto pairs use
Binance/Bybit public sources; generic tickers use exact Yahoo/Stooq symbols without
appending a crypto quote currency; `XAUUSD` uses an exact Biquote public fallback and
never becomes `GC=F` or `PAXGUSDT`. Biquote ücretsiz erişim sağlar ancak ticari yeniden
dağıtım koşulları H05 notices/terms sahibi doğrulamasına tabidir.
`/api/v1/trades` stores record mode and quote provenance atomically in the trade row,
canonical ledger event and rebuildable projection. New Trade/onboarding do not expose
live order routing or collect exchange/market-data credentials; TradingView alerts remain
pending until explicit confirmation.

**Historical provider-backed instrument-search candidate evidence (2026-09-11, source `0a5b8aa`):**
The clean arm64 candidate is bound to source commit
`0a5b8aa2cbdc6528ba4b4b9ce52fb3d728ac6c00`, tracked source tree SHA-256
`e70bc89b530bd055112d179670bb948bdae6f6cc2f7738e180bfd07cc99a20ca`, backend lock
SHA-256 `6291588602869af34e2a4db5d7244a627f4e139cbbd4b034b7cc07d890812399` and frontend
lock SHA-256 `396c757d5733e9618aa71f665aa3f23f5d53fcdaa8d9ff67c11d172464fcc6bc`.
Provider-backed Binance Spot/Yahoo search and the exact Biquote XAU/USD route are now
used instead of treating the small static registry as the instrument universe. The UI
shows name, exchange and source identity; only an explicit confirmation activates a
candidate. If providers return no match, an exact symbol can be explicitly confirmed as
`UNKNOWN/manual`, with no silent USDT conversion. Mac read-only checks returned `READY`
for `LINK`, `AAPL` and `XAUUSD`; no credential, trade or user data was used.

The focused provider/API/backend regression is **31 passed / 2 warnings**. Full frontend
and backend suites are **29 files / 138 tests** and **838 passed / 2 warnings**;
`npm run check:i18n` is **762/762** EN/TR/DE. TypeScript and production build pass.
`uv run --offline --no-project --with-requirements backend/requirements.lock python
scripts/run_local_ci.py --expected-architecture arm64 --report
dist/p1-wp30-provider-backed-search-local-ci-arm64.json --smoke-timeout 90` returned
**MERGE READY** with native arm64 PyInstaller/WKWebView smoke and provenance
`COMPLETE`; report SHA-256 `e0f094ae0fc9f1d6ed514b5329315db07f4f6837b6ea55e4e8128564acbfd5ab`.
The `uv --offline` flag is dependency-resolution evidence only, not runtime offline proof.

The exact arm64 DMG
`dist/Kuantra-Terminal-1.0.0-arm64-provider-search.dmg` passed `hdiutil verify`
(`VALID`), SHA-256 `9b3eeb4a0e345010ebd9f089cd5eb90428867c4cbe902a937dc9afa9e960671b`.
Exact read-only mounted-DMG smoke passed native arm64 and WKWebView/controller identity;
mounted executable SHA-256 `4eb94e83b54ff7f9c03878483d73f4469e18bf65437a9ed18538d3cca768f23e`,
smoke report SHA-256 `40ff61d3a668b002f49355f3fdaae18369bc7a4afaeabe37b232dfc855cedeee`.
The DMG remains ad-hoc trusted-pilot evidence, not notarization or production evidence;
this pre-refresh candidate checkpoint preceded the final private Release refresh.

**Superseded pilot Release refresh evidence (2026-09-11, source `876efe0`):** The canonical
arm64 DMG was rebuilt from the clarified pilot-instructions commit and the existing
`pilot-v1.0.0-arm64` private prerelease was updated in place and its download area was
simplified to the single verified arm64 DMG. The exact mounted-DMG smoke, N05 report,
manifest, checksums and instructions remain in the repository/local audit package.
Local-CI returned **MERGE READY** with backend **838 passed / 2 warnings**, frontend
**29 files / 138 tests**, i18n **762/762**, native arm64 WKWebView smoke and provenance
`COMPLETE`. Local-CI report SHA-256 is
`c30d9eb7930edc40d6468f38eb99b124dff59d65f1f605cc35dbb2f79f195e34`; DMG SHA-256 is
`9d4c7e44b83483ce794d6f628b710bd7c651b8f42ae8e98d4b40c5341d3f627d`; mounted
executable SHA-256 is `f6fef3f39e2e8d591c133ac1607a6ef62f1abffea186223a07c61f4086a26082`;
smoke report SHA-256 is `fcb1a469bdfe2330c2c5093af984fbb4389153e83a7206a12efacfec2517fd5c`.
The package manifest and `SHA256SUMS` hashes are
`04d220ff4bcef12fb4dfdc0ed8f9ccea1bea3e0f60e617f14c50167ed439886a` and
`6ca82cd3e36a8b879f2be234c2d846ead36cd5099ab064f858805f0677963d5a`; every payload
entry passed checksum verification. The installed `/Applications/Kuantra Terminal.app`
matches the mounted executable hash; the previous bundle was moved recoverably to Trash
and the user data directory was not touched. N05 remains intentionally
`BLOCKED/OWNER_REVIEW_REQUIRED` because signing/notarization was not purchased.

**Historical confirmed-symbol-selection candidate evidence (2026-09-11, source `d6c8c3a`):**
The clean arm64 candidate is bound to source commit
`d6c8c3a7c5c053e3c89e32af3195ab1262ae6219`, tracked source tree SHA-256
`bd28325800c52d404e7257f20142b7a5c8ff6ebbd50176623916221b5d21d265`, backend lock
SHA-256 `6291588602869af34e2a4db5d7244a627f4e139cbbd4b034b7cc07d890812399` and frontend
lock SHA-256 `396c757d5733e9618aa71f665aa3f23f5d53fcdaa8d9ff67c11d172464fcc6bc`.
The then-current shared symbol catalog and both UI surfaces required search-result
selection plus explicit confirmation; typed `LINK` resolved to the displayed `LINKUSDT`
candidate, and Enter alone did not activate or fetch it. This superseded record predates
provider-backed search and the explicit `UNKNOWN/manual` fallback.

`uv run --offline --no-project --with-requirements backend/requirements.lock python
scripts/run_local_ci.py --expected-architecture arm64 --report
dist/p1-wp29-confirmed-symbol-selection-clean-local-ci-arm64.json --smoke-timeout 90`
returned **MERGE READY**: backend **832 passed / 2 warnings**, frontend **29 test files /
136 tests**, i18n **754/754**, TypeScript, production build, native arm64 PyInstaller and
native WKWebView smoke all passed; provenance was **COMPLETE**. The report SHA-256 is
`2156c5fe343d704fd9263a5611364d4391ee7c7d125ab1881f397da06c4a6551`.

The exact arm64 DMG
`dist/Kuantra-Terminal-1.0.0-arm64-confirmed-symbol-selection.dmg` passed
`hdiutil verify` with **VALID**; DMG SHA-256 is
`2cdfbdb729ceae5e4ace4bf2c8eb8fcce2b6a6938e8fd8c134867b36152b920e`. Exact read-only
mounted-DMG smoke passed native arm64, WKWebView/controller identity and detach;
mounted executable SHA-256 is
`4e24c7000fda993b0ac20dfc5126d3b4d76540edff84a5815e343ac6d8e3045e`, smoke report
SHA-256 is `548c9a2becf499dbad62fdb31240d953c8d7fc9eaf60a9edb425a8ba8bbf53e5`.
The private GitHub Release was not changed; its existing asset must be refreshed before
pilot users receive this candidate. No trade, user data or credential was used.

**Superseded arm64 pilot package evidence (2026-09-11, source `119ae57`):** The clean Mac
candidate chain is bound to source commit `119ae573ce4e4885c2c83e0e8619ebd6038131dd`,
tracked source tree SHA-256
`2f907ceb265a2cf298f652c2f6a9261dbcaeb224eafc7eaf26a6a8716a8e5b6d`, backend lock SHA-256
`6291588602869af34e2a4db5d7244a627f4e139cbbd4b034b7cc07d890812399` and frontend lock
SHA-256 `396c757d5733e9618aa71f665aa3f23f5d53fcdaa8d9ff67c11d172464fcc6bc`.
`uv run --offline --no-project --with-requirements backend/requirements.lock python
scripts/run_local_ci.py --expected-architecture arm64 --report
dist/manual-update-local-ci-final.json` returned **MERGE READY**: backend **829 passed / 2
warnings**, frontend **28 test files / 128 tests**, i18n **703/703**, TypeScript,
production build, native arm64 PyInstaller and native WKWebView smoke all passed; provenance
was `COMPLETE`. The report SHA-256 is
`9345f70dbe4b28ef419931faceb90f4650d06fc8e97dfa0f8afcc4e146d4715b`.

The exact DMG `Kuantra-Terminal-1.0.0-arm64.dmg` passed `hdiutil verify` with `VALID` and
the read-only mounted-DMG smoke passed with native arm64, WKWebView/controller identity and
detach. DMG SHA-256 is
`7a07847da1134f6a098a491ee97a74db4e949b4ab373a99fa8bb086ada7f3e5d`; mounted executable
SHA-256 is `9d70f2acfdd1b81b124323d0ad1c4b0f280ff76f526a462774c076791161a90b`; final smoke
report SHA-256 is `b59489cdd444447297da51b249936ddf8ddb0d5054da4c11c60623fb6e54b3ef`.
The exact package builder returned `PASS` with type
`TRUSTED_MACOS_PILOT_ARM64` / status `AD_HOC_TRUSTED_PILOT_ONLY_ARM64`; package manifest
SHA-256 is `4ed1e6cc4521223c6282257190d76deac50122c9763ccaa525f06bd1831cc9c2` and
`SHA256SUMS` SHA-256 is `a0bbf709e4236738f3f980f3a1b99e31e01faf908fb2e499030c8d9345bba18c`.
All five payload files passed `shasum -a 256 -c SHA256SUMS`.

The final mounted DMG also passed the native manual-update click-through: Settings →
Application updates → Open update page opened the fixed private Release URL in Chrome.
No automatic installer, version comparison, migration or user-data access was involved.

N05 preflight is structurally valid but intentionally **BLOCKED** with exit 2 because the
artifact is ad-hoc and no Developer ID/notarization proof exists; N05 report SHA-256 is
`2ebf924aa122042f409522cc3637c017ba90530e81ced130f2008ad0365d061f`. This is the expected
zero-cost trusted-pilot boundary, not an app build failure. The package has no Intel
artifact, production/commercial-support claim, live execution or Apple-trusted claim.

**P1-WP30 archived closeout evidence (pre-clean source):** The focused backend/regression command
returned **35 passed, 2 warnings**:

```text
PYTHONPATH=backend .venv/bin/pytest -q backend/tests/test_p1_wp01_evidence_ledger.py backend/tests/test_h02_schema_upgrade_restore.py backend/tests/test_p1_wp30_free_quote_external_journal.py
```

The canonical locked Mac command returned **MERGE READY** with **13/13 steps PASS**:

```text
uv run --offline --no-project --with-requirements backend/requirements.lock python scripts/run_local_ci.py --expected-architecture arm64
```

It recorded backend **829 passed / 2 warnings**, frontend **27 test files / 121 tests**,
EN/TR/DE **696/696**, TypeScript/production build, arm64 PyInstaller and native WKWebView
smoke PASS. `git diff --check`, `python3.11 scripts/check_docs.py` (**115 documents,
152 local links, 5 startup documents**) and `python3.11 scripts/check_release_truth.py`
also PASS. The report hashes are `dist/local-ci-report.json`
`109477ef3f7b66fd779a62c41cec9d1a29d796a1e4f394459a5d4b69e43d5d52` and
`dist/local-ci-smoke.json`
`26675daf07354aacf8c0981b5a2af9d9f8652eede6861e4538b0cf5e577af0ad`.

The tested provenance snapshot is checkout `b972b1848c03d2ad3d6a896750f66f1814ea1247`,
tracked tree SHA-256
`d643951f6f8cd32b8820ca05b4f22778cff48ea01ccdc5025f619d488f1600a6`, backend lock
`6291588602869af34e2a4db5d7244a627f4e139cbbd4b034b7cc07d890812399`, frontend lock
`396c757d5733e9618aa71f665aa3f23f5d53fcdaa8d9ff67c11d172464fcc6bc`, macOS `26.6.2
arm64`, Python `3.11.16`, Node `v20.20.2`, npm `10.8.2`, uv `0.12.10` and PyInstaller
`6.22.2`. The tree was dirty before this implementation commit, so provenance is
`DEVELOPER_DIRTY`; this is development evidence, not release attestation.

The local DMG command produced a `VALID` image in `hdiutil verify`. Exact mounted-DMG
functional smoke reached `SMOKE_OK` with arm64, WKWebView/controller and detach checks;
the release-facing validator intentionally exited 1 because the source tree was dirty.
DMG SHA-256 is `23be62393a725b0e598145cc2a483042a4f2c06ec008d7b5308e5cf603ad226f`,
mounted executable SHA-256 is
`14f8d0120b8442689a5c702b439093638cc507514edca00cb20d61c8e137e1a8`, and the exact
smoke report SHA-256 is
`5281ddc74a91080e018caaa9461e6064f445ec285d781eefdf3f92c42f2eedfe`. This does not
open a production/release claim.

**P1-WP28 remains OPEN / HOST_REQUIRED:** native `arm64` and `x86_64` artifact contract,
executable-derived provenance and exact mounted-DMG smoke are implemented, but Intel
support is not claimed until a native x86_64 host produces its own locked
test/build/package/smoke evidence. Hosted `macos-15-intel` is the reproducible default;
an explicitly controlled native Intel pilot Mac can provide the same build evidence when
the checkout, locks, commands and clean tree are recorded. Once an x86_64 artifact exists,
the pilot Intel Mac can provide separate runtime/N03 evidence. The Rosetta guard rejects
translated or unknown Intel host status. Its implementation evidence remains `bb6ce7c`;
the separate package preparation change is recorded under P1-WP29.

N05 remains the later owner-controlled signing/notarization gate and N03 remains the
deferred clean-profile/second-host final-validation obligation; neither is silently closed
by P1-WP28 or P1-WP29.

**P1-WP29 implementation evidence (`a76f5b0`/`6f8b1ed`):** `prepare_pilot_package.py` is
fail-closed for missing x86_64 evidence in its default dual mode, while explicit
`--architecture arm64` produces a visibly M-series-only package. Both modes bind their
selected architectures to the same source/tree/lock/truth identity, verify exact
mounted-DMG smoke plus either N05 PASS or explicit ad-hoc `BLOCKED` evidence, require
`hdiutil verify` image-integrity evidence before mounting, and write DMGs, evidence JSON,
manifest, instructions and SHA-256 checksums without reading user data or credentials.
The research record is
[`PILOT-DISTRIBUTION-RESEARCH.md`](../release/PILOT-DISTRIBUTION-RESEARCH.md). The
default dual invocation remains `BLOCKED` because neither the hosted Intel job nor a
controlled Intel pilot build has produced the x86_64 chain; the explicit M-series arm64
invocation is the first pilot path. The M-series private prerelease is now published at
[`pilot-v1.0.0-arm64`](https://github.com/alikula37/kuantra-terminal/releases/tag/pilot-v1.0.0-arm64);
the canonical product Release/tag is not published.

**Superseded frontend pilot-flow hardening (`8da8019`):** Journal, CSV import, weekly review and
Trade Evidence Pack surfaces now preserve unknown financial values, bind review decisions
to the displayed period/timezone/as-of snapshot, reject malformed successful responses
before rendering, use the native pywebview save bridge for Evidence Pack exports and
report actual save/cancel outcomes. Journal pagination no longer silently stops at the
first 200 records; CSV replacement clears stale preview state and modal/dropzone keyboard
behavior is explicit. Focused and full frontend evidence is **25 test files / 116 tests**,
EN/TR/DE **670/670**, TypeScript clean and production build clean. The clean locked arm64
local-CI evidence for this change is **MERGE READY** with backend **816 passed / 2
warnings**, native PyInstaller/WKWebView smoke and `COMPLETE` provenance. Exact rebuilt
DMG UI click-through export remains a manual pilot validation obligation. This source
commit was the app artifact behind the previous private prerelease asset set; it is
superseded for pilot distribution by the clean `119ae57` package recorded above.
No new Release/tag was created for that historical refresh.

**Superseded private pilot Release asset refresh (2026-09-10, source commit `8da8019`):** The
existing `pilot-v1.0.0-arm64` prerelease was previously updated in place after the frontend
hardening commit; the tag and download URL did not change. This evidence is retained for
audit history only. The exact arm64 DMG passed `hdiutil verify`
and read-only mounted-DMG smoke. DMG SHA-256 is
`900ce30ebe93bc9a1ded399c0067edfa2f7475b892da9193ff608e579f291a76`; mounted executable
SHA-256 is `6b3b9985058933f655b2a0e1ece69a41b7d51eb28f00c2c2c0023a7792e41ce1`; final smoke
report SHA-256 is `81eb80f7a77191325c43e313a4ce1664aefe4ba27f4f76292adaaaf97d34d6fd`; and
the ad-hoc N05 report SHA-256 is
`5b24b09d1d42aef456777ab398a71e23d1e1a9ee42e0bfad8dc74840454b1ca3`. N05 remains
`BLOCKED/OWNER_REVIEW_REQUIRED` by design because no Developer ID/notarization proof exists.
The six Release assets are the DMG, final smoke, N05 report, pilot manifest, standalone
instructions and `SHA256SUMS`; their GitHub asset digests are checked against the package
checksum file after upload. Local locked arm64 CI for this source is **MERGE READY** with
backend **816 passed / 2 warnings**, frontend **25 files / 116 tests**, i18n **670/670**,
native PyInstaller/WKWebView smoke and `COMPLETE` provenance. The exact DMG UI
import→review→Evidence Pack→native JSON/HTML/CSV save click-through is still a manual
pilot obligation. The local-CI report SHA-256 is
`cde81fe18e0346b534b4828589c462bc4d7381719611df959b5a7000f6bf0c79`; tracked source tree
SHA-256 is `964e672c8c05da2b490de83856a8a4e81e2c4b77f2a333751bdc783547f764cd`; the package
manifest SHA-256 is `1b196a795a82d2dc7b9fea006f0e12e4cf55690956a75b797bbedce4235bc548` and
`SHA256SUMS` SHA-256 is `5577f7ae8b69197b36b754a4290472ad9dcca8314c74d62fbce72911af67e89e`.
No production, Intel, commercial-support or Apple-trusted claim is opened.

**Previous local-only M-series arm64 package evidence (2026-09-10, source commit `25ce02a`):**
The locked arm64 local gate is **MERGE READY** on the Mac mini: backend **815 passed / 2
warnings**, frontend **25 files / 104 tests**, i18n **608/608**, arm64 PyInstaller build,
native WKWebView smoke and `COMPLETE` provenance. The local-CI report SHA-256 is
`4624f4f03c88cef8258c1158830556b21102f0e11fbf5e6b8d791485b51f192a`; tracked source tree
SHA-256 is `c94317aa09cc72da9c27823c073826e730cc2be03b613f7331309cbfb9fb7b98`; backend
and frontend lock hashes are recorded in the report. The exact
`Kuantra-Terminal-1.0.0-arm64.dmg` was rebuilt and passed `hdiutil verify`; DMG SHA-256 is
`a8b5204f0bb37ead68566c63656d3f0908eba259c341e953591bf1a713ca1d99`, mounted executable
SHA-256 is `def6b706fd076b6048193380d55638100710b5466e718d30271d578c421b9d38`, and the
exact read-only mounted-DMG smoke passed native `arm64`, `wkwebview`, controller identity
and detach confirmation. The final smoke report SHA-256 is
`6bace1057e2b776f9fda1bed4911ef09de59bf3b477e80f0679f657bc452108f`; the corresponding
N05 report SHA-256 is `c9bf62099d3b326908248539baa286fcdf1c4092899ba7f6e56266b42105d7a7` and
is correctly `BLOCKED/OWNER_REVIEW_REQUIRED` because the package is ad-hoc and has no
Developer ID/notarization proof. The explicit M-series package passed its internal
five-file checksum verification; manifest SHA-256 is
`88fe31e700b34f1a990dce427fe49dec1eb1914dde99fe7eb6580cea1362852b` and
`SHA256SUMS` SHA-256 is `2791053bd8ebb11402e0f53083813d66db978e145ad6e5e40b3668ed2be4ffbd`.
The package is `TRUSTED_MACOS_PILOT_ARM64` / `AD_HOC_TRUSTED_PILOT_ONLY_ARM64`, scoped to
`APPLE_SILICON_M_SERIES_ONLY`; it contains no Intel artifact or support claim. It is ready
for the three-person M-series pilot before the private Release was created. The current
published package evidence is recorded below.

**Superseded published M-series arm64 pilot package evidence (2026-09-10, source commit `6f8b1ed`):**
This historical Release asset set was replaced in place by the current `8da8019` package
recorded above. Its hashes remain below only for audit traceability and must not be used
to download or validate the current pilot artifact.
The exact source-bound arm64 chain was rebuilt from commit
`6f8b1ed2accdd3f5035a3cf5b0ee42671b4a3b4c` with tracked-tree SHA-256
`4d0e9449f365df10ac09dc3851b12c12b6310ed076c98196d053e9f202e04ffd`. The locked local CI
was **MERGE READY** with backend **816 passed / 2 warnings**, frontend **25 files / 104
tests**, i18n **608/608**, native arm64 PyInstaller build, native WKWebView smoke and
`COMPLETE` provenance; report SHA-256 is
`d2dd6d663441c0202e8940018111a8190589ce82a3e1324c040ab6aea02595ae`. The exact
`Kuantra-Terminal-1.0.0-arm64.dmg` passed `hdiutil verify` and exact read-only mounted-DMG
smoke with native arm64, WKWebView/controller identity and detach confirmation. DMG
SHA-256 is `d2f8151e24e29ae0a3800165d823dfd3e6f44a2ef3b95f04674a6ed9ead6e540`, mounted
executable SHA-256 is `c76315073ef72687bef2bb90dc9c0ec5adfdc1aff912898aa717562aaae2e870`,
and final smoke report SHA-256 is
`40573464091be5d43a3c31b973980559ebc4fe1112a4fa87948f37a428cda080`. N05 remains
`BLOCKED/OWNER_REVIEW_REQUIRED` as expected for an ad-hoc artifact; its report SHA-256 is
`19fa90a538db42d9a110b58359c2c55a33e87cb3a082f9494f25fa948a092eb4`.
The package manifest SHA-256 is
`cdcb68b0cc662e2d54a2805b4d8672c258f1ad9f2df37d44420bca5c56594f10`; `SHA256SUMS`
SHA-256 is `53610c49f7dd10e89cf13070e5d423e88fb1e50100352df90fa956967dcdeab9`. All five
package files passed checksum verification. GitHub Release asset digests match these
values and the published private prerelease is
[`pilot-v1.0.0-arm64`](https://github.com/alikula37/kuantra-terminal/releases/tag/pilot-v1.0.0-arm64).
The package is explicitly `TRUSTED_MACOS_PILOT_ARM64` / `AD_HOC_TRUSTED_PILOT_ONLY_ARM64`;
Intel, production, commercial support and notarization claims remain false.

**Native pilot-host local-CI evidence (`75a4188`):** `run_local_ci.py` now accepts
`--expected-architecture arm64|x86_64`. With that option it rejects a non-native or
translated macOS host before the build, passes the requirement to desktop build/smoke, and
fails the provenance contract if executable architecture, build-host architecture or
translation status do not match. On this Mac mini, the full locked arm64 gate passed with
backend **813 passed / 2 warnings**, frontend **25 files / 104 tests**, i18n **608/608**,
native PyInstaller build and native WKWebView smoke; report SHA-256 is
`b2578aac4d3b8f46a9dd637d778fc2b7b829a171da1c5b2cd071646650be8cbe`, source commit is
`75a4188c907757d564dad5dfd7a616ed98bae7e6`, tracked-tree SHA-256 is
`bb70f41e3ef309cd5c0ec9d10d0c81d4da0e8804bd7a9fd34164c4d9ef7ca8f2`, and provenance is
`COMPLETE` with `expected_architecture=arm64`. The same Mac's x86_64 request exited `2`
with `expected x86_64, got arm64`; this is the intended negative control. No Intel artifact
or x86_64 support claim was invented; a native Intel pilot Mac can now run the identical
command with `--expected-architecture x86_64` and supply the missing host evidence.

**Fresh arm64 download-integrity evidence (2026-09-10, preceding implementation commit
`6646332`):** Local CI is **MERGE READY** with backend **810 passed / 2 warnings**, frontend
**25 files / 104 tests**, i18n **608/608**, arm64 PyInstaller build and native WKWebView
smoke PASS. The exact `Kuantra-Terminal-1.0.0-arm64.dmg` was rebuilt from source commit
`66463327a469d88a79b9f48e7255d01afeaa75da`; its tracked-tree SHA-256 is
`8650e83dfd179974372beb12cf9f3138a9b55655f92ee88b9abfea33d48322c6`, executable SHA-256
is `66326dd635881b43d8d6a23bc9a1b56faf792e3d7805a0aa6cc8a76411579554`, and DMG SHA-256 is
`a8501f796e8c4042fe420376258987452f027b84a4e97c345a0356a0c6d4bec4`. `hdiutil verify` on
that exact DMG returned exit 0 and `checksum ... is VALID`. Exact read-only mounted-DMG
smoke passed with `dmg_image_integrity: PASS`, native arm64 executable, native `wkwebview`,
controller identity and detach confirmation; report SHA-256 is
`921f1baa55c8688b9821fa7b356d4c289d9271a9208bf36bb1e23817e4e9fbfe`. The corresponding
N05 report SHA-256 is `d4438bfc00497ebc2602b66b820638fe5a0e0614e59717e5aaedf0bd546c6c5e`
and remains correctly `BLOCKED/OWNER_REVIEW_REQUIRED` because the artifact is ad-hoc and
has no Developer ID, hardened runtime, Gatekeeper or stapled-ticket proof. The package
builder was then invoked with this exact arm64 chain and correctly stopped at the missing
native x86_64 DMG; no one-architecture pilot package or Release was created.

**Fresh arm64 evidence (2026-09-10, preceding implementation commit `bfc422d`):** Clean
Mac mini arm64 build and default local CI completed with backend **809 passed / 2 warnings**,
frontend **25 files / 104 tests**, i18n **608/608**, and `MERGE READY`. Exact
`Kuantra-Terminal-1.0.0-arm64.dmg` mounted read-only smoke passed with native `wkwebview`,
controller identity, executable architecture and detach confirmation. The exact DMG
SHA-256 is `4482f17d7609f050ed8394c1a39f229d6ebbcdb563cb306723b6e4bf4952bed3`; executable
SHA-256 is `ccca5e8117ae2e7c4db0c7de32b3bfd7ee24b00ee36dd512de852a61dfa858a8`; final
mounted smoke report SHA-256 is `4f93a4f4b0e2f7c4ed2fdf6cabbeb4521a6c39a01b77d72b96128355dcfecfbc`.
The N05 report SHA-256 is `944acec1f21deb2b9ee19ae1864ffdfff71c66562a30e0a0c98ea1bd83e803fa`;
it is correctly `BLOCKED/OWNER_REVIEW_REQUIRED` because this zero-cost pilot artifact is
ad-hoc and has no Developer ID, hardened runtime, Gatekeeper or stapled-ticket proof.
The reports share tracked-tree SHA-256
`58098c1a06f9653c43cf8da69d9b5a3d105323c770e0184f699dea72a2dc9c1f` and truth-matrix
SHA-256 `740b33db5e73b3c9cd7d8fa078282e6d03d8f0c0cf690f0ac1cc2320a617bcf6`. This is
arm64 evidence only; it does not close P1-WP28 or produce a pilot package without the
native x86_64 chain.

**N05 — IN PROGRESS: exact macOS distribution preflight.** The read-only verifier
`run_n05_macos_distribution_preflight.py` binds an exact DMG, its mounted app and
the final mounted-DMG smoke/provenance report; it checks Developer ID identity,
hardened runtime, allowlisted entitlements, Gatekeeper and a stapled DMG ticket
without reading user data, Keychain credentials or raw signing output. Focused
contract tests are green. The current development artifact is intentionally
ad-hoc and has no notarization ticket, so the expected result is `BLOCKED`/exit 2;
this is not an N05 PASS and does not claim production readiness. The exact v1.0.0 smoke/N05
chain has now been regenerated; it must be regenerated again after any source or artifact
change before a release-candidate dossier. Actual Apple
signing/notarization remains an owner/host gate.

**Historical P1-WP28 implementation evidence (2026-09-10, `bb6ce7c`):** Architecture/provenance/
packaging red tests were first failing and then passed **41/41**; the complete backend
suite is **800 passed / 2 warnings**, frontend is **25 files / 104 tests**, i18n is
**608/608**, and `python3.11 scripts/check_docs.py`, release-truth, packaging preflight,
shell syntax and workflow YAML checks pass. Canonical local CI was rerun with the
default market-data behavior and is **MERGE READY**: all steps PASS, including the
arm64 PyInstaller build, native `wkwebview` smoke, renderer preflight and COMPLETE
provenance. This is not runtime-offline evidence; the default local-CI run attempted
the public Binance stream without credentials, while the exact mounted-DMG smoke used
`KUANTRA_MARKET_DATA_ENABLED=false` and an isolated temporary data directory.
The release workflow's app and final-DMG smoke steps now set that flag explicitly, so
candidate artifact smoke does not depend on public market-data availability.

The clean Mac mini arm64 chain is independently verified: executable SHA-256
`cfb75d0a9b1aeb00bce657bb0b393284453ed8975856a5b50231312150c47924`, exact DMG
`Kuantra-Terminal-1.0.0-arm64.dmg` SHA-256
`4801d3c14fc3ffd4ef07af88a3b36c7eb1ef03032cdd6684227c500bbe8a0eb2`, mounted smoke
report SHA-256 `5ae96513963999df5284fb5b1d56d12fcaa2eda0d938e4942b287ac20e7d30eb`,
and N05 report SHA-256 `9e92b104b27fcd30c31547a0b3c5ae9fdb30c5d4d89e159ae7cf55e9d315409e`.
The reports bind source commit `bb6ce7cd34fced2e9dd7d3b6683182cb28174e27`, tracked
tree SHA-256 `cd8ddc7e5de74372649de2d8a3bdf04ca8f3bfb1403d07d73300acfe635cbaf4`,
and truth-matrix digest `740b33db5e73b3c9cd7d8fa078282e6d03d8f0c0cf690f0ac1cc2320a617bcf6`.
N05 is correctly `BLOCKED/OWNER_REVIEW_REQUIRED` for the ad-hoc artifact: codesign
verification and mount/detach passed, but Developer ID, hardened runtime, Gatekeeper
and stapled ticket are absent.

The manual release-candidate workflow `34463755562` was dispatched with
`publish=false`, but both native jobs were rejected before startup because the GitHub
account has a failed payment/spending-limit condition; the publish job was skipped.
Therefore no x86_64 artifact or Intel CI evidence was invented, and the truth matrix
remains `x86_64: PENDING_NATIVE_CI`. P1-WP28 is not closed and Intel support is not a
current claim until that external billing/runner blocker is resolved.

Source `00ce94e` üzerinde canonical locked local CI **13/13 PASS** oldu: backend
**797 passed / 2 warnings**, frontend **25 dosya / 104 test**, i18n **608/608**,
arm64 PyInstaller build, native `wkwebview` smoke ve packaging/provenance PASS.
Report SHA-256 `4a356229e77f611947d6b54877ad2dde095629dceee064e9cd2ff61879507611`;
tracked tree SHA-256 `7e5d3cdd0976b024b2a80b9deb4b9c9c27f1d3f046736711638b746d06d4fd16`;
executable SHA-256 `3971294f9b96aa85a3a0e9f185751098d42594da5e8fd616ff0f2f4e82f2c6b1`.
Exact v1.0.0 arm64 DMG SHA-256 `b759f1e2572d06bd9ffa7faf82949c9e06ee077711fb3067d715a29c58083bd3`
ve mounted-DMG smoke report SHA-256
`0bcf23e06419300f686d8863c565d30392ca8bb4a1a0fbb805f6cb3164b2e9c8` olarak
bağlandı. Report truth-matrix canonical digest'i
`dcbe267d933634033eb7ef000118e28b910088f9ee9caeeeebdc2a107471d768` ve manifest
development snapshot SHA-256 `27fb9c146bfb0915845d6fbd7a79a8ba1d7dab3d33c053908b2d95487a750e86`.
N05 preflight report SHA-256
`338e83e77679633ecd1c16001690f3457fc243e17b7281032622e03c2d9d66d2`; sonuç
`BLOCKED/OWNER_REVIEW_REQUIRED`: read-only mount attach/detach ve codesign
verification PASS, fakat artifact `AD_HOC`, hardened runtime yok, Gatekeeper FAIL
ve DMG stapled ticket yok. Bu beklenen development sonucu; N05 veya production PASS değildir.
`657922b`, `133c269` ve `121a5cd` ile gelen explicit Developer ID/hardened-runtime,
owner-controlled notarization wrapper'ı ve pre-submit gate hâlâ bu v1.0.0 adayında
uygulanır; gerçek Apple kanıtı owner/host kapısıdır.
N06 Windows/Linux host kanıtı v1 release gate'i değil, gelecekteki multi-platform
genişleme koşuludur.

**İç production-candidate audit (2026-09-10):** `uv pip check` PASS, backend/frontend
compile/build PASS ve full testler PASS oldu. `npm audit --omit=dev --audit-level=moderate`
production dependency'lerinde açık bulgu döndürmedi. Tam npm audit, yalnız test-time
Vitest `3.2.7` / `@vitest/mocker` zincirinde 2 moderate bulgu bildirdi; önerilen düzeltme
major Vitest yükseltmesidir. Bu bağımlılık shipped runtime'a girmiyor; kullanıcı kararıyla
Dependabot/H05 release gate'ine deferred bırakıldı ve bu branch'te major upgrade yapılmadı.

H07'nin bounded implementation/evidence sequence'i mevcut Mac artifact'ında
tamamlandı ve acceptance/archive kaydı uzlaştırılarak arşivlendi. Commits
`e3aacc8`, `dfa7252`, `5b82473` and `4e761fa`
move Evidence Pack reads behind a bounded asynchronous bridge job, isolate the
heavy read in a single lazily-created worker process, and reuse bounded worker
state for warm reads. The same `4e761fa` arm64 artifact completed the planned
two-run `1k/10k/100k` campaign with 20 operation samples per mode and a separate
native UI/concurrent-read report. This is implementation and development evidence,
not a production SLO or support-limit decision.

H07 kapanışı bir production SLO veya support limiti değildir. 100k cold Evidence
Pack operation p95 is
`2321.8877 / 2332.4201 ms`, projection-rebuild operation p95 is
`5141.0606 / 5143.9399 ms`, projection process peak RSS is about
`400.4 / 400.5 MB`, and native UI timer-gap percentiles remain `UNKNOWN` (the
observed single run has a maximum gap of about 1002 ms cold and 688 ms warm).
The product owner has now decided that 100k is not a production support
requirement; it remains a stress-test boundary. Therefore no further optimization
is required solely to force 100k below `<2s>`. Fresh native UI evidence for the
1k/10k candidate band is now complete: both runs used the current `198e712`
artifact, rendered through native `wkwebview`, observed loading, and returned
HTTP 200 for concurrent health/read calls. The measured cold/warm elapsed pairs
were `1689/830 ms` at 1k and `1748/888 ms` at 10k. The instrumentation still
records `UNKNOWN_SINGLE_SAMPLE` timer percentiles and `NOT_VERIFIED` network
isolation, so this is functional UI evidence, not a latency SLO.

The tested candidate boundary is now recorded as `<=10k` synthetic history for
this development/release candidate; larger histories are best-effort and 100k is
stress-only, without adding a hard import cap. This boundary does not claim
real-user performance or commercial support. H07 is archived as a completed
non-release measurement/boundary package; its reopen condition is a new explicit
performance SLO/resource-cap or wider-history support request. Commercial,
signing, multi-host and pilot/release gates remain open.

**P1-WP27 — CLOSED / ARCHIVED:**
[G0–G2 supported matrix ve packaged value-chain audit](../archive/strategy/work-packages/P1-WP27-g0-g2-supported-matrix-audit.md).
P1-WP16 timestamp completeness was verified in `ef909d1`; P1-WP17 source identity
and support boundary was verified in `930d25a`; P1-WP18 fee/precision/unit truth was
verified in `0c7d11f`; P1-WP19 funding/corrections/account coverage was verified in
`f67e732`; P1-WP20 economic dedup/lifecycle was verified in `5d691b9`. P1-WP21
journal/projection/evidence propagation is complete in `056b1ca`; N01 exact build
provenance is complete in `05e826d`; N02 exact mounted-DMG/WKWebView smoke is
complete in `cc0ad94`; H03 runtime degraded/offline boundary is complete in
`62921f7`; P1-WP22 R4 import/review/Evidence Pack/export integration is complete in
`ea4e12c`; P1-WP23 U02 reconciliation inbox and correction/user-decision boundary is
complete in `51ee968`; P1-WP24 U03 canonical Evidence Pack/export boundary is complete
in `afedb70`; P1-WP25 U04 weekly review and as-of determinism is complete in `26751f7`;
P1-WP26 U05 accessible/understandable shell is complete in `30dfcd7`; H01 canonical
persistence/recovery is complete in `006e86e`; H02 schema upgrade/restore is complete
in `169c446`; H04 threat model and trust boundaries is complete in `1cf486e`.
H05 machine-checkable implementation/evidence is complete in `c089cd2`. Its
license/notices and default-branch alert disposition were explicitly deferred for
the non-production development period and remain release gates; the archived H05
record preserves the reopen conditions. H06 privacy/data-lifecycle and credential
availability is boundedly complete in `a7b99b7` and archived with its exact Mac
evidence. H07, P1-WP27 and N04 are archived with their exact bounded evidence; N03
remains the open deferred final-validation obligation while N05 is the current
development package. Neither package silently became full
tax/accounting scope or new venue scope. No other historical `Active` WP is
automatically queued. Pilot/release claims remain blocked by their explicit gates.

P1-WP27 closeout evidence: implementation/evidence source is
`e04279032a8554b8005fffa83242f108d9d2b4bc`; the independent packaged audit is
`PASS` on Mac 26.6.2 arm64 and its report SHA-256 is
`89d3d8d8332c1cf32fbc0c79dc437961add0a966d4371cfd530c772602eefad8`. The final
locked local CI is `MERGE READY` with 13/13 steps, backend `769 passed`, frontend
`25 files / 104 tests`, i18n `608/608`, native `wkwebview` smoke and provenance
`COMPLETE`. This is not release/signing/second-host/Windows/Linux evidence.

**N03 — DEFERRED / HOST_REQUIRED:**
[macOS temiz profil / ikinci host install-lifecycle audit](work-packages/N03-macos-clean-profile-install-audit.md)
remains open for final validation. The process-only audit worker/launcher, explicit packaged
executable/hash checks, provenance binding, source worker persistence tests and
scope guards were implemented in `ec162429d4f79e9f6fd581d3e1c81e8cb8b48d42`;
the focused N03 plus related regression set was **37 passed with 2 deprecation
warnings**. The same clean tracked checkout produced canonical local CI
`dist/n03-local-ci-report-ec16242.json`: **13/13 PASS**, backend **775 passed**,
frontend **25 files / 104 tests**, i18n **608/608**, arm64 build, native
`wkwebview` smoke and provenance `COMPLETE`; report SHA-256 is
`7bb4e9bdd2fbb67293de2ff1ab61ac4aed069f458e74d1d384bfce82ae79c4eb`, executable
SHA-256 is `1184f105364160ce19a915cf2336f3778b476886df442e198738e7e8353b1937`
and `.app` tree SHA-256 is
`d1b0041f57a41b3e6a819171e7f03254f15a469eaf5eb5298ee6444d2f331228`.
This is not host acceptance evidence. By owner decision on 2026-09-10, executing this
host/profile audit is deferred until the final macOS distribution/pilot validation
gate; it is not a PASS or COMPLETE. A second genuinely clean macOS profile or
host is still required; the current developer profile and a temporary data
directory are insufficient. Until that host/profile evidence exists, N03 remains
`DEFERRED/HOST_REQUIRED`; no clean-profile execution is scheduled during normal
development by owner decision.
The CI smoke retained default market-data behavior
and may have attempted the public Binance stream, so it is not offline-runtime
proof; H05 supply-chain owner review also remains deferred.

**N04 — CLOSED / ARCHIVED:**
[macOS manual update/uninstall data-preservation audit](../archive/strategy/work-packages/N04-macos-update-uninstall-data-preservation-audit.md)
is complete as a bounded non-release audit. It covers the bounded manual app
replacement transaction, interrupted-update recovery, app-only uninstall/data
preservation, and the user-facing fail-closed schema rollback policy using isolated
synthetic data. It does not add an automatic updater, perform a real migration, or
touch the user's data directory. Exact previous/current packaged artifacts and
provenance were recorded; N03 remains the separate clean-profile launch/reopen gate.

N04 source implementation/evidence commit is `3f4ba822cf367c588cc9e9fe13e6404a5a6d4512`.
Focused N04 tests passed **13**. The clean commit canonical local CI report
`dist/n04-local-ci-report-3f4ba82.json` is `MERGE READY`: backend **788 passed, 2 warnings**, frontend **25 files / 104 tests**,
i18n **608/608**, arm64 desktop build, native `wkwebview` smoke and provenance
`COMPLETE`. Report SHA-256 is
`1990759706893589b7411133c51a624a3a265d3dadafc4a47d35955bf0777576`; source commit
is `3f4ba822cf367c588cc9e9fe13e6404a5a6d4512`; tracked tree SHA-256 is
`b200a27bc8ff110dd4ce13c7c2346771be8e0148c1d4cd80de4e527a2bfb0a0e`; app tree
SHA-256 is `3d97e2a412662f5701d21eb4a8ab8bf0b2a809532ad1377e3b92c80b13f63b1f`;
executable SHA-256 is
`11d9e1085c306574a97c233f646b286e3a29ad8c9baf14d0431397d34a7fdb0a`. The packaged
audit `dist/n04-packaged-audit-3f4ba82.json` is `PASS` with SHA-256
`24492ae5ff85047c2a979bcbdf1c85a987b9b5aeee885ededfb132407d987868`: previous
artifact `ec162429...` and current artifact `3f4ba822...` both had `COMPLETE`
provenance; update, all three interruption phases, app-only uninstall and the
fail-closed schema rollback policy passed. This is bounded non-release evidence and
does not close N03, H05 or signing/production gates.

**N05 — IN PROGRESS:**
[exact macOS signing/notarization preflight](work-packages/N05-macos-signing-notarization-preflight.md)
has a bounded read-only implementation and focused contract tests. The verifier
returns `EVIDENCE_INVALID` for provenance/hash/smoke mismatch and `BLOCKED` for a
valid but ad-hoc/ticketsiz artifact; raw command output is not persisted. The
current v1.0.0 ad-hoc artifact observation is expected to remain blocked (`Signature=adhoc`,
`spctl` rejected, no stapled ticket). The unchecked Developer ID, hardened-runtime,
Gatekeeper, stapled-ticket, N03 clean-profile, N06 host and H05 commercial criteria
remain open and are not inferred from source tests.

## Historical evidence retained for traceability

The dated H07 records below are retained for audit traceability. The selected current
state is recorded above; historical `IMPLEMENTATION_REQUIRED` wording does not reopen
H07 or P1-WP27.

2026-09-09 correction, **a97499b**: payload/provenance validation again enforces
the existing stdlib canonical JSON contract; scalar hash serialization has explicit
type guards. Three new regression cases failed before the fix; all 38 focused H07
tests pass afterward, including a rehashed noncanonical chain rejection.
The historical performance figures below are source-process measurements, not
packaged executable benchmarks: their `--executable` value supplied hash metadata
only. The separate mounted-DMG smoke evidence remains valid for its recorded
binary. The packaged cold/warm/append-tail protocol and its final two-run/20-sample
campaign are recorded under `af8e2a1`; process-level resource capture and a fresh
packaged `projection-rebuild` mode are implemented in `30be78d`, followed by the
bounded projection batch writer in `67eafa2` and the full-chain cold optimization
in `670ee90`. H07 remains open: the latest 100k cold Evidence Pack p95 is above
the planning target, and measured RSS/temp footprint still has no owner-approved
support disposition. The clean Mac locked local CI for `670ee90` was `MERGE READY`:
759 backend tests with 2 deprecation warnings, frontend 25 files/102 tests,
i18n 608/608, arm64 build and native WKWebView smoke PASS on macOS 26.6.2. This
is development evidence, not a signed release artifact. Default smoke attempted
public market data; the H07 campaign itself set network-disabled guards and used
no credentials.

2026-09-09 current H07 worker-isolation package, **e3aacc8 → 4e761fa**: the
native Evidence Pack read no longer performs the heavy synchronous read on the
bridge thread. The bridge validates a bounded job request, retains at most four
jobs for 300 seconds, and polls an isolated single worker process; the worker
reconstructs only the existing read adapters and does not start the application
runtime, connector or market stream. The pool is lazy and shuts down with the
desktop runtime, avoiding a default-smoke semaphore side effect. A process-local
bounded adapter cache reuses warm ledger-verifier state. No schema, event type,
funding/transfer scope, correction lineage or authority changed.

Red contract tests initially failed because the new bridge/job API did not yet
exist. Green evidence: focused desktop bridge **12 passed**, frontend backend
adapter **18 passed**, relevant desktop/H07/packaged-worker backend set **86
passed**, full backend **764 passed with 2 deprecation warnings**, and full
frontend **25 files / 104 tests passed**. Production frontend build and i18n
parity **608/608** also passed. The canonical locked local CI command was:

```text
uv run --offline --no-project --with-requirements backend/requirements.lock python scripts/run_local_ci.py
```

It returned **MERGE READY** with 13/13 steps on macOS 26.6.2 arm64, Python
3.11.16, Node v20.20.2, npm 10.8.2, uv 0.12.10 and PyInstaller 6.22.2. The
development local-CI report SHA-256 is
`28f13f08bafd3fa08dd211f9a30a34b3ce0b012fae69896bc8773b08314c17da`; its
provenance status is `COMPLETE`, executable SHA-256 is
`4052c8635f7dc1784ea328d52e3d66414476938b38a4b4210e045626df6d5f44`, and `.app`
tree SHA-256 is
`92839bb06ec755d340e6368bc2643373ca6051a14051133c1efb8c44053ec843`. The
local-CI smoke report SHA-256 is
`dc5808335cb7002dd6504722726438add28342b75c34cbf9d16b5b655e2b1f08` and the
native worker-cache UI report SHA-256 is
`e04d10148e7f7bf7edffbafbbffde8faa0ddafe3d779246fde0fd0e02b0aa95d`.

The native report used a clean synthetic `100000/100000/100003` fixture with
`KUANTRA_MARKET_DATA_ENABLED=false`: React/bridge/health/push/plugin checks and
concurrent health/read responses passed, loading was observed, and the actual
renderer was `wkwebview`. It records `process_cold=false`,
`percentiles=UNKNOWN_SINGLE_SAMPLE` and `network_isolation=NOT_VERIFIED`; the
timer-gap observation is therefore diagnostic only and not a responsiveness PASS.

The final packaged campaign command was:

```text
.venv/bin/python scripts/run_h07_measurement_campaign.py --executable "dist/Kuantra Terminal.app/Contents/MacOS/Kuantra Terminal" --artifact "dist/Kuantra Terminal.app" --output-dir artifacts/evidence/h07/full-chain-4e761fa-20260909 --sizes 1000,10000,100000 --runs 2 --cold-samples 20 --warm-samples 20 --append-samples 20 --projection-rebuild-samples 20 --batch-size 1000 --timeout 1800
```

It produced 366 packaged manifests: two runs, 20 samples for each of cold,
warm, append-tail and projection-rebuild at each size. All 120 projection
samples were valid and deterministic; every size/run retained the expected
`trades / projections / ledger_events` counts. The campaign report file SHA-256
is `108df12331909af500723427096cb828d2a0c92bd019105be4693ac3a09d605f`, its
embedded report SHA-256 is
`608424a3e2e6fb881aca309fefcd1cec5c763899b9e12b5fe211b7b2481837fb`, and its
campaign manifest SHA-256 is
`b2f96cbcd8c2eb3b435173dd4aae035b9f829b58424259f8f7332ce3a6ee2b9a`.
The campaign records `artifact_executed=true`, `real_data=false`,
`credentials=false`, `network=false`, `live_execution=false`,
`source_to_binary_attestation=NOT_VERIFIED`, `release_provenance=UNKNOWN` and
`os_cache=UNCONTROLLED`. These are reproducible development measurements only;
they do not establish a maximum supported history, RAM limit, commercial support
limit or release artifact claim. The supply-chain step is still the deferred
commercial owner-review boundary; no Dependabot or license/notices change was
made.

2026-09-09 candidate support-band UI evidence, **198e712**: the diagnostic CLI
now accepts only `1k`, `10k` or `100k` synthetic fixture declarations, preserving
the previous 100k default and rejecting other sizes. Clean temporary fixtures at
1k and 10k were run against the explicitly built arm64 executable with
`KUANTRA_MARKET_DATA_ENABLED=false`; no real data, credentials or network market
stream was used. Both reports recorded `status=MEASURED`, actual renderer
`wkwebview`, loading observed, bridge/health/push/plugin smoke checks PASS and
concurrent health/read HTTP 200 responses. Results were:

| Synthetic history | Cold UI elapsed (ms) | Warm UI elapsed (ms) | Cold / warm max timer gap (ms) | Health / read (ms) |
|---:|---:|---:|---:|---:|
| 1,000 | 1689 | 830 | 1000 / 725 | 12 / 21 cold; 3 / 6 warm |
| 10,000 | 1748 | 888 | 1000 / 783 | 18 / 33 cold; 1 / 18 warm |

Each report correctly retains `process_cold=false`,
`percentiles=UNKNOWN_SINGLE_SAMPLE` and `network_isolation=NOT_VERIFIED`.
The timer-gap values are diagnostic observations from one cold/warm pair per
fixture, not a responsiveness PASS or production SLO. Report SHA-256 values are
`bc7b185d2deb077515e16ca73a372963567cbefe721abfd3a1001ef0f8f3a2c7` (1k) and
`22283ed3e573bdaba3697024c5c3b57ecbb08e904cc81a15b70cec8ebdf03b7d` (10k).
The clean local-CI report for the executable is
`7a76291e38dd2dfe319ac147c3c8a4e145efc9838d628620632dcb4782887da0`; its
executable SHA-256 is
`76ee0b45f480230f2cf9e35aa50f966c8723d455702370f8d1c37c0fba665aa6` and its
`.app` tree SHA-256 is
`fe93212b32bfcc96cc4b43c820b627c3235eb74f8ca8ec2672ca94ad56aeba68`.
The owner decision and tested boundary are recorded: 100k remains stress-only,
no further 100k optimization is required, and `<=10k` is the current synthetic
candidate band without a hard import cap. This is not a 100k performance claim
or commercial support promise.

Measurement contract, **caef518**: source benchmark reports now explicitly record
`SOURCE_PROCESS`, `artifact_executed=false`, `cold_process_measured=false` and
`os_cache=UNCONTROLLED`; the validator rejects a forged packaged-execution claim.
Correction fixture count is fixed at three (or dataset size if smaller), independently
of measurement repetitions. Three/five-repeat runs preserve counts and deterministic
snapshots. Default report output is ignored `artifacts/evidence/h07/`.
The earlier H07/packaged-worker contract evidence was 66 tests and the
`670ee90` full backend suite was 759 tests with 2 deprecation warnings. The
current worker-isolation package records 86 relevant backend tests and 764 full
backend tests; the earlier source benchmark measurements and three-sample
correction timing remain historical diagnostics and are not promoted to packaged
or 20-sample performance evidence.

Packaged diagnostic, **a850e7d/af8e2a1**: `--h07-benchmark` dispatches before normal
data-directory initialization, logging, backend and WebView. It creates only its own
temporary synthetic database. A Python audit guard denies network/child-process
operations (not an OS firewall). The launcher executes the explicit binary, validates
PID/path/hash/outcome, checks pre/post artifact hashes, and retains worker/log/manifest
files in a new evidence directory. Existing outputs are not overwritten. Worker
reports distinguish source from frozen execution. This workload imports its fixture
before read measurements: cache state is mixed, NOT cold-chain evidence.
Checkout observations are not embedded source-to-binary attestation; release
provenance remains UNKNOWN. Windows/Linux host gates remain required for this
desktop entry/build change. The final measurement and resource disposition are
recorded below and in the active H07 work package.
The earlier packaged 1k diagnostic produced 1000 trades/projections and 1003 ledger
events, matching its source snapshot. Its durable manifest is
`artifacts/evidence/h07/packaged-worker-1000-v1/manifest.json`, file SHA
`2f29069847b9d2b3c50a4e43ba7d1c3ba881abfc8a21fa88489037bad8d2f70f`; it remains
prior diagnostic evidence, not the final campaign below. That historical focused
H07/worker coverage was 66 PASS and the `670ee90` backend coverage was 759 PASS
with 2 warnings; the clean current local-CI result and its exact artifact hashes
are recorded in the worker-isolation section below and in H07.
Exact hashes, commands and platform limits are in active H07. New final DMG,
signing and clean-release provenance are NOT claimed.

Cold/warm/append-tail final campaign, **af8e2a1**: two runs × `1k/10k/100k`, with
20 fresh packaged-process samples for `cold`, 20 same-process post-warm-up
operation samples for `warm`, and 20 fresh packaged-process append-tail samples
per size. All 246 worker manifests passed packaged-process/path/hash/outcome checks;
all append-tail reports recorded `verification_mode=APPEND_TAIL` and
`verified_events_this_call=1`. The operation-level 100k cold Evidence Pack p95 was
`3212.6465 ms` / `3221.5029 ms` (run 1 / run 2), so the `<2s` planning target is
not met at that size. Warm and append-tail values are diagnostic only; OS page cache
is `UNCONTROLLED`, and process-level RSS/disk are `null` where not measured. Campaign
report embedded SHA-256 is `a691001a06cd3aa750a392aaaa981d4614255b3e66401530db02da530ef57617`;
the full report and manifest file hashes are recorded in H07. The later `30be78d`
campaign supplies the missing process-level RSS/temp evidence; H07 remains
`IMPLEMENTATION_REQUIRED` because the 100k target is still above `<2s>` and no
owner-approved resource disposition exists.

Process resource/projection evidence, **30be78d**: two runs at 100k with 3 cold,
3 append-tail and 20 fresh-process projection-rebuild samples per run, plus one
same-process warm sample per run, produced 54/54 `H07.packaged-manifest.v2`
resource reports with `MEASURED` RSS and isolated temporary-disk occupancy. All 40
projection rebuilds reported `ledger_valid=true`, `projections_written=100000`,
`100000/100000/100003` counts and the same deterministic snapshot. Projection
operation p95 was `6877.9656 / 7336.8517 ms`; packaged process p95 was
`8009.7547 / 8501.7438 ms`, with peak process RSS `888.1719 / 888.2656 MB` and
peak isolated temp footprint `388370264 B`. Resource sampling is diagnostic only:
OS page cache is uncontrolled, no support limit is claimed, and sampler/coverage
errors remain `UNKNOWN` rather than zero/PASS. Exact command, hashes, toolchain and
limitations are in the active H07 package. Campaign report embedded SHA-256 is
`ad45ae7441250d40489e4c02208dfbc7f00cdeb78063a22fe31c8ee3a91f3470`; full report
SHA-256 `c8e047f78979db3b7ec689365678071f624f8a3ddc9294b10665cc2e998835ef` and
campaign manifest SHA-256
`f78f6d6a7adc32d625420ae2fbde0441425fb1be9c22de81442369a1dc3e6a42`. The
development artifact is tied to `30be78d` with local-CI provenance `COMPLETE`, but
release provenance remains `UNKNOWN`; H07 is not closed.

Projection rebuild batch-write optimization, **67eafa2**: the rebuild path now
uses a reusable deterministic upsert statement with bounded 1,000-record
`executemany` batches. The delete/write/commit transaction boundary, projection
semantics, correction lineage, rollback behavior and schema are unchanged; resource
checks move from every row to before/after each bounded batch. A new red test for
the batch writer failed before implementation (`1 failed, 39 passed`) and the
focused H07 file passed `40/40` afterward; the combined H07/packaged-worker suite
passed `64/64`, and H07 plus P1-WP02 projection regression passed `52/52`.

The clean packaged campaign used two runs at 100k with 3 cold, 3 append-tail and
20 fresh-process projection-rebuild samples per run, plus one same-process warm
sample per run:

| Mod | Operation p95 R1 / R2 (ms) | Process p95 R1 / R2 (ms) | Peak process RSS R1 / R2 (MB) | Peak isolated temp R1 / R2 (B) |
|---|---:|---:|---:|---:|
| `cold` | 3350.5229 / 3152.2077 | 4434.6318 / 4137.1279 | 165.2969 / 163.3281 | 287690752 / 287690752 |
| `warm` | 329.9364 / 327.7377 | UNKNOWN (n=1) / UNKNOWN (n=1) | 163.1719 / 163.2812 | 287690752 / 287690752 |
| `append-tail` | 28.3022 / 25.2925 | 4236.1840 / 4176.3699 | 165.3750 / 163.4219 | 287773184 / 287760824 |
| `projection-rebuild` | 6718.6024 / 6287.9183 | 7919.5035 / 7359.8019 | 889.2812 / 888.3281 | 388370264 / 388370264 |

All 54/54 packaged manifests recorded `MEASURED` process resources. Every one of
the 40 projection rebuilds reported `ledger_valid=true`, `100000 trades /
100000 projections / 100003 ledger events`, `projections_written=100000` and the
same determinism snapshot
`f7df42fa141e9a903141fce3f6121093f31f5924d1c58e77939c2d78c753e0d8`. Compared with
the preceding `30be78d` campaign, projection p95 is lower in both runs, but OS
page cache is `UNCONTROLLED` and the two artifacts/runs do not establish an
isolated causal percentage improvement. The 100k cold p95 remains above `<2s>`;
this optimization therefore does not close H07 or authorize a support limit.

Evidence command:

```text
.venv/bin/python scripts/run_h07_measurement_campaign.py --executable "dist/Kuantra Terminal.app/Contents/MacOS/Kuantra Terminal" --artifact "dist/Kuantra Terminal.app" --output-dir artifacts/evidence/h07/resource-batch-67eafa2-20260909 --sizes 100000 --runs 2 --cold-samples 3 --warm-samples 3 --append-samples 3 --projection-rebuild-samples 20 --batch-size 1000 --timeout 1800
```

The campaign report embedded SHA-256 is
`8b37e07392569b928d78da17b1e11818f1dc0cbf3438f469fc4d39405ae319f3`; the full
report file SHA-256 is
`faa90561bfc92d0f3286e516ded334d7c15573c6bf79070562868729f6ef58b2` and the
campaign manifest file SHA-256 is
`31b5c2327043404a3e7e2408805e1eb47bedb74dc45b8cd2d11769bc4b08e317`.
Checkout commit is `67eafa2aaaa311ad8fb1488dec5f121c3e825f56`, tracked source
tree SHA-256 is
`f7925aab979cb164a92aeb8601e9a0edd0c5a5fc21f6a09e3da1f7c235346748` with clean
tracked status. The campaign ran on macOS 26.6.2 arm64 / Darwin 25.6.0 with
Python 3.11.16, Node v20.20.2, npm 10.8.2, uv 0.12.10 and PyInstaller 6.22.2;
backend/frontend lock SHA-256 values remain
`6291588602869af34e2a4db5d7244a627f4e139cbbd4b034b7cc07d890812399` and
`b392a59d09ade73564ce082b1a5bc1236618ebeee11703a992980cfd1812882c`.
The executed arm64 executable SHA-256 is
`1e0905928070c32539f1f1b25fc0ba0d9f50ab0ea62c06c84ec1a79087e7ece8`, the `.app`
tree SHA-256 is
`bcbac11a1981108e99195c9f7d2b38a0d22de189dfb1518f051108b838f10ffb`, the clean
local-CI report SHA-256 is
`7f3f26724548695faa7756aa982689d44393b9edd6e42d93e0ae576c2686f268`, and the
local-CI smoke report SHA-256 is
`04f74054b1f2ae9126005a7caeeb1e76ddca2972c386ad1d717bda0d042a8d13`.
Campaign contract is `real_data=false`, `credentials=false`, `network=false`,
`live_execution=false`, `support_limit_claim=false`; source fixture preparation
is `SOURCE_PROCESS`, source-to-binary attestation is `NOT_VERIFIED` and release
provenance is `UNKNOWN`. Local-CI provenance is `COMPLETE` for this development
artifact. This evidence is not a DMG, signing/notarization, Windows/Linux or
production claim.

Full-chain cold optimization and measurement-boundary disposition, **670ee90**:
the canonical JSON validator now takes an `orjson` fast path only after an exact
canonical-byte match (with conservative exponent handling); the existing strict
stdlib path remains authoritative for exponent, large-integer and other edge
cases. `get_evidence_pack` now reuses its already evaluated coverage and trade
snapshot and derives market context from that snapshot, preserving the public
compatibility behavior without repeated read work. No schema, ledger semantics,
funding/transfer event type or product authority changed. Two new red tests first
failed (`2 failed, 40 passed`); after implementation the focused H07 file passed
`42/42`, the combined H07/packaged-worker suite `66/66`, and the relevant H07,
projection, Evidence Pack and persistence regression set `96/96`. A source-only
cProfile diagnostic moved `get_evidence_pack` from about `5.720 s` to `4.677 s`
and `verify_chain` from about `5.392 s` to `4.527 s`; this is diagnostic guidance,
not a packaged SLA claim.

The clean packaged campaign used two runs at 100k with 3 fresh-process cold,
3 same-process warm, 3 fresh-process append-tail and 20 fresh-process
projection-rebuild samples per run:

| Mode | Operation p95 R1 / R2 (ms) | Process p95 R1 / R2 (ms) | Peak process RSS R1 / R2 (MB) | Peak isolated temp R1 / R2 (B) |
|---|---:|---:|---:|---:|
| `cold` | 2468.2571 / 2444.9360 | 3481.5726 / 3448.4742 | 163.3906 / 164.2188 | 287690752 / 287690752 |
| `warm` | 143.1432 / 144.6606 | UNKNOWN (n=1) / UNKNOWN (n=1) | 162.9688 / 163.2969 | 287690752 / 287690752 |
| `append-tail` | 25.9044 / 25.7300 | 3523.4416 / 3501.9004 | 163.4531 / 163.3750 | 287773184 / 287773184 |
| `projection-rebuild` | 5639.9834 / 5709.4251 | 6747.8792 / 6822.3076 | 887.3594 / 887.8750 | 388370264 / 388370264 |

All 54/54 manifests recorded `MEASURED` process resources. All 40 projection
rebuilds were valid, wrote 100000 projections from `100000/100000/100003`
trade/projection/ledger-event counts and produced the same snapshot
`f7df42fa141e9a903141fce3f6121093f31f5924d1c58e77939c2d78c753e0d8`. The cold
and projection p95 values are lower than the preceding packaged campaign in both
runs, but OS page cache is `UNCONTROLLED` and the artifacts/runs do not establish
an isolated causal percentage. The 100k cold operation p95 is still above the
`<2s>` planning target; H07 is not closed.

The explicit measurement boundary for this evidence is: one clean Mac
26.6.2 arm64 packaged `.app` executable, synthetic `H07-SYNTHETIC-V1` data at
100000 records, two runs, the sample counts above, network/credentials/real data/
live execution disabled, and uncontrolled OS cache. This boundary is valid for
reproducible development measurement only. It does not define a production SLO,
maximum supported history, resource cap or commercial support limit; any such
owner-approved disposition remains an explicit H07 gate. `UNKNOWN` warm process
percentiles stay `UNKNOWN`, and no artifact, source-to-binary, release, DMG,
signing/notarization, Windows or Linux claim is inferred.

Evidence command:

```text
.venv/bin/python scripts/run_h07_measurement_campaign.py --executable "dist/Kuantra Terminal.app/Contents/MacOS/Kuantra Terminal" --artifact "dist/Kuantra Terminal.app" --output-dir artifacts/evidence/h07/cold-chain-670ee90-20260909 --sizes 100000 --runs 2 --cold-samples 3 --warm-samples 3 --append-samples 3 --projection-rebuild-samples 20 --batch-size 1000 --timeout 1800
```

Campaign report embedded SHA-256 is
`65cb34aa9fdb982f109fc0d36b59c3e7e69d0d040e51bcb5da4a83162e458bde`; full
report SHA-256 is `df590c955af7e7233176f4600f5f95ca2b17c75c78e1f9fbf6bb259d9361b3d8`
and campaign manifest SHA-256 is
`54dbdc13dfce353d068ee5ff9dc90e56457d9a342fa83668207f124c70137a4c`. The
artifact is commit `670ee9016ecc133ed998c7274738ed1ec9d697fe`, tracked source
tree SHA-256 `68dc4ed4f8d65756489fcd0f6c92d39bedfd7b067bfee7c24a8af728b4141be9`,
with clean tracked status and local-CI provenance `COMPLETE`. The executed arm64
executable SHA-256 is
`301d366b2167b77604d8dfd610143de5b8924d2a728af42abc3e4d84c4f59836`; `.app`
tree SHA-256 is
`6b656164a7440c55099c10914189ede60744df3b940f26fb1b2e916cda6baad8`;
local-CI report SHA-256 is
`e72be9ad813bc7003608eebcc2d66caa543cf241775e1546dd94060e862760d0`; and
local-CI smoke report SHA-256 is
`7e6a29adceda53ad0b48700b99ec34c0614be578b492984ac30bb5fabfc9346b`. Backend
and frontend lock hashes remain
`6291588602869af34e2a4db5d7244a627f4e139cbbd4b034b7cc07d890812399` and
`b392a59d09ade73564ce082b1a5bc1236618ebeee11703a992980cfd1812882c`.

| Area | Evidence / remaining boundary |
|---|---|
| Runtime baseline | `a7b99b7`; fresh clean Mac local CI `MERGE READY`: 683 backend, 71 frontend, i18n 574/574, arm64 build and native smoke passed. Provenance is COMPLETE; H03 disabled/degraded tests and H06 privacy boundary tests are PASS; supply-chain audit remains an integrated step with commercial owner review explicitly deferred |
| Roadmap baseline | `03b7791`: G0–G7 proposal; no production/pilot gate passed by publishing a document |
| P1 foundations | Implementations recorded in historical packages; source completeness and financial accounting still open |
| Mac (historical clean DMG baseline) | H07 source `5a70f8b` passed clean arm64 locked local CI and exact read-only DMG/WKWebView smoke with provenance `COMPLETE`; local CI report SHA `c513b5f4ce3a14270277c1a9031bcf0b9d51a3271a84ebe59f7deb2daa06be01`, native smoke report SHA `413d5029e79276c66149ae4574be0ced14860a4ac72b7858e34490d6dc0e5c5e`, `.app` SHA `36c84e727a00c305176f7ee45f2f4c32b6693e76cd59021aaa889bc1a4554459`, exact DMG smoke report SHA `bc587f232c7f5d09c787412549d924aa8aa045524590bdcecdd3047490367963`, DMG SHA `f5183bee511352e97b6c4d6e363d0951fc32361d6a9d718ccfe3174752c45fc7`, mounted executable SHA `17508bbfa429689ab6adeeee419e166c604a15457a55a5f8a543bbb16b04cbc0`; Developer ID/notarization/Gatekeeper/second-host evidence remains open |
| H07 bounded baseline | Canonical correctness `a97499b`, packaged worker/launcher and final cold/warm/append-tail campaign `af8e2a1`, process-resource/projection campaign `30be78d`, bounded projection batch writer `67eafa2`, full-chain cold optimization `670ee90`, worker isolation/cache reuse `e3aacc8`→`4e761fa` and bounded native fixture sizing `198e712`. Latest 100k cold Evidence Pack p95 is `2321.8877 / 2332.4201 ms`; projection-rebuild process p95 is `6217.4225 / 6208.4966 ms`; all 366 packaged manifests and 120 projection samples are measured/valid and deterministic. Owner decision: 100k is stress-only, not a production support requirement. Native UI functional evidence for 1k/10k, the tested `<=10k` candidate boundary and the non-SLO timer instrumentation disposition are recorded; active-WP acceptance/archive reconciliation remains. Old `5a70f8b` timings are historical source-process evidence, not current cold-chain performance or packaged benchmark proof. |
| P2 | Short gaps-free Spot observations; controlled-disconnect observations INVALID. No source/live promotion |
| Product | No real-user data/pilot evidence; Faz 1/2 user exits unfulfilled |

## Open obligations and blockers

| ID | Classification | Obligation | Next handling |
|---|---|---|---|
| B1 | CLOSED | Timestamp pagination can skip records and overstate completeness | Closed by P1-WP16 / `ef909d1`; historical package retained in archive |
| B2 | CLOSED | Fee currency/unknown handling, perps identity/accounting and economic dedup are closed within the bounded P1-WP17–21 contracts; broader accounting remains outside scope | Keep full-account PnL/tax, funding/transfer completeness and unclaimed venue coverage as explicit `SCOPE_BOUNDARY`; reopen only with an approved scope package |
| B3/M1 | DEFERRED | Gap recovery waits for stream completion; bounded shutdown/injection tests missing | Complete before another long/24h soak; not primary product path |
| B4 | CLOSED | Mac runtime offline/degraded boundary, exact artifact provenance, mounted executable and WKWebView gate | N01 `05e826d`, N02 `cc0ad94`, H03 `62921f7`; Windows/Linux and distribution signing remain separate host/owner gates |
| H01 | CLOSED | Canonical journal/event/projection persistence under crash, transaction, read-only, disk/busy and concurrent import conditions | Test-only transaction hooks plus real Mac temporary-fixture evidence in `006e86e`; H02 schema/restore boundary remains separate |
| H02 | CLOSED | Supported legacy schema upgrade, interrupted migration/restore, corrupt backup, missing segment, archive traversal/symlink and incompatible future schema fail closed while preserving canonical lineage | `169c446`; archived [H02](../archive/strategy/work-packages/H02-schema-upgrade-restore-boundary.md); 19 focused and 651 backend tests PASS |
| H04 | CLOSED | Untrusted CSV/JSON/HTML, archive extraction, WebView bridge, gateway origin and redaction boundaries are fail-closed under bounded misuse tests | Code `1cf486e`, evidence source `ca94b83`; archived [H04](../archive/strategy/work-packages/H04-threat-model-trust-boundaries.md); 60 focused, 669 backend and 67 frontend tests PASS; exact DMG/WKWebView smoke PASS |
| H05 | DEFERRED | Machine-checkable locked dependency, deterministic SBOM, secret scan and build trust evidence is PASS; commercial license/notices and default-branch alert disposition are deferred | Archived [H05](../archive/strategy/work-packages/H05-supply-chain-sbom-license-secret-boundary.md); reopen before first commercial/release candidate; no LICENSE assumption or Dependabot merge now |
| H06 | CLOSED | Data directory permissions, keychain unavailable behavior, telemetry consent/spool, redacted support/export and privacy truth | Archived [H06](../archive/strategy/work-packages/H06-privacy-data-lifecycle-credential-boundary.md); bounded code/evidence `4270d33`/`a7b99b7`; 683 backend and 71 frontend tests, exact Mac DMG smoke PASS |
| H07 | CLOSED | Non-release synthetic performance/resource measurement, packaged cold/warm/append-tail/projection-rebuild distinction, candidate-band UI evidence and fail-closed boundaries | `e3aacc8`→`4e761fa` and `198e712` provide the Mac evidence: 366 packaged manifests, 120/120 valid projection samples, measured 1k/10k candidate-band behavior, native `wkwebview` evidence and explicit `UNKNOWN` handling. Owner decision: 100k is stress-only; no further 100k optimization or numeric commercial resource cap is required. H07 is archived at [H07](../archive/strategy/work-packages/H07-bounded-performance-resource-limits.md). Windows/Linux, signing and release evidence remain separate. |
| P1-WP27 | CLOSED | G0–G2 supported matrix, independent oracle and packaged import→review→Evidence Pack→export→reopen audit | `e042790` packaged report `PASS`; malformed/partial/unknown fail-closed, coverage propagation, same-second review reopen, scope guard and caller-data isolation are recorded in [archived P1-WP27](../archive/strategy/work-packages/P1-WP27-g0-g2-supported-matrix-audit.md). This is bounded Mac development evidence, not release or cross-platform proof. |
| P1-WP28 | BOUNDED COMPLETE / RELEASE GATES OPEN | macOS 12+ native arm64/x86_64 build, executable-derived provenance, exact per-architecture DMG smoke and native-host release contract | Source `dd58142` plus GitHub Actions run `34664574672` proves native arm64 and native `macos-15-intel` x86_64 build/test/package/exact mounted-DMG smoke. Both reports have `COMPLETE` provenance, matching executable architecture, `wkwebview`, `hdiutil verify: VALID` and truth-matrix SHA-256 `8c647721dc2349cc8fd99d046bf14738121ac4f9a0b7c8b87cdb9f1ccfe681ab`; Intel is no longer `PENDING_NATIVE_CI`. Phase 0 final release audit remains separate because N05 is intentionally ad-hoc `BLOCKED`; Universal2, Windows/Linux, N03 and signing are separate gates. |
| P1-WP29 | IN PROGRESS / OWNER-HOST OBLIGATIONS | Architecture-scoped trusted pilot package, exact evidence bundle, manifest/checksums and user instructions | Source `4298acd`, run `34721385803`: dual native package, exact DMG/local-tracking smoke and checksum PASS. Existing private Release refreshed with exactly two DMGs; installed Mac app updated with data preserved. Current hashes/tests are at the top of STATUS and archived WP31. N03 clean second profile/host, N05 signing/notarization, H05 commercial/dependency disposition and pilot-user read access remain separate obligations. |
| P1-WP31 | CLOSED / BOUNDED COMPLETE | Local TP1/TP2/TP3/SL revisions, exact provider-event quotes and separate estimated partial/full closes | Source `4298acd`, canonical Mac CI and both native exact DMGs PASS; pilot Release and installed app refreshed. [Archived WP31](../archive/strategy/work-packages/P1-WP31-local-tp-tracking.md) retains red/green, concurrency, rollback, rebuild/export/restore and UI evidence. Display-only quotes, old/imported records and actual external fills are not silently promoted. |
| P1-WP32 | IN PROGRESS / DEV EVIDENCE | Turkey-time trade dates, revisioned edit/correction, plan-synchronized TP/SL, declared leverage sizing, bounded quote refresh and unverified-unit money gating | Review round 2: stop/TP edits now drive the local plan (94 after a 95→90 stop edit no longer closes; 89 closes once), entry-time edits persist, failed refreshes demote prices to explicit stale last-known and recover, and unknown contract sizes produce no monetary figures. Backend **914** / frontend **192** / i18n **956**; focused review tests **11 passed**. Installed app and Releases unchanged; docs close-out and commit/push await owner direction. |
| P1-WP30 | CLOSED / BOUNDED COMPLETE | Free multi-asset journal entry, exact public quote provenance, explicit simulation and TradingView pending-observation boundary | Archived [P1-WP30](../archive/strategy/work-packages/P1-WP30-free-multi-asset-journal.md) with focused backend/regression **35 passed / 2 warnings** and current clean regression/local-CI evidence recorded above. No paid data/live order/release claim. |
| N03 | DEFERRED / HOST_REQUIRED | Clean second macOS profile/host install-lifecycle, quarantine observation and synthetic value-chain reopen | Execute at final macOS distribution/pilot validation with the exact packaged artifact; the pilot team's Intel Mac may be the selected host if clean-profile attestation is supplied. Current developer profile/temp data directory is insufficient and the criterion must not be marked PASS |
| N04 | CLOSED | Manual update/interrupted-update/uninstall data preservation and fail-closed schema rollback policy | Bounded packaged audit `3f4ba82` PASS; exact previous/current provenance and hashes recorded above. No automatic updater or real migration was added. |
| N05 | IN PROGRESS / OWNER_REQUIRED | Exact macOS DMG signing/notarization preflight and secretless distribution evidence | `121a5cd` implementation, 6 N05 contract tests plus 9 package-spec tests, 4 manifest tests, 6 Phase-0/workflow tests, clean arm64 local CI and exact mounted smoke are recorded; current v1.0.0 ad-hoc DMG is intentionally `BLOCKED` (report SHA `2ebf924a...`). Developer ID, hardened runtime, Gatekeeper and stapled-ticket evidence require owner/Apple host access; N03/H05 remain v1 gates, N06 is future multi-platform scope |
| WIN | DEFERRED / HOST_REQUIRED | Windows host/controller blocker and Linux final artifact evidence | Not a v1 Mac-only release gate or claim; reopen only after an explicit multi-platform expansion decision |
| VERIFY | HOST_REQUIRED | Historical P1-WP01 latest-SHA verification checkbox and remote/multi-OS evidence gaps | Preserve exact source criteria; current local gate is not a historical remote pass |
| OPS | HOST_REQUIRED / OWNER_DECISION_REQUIRED | Historical P2 network promotion, real disconnect, different-host bundle restore and remote verification | Reference archived open-item index; no automatic closure or permission for live work |
| PRODUCT | OWNER_DECISION_REQUIRED | Review/pilot metrics, product license/notices, signing/host access, support/incident readiness | G2–G7 and explicit product-owner decisions; root `LICENSE`, `NOTICE` and `THIRD_PARTY_NOTICES.md` remain intentionally absent until commercial distribution is prepared |
| DEP | DEFERRED | Branch dependency audit is clean, but GitHub default branch currently retains two open npm alerts for the Vitest/test-time dependency chain | No merge while development-only; before release, remediate or record a time-bounded owner risk acceptance with applicability/mitigation |

All historical unchecked criteria remain discoverable in the
[archive obligation index](../archive/README.md). The archive is not a completed-work list.
Only evidence or an explicit superseding decision can close an obligation. The
registry records unchecked counts so accidental checkbox deletion is detected.

## Historical maintenance evidence (superseded by current evidence above)

P1-WP20 economic dedup/lifecycle contract was implemented in `5d691b9`; P1-WP21
propagation in `056b1ca`; N01 exact provenance in `05e826d`; N02 exact mounted-DMG/
WKWebView smoke in `cc0ad94`; H03 runtime degraded/offline boundary in `62921f7`;
P1-WP22 U01 in `ea4e12c`; P1-WP23 U02 in `51ee968`; P1-WP24 U03 in `afedb70`;
P1-WP25 U04 in `26751f7`; P1-WP26 U05 in `30dfcd7`; H01 canonical
persistence/recovery in `006e86e`; H02 schema upgrade/restore in `169c446`; H04
trust-boundary hardening in `1cf486e`; H05 machine-checkable supply-chain, SBOM and
secret boundary in `c089cd2`; and H06 privacy/data-lifecycle in `4270d33` with final
evidence `a7b99b7`. H04, deferred H05, completed H06, completed H07 and completed
P1-WP27 and N04 are archived; N03 is the current final-validation package. H05's commercial distribution gate
remains explicitly closed until
it is reopened with the required license/notice and dependency dispositions.

The 2026-09-08 H06 Mac evidence used locked dependencies and clean temporary data
directories: local CI was **MERGE READY**, with full backend **683**, frontend **71**,
i18n **574/574**, production build, arm64 desktop build, native `wkwebview` smoke,
packaging preflight, supply-chain audit step and provenance contract PASS. Source
commit `a7b99b7c540629eb3d9b595c05691200c8c0b81e`; tracked source tree SHA-256
`837fee0b94e43cecb06b49195d20b1d13b3b1b235eb8f7e3c521fcc546527c52`; local CI
report SHA-256 `ab71a75f8740a6ed444b14e2bfed429f3b6ad3197ddec8124289edde19220283`;
provenance **COMPLETE**. Local smoke report SHA-256
`c20b7313069a1217b119989102903c5a6311432c798b2d5a090afe6ab0b16176`, executable
SHA-256 `967cf5db996b91bf948763b0d1fe0a003d8cee228883bfc3abe6599dce1815bc`, and
`.app` SHA-256 `a0acd018b2366cb72209c4028473dbd2b5b31c7370f9b9c3c8c68f4e0e48f46e`.
Exact read-only DMG smoke report SHA-256
`5e4980ae1813eb36812d15032afe5d351060d5eb460ca7b41ca263c3603a1582`; DMG SHA-256
`7ec5226771dc3b9619c37b17b179043412d140d84b5e89a0262b5ed4805eaca3`; mounted
executable SHA-256 matched the local smoke value. Renderer `wkwebview`, controller
identity and clean detach passed. The smoke used the configured public Binance
stream; it is not offline runtime proof.
H05 archived supply-chain report SHA-256 `c180de2bffb92f279f1995c9fe4061a4e1c6b28628b428679b4aa01b5d74646f`:
lock contract PASS, 395-component deterministic inventory and source/DMG secret scan
PASS, but overall `OWNER_REVIEW_REQUIRED` because root license/notices are absent.
The six default-branch Dependabot alerts (1 critical, 1 high, 4 moderate) remain
open and were not merged. Advisory scans used network and are not offline proof.
No PnL, live execution, pilot, commercial package or production claim was opened.

Earlier H07 bounded evidence, superseded for the current performance disposition
by the `af8e2a1` campaign above, is recorded in
[H07](../archive/strategy/work-packages/H07-bounded-performance-resource-limits.md): deterministic
1k/10k/100k synthetic reports, indexed trade lookup, atomic grouped-batch
cancellation, streamed full-chain verification, correction/replay measurement,
dynamic RSS/disk budget abort/rollback boundaries, malformed/oversized plus
partial/unknown coverage fixtures, legacy/typed query mid-operation abort fixtures,
bounded frontend cancellation/read truth, ledger-only fingerprint/shared verifier,
append-tail verification, safe-persona surface gating, `f94ba8e` canonical-hash /
provenance cache and `5a70f8b` canonical JSON validation fast path are present.
Exact Mac arm64 app/DMG/WKWebView evidence is tied to code baseline `5a70f8b`; local
CI report SHA `c513b5f4ce3a14270277c1a9031bcf0b9d51a3271a84ebe59f7deb2daa06be01`, native
smoke report SHA `413d5029e79276c66149ae4574be0ced14860a4ac72b7858e34490d6dc0e5c5e`,
exact DMG smoke report SHA `bc587f232c7f5d09c787412549d924aa8aa045524590bdcecdd3047490367963`,
mounted executable SHA `17508bbfa429689ab6adeeee419e166c604a15457a55a5f8a543bbb16b04cbc0`
and DMG SHA `f5183bee511352e97b6c4d6e363d0951fc32361d6a9d718ccfe3174752c45fc7`.
At that historical baseline, the exact 100k report SHA was
`c92200c37fe1db0e7d13727d818060998d112c54c049e1c9bd81201ee57f5087`; append-tail
Evidence Pack p95 is `349.5183 ms`, export p95 is `340.3408 ms`, and projection
rebuild p95 is `4153.3801 ms` with `0 B` temporary-disk growth in the rebuild
operation. Separate no-cache full-chain audit samples were
`2217.7044 / 2190.9482 / 2208.2548 ms`, p95 `2216.36659 ms`; every `100003` event
was valid. At that historical baseline H07 remained `IMPLEMENTATION_REQUIRED`: the
append-tail path met the measured `<2s` planning target, but true no-cache cold
startup did not and resource acceptance gaps were not silently closed. The current
campaign supersedes those performance numbers; the safe-persona core read surface
is bounded and experimental surfaces are not promoted; auxiliary/disabled surfaces
remain outside the production capability claim. The current handoff is now the
H07 disposition recorded above: the worker-isolation implementation and the
two-run campaign are complete. The owner decision makes 100k stress-only; native
functional UI evidence for the 1k/10k candidate band is complete, while timer-gap
percentiles remain explicitly non-SLO/UNKNOWN. H07 close-out is complete; no further
100k optimization is presumed. P1-WP27's G0–G2 supported-matrix and packaged
value-chain acceptance audit is archived; N03 owns the current clean-profile/
second-host dependency; N03 remains a final validation obligation before pilot/release.
H05 license/notices and default-branch Dependabot remain deferred release gates;
no production or commercial package claim is allowed.

## Update protocol

Replace the relevant rows as work progresses; do not append a new full status report.
Each outcome must cite WP, code/evidence SHA, actual commands/results, platform,
unchecked criteria and next dependency. Keep this file concise; long history belongs
in completed packages/Git, not additional competing roadmaps.
