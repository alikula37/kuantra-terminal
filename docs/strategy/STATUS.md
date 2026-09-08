<!-- doc-role: current-status -->
# Current development status

Updated: 2026-09-08. Branch: `codex/p1-wp01-evidence-ledger`.
Roadmap: [KPR-001](PRODUCTION-READINESS-PLAN.md), current planning source, still Proposed
for new scope/estimates. Selecting one roadmap does not approve its commercial assumptions.

## Selected next work

**H04 — Ready:**
[Threat model and trust boundaries](work-packages/H04-threat-model-trust-boundaries.md).
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
in `169c446`. Neither package
silently became full tax/accounting scope or new venue scope. The next bounded
implementation is H04: threat model and trust boundaries. No other historical
`Active` WP is automatically queued. Pilot/release claims remain blocked by their
explicit gates.

## Current evidence, not completion claims

| Area | Evidence / remaining boundary |
|---|---|
| Runtime baseline | `ed689a0`; fresh clean Mac local CI `MERGE READY`: 651 backend, 67 frontend, i18n 560/560, arm64 build and native smoke passed. Exact DMG-mounted smoke and release provenance are PASS; H03 disabled/degraded tests are PASS |
| Roadmap baseline | `03b7791`: G0–G7 proposal; no production/pilot gate passed by publishing a document |
| P1 foundations | Implementations recorded in historical packages; source completeness and financial accounting still open |
| Mac (latest H01 evidence) | Exact read-only DMG-mounted smoke PASS for source `006e86e`: DMG SHA `80764167ba924db4d918dfccb893936b1ac95d72931524351a0c4bd8a37530ad`, mounted executable SHA `90f3b06f9cde166eacb7310927b600fb3b6f0c1195435c99cca0d7f721a9ce60`, `wkwebview`, controller ready, detach PASS. Ad-hoc signature is only packaging preflight; Developer ID/notarization/Gatekeeper/second-host evidence remains open |
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
| H04 | IMPLEMENTATION_REQUIRED | Untrusted CSV/JSON/HTML, archive extraction, WebView bridge and gateway trust boundaries require misuse tests and fail-closed behavior | Current bounded package: [H04](work-packages/H04-threat-model-trust-boundaries.md) |
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

P1-WP20 economic dedup/lifecycle contract was implemented in `5d691b9`; P1-WP21
propagation in `056b1ca`; N01 exact provenance in `05e826d`; N02 exact mounted-DMG/
WKWebView smoke in `cc0ad94`; H03 runtime degraded/offline boundary in `62921f7`;
P1-WP22 U01 in `ea4e12c`; P1-WP23 U02 in `51ee968`; P1-WP24 U03 in `afedb70`;
P1-WP25 U04 in `26751f7`; P1-WP26 U05 in `30dfcd7`; H01 canonical
persistence/recovery in `006e86e`; and H02 schema upgrade/restore in `169c446`.
Their historical evidence records are archived.

The 2026-09-08 H01 Mac evidence used locked dependencies and clean temporary data
directories: local CI was **MERGE READY**, with full backend **643**, frontend **67**,
i18n **560/560**, production build, arm64 desktop build, native `wkwebview` smoke,
packaging preflight and provenance contract PASS. Local CI report SHA-256
`dd80ec3a8b6ad5e57ef6a3586f45ebacafa823e0111c6a677926e5391bf06154`; source commit
`006e86e6b6fae022fc27a1169f55f0c1e82c7120`; tracked source tree SHA
`1ecee1a18702ca26bbf76ee6825e60bbf4de9d9285a09da0b1921de650862b86`; provenance
`COMPLETE`; release validator PASS. Local executable SHA
`90f3b06f9cde166eacb7310927b600fb3b6f0c1195435c99cca0d7f721a9ce60`; `.app` SHA
`a44a78640097827e0a597a698d032194cb8a1d9669adebc4d2b5f4a093e8d2a2`. Exact H01
DMG evidence: DMG SHA
`80764167ba924db4d918dfccb893936b1ac95d72931524351a0c4bd8a37530ad`; mounted
executable SHA `90f3b06f9cde166eacb7310927b600fb3b6f0c1195435c99cca0d7f721a9ce60`,
read-only mount, explicit executable, `wkwebview`, controller ready and detach PASS.
`uv --offline` is dependency-preparation evidence only; the default runtime smoke
still attempts the configured public market-data connection. H03 disabled/degraded
tests cover the explicit no-network boundary. H01/H02 tests used only synthetic
temporary data and no credentials/user data. Branch `npm audit` reported zero findings,
while the GitHub default branch still exposes five open npm Dependabot alerts. Source
identity conflicts, unknown position mode, incomplete lifecycle, funding/transfer
schema, Windows/Linux host evidence, licensing, pilot and release-owner decisions
remain boundaries; H04 trust-boundary work is not yet closed; no PnL, live execution
or pilot claim was opened.

Final H02 Mac evidence on source `ed689a0ba7fd571d176cb3dfc09ae9397dace298`:
local-CI report SHA-256
`4ad98b4fd3d6eb6f0cc2afb2b554402c8f8bb1ede35643a8d0065f30ec935580`, smoke report
SHA-256 `91e1273b1f2a6052b4165bae822174b415c35244bfc5409abe0d2ab7b430d5ec`, full
backend **651**, frontend **67**, i18n **560/560**, release truth, packaging preflight,
arm64 PyInstaller, frozen native `wkwebview` smoke and provenance **COMPLETE**. Tracked
source tree SHA `cf382072bb678f95286170fe3cfe0c2e8f886b546a707fa890c298c58e966c73`;
local `.app` SHA `51d44e29faa675acfcd10878d5ef0dd11ddb66cf2da8553d52d28c18cba3b4df`;
mounted executable SHA `c75201db4fe54ace8b06eb85d6315ed5695e5ae7219c6d7b60434cc955980173`.
Exact read-only DMG smoke report SHA
`da82507eda312bb6effc14acc2dbd2febf14109ab45175411593bad30105e1f2`; DMG SHA
`0f53140163ba6526b611fbe7dff8b70425155ac1173e8c9801e140e4fd5c4fc8`; mount selected
the DMG-contained executable, verified `wkwebview`/controller identity and detached
cleanly. The smoke attempted the configured public Binance stream; it is not offline
runtime evidence.

Next handoff: H04 threat model and trust boundaries.

## Update protocol

Replace the relevant rows as work progresses; do not append a new full status report.
Each outcome must cite WP, code/evidence SHA, actual commands/results, platform,
unchecked criteria and next dependency. Keep this file concise; long history belongs
in completed packages/Git, not additional competing roadmaps.
