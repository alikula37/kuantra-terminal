<!-- doc-role: archived -->
# P1-WP50 — Readable journal and compact, accessible actions

```yaml
work_package: P1-WP50
status: Complete
date: 2026-10-02
branch: main
baseline: 84e7afd
```

Completed bounded item of the owner-approved UX sequence. **Clean native delivery and
installed visual acceptance verified.** WP29 obligations remain open; WP51 is selected next.

## Verified starting finding

Installed 1.1.6 local WP49 build, native light-theme screenshot: wide sticky Actions
cell (Edit/Evidence/Chart/Cancel) hides date, price freshness and status columns while
the first row is excessively tall. AX includes the correct price explanations, but
their presence in AX is not evidence that the trader can see them without scrolling.

## Bounded scope

- Keep Edit discoverable; move secondary actions into a compact, keyboard-accessible
  arrangement without dropping Evidence/Chart/Cancel or changing their safety behavior.
- No sticky-cell overlay of essential values. Prioritize instrument, side, entry/value,
  quote freshness and status; keep full ID/time/PnL/R and provenance discoverable.
- Wrap/bound quote explanation width and offer detail disclosure where necessary;
  never hide delayed/unknown/stale state behind a reassuring live indicator.
- Check real native window layout, light/dark themes and EN/TR/DE; do not assume jsdom
  assertions validate CSS geometry. All new text translated, readable and focusable.
- No API/accounting/schema change, real orders or user record cleanup. Existing edit,
  cancellation, chart, evidence, simulation separation and quote-truth rules stay intact.
- No release/tag or Intel build is authorized by this UI package.

## Acceptance

- [x] Red regression for action discoverability/focus and preserved secondary workflows.
  WP50 DOM suite: 5 real red failures (12 columns / no disclosure) after correcting unstable
  test doubles, then green. Primary Edit, evidence/chart routing, confirmation-only cancellation,
  canceled tombstone, Escape focus return and EN/TR/DE text checked. Existing sticky assertion
  superseded by the no-overlay contract; original workflow regression tests retained.
- [x] Bounded frontend implementation; no date/price/status overlap in native visual QA.
- [x] Focused/full frontend, i18n/tsc/build; relevant backend regressions and full local CI.
- [x] Clean commit/push main, native arm64 build/exact-DMG smoke, data-preserving install.
- [x] STATUS/registry closure with actual evidence; archive only after verified acceptance.

## Implementation and pre-delivery evidence

Seven fixed-width columns replace the 12-column table; instrument, Istanbul entry time,
entry price, position value, quote quality and external/local statuses remain in the main row.
Edit and a labelled 44px disclosure control are in-flow, never a sticky overlay. Secondary
actions and complete ID/entry time/exit/PnL/R open in a full-width inline row. Closed PnL
remains in the main status cell (unknown is not zero). Cancellation still requires the existing
confirmation and keeps its audit tombstone. No API, schema or accounting change.

Compact journal quote rendering always shows status, age, provider/symbol and display-only
or unverified-time warning; only long timestamp explanation is disclosed. Entry/edit/dashboard
keep the existing full presentation. Local tracking and simulation labels remain separate.

Pre-delivery: focused frontend 29 PASS, related backend 89 PASS / 2 warnings (WP49,
WP44, WP32 trade edits, local tracking, journal export); i18n/tsc/build PASS. Full frontend
first found the new dynamic status-key family missing from the key-content registry; registry
extended with OPEN/CLOSED/CANCELED, not bypassed. Final suites and native proof recorded below.

Final pre-commit suites: full backend **1209 PASS / 3 warnings** in fresh isolated data;
full frontend **46 files / 309 tests PASS**, i18n **1259/1259/1259**, tsc/production build,
docs (**136 documents / 184 links / 5 startup**), release truth and diff check PASS.
No dependency install required; `uv --offline` proves dependency resolution only.
Clean-source CI, native visual acceptance and install are recorded below.

Initial native candidate `a187e94`: canonical CI 13/13 COMPLETE, exact DMG smoke PASS,
data-preserving install; TR/EN light/dark and DE light main/disclosed rows showed no overlay.
Native DE revealed a real layout defect: `Richtung` split at its final letter. Direction
width increased 7% → 9% (status 20% → 18%), header wrapping restricted to normal word
boundaries. Final clean build and native acceptance use the follow-up commit, not the first
candidate's report. The initial candidate is not final package proof.

## Final clean-source delivery and native acceptance

Implementation commits `a187e941e4c4766b748282a4d4fbf4b36821bc32` and
`efe269b26ebd503692ccbe16f02e3c4e801a44f4` pushed to main. Final binary source is **efe269b**;
tracked tree clean, SHA-256 `c24b78f89b07b104a32bf720e886c0987d6715efdb48c9769371e39c0843f18b`.
Platform: macOS 26.6.2 native arm64; Python 3.11.16, Node 24.20.0, npm 11.19.0,
uv 0.12.10, PyInstaller 6.22.2. Commands:

