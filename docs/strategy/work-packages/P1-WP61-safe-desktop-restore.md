<!-- doc-role: current-work-package -->
# P1-WP61 — Safe desktop restore: maintenance, recovery and explicit confirmation

```yaml
work_package: P1-WP61
status: InProgress
planning_status: Complete
date: 2026-10-04
branch: main
baseline: 3cd0cd54745132804c9199fa6d15a6d1fcd3a482
depends_on: P1-WP60
authorization: owner-approved A–E implementation; isolated restore drills only
```

The owner approved all remaining A–E development steps on 2026-10-04. This document specifies
the next bounded implementation sequence; it does not authorize an agent to restore real
user data, enable an apply button now, publish a Release or close owner-host obligations.
WP61 is now the single selected package. WP29 obligations remain open as reference.
Development approval is not approval to apply a restore to the owner's real journal.

## Goal and observed baseline

Settings backup verification currently reads a disposable copy without applying anything.
The future restore would explicitly **replace the journal with the selected snapshot**,
not merge/dedupe two histories. Records newer than the snapshot would disappear from the
active view but remain intact in the retained recovery profile. The user must see this
consequence, source integrity/compatibility and before/after counts before confirmation.
No claim of broker authenticity, financial completeness or lost-time TP/SL execution.

Code inspected at the baseline:

- `backend/app/services/local_backup.py`: create/preview only; no restore entry point.
- `backend/app/services/macos_migration.py:restore_migration_bundle`: bounded verification,
  staged extraction, SQLite/ledger/projection checks and exception rollback exist. With
  `force=True` it renames the current directory aside, then promotes staging. These **two
  renames are not a crash-atomic transaction**, despite the existing docstring's shorthand.
  No desktop lifecycle lease, durable recovery journal or verified automatic safety backup
  is provided. Reopening a mutable source path after verification requires separate defense.
- `backend/desktop/runtime.py:stop`: signals/cancels work and waits, but returns no verified
  whole-process quiescence certificate. Async task cancellation does not prove a running
  `asyncio.to_thread` database write has finished.
- `backend/desktop_main.py:_stop_resources`: catches cleanup exceptions; normal desktop
  shutdown alone is not permission for promotion. `os._exit` is not a restore commit protocol.
- `backend/main.py:lifespan` and `local_tracking_monitor.py`: background monitoring may write
  local close evidence. Ordinary startup must not run it during restore/recovery.
- `app/core/paths.py`: importing currently creates DATA_DIR. Recovery dispatch must happen
  **before** this import or SQLite/DuckDB singleton construction, otherwise a missing target
  after interruption could be silently recreated as an empty profile.
- Frozen WebView storage is under `DATA_DIR/webview`; the ZIP excludes it and machine secrets.
  Calling the existing force restore directly would not preserve current machine preferences.

These are gaps in the proposed desktop workflow, not claims that the documented clean-target
CLI or WP60 preview is broken. Reuse existing archive limits and validators, not their force
promotion path without the following contract. No legacy schema upgrade is added here:
initial desktop apply accepts only the tested current schema/bundle contract; older/future,
incomplete or malformed candidates remain preview-only and explain why.

## Chosen proposed architecture

Use the same verified native executable in an **offline maintenance mode before normal
backend/WebView-profile startup**. No in-process hot swap of the active SQLite directory.
An intent prepared in Settings requests a controlled quit/restart into maintenance; that
request alone is not destructive confirmation. The user confirms the final verified plan
in maintenance while no ordinary Kuantra writer is running. Then restart into a restricted
post-restore review, not into immediately armed automatic tracking.

Required invariants:

1. Native code fixes the canonical profile and private sibling workspace. Renderer supplies
   only bounded opaque operation/confirmation identifiers, never arbitrary paths/force/SQL.
   Open dialog selection is copied once, size-capped, to private immutable staging; all
   parsing/verification/apply uses those exact bytes. Changed hash/settings/target fingerprint,
   expired intent or replay requires a new preview/confirmation. Hash is integrity, not trust.
2. An OS-owned per-profile lease **outside the renamed profile** coordinates the maintenance
   helper, desktop instances and Kuantra write-capable CLI entry points. Hold it throughout
   preparation, promotion and recovery. PID strings, an unlocked sentinel file, window close
   or a stale mtime are not proof. A live owning process/lease blocks apply; never kill a writer
   to proceed. Advisory locking is not a guarantee against arbitrary external programs editing
   the database; unexplained interference fails closed and that limitation stays documented.
