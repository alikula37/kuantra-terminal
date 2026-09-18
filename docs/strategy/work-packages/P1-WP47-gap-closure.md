<!-- doc-role: current-work-package -->
# P1-WP47 — Gap closure: TP live proof, forensic cadence, USD analytics/export tests, endpoint metadata, dynamic i18n audit, WS TLS

```yaml
work_package: P1-WP47
status: InProgress
branch: main
baseline: 59a5e46
```

Owner instruction (2026-09-18): close the gaps the previous delivery honestly reported.

## Ordered acceptance

- [ ] **TP-specific live automatic close** demonstrated on the installed app with a NEW labelled
  simulation record whose take-profit is valid, above entry and already reached at save time;
  the pre-save `role=alert` warning and the value-based single closure are captured.
- [ ] **Forensic cadence reconstruction** documented and tested: the surviving pre-fix cadence
  (31/61/105/127 s) is compared against the old exponential backoff arithmetic
  (30/60/120 s + poll drift) and the new stale-retry behaviour (5 s, no failure increment);
  the attribution is labelled "consistent with", never "proven".
- [ ] **USD analytics/export end-to-end tests**: a closed USD trade flows through portfolio
  summary/breakdown/equity/heatmap, the pivot grid and the journal export snapshot with
  value-based results and explicit units (no base-quantity artifacts).
- [ ] **`/trades/open` metadata regression**: the endpoint payload carries `qty_unit`,
  `record_mode` and value-based sizing for a USD trade.
- [ ] **Dynamic localization audit**: content tests cover every dynamically composed key
  family discovered in the frontend source, plus a source-scan guard that fails when a new
  dynamic family appears without coverage.
- [ ] **Desktop websocket TLS**: the Binance stream uses an explicit certifi-based SSL context
  (the packaged app previously logged `CERTIFICATE_VERIFY_FAILED` while REST worked); the
  installed app log shows a successful stream connection after the update.
- [ ] Full suites, i18n/docs checks, canonical Mac local CI, commit/push, clean-commit arm64
  package, exact-DMG verification, data-preserving install. Release/tag unchanged.

## Scope boundaries

- No eligibility/freshness loosening; no changes to existing user records (new labelled
  simulation records only); release/tag untouched.
