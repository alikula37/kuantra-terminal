<!-- doc-role: current-status -->
# Current development status

Updated: 2026-09-08. Branch: `codex/p1-wp01-evidence-ledger`.
Roadmap: [KPR-001](PRODUCTION-READINESS-PLAN.md), current planning source, still Proposed
for new scope/estimates. Selecting one roadmap does not approve its commercial assumptions.

## Selected next work

**P1-WP25 — Ready:**
[U04 weekly review and as-of determinism boundary](work-packages/P1-WP25-weekly-review-asof-boundary.md).
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
in `afedb70`. Neither package silently became full tax/accounting scope or new venue
scope. The next bounded implementation is U04: deterministic weekly review and as-of
boundary. No other historical `Active` WP is automatically queued. Pilot/release
claims remain blocked by their explicit gates.

## Current evidence, not completion claims

| Area | Evidence / remaining boundary |
|---|---|
| Runtime baseline | `afedb70`; fresh clean Mac local CI `MERGE READY`: 629 backend, 59 frontend, i18n 528/528, arm64 build and native smoke passed. Exact DMG-mounted smoke and release provenance are PASS; H03 disabled/degraded tests are PASS |
| Roadmap baseline | `03b7791`: G0–G7 proposal; no production/pilot gate passed by publishing a document |
| P1 foundations | Implementations recorded in historical packages; source completeness and financial accounting still open |
| Mac (latest WP24 evidence) | Exact read-only DMG-mounted smoke PASS for source `afedb70`: DMG SHA `53ec57a3f65fc2a489e7c9e130ee9a0654cbe4f423b9297738d83223701f42fd`, mounted executable SHA `4d6aefb9c3898811c8020046fb9f16c896ee91bf4bc1bf5abbda977384869bd9`, `wkwebview`, controller ready, detach PASS. Ad-hoc signature is only packaging preflight; Developer ID/notarization/Gatekeeper/second-host evidence remains open |
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
in `cc0ad94`, H03 runtime degraded/offline boundary in `62921f7`, P1-WP22 U01 in
`ea4e12c`, P1-WP23 U02 in `51ee968` and P1-WP24 U03 in `afedb70`; these are archived
with focused/full test and Mac evidence. The 2026-09-08 Mac evidence for WP24 used
locked dependencies and temporary data directories: local CI was `MERGE READY`, with
full backend **629**, frontend **59**, i18n **528/528**, production build, arm64
desktop build, native `wkwebview` smoke and packaging preflight. Local CI source
commit `afedb70edebb990ceb19555b4312460554fdbc56`; tracked source tree SHA
`0ac3d9f65e1d839ef4a48d51785479e45e23d8aeed4195c5cd47c77fd5dd81c6`; provenance
`COMPLETE`; release validator PASS; executable SHA
`4d6aefb9c3898811c8020046fb9f16c896ee91bf4bc1bf5abbda977384869bd9`; `.app` SHA
`9803f07916e48d02f3d8b684fe88b22957b5b627bfecf524be59bf430733a859`. Exact WP24
DMG evidence is DMG SHA
`53ec57a3f65fc2a489e7c9e130ee9a0654cbe4f423b9297738d83223701f42fd` and mounted
executable SHA `4d6aefb9c3898811c8020046fb9f16c896ee91bf4bc1bf5abbda977384869bd9`,
with read-only mount, explicit executable, `wkwebview`, controller ready and detach
PASS. `uv --offline` is dependency-preparation evidence only; the default runtime
smoke still attempts the configured public market-data connection. H03 disabled/
degraded tests cover the explicit no-network boundary. Branch `npm audit` reported
zero findings, while the GitHub default branch still exposes five open npm Dependabot
alerts. Source identity conflicts, unknown position mode, incomplete lifecycle,
funding/transfer schema, Windows/Linux host evidence, licensing, pilot and release-
owner decisions remain boundaries; no PnL, live execution or pilot claim was opened.
The next handoff is P1-WP25 U04.

P1-WP24 `afedb70` completed the bounded canonical Evidence Pack and deterministic
JSON/HTML/CSV export boundary. Clean local CI was `MERGE READY`: backend **629**,
frontend **59**, i18n **528/528**, arm64 build, native smoke and provenance contract
PASS. Exact mounted-DMG smoke used a read-only mount and the explicit mounted
executable; source `afedb70`, provenance `COMPLETE`, release validator PASS, DMG SHA
`53ec57a3f65fc2a489e7c9e130ee9a0654cbe4f423b9297738d83223701f42fd`, mounted
executable SHA `4d6aefb9c3898811c8020046fb9f16c896ee91bf4bc1bf5abbda977384869bd9`,
`wkwebview`/controller ready and detach PASS. No new ledger schema or funding/transfer
event was introduced. Next active contract: P1-WP25 U04 weekly review and as-of
determinism boundary.

## Update protocol

Replace the relevant rows as work progresses; do not append a new full status report.
Each outcome must cite WP, code/evidence SHA, actual commands/results, platform,
unchecked criteria and next dependency. Keep this file concise; long history belongs
in completed packages/Git, not additional competing roadmaps.
