<!-- doc-role: current-status -->
# Current development status

Updated: 2026-09-10. Branch: `main`.
Roadmap: [KPR-001](PRODUCTION-READINESS-PLAN.md), current planning source, still Proposed
for new scope/estimates. Selecting one roadmap does not approve its commercial assumptions.

**Owner decision (2026-09-10):** İlk production sürümü macOS-only olacak ve macOS 12
Monterey veya üzeri için ayrı native arm64 ve x86_64 DMG’ler olarak doğrudan Developer ID
imzalı/notarize biçimde dağıtılacaktır. Intel desteği, fiziksel Intel Mac erişimi olmadan
native Intel CI build + exact mounted-DMG smoke kanıtıyla kapatılacaktır; fiziksel Intel
pilot ek güven kanıtıdır, zorunlu release kapısı değildir. Windows ve Linux v1 claim’i
değildir. Apple Developer üyeliği ve gerçek signing/notarization erişimi Release Candidate
aşamasına kadar ertelenmiştir.

**Pilot distribution decision (2026-09-10):** Apple Developer ID üyeliği satın alınmayacak.
Üç kişilik kapalı pilot, iki native DMG ve hash/evidence bundle taşıyan private GitHub
Release ile yapılabilir; ad-hoc artifact manual Gatekeeper approval gerektirir ve yalnızca
`TRUSTED_PILOT_ONLY` olarak sınıflandırılır. Bu seçim public download, commercial support,
production veya notarized-artifact claim'i açmaz. Pilot kullanıcılarının repository read
erişimi owner tarafından ayrıca verilmelidir; bu çalışma sırasında erişim, Release/tag veya
asset upload işlemi yapılmamıştır.

**Version reset decision (2026-09-10):** Kullanılamaz durumdaki v1.4.0 yayın kaydı geri
çekilmiş olarak korunacak; tag, assets ve eski truth matrix izlenebilirlik için silinmeyecek.
Güncel release train `v1.0.0`'dır ve henüz yayımlanmamıştır. Aşağıdaki v1.4.0 ad-hoc
hash'leri yalnızca pre-reset historical evidence'tir; güncel release kanıtı olarak
kullanılamaz.
Eski kök `UAT_AUDIT_REPORT.json` raporu geri çekilmiş tarihsel kayıt olarak arşivlendi;
güncel UAT çıktısı yalnızca ignore edilen `artifacts/evidence/uat/` altında tutulur.
Son güvenli çalıştırmada 2 temel senaryo `PASSED`, 3 deneysel senaryo `DISABLED` oldu;
komutun yüzde-100 dışı sonucu bilinçli bir release engelidir ve production PASS değildir.

## Selected next work

**P1-WP29 — IN PROGRESS: trusted macOS pilot package preparation.** The package adds the
official-source-backed private GitHub Release decision, exact dual-architecture pilot
package builder, standalone user instructions, checksum/evidence bundle and manual
Gatekeeper boundary. It cannot emit a pilot package until P1-WP28 produces both native
DMGs and exact final smoke/N05 reports. The active work package is
[P1-WP29](work-packages/P1-WP29-trusted-macos-pilot-package.md).

**P1-WP28 remains OPEN / HOST_REQUIRED:** native `arm64` and `x86_64` artifact contract,
executable-derived provenance and exact mounted-DMG smoke are implemented, but Intel
support is not claimed until the native x86_64 CI job produces its own locked
test/build/package/smoke evidence. The Rosetta guard now rejects translated or unknown
Intel host status. Its implementation evidence remains `bb6ce7c`; the separate package
preparation change is recorded under P1-WP29.

N05 remains the later owner-controlled signing/notarization gate and N03 remains the
deferred clean-profile/second-host final-validation obligation; neither is silently closed
by P1-WP28 or P1-WP29.

**P1-WP29 implementation evidence (this change):** `prepare_pilot_package.py` is
fail-closed for missing x86_64 evidence, binds both architectures to the same source/tree/
lock/truth identity, verifies exact mounted-DMG smoke plus either N05 PASS or explicit
ad-hoc `BLOCKED` evidence, requires `hdiutil verify` image-integrity evidence before
mounting, and writes DMGs, evidence JSON, manifest, instructions and SHA-256 checksums
without reading user data or credentials. The research record is
[`PILOT-DISTRIBUTION-RESEARCH.md`](../release/PILOT-DISTRIBUTION-RESEARCH.md). The
current invocation is expected to remain `BLOCKED` because the GitHub account billing/
spending-limit blocker has not produced the x86_64 chain; no Release/tag or asset upload
was performed.

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

**P1-WP28 implementation evidence (2026-09-10, `bb6ce7c`):** Architecture/provenance/
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
| P1-WP28 | IN PROGRESS | macOS 12+ native arm64/x86_64 build, executable-derived provenance, exact per-architecture DMG smoke and dual-runner release contract | `bb6ce7c` implements the guards and dual-runner contract; arm64 clean build/local CI/exact mounted-DMG smoke is PASS. Intel runner jobs are currently blocked before startup by GitHub account billing/spending-limit state, so x86_64 remains `PENDING_NATIVE_CI`; Universal2, Windows/Linux and signing are separate gates. |
| N03 | DEFERRED / HOST_REQUIRED | Clean second macOS profile/host install-lifecycle, quarantine observation and synthetic value-chain reopen | Execute at final macOS distribution/pilot validation with the exact packaged artifact; current developer profile/temp data directory is insufficient and the criterion must not be marked PASS |
| N04 | CLOSED | Manual update/interrupted-update/uninstall data preservation and fail-closed schema rollback policy | Bounded packaged audit `3f4ba82` PASS; exact previous/current provenance and hashes recorded above. No automatic updater or real migration was added. |
| N05 | IN PROGRESS / OWNER_REQUIRED | Exact macOS DMG signing/notarization preflight and secretless distribution evidence | `121a5cd` implementation, 6 N05 contract tests plus 9 package-spec tests, 4 manifest tests, 6 Phase-0/workflow tests, local CI and exact mounted smoke are recorded; current v1.0.0 ad-hoc DMG is intentionally `BLOCKED` (report SHA `338e83e...`). Developer ID, hardened runtime, Gatekeeper and stapled-ticket evidence require owner/Apple host access; N03/H05 remain v1 gates, N06 is future multi-platform scope |
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
