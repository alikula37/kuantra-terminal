<!-- doc-role: archived -->
# P1-WP55 — First-use and backup guidance

```yaml
work_package: P1-WP55
status: Complete
date: 2026-10-02
branch: main
baseline: e15f4e7288e1cbf43619d4ca21f849a4504df617
```

Completed owner-approved UX item after WP54; isolated DOM, clean-commit native packaging
and installed acceptance verified. Historical reference, not a new work order.
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

- [x] Reproduce current first-use/backup confusion and add red tests before changing UI.
- [x] Accurate first-record and report-versus-backup guidance maps to working existing actions.
- [x] No implied broker orders, automatic backup, unverified restore success or user-data change.
- [x] EN/TR/DE/themes/keyboard, regressions, full gates and canonical arm64 CI pass.
- [x] Commit/push main; clean exact-DMG/native smoke and safe matching-hash installation.
- [x] Record evidence in STATUS/registry, archive only after verified acceptance and select
  update guidance under existing roadmap; no Release/tag refresh without authorization.

## Implementation evidence — this change

Current installed Settings had no first-record/backup explanation. Code inspection found
FirstBootWizard advanced fake diagnostic success with timers and dismissed setup on a
network exception. Two red DOM assertions reproduced absent summary/backup boundaries.
The wizard now presents a preference summary, not health claims; HTTP/network save failure
stays open for retry. Keyboard mode/theme/language selection and semantic theme surfaces.
Journal/Settings optional, initially collapsed help directs existing New Trade/export or
Journal navigation. Export modal repeats report/backup distinction and privacy warning.
No backup button or inferred restore success: SQLite snapshot and migration bundle remain
technical assisted tools, not one-click/full automatic backup. No API/schema/financial change.
Journal action and keyboard/HTTP-failure regression tests added. Native first-boot flow will
not be forced on the installed profile; its state coverage remains isolated DOM evidence.

## Final verification

Implementation **164396c**, native contrast correction **70aa16a**, both pushed main.
Two initial red tests; additional native-found primary recipe red → **34 focused tests**
in wizard/settings/journal/export files, **374 frontend tests / 51 files** total.
Canonical clean-source `70aa16ab6b53c63c38b218891c8fae55e9395c95`: **1220 backend / 3 warnings**,
1312 keys per EN/TR/DE, typecheck/build/docs/truth/packaging/diff PASS;
**13/13 / MERGE READY / COMPLETE**. Commands: `npm --prefix frontend test`,
`npm --prefix frontend run build`, `python3.11 scripts/check_docs.py`, canonical
`uv run --offline --no-project --with-requirements backend/requirements.lock python
scripts/run_local_ci.py --expected-architecture arm64 --report dist/p1-wp55-final-local-ci.json`,
`scripts/package_macos.sh --architecture arm64`, `scripts/smoke_macos_dmg.py`, N05 preflight.
Evidence: `artifacts/evidence/p1-wp55/{local-ci,exact-dmg-smoke,n05-preflight,installed-acceptance}.json`.
CI report **6483873b…**, exact-DMG **5f7674a0…**, N05 **6a32a28f…**.
Final DMG **c32ff1067d4d28eb067ffbfd5a32cf79c787208a87cce4645c093c17a9eee295**;
CI/read-only mounted DMG/installed executable
**aad6e8e46267f627791ed0845fc51344524881485178a480b5c3e267c346cd20**.
Installed version **1.1.6 local source build**, strict/deep codesign PASS, ad-hoc.
TR/light and TR/dark final guide/button visual acceptance; Settings→Journal→New Trade/export
worked without saving. DE/dark + EN/light unchanged content checked on initial candidate.
Keyboard summary/focus checked; first-boot summary/save failure/retry are synthetic DOM
evidence, not fresh-profile native acceptance. Original wizard's fake health checks removed.
Stopped SQLite identical across each replacement; ordered trade/event hashes unchanged
after QA, **5 trades / 24 events / 5 tracking rows**. TR/light/LITE after normal reopen.
Recoverable prior accepted bundle `/tmp/kuantra-wp55-update.j6uzLL/Kuantra Terminal.app`;
contrast candidate `/tmp/kuantra-wp55-final-update.HZ2AOr/Kuantra Terminal.app`.
No user-data export/restore/reset/migration, secrets, Release/tag/Intel/workflow refresh.
Public market startup network occurred; no runtime-offline claim. **N05 BLOCKED**;
N03/H05/legal/gold/XM/helper obligations stay open. Documentation closure is not a new binary.

Changed files: App, JournalView, SettingsView, FirstUseGuide, FirstBootWizard,
JournalExportModal; wizard/settings/journal DOM tests; EN/TR/DE locales;
STATUS, registry, WP55/WP56 and the evidence above. No backend/API/schema changes.
