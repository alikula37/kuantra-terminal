<!-- doc-role: current-status -->
# Current development status

Updated: 2026-09-08. Branch: `codex/p1-wp01-evidence-ledger`.
Roadmap: [KPR-001](PRODUCTION-READINESS-PLAN.md), current planning source, still Proposed
for new scope/estimates. Selecting one roadmap does not approve its commercial assumptions.

## Selected next work

**P1-WP22 — InProgress:**
[R4 value-chain integration gate](work-packages/P1-WP22-value-chain-integration.md).
P1-WP16 timestamp completeness was verified in `ef909d1`; P1-WP17 source identity
and support boundary was verified in `930d25a`; P1-WP18 fee/precision/unit truth was
verified in `0c7d11f`; P1-WP19 funding/corrections/account coverage was verified in
`f67e732`; P1-WP20 economic dedup/lifecycle was verified in `5d691b9`. P1-WP21
journal/projection/evidence propagation is complete in `056b1ca`; N01 exact build
provenance is complete in `05e826d`; N02 exact mounted-DMG/WKWebView smoke is
complete in `cc0ad94`; H03 runtime degraded/offline boundary is complete in
`62921f7`. Neither package silently became full tax/accounting scope or new venue
scope. The next bounded implementation is the R4 import → reconciliation → Trade
Evidence Pack/export integration gate. No other historical `Active` WP is
automatically queued. Weekly review remains a later R5 package and is not implied by
R4.

## Current evidence, not completion claims

| Area | Evidence / remaining boundary |
|---|---|
| Runtime baseline | `62921f7`; fresh Mac local CI `MERGE READY`: 615 backend, 54 frontend, i18n 480/480, arm64 build and native smoke passed. Exact DMG-mounted smoke and release provenance are PASS; H03 disabled/degraded tests are PASS |
| Roadmap baseline | `03b7791`: G0–G7 proposal; no production/pilot gate passed by publishing a document |
| P1 foundations | Implementations recorded in historical packages; source completeness and financial accounting still open |
| Mac | Exact read-only DMG-mounted executable smoke PASS: DMG SHA `5a0010a919ba8a6a296531486918379d5bd58257b86445a76fb14a02089e09e6`, executable SHA `2d53c4c2c0b894a43127c34be76c53726fe2130d0dbcc9583282dba776fa9f44`, `wkwebview`, controller ready, detach PASS. Ad-hoc signature is only packaging preflight; Developer ID/notarization/Gatekeeper/second-host evidence remains open |
| P2 | Short gaps-free Spot observations; controlled-disconnect observations INVALID. No source/live promotion |
| Product | No real-user data/pilot evidence; Faz 1/2 user exits unfulfilled |

## Open obligations and blockers

| ID | Classification | Obligation | Next handling |
|---|---|---|---|
| B1 | CLOSED | Timestamp pagination can skip records and overstate completeness | Closed by P1-WP16 / `ef909d1`; historical package retained in archive |
| B2 | IMPLEMENTATION_REQUIRED | Fee currency/unknown handling, perps identity/accounting and economic dedup | P1-WP17–20 and P1-WP21 propagation are closed within their bounded contracts. Full account PnL/tax accounting remains out of scope |
| B3/M1 | DEFERRED | Gap recovery waits for stream completion; bounded shutdown/injection tests missing | Complete before another long/24h soak; not primary product path |
| B4 | CLOSED | Mac runtime offline/degraded boundary, exact artifact provenance, mounted executable and WKWebView gate | N01 `05e826d`, N02 `cc0ad94`, H03 `62921f7`; Windows/Linux and distribution signing remain separate host/owner gates |
| WIN | HOST_REQUIRED | Windows host/controller blocker | Historical P0-WP11 reference; verify on Windows before platform claim |
| VERIFY | HOST_REQUIRED | Historical P1-WP01 latest-SHA verification checkbox and remote/multi-OS evidence gaps | Preserve exact source criteria; current local gate is not a historical remote pass |
| OPS | HOST_REQUIRED / OWNER_DECISION_REQUIRED | Historical P2 network promotion, real disconnect, different-host bundle restore and remote verification | Reference archived open-item index; no automatic closure or permission for live work |
| PRODUCT | OWNER_DECISION_REQUIRED | Review/pilot metrics, MIT LICENSE/notices, signing/host access, support/incident readiness | G2–G7 and explicit product-owner decisions; `LICENSE`, `NOTICE` and `THIRD_PARTY_NOTICES.md` are currently absent |
| DEP | OWNER_DECISION_REQUIRED | Branch dependency audit is clean, but GitHub default branch retains five open npm alerts | Branch `npm audit`: 0 vulnerabilities. Default-branch alerts remain open until an approved PR merge or explicit repository action |

All historical unchecked criteria remain discoverable in the
[archive obligation index](../archive/README.md). The archive is not a completed-work list.
Only evidence or an explicit superseding decision can close an obligation. The
registry records unchecked counts so accidental checkbox deletion is detected.

## Latest maintenance handoff

P1-WP20 economic dedup/lifecycle contract was implemented in `5d691b9` and its
historical evidence record is archived. P1-WP21 propagation was implemented in
`056b1ca`, N01 exact provenance in `05e826d`, N02 exact mounted-DMG/WKWebView smoke
in `cc0ad94`, and H03 runtime degraded/offline boundary in `62921f7`; all are
archived or recorded with focused/full test and Mac evidence. The fresh 2026-09-08
Mac audit used locked dependencies and temporary data directories: local CI was
`MERGE READY`, with frontend **54**, i18n **480/480**, full backend **615**, production
build, arm64 desktop build, native `wkwebview` smoke and packaging preflight. H03
focused tests cover explicit env disable, no socket scheduling, preserved last real
value with `DEGRADED`, status-only transition broadcast, disabled health/ticker/
WebSocket/desktop contracts and local CSV preview continuity. Local CI source commit
`62921f72df12c3bf50cf10c05e903ad463d3ec00`; provenance `COMPLETE`; release validator
PASS; executable SHA `91308c4b60a0b9f5685fd3392d319a29e15b73189a56a1a96364f0e71d36a521`;
`.app` artifact SHA `1631e5e38d7b3f773567e7635d5055ea26b3893fab1b09aa58d0e9adc7c2b921`.
The exact N02 DMG evidence remains DMG SHA `5a0010a919ba8a6a296531486918379d5bd58257b86445a76fb14a02089e09e6`
and mounted executable SHA `2d53c4c2c0b894a43127c34be76c53726fe2130d0dbcc9583282dba776fa9f44`.
Ad-hoc signature is packaging preflight only, not Developer ID/notarization/Gatekeeper.
Branch `npm audit` reported zero findings, while the GitHub default branch still exposes
five open npm Dependabot alerts. Source identity conflicts, unknown position mode,
incomplete lifecycle, funding/transfer schema, Windows/Linux host evidence, licensing,
pilot and release-owner decisions remain boundaries; no PnL, live execution or pilot
claim was opened. Next active contract: P1-WP22 R4.

## Update protocol

Replace the relevant rows as work progresses; do not append a new full status report.
Each outcome must cite WP, code/evidence SHA, actual commands/results, platform,
unchecked criteria and next dependency. Keep this file concise; long history belongs
in completed packages/Git, not additional competing roadmaps.
