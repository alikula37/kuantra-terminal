<!-- doc-role: current-work-package -->
# P1-WP60 — Safe in-app backup and restore preview

```yaml
work_package: P1-WP60
status: Ready
date: 2026-10-04
branch: main
baseline: 3b773515
depends_on: P1-WP59
```

Next bounded piece of the owner-approved backup/restore sequence. Not implemented.
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

## Acceptance

- [ ] Inspect existing runbook/service/bridge; record baseline and red tests for actual gaps.
- [ ] Explicit local backup snapshot verifies canonical rows/ledger/tracking/review coverage
      and documented exclusions using synthetic fixtures; no silent omission/compatibility claim.
- [ ] No-clobber, source containment, concurrent writes/WAL, failure/cancel/cleanup tested;
      original journal and any preexisting destination remain unchanged on rejected attempts.
- [ ] User-selected read-only preview preserves source bundle and active data; invalid archive,
      schema/resource/path boundaries and unknown compatibility are explicit and tested.
- [ ] No restore apply path exposed; reports vs backups and remaining apply obligation explicit.
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
