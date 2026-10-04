<!-- doc-role: archived -->
# P1-WP60 — Safe in-app backup and restore preview

```yaml
work_package: P1-WP60
status: Complete
date: 2026-10-04
branch: main
baseline: 3b773515
depends_on: P1-WP59
```

Completed bounded piece of the owner-approved backup/restore sequence. Source
`69f0937` plus native keyboard correction `60341ee`, verified and installed below.
Expose a user-initiated local backup and **read-only restore preview**, not destructive apply.
CSV/PDF reports are not a complete restorable backup. Reuse the existing bundle contract;
inspect `docs/MACOS_MIGRATION.md`, migration service, desktop bridge and relevant tests before
implementation. A valid checksum is integrity evidence, not source authenticity or guaranteed
cross-version restore compatibility.

## Scope and safety contract

- Settings entry explains backup contents, exclusions, local sensitive data and destination.
  Explicit user interaction selects the local destination/input via the desktop boundary;
  no arbitrary path API or automatic background backup/upload/cloud/credential transfer.
- Reuse `create_migration_bundle` / `verify_migration_bundle` and SQLite snapshot support.
  Keep versioned manifest, ledger/projection checks and credential exclusions. No new format
  or guessed data. Verify inclusion of saved review/tracking records before claiming coverage.
- Never overwrite implicitly or place output inside source data. Existing service checks an
  existing destination early but later unlinks it before replace: reproduce concurrent target
  creation and require a bounded no-clobber fix before exposing this path in the UI.
  Cancellation/failure/late responses must not report success or leave a partial user artifact.
- Backup requires a coherent snapshot including active WAL; protect journal writes and clearly
  scope multi-store consistency. Existing private operational/credential exclusions stay excluded.
- Restore preview reads a user-selected bundle, shows actual contents/schema/version/checks,
  and distinguishes invalid/unknown/not-compatible from ready-for-further-review. Unsupported
  future schemas, corrupt/traversal/duplicate/symlink/oversized archives fail closed.
- Preview must not call restore/apply, swap databases, modify source bundle or active journal.
  There is **no apply/restore button in this package**. Later real apply needs its own quiesce,
  pre-restore backup, recovery/rollback and explicit-confirmation contract; preview does not
  complete that obligation or authorize an agent to restore real user data.
- EN/TR/DE, readable light/dark, keyboard, progress/cancel/error/retry and diagnostic details.
  Actual selected-file contents and failures are shown; no fabricated completion.
  Cancellation is via the native chooser before confirmation. Once snapshot processing starts,
  controls wait for completion; navigation is not a rollback/cancel. Shutdown checks cooperate
  before publication. No claim of interactive interruption or cross-store atomic backup.

## Acceptance

- [x] Inspect existing runbook/service/bridge; record baseline and red tests for actual gaps.
- [x] Explicit local backup snapshot verifies canonical rows/ledger/tracking/review coverage
      and documented exclusions using synthetic fixtures; no silent omission/compatibility claim.
- [x] No-clobber, source containment, concurrent writes/WAL, failure/cancel/cleanup tested;
      original journal and any preexisting destination remain unchanged on rejected attempts.
- [x] User-selected read-only preview preserves source bundle and active data; invalid archive,
      schema/resource/path boundaries and unknown compatibility are explicit and tested.
- [x] No restore apply path exposed; reports vs backups and remaining apply obligation explicit.
- [x] EN/TR/DE/keyboard/theme/async tests and relevant full backend/frontend/local CI pass.
- [x] Clean arm64 build, exact DMG and installed native open/cancel acceptance verified;
      core user-row preservation and normal quit/reopen under standing instruction.
- [x] STATUS/registry actual evidence, bounded commit/push/install; no Release/tag refresh.

## Testing and delivery boundaries

Create/verify bundles only from isolated synthetic data in agent tests. Real installed native
QA may open/cancel the controls but must not create a real-user migration/backup ZIP or apply
restore without explicit approval. No user reset/delete, real trades/credentials/Keychain,
orders/AI/Pine/provider, Release/tag/workflow/Intel/signing changes. Read local CI policy;
uv offline is dependency resolution only. Existing WP29 owner-host obligations and WP58
intermittent smoke follow-up remain open. Record exact tests/hashes and native limitations
before closure, not implementation intent as evidence.

## Implementation-stage evidence — 2026-10-04

