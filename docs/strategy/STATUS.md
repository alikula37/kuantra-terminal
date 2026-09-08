<!-- doc-role: current-status -->
# Current development status

Updated: 2026-09-08. Branch: `codex/p1-wp01-evidence-ledger`.
Roadmap: [KPR-001](PRODUCTION-READINESS-PLAN.md), current planning source, still Proposed
for new scope/estimates. Selecting one roadmap does not approve its commercial assumptions.

## Selected next work

**H05 — Ready:**
[Supply chain, SBOM, license and secret boundary](work-packages/H05-supply-chain-sbom-license-secret-boundary.md).
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
Neither package silently became full tax/accounting scope or new venue scope. The
next bounded implementation is H05: supply chain, SBOM, license and secret
boundary. No other historical `Active` WP is automatically queued. Pilot/release
claims remain blocked by their explicit gates.

## Current evidence, not completion claims

| Area | Evidence / remaining boundary |
|---|---|
| Runtime baseline | `ca94b83`; fresh clean Mac local CI `MERGE READY`: 669 backend, 67 frontend, i18n 560/560, arm64 build and native smoke passed. Provenance is COMPLETE; H03 disabled/degraded tests are PASS |
| Roadmap baseline | `03b7791`: G0–G7 proposal; no production/pilot gate passed by publishing a document |
| P1 foundations | Implementations recorded in historical packages; source completeness and financial accounting still open |
| Mac (latest local evidence) | H04 source `ca94b83` passed clean arm64 local CI and exact read-only DMG/WKWebView smoke; DMG SHA `cc1fab496a1cfbb66bdea5ee94da61c4ed9d64dc635019890a8216d01663189b`, smoke report SHA `5ebc294420567b3789be1ddf3986b7c05f8cb7cefdef7ede6a279ce23b119a66`, mounted executable SHA `00725e65ff915174a820d39e252646ff8cd54877feb32b22331fb73413201d7a`; Developer ID/notarization/Gatekeeper/second-host evidence remains open |
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
| H05 | IMPLEMENTATION_REQUIRED | Locked dependency, SBOM/license notice, secret scan and build trust evidence | Current bounded package: [H05](work-packages/H05-supply-chain-sbom-license-secret-boundary.md); default-branch Dependabot alerts and owner license decisions remain open |
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
persistence/recovery in `006e86e`; H02 schema upgrade/restore in `169c446`; and
H04 trust-boundary hardening in `1cf486e`. Their historical evidence records are
archived.

The 2026-09-08 H04 Mac evidence used locked dependencies and clean temporary data
directories: local CI was **MERGE READY**, with full backend **669**, frontend **67**,
i18n **560/560**, production build, arm64 desktop build, native `wkwebview` smoke,
packaging preflight and provenance contract PASS. Local CI report SHA-256
`e40f10591206c0ea612a2afe64928bc2684739f144ce11f0121e16126078d639`; source commit
`ca94b83e0f018c83e7aaebfd4e40b4708cdaedf7`; tracked source tree SHA
`ead42c15aecda199619e64fa55ebd42479d5e7135a128e8e120ace1e19ae5d9e`; provenance
`COMPLETE`; release validator PASS. Local smoke report SHA-256
`d8bb1c09d919a2270150cd2676527ca78c959f7b9bea7af797e96ec9729b340b`, executable
SHA-256 `00725e65ff915174a820d39e252646ff8cd54877feb32b22331fb73413201d7a`, and
`.app` SHA-256 `5a2ecb0e7db672a51958050c52f7edc219963f854ca08343a7e848f5b20c0081`.
Exact read-only DMG smoke report SHA-256
`5ebc294420567b3789be1ddf3986b7c05f8cb7cefdef7ede6a279ce23b119a66`; DMG SHA-256
`cc1fab496a1cfbb66bdea5ee94da61c4ed9d64dc635019890a8216d01663189b`; mounted
executable SHA-256 `00725e65ff915174a820d39e252646ff8cd54877feb32b22331fb73413201d7a`.
The read-only mount selected the DMG-contained executable, verified `wkwebview`/
controller identity and detached cleanly.

`uv --offline` is dependency-preparation evidence only; the default runtime smoke
still attempts the configured public market-data connection. H03 disabled/degraded
tests cover the explicit no-network boundary. H04 tests used only synthetic temporary
fixtures and no credentials/user data. Branch `npm audit` reported zero findings,
while the GitHub default branch still exposes five open npm Dependabot alerts. Source
identity conflicts, unknown position mode, incomplete lifecycle, funding/transfer
schema, Windows/Linux host evidence, licensing, pilot and release-owner decisions
remain boundaries; no PnL, live execution or pilot claim was opened.

Next handoff: H05 supply chain, SBOM, license and secret boundary.

## Update protocol

Replace the relevant rows as work progresses; do not append a new full status report.
Each outcome must cite WP, code/evidence SHA, actual commands/results, platform,
unchecked criteria and next dependency. Keep this file concise; long history belongs
in completed packages/Git, not additional competing roadmaps.
