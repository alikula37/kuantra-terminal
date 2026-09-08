<!-- doc-role: current-status -->
# Current development status

Updated: 2026-09-08. Branch: `codex/p1-wp01-evidence-ledger`.
Roadmap: [KPR-001](PRODUCTION-READINESS-PLAN.md), current planning source, still Proposed
for new scope/estimates. Selecting one roadmap does not approve its commercial assumptions.

## Selected next work

**H07 — Active / IMPLEMENTATION_REQUIRED:**
[Bounded performance and resource limits](work-packages/H07-bounded-performance-resource-limits.md).
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
evidence. H07 is now the sole active non-release package. Neither package silently
became full tax/accounting scope or new venue scope. No other historical `Active` WP
is automatically queued. Pilot/release claims remain blocked by their explicit gates.

## Current evidence, not completion claims

| Area | Evidence / remaining boundary |
|---|---|
| Runtime baseline | `a7b99b7`; fresh clean Mac local CI `MERGE READY`: 683 backend, 71 frontend, i18n 574/574, arm64 build and native smoke passed. Provenance is COMPLETE; H03 disabled/degraded tests and H06 privacy boundary tests are PASS; supply-chain audit remains an integrated step with commercial owner review explicitly deferred |
| Roadmap baseline | `03b7791`: G0–G7 proposal; no production/pilot gate passed by publishing a document |
| P1 foundations | Implementations recorded in historical packages; source completeness and financial accounting still open |
| Mac (latest local evidence) | H07 source `3863288` passed clean arm64 locked local CI and exact read-only DMG/WKWebView smoke; DMG SHA `5f84d80eea209167d52709fe1d1bf3da1ec8d54e848769933986e3f43fd85ccb`, exact smoke report SHA `7fe0761f474ad72dcfb2fc907e3b2611c3607d31d42ec9fc883d7e43a9306d14`, mounted executable SHA `ffc1fd0358d54bafc5f44b4e22b6622a00945a9369d1c2c778fcb7766327c438`; Developer ID/notarization/Gatekeeper/second-host evidence remains open |
| H07 bounded baseline | Code `3863288` on clean Mac arm64: 713 backend, 100 frontend, i18n 608/608, local CI `MERGE READY`; legacy and exact-coverage typed trade queries abort mid-stream at the cooperative resource boundary without returning partial results. Evidence Pack/Reconciliation Inbox/Weekly Review/CSV preview plus Dashboard/Quant Analytics/Header portfolio, JournalView trade-list, MAE/MFE, SettingsView portfolio-summary, Charts/TradingViewChart historical OHLCV and plugin registry/ModStore read surfaces have bounded AbortSignal, stale-response suppression and explicit loading/error truth; malformed successful payloads fail closed, unavailable analytics never becomes a zero scorecard/empty journal/chart, historical candles never become synthetic live ticks, Settings never falls back to zero balance, and malformed registry metadata never becomes capability. Ledger verification now uses an evidence-events-only append fingerprint with no persistent SQLite verifier connection; projection repository and TradeReadAdapter share the verifier, so projection-only commits do not invalidate ledger verification while ledger appends still do. Exact DMG/WKWebView smoke is PASS with provenance COMPLETE: report `7fe0761...`, DMG `5f84d80...`, mounted executable `ffc1fd0...`; local CI report `f9a2e18...`, `.app` `0e71fc1...`. Current artifact-bound 100k Evidence Pack p95 `4187.8654 ms` (cold first verification included), Evidence Pack p50 `343.8738 ms`, export p95 `344.4804 ms`, projection rebuild p95 `6316.4108 ms`, max operation RSS `335.75 MB`, temporary disk `0 B` for projection rebuild; the `<2s` planning target is not met and H07 remains `IMPLEMENTATION_REQUIRED` |
| P2 | Short gaps-free Spot observations; controlled-disconnect observations INVALID. No source/live promotion |
| Product | No real-user data/pilot evidence; Faz 1/2 user exits unfulfilled |

## Open obligations and blockers