Six baseline red tests: overwrite race, live-source rather than snapshot projection preflight,
missing cancellation/service paths and world-readable ZIP permissions. Additional cold-storage
root symlink red test reproduced copying outside source. Fixed atomic same-directory no-clobber
link publication (unsupported filesystem fails closed), unique 0600 staging, same sanitized
SQLite preflight/record counts, cooperative shutdown checks, root-symlink rejection and bounded
local snapshot verification before publication. Source rows stay untouched; partial temp ZIP
cleanup tested, explicit CLI force retained and never available to renderer.
SQLite includes committed WAL and saved tracking/review events; cold files copied separately,
not a simultaneous multi-store snapshot. Browser-only preferences are explicitly excluded.
Two desktop actions accept **empty specs only**; source is native DATA_DIR and destinations/
inputs come from native file dialogs. No HTTP path/upload/restore API added. Preview verifies
a bounded disposable input copy; reports/backup/integrity/authenticity/apply distinctions explicit.
Four bridge tests initially red (missing methods). New UI collection red (missing component),
then **9 DOM** plus **12 helper** tests green; initial full frontend **430 PASS**, i18n **1397**.
Initial focused backend safety/bridge/migration/ZIP/H02/native bridge **57 PASS / 1 warning**;
subsequent additional checks and full clean/native/install gates pending. No real-user ZIP made.
Pre-commit full backend **1263 PASS / 3 warnings**, frontend **53 files / 435 PASS**, TypeScript/
production build/docs/truth/packaging/diff PASS. Four additional red malformed diagnostic
metadata tests → validated helper metadata rather than a React object-render crash; **16 helper**
tests now pass. Additional pending-transaction/WAL coherence test and canonical clean gate
follow; previous full suite is not evidence for a different final binary. Read-only native
baseline is TR/light/LITE, **5 trades / 24 events / 5 tracking**; canonical row hashes recorded
before replacement. A focused disk-failure test exposed a WAL checkpoint changing physical
SQLite bytes without a row mutation; source access is now explicit read-only URI, and logical
source rows/settings/credential-table preservation is tested rather than claiming live WAL
byte identity. Actual backup/preview native smoke is opt-in against isolated synthetic
data; native chooser open/cancel acceptance remains separate and pending.

Native candidate `69f0937` passed both chooser open/cancel flows and theme inspection, but
plain Tab skipped both new buttons in this WKWebView profile. An additional red DOM test
pinpoints missing explicit keyboard inclusion; buttons/diagnostic summary now declare
`tabIndex=0`. New clean binary and actual native Tab verification are required; the preceding
candidate's CI/DMG evidence is not final acceptance for this keyboard correction.

## Final clean and installed acceptance — 2026-10-04

Implementation `69f0937db2ea5eceb27e13e42b3ac7120a4a88fa`; final native-keyboard source
`60341ee3cecc3adc540f32f76415b3f724a6effe`, both pushed `main`. Extra red DOM assertion
for explicit tabindex passed after correction; **10 DOM + 16 helper** tests. Final clean
canonical CI: **1264 backend / 3 warnings**, **53 files / 436 frontend**, **1397** keys
EN/TR/DE, tsc/build/docs/truth/packaging/diff PASS, **13/13 MERGE READY / COMPLETE**.
Python 3.11.16, Node 24.20.0, npm 11.19.0, uv 0.12.10, PyInstaller 6.22.2,
macOS 26.6.2 arm64. Tree `978a1083ba294bf71d233e71564b1090217a96396a62cd31cd20e32497eb30b0`.

Commands (repository root, isolated test/smoke data):

```sh
uv run --offline --no-project --with-requirements backend/requirements.lock python scripts/run_local_ci.py --expected-architecture arm64 --report dist/p1-wp60-keyboard-committed-local-ci.json
PYTHON_BIN=python3.11 bash scripts/package_macos.sh --architecture arm64 --output dist/Kuantra-Terminal-1.1.6-wp60-keyboard-arm64.dmg
KUANTRA_MARKET_DATA_ENABLED=false KUANTRA_SMOKE_LOCAL_TRACKING=1 KUANTRA_SMOKE_LOCAL_BACKUP=1 uv run --offline --no-project --with-requirements backend/requirements.lock python scripts/smoke_macos_dmg.py --dmg dist/Kuantra-Terminal-1.1.6-wp60-keyboard-arm64.dmg --expected-architecture arm64 --report dist/p1-wp60-keyboard-exact-dmg-smoke.json
uv run --offline --no-project --with-requirements backend/requirements.lock python scripts/run_n05_macos_distribution_preflight.py --dmg dist/Kuantra-Terminal-1.1.6-wp60-keyboard-arm64.dmg --smoke-report dist/p1-wp60-keyboard-exact-dmg-smoke.json --output dist/p1-wp60-keyboard-n05-preflight.json
```