3. No normal runtime/gateway/network/plugin/quote/import/tracking/Evidence worker starts in
   maintenance. Observe normal parent/owned-worker exit and lock transfer with bounded waits.
   Timeout, cleanup failure or ambiguous ownership leaves the current profile untouched.
4. After quiescence, validate the current profile read-only and create/verify a private
   pre-restore safety snapshot outside the target. Also retain the entire original profile,
   including original WAL/SHM and machine-local files, on promotion. No hard delete or automatic
   cleanup of recovery copies; disk exhaustion/integrity failure stops before moving the target.
   Recovery material is sensitive, owner-only and not uploaded or exported with secrets.
5. Build and validate the entire candidate **before** final confirmation: bundle integrity,
   current schema, chain and canonical projections, tracking/review/lineage/counts, archive
   containment and resource budgets. Rebuild DuckDB in staging; no projection failure becomes
   a successful restore or a guessed empty analytics database. Unknown diagnostics fail closed.
6. Content policy must be an explicit tested allowlist. Restore journal-context values from
   the snapshot, including its capital basis/rules/decisions; do not silently mix current
   capital with historical performance. Preserve current machine UI preferences/WebView
   storage without overlaying old UI settings. Do not import credential/reference rows from
   the ZIP, access Keychain, or silently bind old connector settings to a different account.
   Current local credential material remains recoverable in the retained original profile;
   connectors remain unavailable pending an explicit separate account-binding decision.
   Inventory/classify actual settings and files first; unclassified/conflicting items block
   apply instead of an indiscriminate directory copy or silent preference reset. No plugins,
   models/logs or credentials are activated/copied into a migration ZIP.
7. A private versioned, bounded operational journal lives outside both profiles. Record operation
   ID, exact source/candidate/original identities and intended phase transitions durably before
   irreversible steps. Fsync files and parent directories as appropriate; validate paths/types
   and use exclusive creation/no-clobber names. This operational record is not a financial
   ledger event and must never rewrite source hashes or historical correction lineage.
8. No global atomicity claim for two directory renames. Record recoverable transition states
   before moving original/publishing candidate. If promotion fails, restore the original only
   when identities and state prove that is safe; otherwise retain both and block normal boot.
   The early boot recovery guard runs before DATA_DIR creation/DB initialization. It never
   invents a blank profile, merges generations, repeats apply on launch or deletes a recovery
   profile. Corrupt/ambiguous journal => `RECOVERY_REQUIRED`, explicit guidance, no writes.
9. Final confirmation binds immutable input digest, original/candidate fingerprints, schema,
   counts, scope and recovery location. Single-use, bounded lifetime; cancellation before the
   commit phase changes no active records. During commit say “finishing safely”, not “Cancel”
   or a rollback guarantee. Closing/power loss follows the durable recovery protocol.
10. Completion requires post-promotion verification of the intended generation and retained
    recovery copy, then a bounded clean relaunch. `FAILED`, `ROLLED_BACK`, `RECOVERY_REQUIRED`
    and `APPLIED_AWAITING_REVIEW` are distinct. No success from a rename or a lost callback.
    Restored local plans/connector activity stay fenced **outside canonical history** until
    explicit review/resume; never silently change old enabled flags or simulate missed closes.
    Subsequent tracking accepts only a new eligible LIVE/provider-event quote under existing
    rules. Clear old process/UI quote caches; do not treat restored cached prices as LIVE.

## Sequential bounded deliveries (one WP, separate evidence/commits)

| Step | Deliverable | Gate before the next step |
| --- | --- | --- |
| A | Private operation state, profile lease and early maintenance/recovery dispatch; no apply UI | Writer contention, pending/corrupt state and missing target block unsafe startup; existing ordinary startup/quit unchanged |
| B | Immutable selection, settings/file inventory, staged current-schema candidate + verified safety backup; no active promotion | Every reject/cancel leaves original unchanged; counts/chain/settings policy and disk limits measured |
| C | Offline commit/recovery engine in **isolated synthetic fixtures only** | Process-kill at each phase, reopen recovery, failed rollback and repeated apply are deterministic; no mixed/blank generation |
| D | Explicit maintenance confirmation and post-restore review UX, EN/TR/DE/light/dark/keyboard | Opaque revision-bound intent, no force/path HTTP API; no automated apply/resume; real-profile agent QA remains selector/cancel only |
| E | Full clean arm64 CI, exact-DMG synthetic restore/recovery and install preserving current data | Hash-bound binary, native cancel/reopen acceptance; docs/archive only with all measured criteria |

