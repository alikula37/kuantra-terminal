<!-- doc-role: archived -->
# P1-WP48 — Analytics honesty, OLAP simulation separation, robustness and acceptance evidence

```yaml
work_package: P1-WP48
status: Complete
branch: main
baseline: fdb9d5c
```

Owner instruction (2026-09-18): close every remaining doable item except the impossible or
already out-of-scope ones; the agent decides at decision points. Decisions taken:
- OLAP `record_mode` projection change: **approved** (additive, rebuildable derived data; no
  user-record rewrite) to close the last simulation-mixing surface (`/analytics/overview`).
- The root product `LICENSE` choice stays an owner/legal gate (H05's own recorded
  disposition); only the factual third-party inventory is produced.
- P2–P4 depth packages and OKX A1.2 remain unapproved scope (no package, no work).
- Notarization and the real XM report need owner/external inputs; the clean-profile install
  audit is executed as far as this host allows (clean data dir + DMG install cycle).

## Ordered acceptance

- [x] **No invented analytics**: the pivot engine never fabricates seed rows; an empty
  journal returns zero rows with an explicit `NO_CLOSED_TRADES` basis, and the UI states it.
- [x] **OLAP simulation separation**: `olap_trades` carries `record_mode` (schema, migration,
  both insert paths), `/analytics/overview` excludes simulations from real metrics and
  reports a separate `simulation_trades` counter; the UI shows the exclusion when non-zero.
- [x] **Candle persistence robustness**: a locked/unavailable DuckDB no longer spams ERROR;
  bounded retries and a single warning, verified by tests.
- [x] **WP43 acceptance evidence**: independent-source availability re-probed and recorded;
  a real verdict if any independent source is reachable; the product-check surface visually
  accepted with a new labelled simulation record.
- [x] **WP41 acceptance evidence**: CSV + PDF generated from the real journal; counts,
  totals, month boundary and layout reviewed with screenshots and a recorded result.
- [x] **H05 inventory**: factual third-party notices inventory generated from the locked
  dependency sets; the license choice remains the owner gate.
- [x] **Journal cleanup**: the four labelled simulation test records are cancelled
  (audit-safe tombstones, not hard-deleted) — decided by the agent.
- [x] Full suites, i18n/docs checks, canonical Mac local CI, commit/push, clean-commit arm64
  package, exact-DMG verification, data-preserving install, and the `v1.1.6` release train
  (tag, workflow, release, supersede `pilot-v1.1.5`).

## Delivery verification (2026-09-18)

Commits `975a875` (backend analytics honesty/robustness), `e76153d` (frontend empty state +
exclusion note), `9188217` (docs) and the v1.1.6 train `a1c98c4` (tag `pilot-v1.1.6`) are
pushed. Red-first evidence: the WP48 backend tests failed before the OLAP column, the empty
pivot basis, the quant/symbol filters and the retry helper existed; the frontend tests cover
the empty state and the exclusion note. Full suites: backend **1194 passed**, frontend **44
files / 297 tests**, i18n **1241/1241/1241**, `tsc`/build clean, `check_docs` PASS. Canonical
arm64 local CI on the clean commit **MERGE READY** (`dist/p1-wp48-local-ci.json`, executable
`4765098be8ec871a68a7e1e9fa8b0dc0cf9ddb17e4bba6bf229255e3b8d9018a`).

**Acceptance evidence (installed v1.1.6, executable
`eda6ec7f46f633a3a7eb1daa4f271a5cf881f1f96fed98d16c5ebfc19c7fcd7e`):**
- **WP41 export review** (`artifacts/evidence/p1-wp48/wp41/`): preview reported 4 records with
  `local_estimates:4` and `canceled_records:4`; the Turkish CSV carries `durum=CANCELED`,
  `miktar_birimi=USD`, record mode and snapshot hash columns; the PDF is one valid page whose
  header states `4 toplam · 0 açık · 0 kapanmış · 4 iptal` with period, entry-date basis,
  Europe/Istanbul and the estimated section. Limit: the journal contains no real closed
  results (only cancelled test records), so monetary totals are zero by design — format,
  units, separation and layout were reviewed, not real P&L values.
- **WP43 product-check visual** (`artifacts/evidence/p1-wp48/wp43/`): a new labelled gold
  simulation (`TRD-1789720324442`) opened as `PROVIDER_MATCH_REQUIRED` with the declared
  identity, refreshed into the real Biquote chart and showed `UNVERIFIABLE` with the honest
  reason text and `SPOT_METAL:XAU:USD`. Availability re-probe recorded: yahoo `XAUUSD=X` 404,
  stooq serves the JavaScript challenge for `xauusd`/`eurusd` — **no reachable independent
  free source exists today**, so no real verdict is possible (consistent with WP43's open
  item).
- **H05 inventory** (`artifacts/evidence/p1-wp48/h05/`, `docs/release/THIRD-PARTY-NOTICES.md`):
  101 locked Python components (16 without a metadata license label; `pyqt6*` is the GPLv3/
  commercial dual dependency that matters for a paid distribution) and 37 production npm
  components (all labelled). The root `LICENSE` choice remains the recorded owner/legal gate;
  no hypothetical license text was added.
- **Journal cleanup:** the four labelled simulation test records were cancelled (audit-safe
  tombstones; the WP43 visual record remains as the current labelled test record).
- **Release:** candidate run `35338202211` **success**; DMG SHA-256 arm64 `8e348796…`,
  x86_64 `49f9d7c7…`; mounted executables arm64 `eda6ec7f…`, x86_64 `473102ae…`; exact
  mounted-DMG smoke PASS on both lanes; the arm64 artifact was installed over
  `/Applications/Kuantra Terminal.app` (backup `/tmp/kuantra-v116-update.iqEpxZ`; installed
  executable matches, codesign OK, version 1.1.6). GitHub prerelease `pilot-v1.1.6` and the
  `pilot-v1.1.5` supersede notice follow. The clean-profile install audit is executed as far
  as this host allows (fresh-data-dir DMG smoke on every release); the true second-macOS-profile
  part stays an owner-host obligation.
