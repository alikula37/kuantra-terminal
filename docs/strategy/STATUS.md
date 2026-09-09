<!-- doc-role: current-status -->
# Current development status

Updated: 2026-09-09. Branch: `codex/p1-wp01-evidence-ledger`.
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

2026-09-09 correction, **a97499b**: payload/provenance validation again enforces
the existing stdlib canonical JSON contract; scalar hash serialization has explicit
type guards. Three new regression cases failed before the fix; all 38 focused H07
tests pass afterward, including a rehashed noncanonical chain rejection.
The performance figures below are historical source-process measurements, not
packaged executable benchmarks: `--executable` only supplied hash metadata.
The separate mounted-DMG smoke evidence remains valid for its recorded binary.
The packaged cold/warm/append-tail protocol is implemented in the current change;
the final two-run/20-sample campaign and H07 resource disposition remain pending.
Validation: canonical locked local CI `MERGE READY`; backend 731 (2 deprecation
warnings), frontend 25 files/102 tests, i18n 608/608, arm64 build/native WKWebView
smoke PASS on macOS 26.6.2. This run used the tracked working diff before commit;
it is not a clean release artifact. Default smoke attempted public market data.

Measurement contract, **caef518**: source benchmark reports now explicitly record
`SOURCE_PROCESS`, `artifact_executed=false`, `cold_process_measured=false` and
`os_cache=UNCONTROLLED`; the validator rejects a forged packaged-execution claim.
Correction fixture count is fixed at three (or dataset size if smaller), independently
of measurement repetitions. Three/five-repeat runs preserve counts and deterministic
snapshots. Default report output is ignored `artifacts/evidence/h07/`.
Focused H07: 39 tests; full backend: 732 tests, 2 deprecation warnings.
Pending: 20 fresh-process cold samples per size in two
runs and final operation-specific resource evidence. Correction timing still
has only three samples; it is not a completed 20-sample performance gate.

Packaged diagnostic, **this change**: `--h07-benchmark` dispatches before normal
data-directory initialization, logging, backend and WebView. It creates only its own
temporary synthetic database. A Python audit guard denies network/child-process
operations (not an OS firewall). The launcher executes the explicit binary, validates
PID/path/hash/outcome, checks pre/post artifact hashes, and retains worker/log/manifest
files in a new evidence directory. Existing outputs are not overwritten. Worker
reports distinguish source from frozen execution. This workload imports its fixture
before read measurements: cache state is mixed, NOT cold-chain evidence.
Checkout observations are not embedded source-to-binary attestation; release
provenance remains UNKNOWN. Windows/Linux host gates remain required for this
desktop entry/build change. Next: fresh-process cold/warm/append-tail measurement
protocol, then two 20-sample runs per size and the H07 resource acceptance audit.
Evidence: 5 red isolation tests → 56 focused H07/worker tests PASS; latest full
backend 749 PASS (2 warnings). Mac canonical CI MERGE READY (737 backend at that
run, frontend 102, i18n 608/608, arm64 build/WKWebView smoke); the 12 later guard/
launcher tests passed in the separate 752-test full suite. Actual packaged 1k
worker produced 1000 trades/projections and 1003 ledger events, matching the source
snapshot. Durable manifest: `artifacts/evidence/h07/packaged-worker-1000-v1/manifest.json`,
file SHA `2f29069847b9d2b3c50a4e43ba7d1c3ba881abfc8a21fa88489037bad8d2f70f`.
Exact hashes, commands and platform limits are in active H07. New final DMG,
signing and clean-release provenance are NOT claimed.

Cold/warm/append-tail protocol, **this change**: worker/launcher modes now keep
fresh-process cold, same-process warm-up, and append-tail verification separate.
The 1k two-run/3-sample and 10k/100k one-run/3-sample scale sanity campaigns
passed on the updated arm64 packaged executable. Cold operation, warm Evidence
Pack operation, and append-tail `verified_events_this_call=1` are recorded; OS
cache remains `UNCONTROLLED`, process RSS/disk remains `null` where unmeasured.
These are protocol evidence only, not the required 20-sample/two-run acceptance.
Next: run the full 1k/10k/100k campaign from a clean implementation commit,
then classify H07 without changing the `<2s` target silently.

