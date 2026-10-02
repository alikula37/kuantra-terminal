<!-- doc-role: archived -->
# P1-WP56 — Update guidance UX

```yaml
work_package: P1-WP56
status: Complete
date: 2026-10-03
branch: main
baseline: 70aa16ab6b53c63c38b218891c8fae55e9395c95
```

Completed under the existing owner-approved UX sequence after WP55. Presentation-only
implementation, clean-commit packaging and installed acceptance are verified below.

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
- [x] EN/TR/DE/themes/keyboard/regressions/full canonical arm64 local CI pass.
- [x] Commit/push main; exact-DMG smoke and matching-hash installed update preserve user data.
- [x] STATUS/registry/evidence recorded; do not select an unapproved new feature sequence.

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
`git diff --check`: clean.

Initial native UI `noWindowsAvailable`/`timeoutReached` recovered. Inspected the old installed
screen before normal quit; no forced kill or crash assumption was used.

Implementation commit `db196c3523d3b7bf1b83861f4d83804857123078` pushed main. Clean-commit
canonical arm64 local CI: MERGE READY, 13/13 PASS, COMPLETE provenance; full backend
1220 PASS / 3 warnings, frontend 51 files / 375 PASS. Exact read-only mounted DMG
WKWebView/controller smoke PASS, detach PASS, hdiutil verify VALID. N05 exit 2 BLOCKED
(ad-hoc, no Developer ID/notarization), not a production pass.
Evidence: `artifacts/evidence/p1-wp56/{local-ci,exact-dmg-smoke,n05-preflight,installed-acceptance}.json`.
CI SHA-256 `a20a17dcc6d74a5cab3126496fa2449ee96750e71bd589397f27689399e315ca`;
exact-DMG report `f037b82cfa0b76841b883bedaafef8f1d436d31e0521f84740c4e3a03be019f8`;
N05 `0a4e34d602879daea677483fadebc531a4e132f9bd0556e005e5877f375d003d`.
DMG `6c0ac2c0b03a946296c300b09ac98983ce855be40818d2bf4477b6c6ea6f5ade`;
installed executable matches CI/mounted DMG:
`8b39c385972cfe1e8a192a50f415405fc0319c24784a41c9447dd24c9c020570`.
Installed version remains 1.1.6 local source build, not the published pilot artifact.
Previous accepted bundle: `/tmp/kuantra-wp56-update.mKkuYp/Kuantra Terminal.app`.
Stopped DB hash unchanged across replacement; 5 trades/24 events/5 tracking rows and
ordered trade/event hashes unchanged after native QA. Native TR light/dark, DE dark,
EN light, keyboard Return disclosure, fixed Releases browser handoff and normal reopen
TR/light/LITE verified without trade mutations. Public runtime network occurred;
uv offline is dependency resolution, not runtime network isolation.
Selected WP29 only for existing owner-host obligations; no new feature sequence approved.
Release/tag/Intel refresh and WP29 obligations remain outside scope.