Exact read-only mounted DMG **9/9 PASS / COMPLETE**: actual WKWebView/controller, existing
CSV/PDF/worker/local-tracking checks plus synthetic native-bridge backup/preview, verified
digest/counts, repeated destination fails, source core rows unchanged. Dialog selection in
that smoke is injected; actual installed chooser acceptance is recorded separately.
DMG `a70d846678fa7cd1fb3f3b33a1511285fed415c2956b98627e80fd226ed9b36f`;
CI/mounted/installed executable
`ad62b1c9ddcd0f3e06adcec2b4045fc262c1e6307eb898b7a3ec2e7d4628c454`.
Native arm64 only; not Intel or pilot-distribution evidence. N05 **BLOCKED** (exit 2):
Developer ID/hardened runtime/Gatekeeper/notarization ticket absent, not a successful gate.
Runtime public network occurred; uv offline is resolution only, stream disabled is not firewall.

Persistent evidence under `artifacts/evidence/p1-wp60/`:

| Report | Persistent SHA-256 | Raw dist SHA-256 |
| --- | --- | --- |
| committed-local-ci.json | `0744f6ae216424330efbb054235d5f9c7f89aa16c53fac97efca806848d50475` | `8bf49557d7f0ec2783582d08ea6fc253b1c80124f4561155229c881f03827320` |
| exact-dmg-smoke.json | `ea88cfaa1192c06549e85163f9fe7b81f78ddd537ce27c3c58ccb47d5d7600a0` | `57b43891c498d50fc803ed1b0922cebd5d91cae69bb3a5ec17ef1a72b7ab32a0` |
| n05-preflight.json | `0bb2af4ddac8a776cdce2b5de3870cd851f4d6012a7788632b6689e5d6be83c8` | same |
| installed-acceptance.json | `d102ff796786bbfa35c449c4f2e6fa3594f254e932bb9aba86943554273ed54d` | operator record, no dist copy |

CI/exact persistent copies append LF; parsed JSON equal to raw reports, not byte-identical.
Candidate `69f0937` reports were ephemeral dist files removed by the next normal desktop
build; candidate metadata/keyboard defect retained in installed acceptance, not final evidence.

Installed `/Applications/Kuantra Terminal.app`, Settings runtime **1.1.6 local source build**;
strict/deep codesign PASS, ad-hoc. Actual native plain Tab goes first-use summary → backup →
preview; Shift+Tab reverses; Return opens each native chooser and Escape cancels without
success or persistent backup. Controls re-enable. TR light/dark, DE dark, EN light accepted
at 1440x900 and ~1060x715, controls/readability retained. Native Save confirmation with real
user data intentionally not attempted; actual writes/verification/invalid/error cases use
synthetic fixtures/smoke only. No agent-created real-user ZIP. No active long-job shutdown
time-bound claim. Normal Cmd+Q exited parent **29258**; reopen **TR/light/LITE**.

Stopped DB hash identical across replacement
`b96d167960b134155d51905279ef48fe6740d7edab80ab3ffb1f63c256b1f452`.
After native QA/reopen **5 trades / 24 events / 5 tracking** canonical row hashes unchanged
(method/full hashes in installed acceptance); runtime cache/settings can change database
bytes, so no whole-database byte identity claim across QA. Old bundle recoverable at
`/tmp/kuantra-wp60-keyboard-update.7pJ4hr/Kuantra Terminal.app`; preceding WP59 bundle
retained at `/tmp/kuantra-wp60-update.7fTquc/Kuantra Terminal.app`.

Closure in this docs/evidence-only change; installed binary source remains `60341ee`.
No Release/tag/workflow/Intel/signing secret/real trade edit/reset/delete/restore/migration.
WP29 remains open for owner-host obligations and is reselected; WP58 intermittent smoke
follow-up remains open. **Actual restore apply is not delivered**: separate bounded design,
quiesce/pre-restore backup/recovery/explicit confirmation and owner authorization required.
