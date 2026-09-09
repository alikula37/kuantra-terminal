<!-- doc-role: current-status -->
# Current development status

Updated: 2026-09-09. Branch: `codex/p1-wp01-evidence-ledger`.
Roadmap: [KPR-001](PRODUCTION-READINESS-PLAN.md), current planning source, still Proposed
for new scope/estimates. Selecting one roadmap does not approve its commercial assumptions.

## Selected next work

The selected H07 bounded implementation and evidence sequence is now executed on
the current Mac artifact. Commits `e3aacc8`, `dfa7252`, `5b82473` and `4e761fa`
move Evidence Pack reads behind a bounded asynchronous bridge job, isolate the
heavy read in a single lazily-created worker process, and reuse bounded worker
state for warm reads. The same `4e761fa` arm64 artifact completed the planned
two-run `1k/10k/100k` campaign with 20 operation samples per mode and a separate
native UI/concurrent-read report. This is implementation and development evidence,
not a production SLO or support-limit decision.

The evidence does not close H07: 100k cold Evidence Pack operation p95 is
`2321.8877 / 2332.4201 ms`, projection-rebuild operation p95 is
`5141.0606 / 5143.9399 ms`, projection process peak RSS is about
`400.4 / 400.5 MB`, and native UI timer-gap percentiles remain `UNKNOWN` (the
observed single run has a maximum gap of about 1002 ms cold and 688 ms warm).
The product owner has now decided that 100k is not a production support
requirement; it remains a stress-test boundary. Therefore no further optimization
is required solely to force 100k below `<2s>`. The next dependency is fresh native
UI/resource evidence for the practical 1k/10k candidate support band, followed by
an explicit tested support boundary. No arbitrary hard cap is being invented from
the synthetic campaign. Commercial, signing, multi-host and pilot/release gates
remain open.

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
| H07 bounded baseline | Canonical correctness `a97499b`, packaged worker/launcher and final cold/warm/append-tail campaign `af8e2a1`, process-resource/projection campaign `30be78d`, bounded projection batch writer `67eafa2`, full-chain cold optimization `670ee90` and worker isolation/cache reuse `e3aacc8`→`4e761fa`. Latest 100k cold Evidence Pack p95 is `2321.8877 / 2332.4201 ms`; projection-rebuild process p95 is `6217.4225 / 6208.4966 ms`; all 366 packaged manifests and 120 projection samples are measured/valid and deterministic. Owner decision: 100k is stress-only, not a production support requirement. The candidate 1k/10k supported-band `<2s>` target, UI responsiveness boundary and final tested resource disposition remain open. Old `5a70f8b` timings are historical source-process evidence, not current cold-chain performance or packaged benchmark proof. |
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
| H07 | IMPLEMENTATION_REQUIRED | Synthetic performance/resource boundaries; source/packaged execution, cold/warm/append-tail/projection-rebuild distinction and process resource capture are implemented | `e3aacc8`→`4e761fa` moves the heavy Evidence Pack read behind a bounded isolated worker with lazy pool/cache lifecycle. The final clean campaign is deterministic with 366 packaged manifests and 120/120 valid projection samples; 100k cold p95 remains `2321.8877 / 2332.4201 ms`, projection process peak RSS is `400.4 / 400.5 MB`, and native timer-gap percentiles remain `UNKNOWN`. Owner decision: 100k is stress-only, so no further 100k optimization is required. Next: fresh native UI/resource evidence for the practical 1k/10k candidate support band, then record the tested boundary; Windows/Linux host evidence remains separate. |
| WIN | HOST_REQUIRED | Windows host/controller blocker | Historical P0-WP11 reference; verify on Windows before platform claim |
| VERIFY | HOST_REQUIRED | Historical P1-WP01 latest-SHA verification checkbox and remote/multi-OS evidence gaps | Preserve exact source criteria; current local gate is not a historical remote pass |
| OPS | HOST_REQUIRED / OWNER_DECISION_REQUIRED | Historical P2 network promotion, real disconnect, different-host bundle restore and remote verification | Reference archived open-item index; no automatic closure or permission for live work |
| PRODUCT | OWNER_DECISION_REQUIRED | Review/pilot metrics, product license/notices, signing/host access, support/incident readiness | G2–G7 and explicit product-owner decisions; root `LICENSE`, `NOTICE` and `THIRD_PARTY_NOTICES.md` remain intentionally absent until commercial distribution is prepared |
| DEP | DEFERRED | Branch dependency audit is clean, but GitHub default branch retains six open npm alerts (1 critical, 1 high, 4 moderate) | No merge while development-only; before release, remediate or record a time-bounded owner risk acceptance with applicability/mitigation |

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
The six default-branch Dependabot alerts (1 critical, 1 high, 4 moderate) remain
open and were not merged. Advisory scans used network and are not offline proof.
No PnL, live execution, pilot, commercial package or production claim was opened.

Earlier H07 bounded evidence, superseded for the current performance disposition
by the `af8e2a1` campaign above, is recorded in
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
two-run campaign are complete, while the `<2s>` target, statistically sufficient
UI responsiveness evidence and any production/resource support limit remain open.
No further optimization is presumed without a new bounded hypothesis or the
explicit owner decision on the measurement/support boundary.
H05 license/notices and default-branch Dependabot remain deferred release gates;
no production or commercial package claim is allowed.

## Update protocol

Replace the relevant rows as work progresses; do not append a new full status report.
Each outcome must cite WP, code/evidence SHA, actual commands/results, platform,
unchecked criteria and next dependency. Keep this file concise; long history belongs
in completed packages/Git, not additional competing roadmaps.