| ID | Classification | Obligation | Next handling |
|---|---|---|---|
| B1 | CLOSED | Timestamp pagination can skip records and overstate completeness | Closed by P1-WP16 / `ef909d1`; historical package retained in archive |
| B2 | IMPLEMENTATION_REQUIRED | Fee currency/unknown handling, perps identity/accounting and economic dedup | P1-WP17–20 and P1-WP21 propagation are closed within their bounded contracts. Full account PnL/tax accounting remains out of scope |
| B3/M1 | DEFERRED | Gap recovery waits for stream completion; bounded shutdown/injection tests missing | Complete before another long/24h soak; not primary product path |
| B4 | CLOSED | Mac runtime offline/degraded boundary, exact artifact provenance, mounted executable and WKWebView gate | N01 `05e826d`, N02 `cc0ad94`, H03 `62921f7`; Windows/Linux and distribution signing remain separate host/owner gates |
| H01 | CLOSED | Canonical journal/event/projection persistence under crash, transaction, read-only, disk/busy and concurrent import conditions | Test-only transaction hooks plus real Mac temporary-fixture evidence in `006e86e`; H02 schema/restore boundary remains separate |
| H02 | CLOSED | Supported legacy schema upgrade, interrupted migration/restore, corrupt backup, missing segment, archive traversal/symlink and incompatible future schema fail closed while preserving canonical lineage | `169c446`; archived [H02](../archive/strategy/work-packages/H02-schema-upgrade-restore-boundary.md); 19 focused and 651 backend tests PASS |
| H04 | CLOSED | Untrusted CSV/JSON/HTML, archive extraction, WebView bridge, gateway origin and redaction boundaries are fail-closed under bounded misuse tests | Code `1cf486e`, evidence source `ca94b83`; archived [H04](../archive/strategy/work-packages/H04-threat-model-trust-boundaries.md); 60 focused, 669 backend and 67 frontend tests PASS; exact DMG/WKWebView smoke PASS |
| H05 | DEFERRED | Machine-checkable locked dependency, deterministic SBOM, secret scan and build trust evidence is PASS; commercial license/notices and default-branch alert disposition are deferred | Archived [H05](../archive/strategy/work-packages/H05-supply-chain-sbom-license-secret-boundary.md); reopen before first commercial/release candidate; no LICENSE assumption or Dependabot merge now |
| H06 | CLOSED | Data directory permissions, keychain unavailable behavior, telemetry consent/spool, redacted support/export and privacy truth | Archived [H06](../archive/strategy/work-packages/H06-privacy-data-lifecycle-credential-boundary.md); bounded code/evidence `4270d33`/`a7b99b7`; 683 backend and 71 frontend tests, exact Mac DMG smoke PASS |
| H07 | IMPLEMENTATION_REQUIRED | Deterministic 1k/10k/100k synthetic performance baselines, resource limits and explicit cancellation/failure truth | `f0b93ba` benchmark/index path, `779e2d7` atomic grouped-batch cancellation, `d2463b2` streamed integrity verification, `4e85e3f` correction/replay measurement, `46531e4`/`6af4fd9` dynamic budget boundary, `6748d96` bounded input/coverage fail-closed fixtures, `5137383` legacy/typed query mid-operation abort, `27b3404` bounded value-chain frontend cancellation, `42d67c6` dashboard/analytics/header read truth, `3de57c5` JournalView trade-list read truth, `f57da9d` MAE/MFE read truth, `3fa98a9` SettingsView portfolio-summary read truth, `dd0639b` Charts/TradingViewChart historical read truth, `950af74` plugin registry/ModStore read truth, `da9af9b` initial ledger verification cache, `2da9fe1` projection verifier reuse, `f551b1f` WAL boundary test and `3863288` ledger-only fingerprint/shared verifier are present. Current exact Mac 100k evidence is artifact-bound and non-release; cold Evidence Pack p95 still exceeds the planning target while projection rebuild p95 has `0 B` operation temporary disk, so the next bounded work is cold Evidence Pack verification or explicit target classification |
| WIN | HOST_REQUIRED | Windows host/controller blocker | Historical P0-WP11 reference; verify on Windows before platform claim |
| VERIFY | HOST_REQUIRED | Historical P1-WP01 latest-SHA verification checkbox and remote/multi-OS evidence gaps | Preserve exact source criteria; current local gate is not a historical remote pass |
| OPS | HOST_REQUIRED / OWNER_DECISION_REQUIRED | Historical P2 network promotion, real disconnect, different-host bundle restore and remote verification | Reference archived open-item index; no automatic closure or permission for live work |
| PRODUCT | OWNER_DECISION_REQUIRED | Review/pilot metrics, product license/notices, signing/host access, support/incident readiness | G2–G7 and explicit product-owner decisions; root `LICENSE`, `NOTICE` and `THIRD_PARTY_NOTICES.md` remain intentionally absent until commercial distribution is prepared |
| DEP | DEFERRED | Branch dependency audit is clean, but GitHub default branch retains five open npm alerts | No merge while development-only; before release, remediate or record a time-bounded owner risk acceptance with applicability/mitigation |

