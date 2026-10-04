<!-- doc-role: current-work-package -->
# P1-WP60 — Safe in-app backup and restore preview

```yaml
work_package: P1-WP60
status: InProgress
date: 2026-10-04
branch: main
baseline: 3b773515
depends_on: P1-WP59
```

Next bounded piece of the owner-approved backup/restore sequence. In implementation;
not final native/install acceptance yet.
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
- [ ] EN/TR/DE/keyboard/theme/async tests and relevant full backend/frontend/local CI pass.
- [ ] Clean arm64 build, exact DMG and installed native open/cancel acceptance verified;
      core user-row preservation and normal quit/reopen under standing instruction.
- [ ] STATUS/registry actual evidence, bounded commit/push/install; no Release/tag refresh.

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