```sh
uv run --offline --no-project --with-requirements backend/requirements.lock python scripts/run_local_ci.py --expected-architecture arm64 --report dist/p1-wp50-local-ci.json
PYTHON_BIN="$PWD/.venv/bin/python" bash scripts/package_macos.sh --architecture arm64 --output dist/Kuantra-Terminal-1.1.6-wp50-arm64.dmg
uv run --offline --no-project --with-requirements backend/requirements.lock python scripts/smoke_macos_dmg.py --dmg dist/Kuantra-Terminal-1.1.6-wp50-arm64.dmg --report dist/p1-wp50-exact-dmg-smoke.json --expected-architecture arm64
uv run --offline --no-project --with-requirements backend/requirements.lock python scripts/run_n05_macos_distribution_preflight.py --dmg dist/Kuantra-Terminal-1.1.6-wp50-arm64.dmg --smoke-report dist/p1-wp50-exact-dmg-smoke.json --output dist/p1-wp50-n05-preflight.json
```

Canonical local CI **MERGE READY / 13 of 13 PASS / COMPLETE**. Full backend **1209 PASS**,
frontend **46 files / 309 PASS**, i18n **1259/1259/1259**, typecheck/build PASS. Native
WKWebView controller/bridge/health/export boundaries passed. Exact read-only mounted-DMG
smoke PASS; mounted executable matches the CI executable and installed app. Public market
network is used at native startup; offline dependency resolution is not offline runtime proof.
N05 remains **BLOCKED / OWNER_REVIEW_REQUIRED** (exit 2): ad-hoc signing is not Developer ID
or notarization. Commercial-license review remains an external H05 obligation.

Final reports retained in `artifacts/evidence/p1-wp50/`:

- `local-ci.json`: `824b2e37d3e8912d984e464efbcd44d746960a0217d7a6b7e6fab145b1c56f8d`.
- `exact-dmg-smoke.json`: `e3c686f4e050c8e1beae199469010975f9a246a8d9c397b8c6c890194a1d986e`.
- `n05-preflight.json`: `a2e0f21e83cbb8d2f85485f83a1bec53925f10ad8995eacad002934cbbd0c578`.
- DMG `Kuantra-Terminal-1.1.6-wp50-arm64.dmg`:
  `7383e8bc33dbaaed3f3e98e3c5f4f498ba7e8f539810db7b388f0f2f685f59c0`.
- CI / mounted / installed executable:
  `965063656d0da0eda37cefefc64847b0847a3e96e5933011d741cbe8e347e8c7`.

Installed `/Applications/Kuantra Terminal.app`, version **1.1.6 local source build**;
codesign verification PASS, native launch and journal verified. Final backup:
`/tmp/kuantra-wp50-final.1hiB7V/Kuantra Terminal.app` (initial WP50 candidate);
preceding WP49 backup: `/tmp/kuantra-wp50-update.kRrFe6/Kuantra Terminal.app`.
Stopped DB hash before/after final replacement remained
`b4e1e847561654480d3e5aa858f10af851a846559f231664b38f781ce9ca9b80`;
**5 trades / 24 evidence events / 5 tracking projections** unchanged after launch.
No trade saved/edited/cancelled, user-data reset/delete/migration apply, real order or credential.
TR/light/LITE preferences restored after visual checks. No Release/tag or Intel build.

Native visual acceptance at 1440×900 logical (2880×1800 physical): TR/EN/DE light/dark
main/disclosed journal rows verified across initial/final candidates; final DE `Richtung`
fits, essential price/date/status never covered by action cells. Final DE/EN dark and TR
light rechecked on installed efe269b. Evidence action opens the read-only panel, quote
details retain exact timestamp/limitations. On this Mac, **Option+Tab** reaches buttons;
Escape in disclosed content collapses it and returns focus to its arrow (initial candidate;
unchanged interaction in the final candidate plus DOM regression). Standard Tab behavior is
affected by the Mac keyboard-navigation setting; no OS preference changed. Small-window
geometry beyond this native window is not claimed; the 900px table scrolls in flow without
sticky actions. jsdom checks semantic behavior, not CSS geometry.

## Open observations outside this bounded layout change

- Dark-theme New Trade/manual-entry global accents can appear black-on-dark. Journal
  Edit/details/secondary actions remain legible; broader theme contrast needs diagnosis
  in the approved translation/readability step, not a claim of full-app accessibility.
- Quitting the initial candidate left two installed-app multiprocessing helpers with
  PPID 1. No journal/OLAP data handles were found; exact orphan PIDs were stopped with
  SIGTERM before replacement and verified gone. Shutdown lifecycle needs reproduction
  and diagnosis; this package did not fix it or claim clean helper shutdown.
- Gold-source/XM, clean-profile, signing/notarization and commercial-license obligations
  remain open. Next selected work: **WP51 no-data metric states**, prepared, not implemented.