All historical unchecked criteria remain discoverable in the
[archive obligation index](../archive/README.md). The archive is not a completed-work list.
Only evidence or an explicit superseding decision can close an obligation. The
registry records unchecked counts so accidental checkbox deletion is detected.

## Latest maintenance handoff

P1-WP20 economic dedup/lifecycle contract was implemented in `5d691b9`; P1-WP21
propagation in `056b1ca`; N01 exact provenance in `05e826d`; N02 exact mounted-DMG/
WKWebView smoke in `cc0ad94`; H03 runtime degraded/offline boundary in `62921f7`;
P1-WP22 U01 in `ea4e12c`; P1-WP23 U02 in `51ee968`; P1-WP24 U03 in `afedb70`;
P1-WP25 U04 in `26751f7`; P1-WP26 U05 in `30dfcd7`; H01 canonical
persistence/recovery in `006e86e`; H02 schema upgrade/restore in `169c446`; H04
trust-boundary hardening in `1cf486e`; H05 machine-checkable supply-chain, SBOM and
secret boundary in `c089cd2`; and H06 privacy/data-lifecycle in `4270d33` with final
evidence `a7b99b7`. H04, deferred H05 and completed H06 are archived; H07 is the
current package. H05's commercial distribution gate remains explicitly closed until
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
The five default-branch Dependabot alerts (1 critical, 1 high, 3 moderate) remain
open and were not merged. Advisory scans used network and are not offline proof.
No PnL, live execution, pilot, commercial package or production claim was opened.

H07's current bounded evidence is recorded in
[H07](work-packages/H07-bounded-performance-resource-limits.md): deterministic
1k/10k/100k synthetic reports, indexed trade lookup, atomic grouped-batch
cancellation, streamed full-chain verification, correction/replay measurement,
dynamic RSS/disk budget abort/rollback boundaries, `6748d96` malformed/oversized
plus partial/unknown coverage fixtures, `5137383` legacy/typed query
mid-operation abort fixtures, `27b3404` value-chain frontend cancellation
fixtures, `42d67c6` dashboard/analytics/header read truth fixtures, `3de57c5`
JournalView trade-list read truth fixtures, `f57da9d` MAE/MFE read truth fixtures,
`3fa98a9` SettingsView portfolio-summary read truth fixtures, `dd0639b` Charts/
TradingViewChart historical read truth fixtures, `950af74` plugin registry/ModStore
read truth fixtures, `da9af9b` initial unchanged-ledger verification cache,
`2da9fe1` projection verifier reuse, `f551b1f` WAL boundary test and `3863288`
ledger-only fingerprint/shared verifier are present. Exact Mac arm64 app/DMG/WKWebView
evidence is tied to code baseline `3863288`;
local CI report SHA
`f9a2e18620a68c3eb482c2e7412dc80de20beee96a925095e966d8f94068a382`, exact DMG
smoke report SHA `7fe0761f474ad72dcfb2fc907e3b2611c3607d31d42ec9fc883d7e43a9306d14`,
mounted executable SHA `ffc1fd0358d54bafc5f44b4e22b6622a00945a9369d1c2c778fcb7766327c438`
and DMG SHA `5f84d80eea209167d52709fe1d1bf3da1ec8d54e848769933986e3f43fd85ccb`.
The exact 100k report SHA is
`35c20c31fdab0391f6a39d1ac06722b2e8b37d4c0ccaf3ee5e397d4fbe4c2987`; cold Evidence
Pack p95 still does not meet the planning target, while projection rebuild p95 is
`6316.4108 ms` with `0 B` temporary-disk growth in the rebuild operation. H07 remains
`IMPLEMENTATION_REQUIRED`. Safe-persona read surfaces listed in the H07 work package
have current bounded evidence; auxiliary and disabled surfaces are not promoted. Next
handoff is a cold Evidence Pack verification budget audit.
H05 license/notices and default-branch Dependabot remain deferred release gates;
no production or commercial package claim is allowed.

## Update protocol

Replace the relevant rows as work progresses; do not append a new full status report.
Each outcome must cite WP, code/evidence SHA, actual commands/results, platform,
unchecked criteria and next dependency. Keep this file concise; long history belongs
in completed packages/Git, not additional competing roadmaps.
