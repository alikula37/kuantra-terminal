<!-- doc-role: current-work-package -->
# P1-WP55 — First-use and backup guidance

```yaml
work_package: P1-WP55
status: Ready
date: 2026-10-02
branch: main
baseline: e15f4e7288e1cbf43619d4ca21f849a4504df617
```

Selected next owner-approved UX item after WP54; not implemented or verified.
One guidance/discoverability package, not a migration, broker or backup capability expansion.

## Reproduce before implementation

Inspect current onboarding, Settings/data tools and export contracts. Identify the actual
obstruction for a trader with no CSV and explain existing first-record/manual/simulation
choices without claiming broker execution. Verify which export is a report and which is
a restorable backup; do not equate CSV/PDF with a full backup.

## Bounded scope and safety

- Clear existing first-use steps and discoverable guidance to current backup/export tools,
  with accurate scope, privacy and restore limitations; contextual help rather than forced setup.
- Preserve existing dismissal/preferences and EN/TR/DE, theme and keyboard behavior.
- No automatic backup, cloud upload, credentials, connector, schema/API changes, silent
  import, reset/delete, migration apply or restore of installed data.
- Test export/restore only in isolated synthetic data when required to validate guidance.
- Update guidance is a later separate UX item. WP29 owner-host/signing/legal/XM/gold gates
  and previous outside-core/helper-lifecycle obligations remain open.

## Acceptance

- [ ] Reproduce current first-use/backup confusion and add red tests before changing UI.
- [ ] Accurate first-record and report-versus-backup guidance maps to working existing actions.
- [ ] No implied broker orders, automatic backup, unverified restore success or user-data change.
- [ ] EN/TR/DE/themes/keyboard, regressions, full gates and canonical arm64 CI pass.
- [ ] Commit/push main; clean exact-DMG/native smoke and safe matching-hash installation.
- [ ] Record evidence in STATUS/registry, archive only after verified acceptance and select
  update guidance under existing roadmap; no Release/tag refresh without authorization.
