<!-- doc-role: current-status -->
# Current development status

Updated: 2026-09-08. Branch: `codex/p1-wp01-evidence-ledger`.
Roadmap: [KPR-001](PRODUCTION-READINESS-PLAN.md), current planning source, still Proposed
for new scope/estimates. Selecting one roadmap does not approve its commercial assumptions.

## Selected next work

**H06 — Ready:**
[Privacy, data lifecycle and credential availability boundary](work-packages/H06-privacy-data-lifecycle-credential-boundary.md).
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
record preserves the reopen conditions. H06 is now the sole active package and may
proceed only as non-release privacy/data-lifecycle development. Neither package
silently became full tax/accounting scope or new venue scope. No other historical
`Active` WP is automatically queued. Pilot/release claims remain blocked by their
explicit gates.

## Current evidence, not completion claims

| Area | Evidence / remaining boundary |
|---|---|
| Runtime baseline | `c089cd2`; fresh clean Mac local CI `MERGE READY`: 675 backend, 67 frontend, i18n 560/560, arm64 build and native smoke passed. Provenance is COMPLETE; H03 disabled/degraded tests are PASS; supply-chain audit is integrated as a PASS step with owner review explicitly reported |
| Roadmap baseline | `03b7791`: G0–G7 proposal; no production/pilot gate passed by publishing a document |
| P1 foundations | Implementations recorded in historical packages; source completeness and financial accounting still open |
| Mac (latest local evidence) | H05 source `c089cd2` passed clean arm64 local CI and exact read-only DMG/WKWebView smoke; DMG SHA `6d517542848a04d16e8e326432b79f683f4722c28413e62c34a494bfadfd7b2e`, smoke report SHA `c6d935c8fa6f5b4e816ab09e9d1c741eff66a0cd4ab941f66b3fdc44e5c53a2f`, mounted executable SHA `a4ae72354581032dca2cef42f2a27bac7e6a204a1bdbdbee0b9b7b154149181c`; Developer ID/notarization/Gatekeeper/second-host evidence remains open |
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
| H06 | IMPLEMENTATION_REQUIRED | Data directory permissions, keychain unavailable behavior, telemetry consent/spool, redacted support/export and privacy truth | Current package: [H06](work-packages/H06-privacy-data-lifecycle-credential-boundary.md); development-only, no real data/credential, no release claim |
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
trust-boundary hardening in `1cf486e`; and H05 machine-checkable supply-chain,
SBOM and secret boundary in `c089cd2`. H04 and deferred H05 are archived; H06 is
the current package. H05's commercial distribution gate remains explicitly closed
until it is reopened with the required license/notice and dependency dispositions.

The 2026-09-08 H05 Mac evidence used locked dependencies and clean temporary data
directories: local CI was **MERGE READY**, with full backend **675**, frontend **67**,
i18n **560/560**, production build, arm64 desktop build, native `wkwebview` smoke,
packaging preflight, supply-chain audit step and provenance contract PASS. Local CI
report SHA-256 `4ca05d22d9fc459dac1de76ef0bcb889595372a5f3478824a718a940fa903c52`;
source commit `c089cd2b48f0a849bd67c6da3e652d1ab65a1d37`; tracked source tree SHA
`ac09ccce98b8b2d79a3115c390066edb1cd7eed375da14901e8b847d0edcc74f`; provenance
`COMPLETE`; release validator PASS. Local smoke report SHA-256
`36c097f6a0b4918de820edb95e4cfd7f433d10e5013b1a625b55b19c0a659d63`, executable
SHA-256 `a4ae72354581032dca2cef42f2a27bac7e6a204a1bdbdbee0b9b7b154149181c`, and
`.app` SHA-256 `9f3357d433b82ea372c8d07867c09bf6dd7ff386485cfa71d9f661e5747ab06b`.
Exact read-only DMG smoke report SHA-256
`c6d935c8fa6f5b4e816ab09e9d1c741eff66a0cd4ab941f66b3fdc44e5c53a2f`; DMG SHA-256
`6d517542848a04d16e8e326432b79f683f4722c28413e62c34a494bfadfd7b2e`; mounted
executable SHA-256 `a4ae72354581032dca2cef42f2a27bac7e6a204a1bdbdbee0b9b7b154149181c`.
The read-only mount selected the DMG-contained executable, verified `wkwebview`/
controller identity and detached cleanly.

H05 supply-chain report SHA-256 `c180de2bffb92f279f1995c9fe4061a4e1c6b28628b428679b4aa01b5d74646f`:
lock contract PASS, 395-component deterministic inventory, source/DMG secret scan
PASS, but overall `OWNER_REVIEW_REQUIRED` because root license/notices are absent.
Python `pip-audit` report SHA-256 `fd8d91aa438cee28cfc25575394c9b3f35d4ae59511659c96cbe8cbf36234f31`
reported 80 dependencies / 0 known vulnerabilities; frontend `npm audit` report
SHA-256 `f3ff707e3ec193e8e0e5d725180374b4e93657ebea4f844a1f67a2acdb7cccd3` reported
0 vulnerabilities. Both advisory scans used network; they are not offline proof.
GitHub default branch retains five open Dependabot alerts (1 critical, 1 high, 3
moderate), kept separate from branch-local audit results. No PnL, live execution,
pilot or production claim was opened.

Next handoff: H06 privacy/data-lifecycle red tests and bounded implementation. H05
license/notices and default-branch Dependabot remain deferred release gates; no
production or commercial package claim is allowed.

## Update protocol

Replace the relevant rows as work progresses; do not append a new full status report.
Each outcome must cite WP, code/evidence SHA, actual commands/results, platform,
unchecked criteria and next dependency. Keep this file concise; long history belongs
in completed packages/Git, not additional competing roadmaps.
