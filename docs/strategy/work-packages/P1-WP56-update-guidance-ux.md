<!-- doc-role: current-work-package -->
# P1-WP56 — Update guidance UX

```yaml
work_package: P1-WP56
status: InProgress
date: 2026-10-03
branch: main
baseline: 70aa16ab6b53c63c38b218891c8fae55e9395c95
```

Selected under the existing owner-approved UX sequence after WP55. Presentation-only
implementation is under verification; installed acceptance remains pending.

## Bounded scope

- Reproduce genuine confusion about installed version, Releases access, architecture selection
  and manual update/data preservation; explain only existing working actions.
- Distinguish opening Releases from checking latest version or installing an update. A local
  source build and published pilot with the same version are not automatically identical.
- Accurate EN/TR/DE, readable themes/keyboard, no guarantee that ad-hoc signing is notarization.
- No automatic installer/download/updater API, security bypass, user-data backup/restore/reset,
  credential collection, signing/billing/workflow/Release/tag or Intel capability expansion.
- N03/N05/H05/legal/XM/gold and helper lifecycle remain separate obligations in WP29.

## Acceptance

- [x] Inspect current behavior and reproduce confusion with red regression tests.
- [x] Clear guidance mapped to working current actions; no invented latest-version/update success.
- [ ] EN/TR/DE/themes/keyboard/regressions/full canonical arm64 local CI pass.
- [ ] Commit/push main; exact-DMG smoke and matching-hash installed update preserve user data.
- [ ] STATUS/registry/evidence recorded; do not select an unapproved new feature sequence.

## Current evidence (2026-10-03)

Inspected UpdateNotifier, its bridge-only fixed Releases action and 11 existing regressions.
New regression failed because build/artifact boundary and optional manual guidance were absent;
after implementation `npm --prefix frontend test -- UpdateNotifier.dom.test.tsx`: 12 PASS.
No updater API, download, automatic installation or latest-version claim was added.
Semantic theme/control styles replace fixed dark colors and small update text. Collapsed
keyboard-operable guidance covers arm64/Intel selection, private repository access, package
hash limits, preserving the separate data directory and ad-hoc/Gatekeeper boundaries.
`npm --prefix frontend run build`: PASS (tsc, production build, EN/TR/DE 1318 keys each).
`python3.11 scripts/check_docs.py`: PASS (142 documents / 190 links / 5 startup documents).
`git diff --check`: clean. Full suite and clean-commit native packaging evidence pending.

Native UI access to the installed app repeatedly returned `noWindowsAvailable` or
`timeoutReached`; the installed process is still running. This is an acceptance/normal-quit
blocker, not proof of an application crash. No installed bundle or user data has been changed.
Do not archive this package until native themes/keyboard, exact-DMG and safe installation
acceptance have actual evidence. Release/tag/Intel refresh and WP29 obligations remain outside scope.