Do not expose step D before A–C pass. First bounded delivery is **A only**, followed by B–E,
combined speculative rewrite. Do not bypass the recovery gate because the CLI already restores.
Each bounded code delivery follows AGENTS commit/push/clean build/exact hash/install; no Release,
tag, workflow, billing or Intel refresh. One successful arm64 drill is not dual-platform evidence.

## Acceptance

- [x] Inspect current preview/CLI/runtime/paths and record specific lifecycle/recovery gaps.
- [x] Define order, authority, content policy, confirmation, recovery states and red-test gates.
- [x] A: profile lease contention/ownership, failure/timeouts and early boot ordering tested;
      no normal runtime or blank profile creation while maintenance/recovery is pending.
- [x] B: fixed native target, changed bundle/target, token replay/expiry, settings conflicts,
      current/future/legacy schema, chain/hash/duplicate/traversal/symlink/archive caps tested.
- [ ] B: verified pre-restore snapshot + retained complete original; WAL/coherent committed
      rows, secrets exclusion from ZIP, UI preferences and journal capital basis preserved.
- [ ] C: real subprocess crash injection before/after each durable transition and rename,
      disk-full/read-only/fsync/promotion/rollback failures, missing/corrupt journal, repeat
      recovery/apply and competing writer tested; original or candidate complete, never mixed.
- [ ] C: source event hashes, revisions/correction lineage, local estimates, broker observations,
      saved reviews and Evidence Packs retained; successful/failed state truthful and deterministic.
- [ ] D: final counts/scope/recovery location, native confirmation/cancel, progress/errors/retry,
      late callback, double-submit, keyboard and responsive EN/TR/DE/light/dark tests pass.
- [ ] D: post-restore fence prevents automatic connector/TP/SL activation, old quote reuse or
      missed-time closures; explicit resume/new eligible quote only, no historical rewrite.
- [ ] E: focused/full backend/frontend/i18n/docs/truth/packaging and canonical Mac CI pass;
      actual frozen exact-DMG synthetic restore/recovery + native cancel/reopen evidence recorded.
- [ ] E: clean source commit/hash/install, read-only before/after core row preservation,
      docs/status/registry closure; real-user restore needs its own explicit approval.

## File scope and exclusions

Likely implementation: `backend/desktop_main.py`, `desktop/bridge.py`, native maintenance/
operation-state modules, `app/core/paths.py`, `app/services/local_backup.py`, migration staging
helpers, write-capable entry-point lease plumbing, `frontend` Settings/typed bridge/three
locales, focused synthetic subprocess/DOM tests, smoke validator, current WP/STATUS/runbook.
Before A, enumerate every participating writer and initialization order; if safe enforcement
requires broader architecture, report it and revise scope before implementation.

No schema/event invention, funding/transfer/financial-model changes, restore merge/dedup,
cloud/upload/paid data, AI/Pine/live orders, real account/secret collection, automatic backup
cleanup, data reset/delete, agent-run real-user restore or release/signing expansion. WP58
smoke follow-up and WP29 N03/N05/H05/pilot/gold/XM obligations remain open.

## Planning verification

## A implementation evidence (this change)

`app/core/profile_safety.py` is stdlib-only and guards `paths` before mkdir.
Desktop/dev ASGI factory/maintenance CLI and migration mutation commands claim the
same OS lease, outside the renamed profile. Read-only bundle verification needs no lease;
H07/G0-G2/N03 diagnostic entry points constrain their own isolated synthetic profiles and
do not select the user's profile. Evidence Pack owned processes extend the actual parent's
OS lock through `DupFd`; cancellation/PID strings are not ownership proof. POSIX/macOS v1
only; no Windows support claim. Advisory locking does not constrain external DB editors.
Maintenance status dispatch imports no ordinary runtime and creates no active profile.

Red missing module → **12 profile safety + 15 desktop/shutdown PASS**; existing isolated
backup/migration/archive suite **43 PASS / 1 warning**. Missing/corrupt/unknown/oversized
operation journal, symlink, live writer, worker lease survival, pre-write fsync failure and
early empty-profile prevention tested. Docs **147/196/5 PASS**, diff clean. First dirty
canonical run: **1274 backend / 3 warnings**, **53 files / 436 frontend**, 1397 locale keys,
build passed but frozen worker failed `PROFILE_BUSY` (freeze_support dispatched too late).
Moved frozen spawn dispatch before the exclusive desktop claim; rerun **1276 backend /
3 warnings**, **53 files / 436 frontend**, canonical arm64 **13/13 MERGE READY**, actual
WKWebView + spawned Evidence Pack PASS. Dirty-tree validation is not clean binary provenance.
This failed first candidate is not installed and not acceptance evidence.
No apply UI, profile move or user-data restore. B–E criteria remain open.

