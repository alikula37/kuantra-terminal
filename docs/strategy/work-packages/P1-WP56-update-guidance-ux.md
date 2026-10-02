<!-- doc-role: current-work-package -->
# P1-WP56 — Update guidance UX

```yaml
work_package: P1-WP56
status: Ready
date: 2026-10-02
branch: main
baseline: 70aa16ab6b53c63c38b218891c8fae55e9395c95
```

Selected next under the existing owner-approved UX sequence after WP55. Not implemented.
Inspect current installed UpdateNotifier/manual update contracts before changing anything.

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

- [ ] Inspect current behavior and reproduce confusion with red regression tests.
- [ ] Clear guidance mapped to working current actions; no invented latest-version/update success.
- [ ] EN/TR/DE/themes/keyboard/regressions/full canonical arm64 local CI pass.
- [ ] Commit/push main; exact-DMG smoke and matching-hash installed update preserve user data.
- [ ] STATUS/registry/evidence recorded; do not select an unapproved new feature sequence.
