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
| Mac (latest local evidence) | H07 source `bf30860` passed clean arm64 locked local CI and exact read-only DMG/WKWebView smoke; DMG SHA `e264df8d29b37c46efb278b58270eb8b63fab1eacbe5035b0b0a8631c08e84c2`, exact smoke report SHA `6ff74f30ca5ac87f8c00f22558fbca56c549f15b62cce0f19e13a58715073707`, mounted executable SHA `eca9eeea7277ce95cad92e1a7d49434c80f89e2940439c16b7562afe01296ef7`; Developer ID/notarization/Gatekeeper/second-host evidence remains open |
| H07 bounded baseline | Code `bf30860` on clean Mac arm64: 714 backend, 100 frontend, i18n 608/608, local CI `MERGE READY`; legacy and exact-coverage typed trade queries abort mid-stream at the cooperative resource boundary without returning partial results. Evidence Pack/Reconciliation Inbox/Weekly Review/CSV preview plus Dashboard/Quant Analytics/Header portfolio, JournalView trade-list, MAE/MFE, SettingsView portfolio-summary, Charts/TradingViewChart historical OHLCV and plugin registry/ModStore read surfaces have bounded AbortSignal, stale-response suppression and explicit loading/error truth; malformed successful payloads fail closed, unavailable analytics never becomes a zero scorecard/empty journal/chart, historical candles never become synthetic live ticks, Settings never falls back to zero balance, and malformed registry metadata never becomes capability. Ledger verification now uses an evidence-events-only append fingerprint with no persistent SQLite verifier connection; projection repository and TradeReadAdapter share the verifier, and append-only cached prefixes are reused for tail verification. Exact DMG/WKWebView smoke is PASS with provenance COMPLETE: report `6ff74f3...`, DMG `e264df8...`, mounted executable `eca9eee...`; local CI report `d0575d7...`, `.app` `0168b77...`. Current artifact-bound 100k append-tail Evidence Pack p95 `353.6237 ms`, no-cache full-chain audit p95 `5307.20623 ms`, export p95 `341.1627 ms`, projection rebuild p95 `6430.7846 ms`, max operation RSS `319.0156 MB`, temporary disk `0 B` for projection rebuild; the append-tail workload meets `<2s`, but true no-cache cold startup does not, so H07 remains `IMPLEMENTATION_REQUIRED` |
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
| H07 | IMPLEMENTATION_REQUIRED | Deterministic 1k/10k/100k synthetic performance baselines, resource limits and explicit cancellation/failure truth | `f0b93ba` benchmark/index path, `779e2d7` atomic grouped-batch cancellation, `d2463b2` streamed integrity verification, `4e85e3f` correction/replay measurement, `46531e4`/`6af4fd9` dynamic budget boundary, `6748d96` bounded input/coverage fail-closed fixtures, `5137383` legacy/typed query mid-operation abort, `27b3404` bounded value-chain frontend cancellation, `42d67c6` dashboard/analytics/header read truth, `3de57c5` JournalView trade-list read truth, `f57da9d` MAE/MFE read truth, `3fa98a9` SettingsView portfolio-summary read truth, `dd0639b` Charts/TradingViewChart historical read truth, `950af74` plugin registry/ModStore read truth, `da9af9b` initial ledger verification cache, `2da9fe1` projection verifier reuse, `f551b1f` WAL boundary test, `3863288` ledger-only fingerprint/shared verifier and `bf30860` incremental append-tail verification are present. Current exact Mac evidence is artifact-bound and non-release; append-tail Evidence Pack p95 is below `<2s`, but no-cache full-chain cold p95 is `5307.20623 ms`, so the target is not globally closed and the next handling is explicit cold-target classification plus remaining H07 acceptance gaps |
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
`2da9fe1` projection verifier reuse, `f551b1f` WAL boundary test, `3863288`
ledger-only fingerprint/shared verifier and `bf30860` incremental append-tail
verification are present. Exact Mac arm64 app/DMG/WKWebView evidence is tied to
code baseline `bf30860`;
local CI report SHA
`d0575d7df1e1345e65cfb2f6e2e5c74fce565ea6c480b460c2c054adcc9b1837`, exact DMG
smoke report SHA `6ff74f30ca5ac87f8c00f22558fbca56c549f15b62cce0f19e13a58715073707`,
mounted executable SHA `eca9eeea7277ce95cad92e1a7d49434c80f89e2940439c16b7562afe01296ef7`
and DMG SHA `e264df8d29b37c46efb278b58270eb8b63fab1eacbe5035b0b0a8631c08e84c2`.
The exact 100k report SHA is
`9633c8dc66dabd29b3f52a5e18e54a8547eb47351dfc3502452566d291ff305a`; append-tail
Evidence Pack p95 is `353.6237 ms`, while the separate no-cache full-chain audit on
the same artifact dataset measured `5309.6422 / 5280.5680 / 5285.2825 ms` with p95
`5307.20623 ms`. Projection rebuild p95 is `6430.7846 ms` with `0 B` temporary-disk
growth in the rebuild operation. H07 remains `IMPLEMENTATION_REQUIRED`: the
append-tail path meets the measured `<2s` planning target, but true no-cache cold
startup does not and remaining H07 acceptance gaps are not silently closed.
Safe-persona read surfaces listed in the H07 work package have current bounded
evidence; auxiliary and disabled surfaces are not promoted. Next handoff is explicit
cold-target classification and the remaining H07 acceptance audit.
H05 license/notices and default-branch Dependabot remain deferred release gates;
no production or commercial package claim is allowed.

## Update protocol

Replace the relevant rows as work progresses; do not append a new full status report.
Each outcome must cite WP, code/evidence SHA, actual commands/results, platform,
unchecked criteria and next dependency. Keep this file concise; long history belongs
in completed packages/Git, not additional competing roadmaps.