A clean delivery **37d4ed31ab2ea32ef19cad521e9dd0c85289b325**, pushed main:
canonical **13/13 MERGE READY / COMPLETE**, exact read-only mounted DMG **9/9 PASS**,
frozen offline maintenance status `NONE` without an active profile. Installed runtime
**1.1.6**, executable **b3031a4d3dba1ac42ebe2cd222aff8d10fe3d53213703f186f0ecedb2d5cf1aa**,
DMG **46ddc48627e900a8fc1fda478398bee44b4975581f4def118f53ed8c769c6ba4**.
Stopped DB **af9a570a…** unchanged across replacement; **5 trades / 24 events / 5 tracking**
canonical row hashes unchanged after normal quit/reopen, TR/light/LITE preserved. Strict
deep ad-hoc codesign PASS, not Apple trust. Prior bundle retained at
`/tmp/kuantra-wp61-a-update.EhmNHv/Kuantra Terminal.app`. Persistent evidence in
`artifacts/evidence/p1-wp61/a-{committed-local-ci,exact-dmg-smoke,installed-acceptance}.json`.
JSON copies are reserialized with a final LF, not raw report byte-identical copies.

## B preparation evidence (this change)

`desktop_restore.py`: bounded immutable native selection, 15-minute operation/confirmation,
explicit file/table/settings inventory, current-schema/chain/projection/tracking/review
checks on private copies, raw quiesced DB/WAL/SHM copy then coherent safety SQLite snapshot,
staged DuckDB rebuild and post-hydration history hash verification. No promotion/apply UI.
Offline maintenance accepts opaque operation ID, not renderer paths/force/SQL.
Unknown settings/files/tables or malformed/archive-limited candidates reject unchanged.
Original total cap 2 GiB/20k paths; financial table cap 250k rows/256 MiB canonical text
and 1 MiB per row. Free-space estimate is conservative; disk errors still fail closed.

Machine policy: current locale/theme/first-use/telemetry/layout settings + WebView storage;
snapshot capital/paper basis/rule/decision history. `trading_mode=paper`, `ai_mode=disabled`,
installed-plugin and verified-instrument cache rows not activated. ZIP permits only SQLite
and cold Parquet paths. No credential references/Keychain material enter candidate;
current credential references remain only in owner-private safety/original recovery data.
Complete original retention is still C's promotion criterion, not claimed from B.

Red absent module → corrected constructor/test fixtures; two real safety gaps caught:
SQLite mode=ro changed SHM read marks (now opens private raw copy only), and projection
rebuild defaulted dry-run (explicit apply on private validation copy + equality check now
rejects corrupted derived values). **22 preparation PASS / 1 duplicate-ZIP warning**,
including a fresh network-denied maintenance subprocess with no normal runtime startup,
hot WAL, expired/replayed/wrong token, changed source/target/candidate, schema/chain/coverage,
malicious extra ZIP content, unknown inventory, disk/hydration failure and current UI/secret
policy. The entry-point review also found ASGI factory/console imports could initialize
singletons before taking the lease: moved claims before those imports, two red→green
subprocess regressions; focused safety/preparation/desktop **51 PASS / 1 warning**.
Final full backend **1300 PASS / 4 warnings**; pre-final-import canonical dirty run
**13/13 MERGE READY**, frontend **53/436**, i18n **1397**. Clean commit CI/native acceptance
must bind the final import changes before installation; no real-user restore.

Baseline read-only inspection at `3cd0cd5`; isolated existing backup/restore regressions:
`test_wp60_backup_safety.py`, `test_wp60_backup_bridge.py`, `test_h02_schema_upgrade_restore.py`,
`test_security_crafted_zip.py` => **43 passed / 1 warning** on macOS arm64, Python 3.11.16,
locked uv environment with temporary KUANTRA_DATA_DIR and market data disabled. These test
**existing** contracts, not proposed apply/maintenance/recovery behavior. No new red→green
implementation, full CI/build/native restore or production-readiness result is claimed.
Final docs contract **PASS: 147 documents / 197 links / 5 startup documents**, release-truth,
packaging preflight (1397-key parity) and `git diff --check` PASS. Existing documentation/
packaging/truth regression files `test_docs_contract.py`, `test_phase18_documentation_packaging.py`,
`test_p0_wp09_release_truth.py` => **20 passed** in isolated data. Initial role gate rejected
Proposed as current; retained WP29 current and WP61 reference, without changing the validator
or labelling an unapproved package Ready. No binary replacement/full CI run claimed.