| Area | Evidence / remaining boundary |
|---|---|
| Runtime baseline | `a7b99b7`; fresh clean Mac local CI `MERGE READY`: 683 backend, 71 frontend, i18n 574/574, arm64 build and native smoke passed. Provenance is COMPLETE; H03 disabled/degraded tests and H06 privacy boundary tests are PASS; supply-chain audit remains an integrated step with commercial owner review explicitly deferred |
| Roadmap baseline | `03b7791`: G0–G7 proposal; no production/pilot gate passed by publishing a document |
| P1 foundations | Implementations recorded in historical packages; source completeness and financial accounting still open |
| Mac (historical clean DMG baseline) | H07 source `5a70f8b` passed clean arm64 locked local CI and exact read-only DMG/WKWebView smoke with provenance `COMPLETE`; local CI report SHA `c513b5f4ce3a14270277c1a9031bcf0b9d51a3271a84ebe59f7deb2daa06be01`, native smoke report SHA `413d5029e79276c66149ae4574be0ced14860a4ac72b7858e34490d6dc0e5c5e`, `.app` SHA `36c84e727a00c305176f7ee45f2f4c32b6693e76cd59021aaa889bc1a4554459`, exact DMG smoke report SHA `bc587f232c7f5d09c787412549d924aa8aa045524590bdcecdd3047490367963`, DMG SHA `f5183bee511352e97b6c4d6e363d0951fc32361d6a9d718ccfe3174752c45fc7`, mounted executable SHA `17508bbfa429689ab6adeeee419e166c604a15457a55a5f8a543bbb16b04cbc0`; Developer ID/notarization/Gatekeeper/second-host evidence remains open |
| H07 bounded baseline | Canonical correctness `a97499b`, source measurement contract `caef518`, actual packaged worker/launcher and separate cold/warm/append-tail campaign protocol in this change. Final 20-sample/two-run evidence and resource disposition remain open. Old `5a70f8b` timings are historical source-process evidence, not current cold-chain performance or packaged benchmark proof. |
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
| H07 | IMPLEMENTATION_REQUIRED | Synthetic performance/resource boundaries; source/packaged execution and cold/warm/append-tail distinction is implemented | Next: clean-commit full campaign with two 20-sample runs per size, then resource acceptance and target disposition. Historical/sanity timings do not close the target. Windows/Linux host evidence for the desktop change is still required. |
| WIN | HOST_REQUIRED | Windows host/controller blocker | Historical P0-WP11 reference; verify on Windows before platform claim |
| VERIFY | HOST_REQUIRED | Historical P1-WP01 latest-SHA verification checkbox and remote/multi-OS evidence gaps | Preserve exact source criteria; current local gate is not a historical remote pass |
| OPS | HOST_REQUIRED / OWNER_DECISION_REQUIRED | Historical P2 network promotion, real disconnect, different-host bundle restore and remote verification | Reference archived open-item index; no automatic closure or permission for live work |
| PRODUCT | OWNER_DECISION_REQUIRED | Review/pilot metrics, product license/notices, signing/host access, support/incident readiness | G2–G7 and explicit product-owner decisions; root `LICENSE`, `NOTICE` and `THIRD_PARTY_NOTICES.md` remain intentionally absent until commercial distribution is prepared |
| DEP | DEFERRED | Branch dependency audit is clean, but GitHub default branch retains five open npm alerts | No merge while development-only; before release, remediate or record a time-bounded owner risk acceptance with applicability/mitigation |

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
The exact 100k report SHA is
`c92200c37fe1db0e7d13727d818060998d112c54c049e1c9bd81201ee57f5087`; append-tail
Evidence Pack p95 is `349.5183 ms`, export p95 is `340.3408 ms`, and projection
rebuild p95 is `4153.3801 ms` with `0 B` temporary-disk growth in the rebuild
operation. Separate no-cache full-chain audit samples were
`2217.7044 / 2190.9482 / 2208.2548 ms`, p95 `2216.36659 ms`; every `100003` event
was valid. H07 remains `IMPLEMENTATION_REQUIRED`: the append-tail path meets the
measured `<2s` planning target, but true no-cache cold startup does not and remaining
H07 resource acceptance gaps are not silently closed. The safe-persona core read
surface is bounded and experimental surfaces are not promoted; auxiliary/disabled
surfaces remain outside the production capability claim. Next handoff is the explicit
cold-target decision or another bounded optimization, followed by the remaining H07
resource acceptance audit.
H05 license/notices and default-branch Dependabot remain deferred release gates;
no production or commercial package claim is allowed.

## Update protocol

Replace the relevant rows as work progresses; do not append a new full status report.
Each outcome must cite WP, code/evidence SHA, actual commands/results, platform,
unchecked criteria and next dependency. Keep this file concise; long history belongs
in completed packages/Git, not additional competing roadmaps.
