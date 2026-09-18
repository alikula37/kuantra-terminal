<!-- doc-role: current-work-package -->
# P1-WP48 — Analytics honesty, OLAP simulation separation, robustness and acceptance evidence

```yaml
work_package: P1-WP48
status: InProgress
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

- [ ] **No invented analytics**: the pivot engine never fabricates seed rows; an empty
  journal returns zero rows with an explicit `NO_CLOSED_TRADES` basis, and the UI states it.
- [ ] **OLAP simulation separation**: `olap_trades` carries `record_mode` (schema, migration,
  both insert paths), `/analytics/overview` excludes simulations from real metrics and
  reports a separate `simulation_trades` counter; the UI shows the exclusion when non-zero.
- [ ] **Candle persistence robustness**: a locked/unavailable DuckDB no longer spams ERROR;
  bounded retries and a single warning, verified by tests.
- [ ] **WP43 acceptance evidence**: independent-source availability re-probed and recorded;
  a real verdict if any independent source is reachable; the product-check surface visually
  accepted with a new labelled simulation record.
- [ ] **WP41 acceptance evidence**: CSV + PDF generated from the real journal; counts,
  totals, month boundary and layout reviewed with screenshots and a recorded result.
- [ ] **H05 inventory**: factual third-party notices inventory generated from the locked
  dependency sets; the license choice remains the owner gate.
- [ ] **Journal cleanup**: the four labelled simulation test records are cancelled
  (audit-safe tombstones, not hard-deleted) — decided by the agent.
- [ ] Full suites, i18n/docs checks, canonical Mac local CI, commit/push, clean-commit arm64
  package, exact-DMG verification, data-preserving install, and the `v1.1.6` release train
  (tag, workflow, release, supersede `pilot-v1.1.5`).
