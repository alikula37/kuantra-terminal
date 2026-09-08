# Historical archive and outstanding acceptance criteria

Archived files are **reference evidence, not current instructions**. Their original status,
commits and checkboxes describe their historical scope. Archiving does not close work.
Start instead at [AGENTS](../../AGENTS.md) and [STATUS](../strategy/STATUS.md).

No evidence was deleted. Relative links were relocated; original versions remain in Git.
The Phase 0 audit/status files remain at their old paths for the audit script and carry
historical-reference banners. Accepted ADRs and live runbooks are not archived.

## Historical strategy

- [Former full catalog/history](strategy/CATALOG-2026-09-08.md)
- [KPS-001 strategy and historical market/code audit](strategy/KUANTRA-STRATEGY-001.md)
- [2026-09-08 roadmap/code review](strategy/ROADMAP-REVIEW-2026-09-08.md)

## Package index — unchecked counts are NOT completion labels

The exact unchecked wording is retained in each linked package. Counts are pinned in
`docs/documentation.json` and checked automatically. Zero means no unchecked boxes in
that document, **not** current release verification. Forty packages retain open boxes.
Remote evidence, Windows host, latest-SHA and P2 operational gaps remain in STATUS.

| Historical package | Unchecked criteria retained |
|---|---:|
| [P0-WP01-execution-risk-contract](strategy/work-packages/P0-WP01-execution-risk-contract.md) | 0 |
| [P0-WP02-market-data-truth-contract](strategy/work-packages/P0-WP02-market-data-truth-contract.md) | 0 |
| [P0-WP03-frontend-toolchain-security](strategy/work-packages/P0-WP03-frontend-toolchain-security.md) | 0 |
| [P0-WP04-ci-truth-and-release-gates](strategy/work-packages/P0-WP04-ci-truth-and-release-gates.md) | 0 |
| [P0-WP05-python-universal-lock](strategy/work-packages/P0-WP05-python-universal-lock.md) | 0 |
| [P0-WP06A-replay-excursion-truth](strategy/work-packages/P0-WP06A-replay-excursion-truth.md) | 0 |
| [P0-WP06B-orderflow-fix-truth](strategy/work-packages/P0-WP06B-orderflow-fix-truth.md) | 0 |
| [P0-WP07-credential-keychain-boundary](strategy/work-packages/P0-WP07-credential-keychain-boundary.md) | 0 |
| [P0-WP08-experimental-containment](strategy/work-packages/P0-WP08-experimental-containment.md) | 0 |
| [P0-WP09-release-truth-matrix](strategy/work-packages/P0-WP09-release-truth-matrix.md) | 0 |
| [P0-WP10-phase0-exit-audit](strategy/work-packages/P0-WP10-phase0-exit-audit.md) | 0 |
| [P0-WP11-webview2-host-diagnostics](strategy/work-packages/P0-WP11-webview2-host-diagnostics.md) | 7 |
| [P1-WP01-canonical-evidence-ledger](strategy/work-packages/P1-WP01-canonical-evidence-ledger.md) | 1 |
| [P1-WP02-atomic-journal-evidence-write](strategy/work-packages/P1-WP02-atomic-journal-evidence-write.md) | 1 |
| [P1-WP03-rebuildable-trade-projection](strategy/work-packages/P1-WP03-rebuildable-trade-projection.md) | 1 |
| [P1-WP04-projection-read-adapter](strategy/work-packages/P1-WP04-projection-read-adapter.md) | 1 |
| [P1-WP05-evidence-gated-olap-hydration](strategy/work-packages/P1-WP05-evidence-gated-olap-hydration.md) | 1 |
| [P1-WP06-bulk-olap-sync-gate](strategy/work-packages/P1-WP06-bulk-olap-sync-gate.md) | 1 |
| [P1-WP07-trade-evidence-pack-api](strategy/work-packages/P1-WP07-trade-evidence-pack-api.md) | 1 |
| [P1-WP08-deterministic-replay-market-context](strategy/work-packages/P1-WP08-deterministic-replay-market-context.md) | 1 |
| [P1-WP09-market-data-provenance](strategy/work-packages/P1-WP09-market-data-provenance.md) | 1 |
| [P1-WP10-csv-import-evidence-provenance](strategy/work-packages/P1-WP10-csv-import-evidence-provenance.md) | 1 |
| [P1-WP11-broker-lifecycle-import-reconciliation](strategy/work-packages/P1-WP11-broker-lifecycle-import-reconciliation.md) | 1 |
| [P1-WP12-read-only-api-snapshot-adapter](strategy/work-packages/P1-WP12-read-only-api-snapshot-adapter.md) | 1 |
| [P1-WP13-evidence-pack-export-restore-drill](strategy/work-packages/P1-WP13-evidence-pack-export-restore-drill.md) | 1 |
| [P1-WP14-versioned-playbook-risk-policy-events](strategy/work-packages/P1-WP14-versioned-playbook-risk-policy-events.md) | 1 |
| [P1-WP15-trade-evidence-pack-ui](strategy/work-packages/P1-WP15-trade-evidence-pack-ui.md) | 1 |
| [P1-WP16-read-only-snapshot-completeness](strategy/work-packages/P1-WP16-read-only-snapshot-completeness.md) | 0 |
| [P1-WP17-read-only-source-identity](strategy/work-packages/P1-WP17-read-only-source-identity.md) | 0 |
| [P1-WP18-fee-precision-unit-contract](strategy/work-packages/P1-WP18-fee-precision-unit-contract.md) | 0 |
| [P1-WP19-funding-account-reconciliation](strategy/work-packages/P1-WP19-funding-account-reconciliation.md) | 0 |
| [P1-WP20-economic-dedup-lifecycle](strategy/work-packages/P1-WP20-economic-dedup-lifecycle.md) | 0 |
| [P1-WP21-journal-evidence-propagation](strategy/work-packages/P1-WP21-journal-evidence-propagation.md) | 0 |
| [P1-WP22-value-chain-integration](strategy/work-packages/P1-WP22-value-chain-integration.md) | 0 |
| [P1-WP23-reconciliation-inbox-correction-boundary](strategy/work-packages/P1-WP23-reconciliation-inbox-correction-boundary.md) | 0 |
| [P1-WP24-evidence-pack-export-boundary](strategy/work-packages/P1-WP24-evidence-pack-export-boundary.md) | 0 |
| [P1-WP25-weekly-review-asof-boundary](strategy/work-packages/P1-WP25-weekly-review-asof-boundary.md) | 0 |
| [P1-WP26-accessible-shell-boundary](strategy/work-packages/P1-WP26-accessible-shell-boundary.md) | 0 |
| [H01-canonical-persistence-boundary](strategy/work-packages/H01-canonical-persistence-boundary.md) | 0 |
| [H02-schema-upgrade-restore-boundary](strategy/work-packages/H02-schema-upgrade-restore-boundary.md) | 0 |
| [H04-threat-model-trust-boundaries](strategy/work-packages/H04-threat-model-trust-boundaries.md) | 0 |
| [P2-WP01-sequence-gap-aware-market-context](strategy/work-packages/P2-WP01-sequence-gap-aware-market-context.md) | 1 |
| [P2-WP02-binance-depth-sequence-validator](strategy/work-packages/P2-WP02-binance-depth-sequence-validator.md) | 1 |
| [P2-WP03-binance-depth-recovery-coordinator](strategy/work-packages/P2-WP03-binance-depth-recovery-coordinator.md) | 1 |
| [P2-WP04-binance-depth-payload-projection](strategy/work-packages/P2-WP04-binance-depth-payload-projection.md) | 1 |
| [P2-WP05-market-event-envelope](strategy/work-packages/P2-WP05-market-event-envelope.md) | 1 |
| [P2-WP06-market-event-segment-writer](strategy/work-packages/P2-WP06-market-event-segment-writer.md) | 1 |
| [P2-WP07-market-event-segment-manifest](strategy/work-packages/P2-WP07-market-event-segment-manifest.md) | 1 |
| [P2-WP08-market-event-batch-contract](strategy/work-packages/P2-WP08-market-event-batch-contract.md) | 1 |
| [P2-WP09-binance-depth-ingestor](strategy/work-packages/P2-WP09-binance-depth-ingestor.md) | 1 |
| [P2-WP10-binance-depth-transport-boundary](strategy/work-packages/P2-WP10-binance-depth-transport-boundary.md) | 1 |
| [P2-WP11-binance-depth-network-adapter](strategy/work-packages/P2-WP11-binance-depth-network-adapter.md) | 2 |
| [P2-WP12-binance-depth-reconnect-session](strategy/work-packages/P2-WP12-binance-depth-reconnect-session.md) | 2 |
| [P2-WP13-binance-depth-soak-harness](strategy/work-packages/P2-WP13-binance-depth-soak-harness.md) | 2 |
| [P2-WP14-binance-depth-testnet-soak-gate](strategy/work-packages/P2-WP14-binance-depth-testnet-soak-gate.md) | 2 |
| [P2-WP15-binance-depth-report-verification](strategy/work-packages/P2-WP15-binance-depth-report-verification.md) | 1 |
| [P2-WP16-binance-depth-report-hash-archive](strategy/work-packages/P2-WP16-binance-depth-report-hash-archive.md) | 1 |
| [P2-WP17-binance-depth-operator-attestation](strategy/work-packages/P2-WP17-binance-depth-operator-attestation.md) | 1 |
| [P2-WP18-binance-depth-key-registry](strategy/work-packages/P2-WP18-binance-depth-key-registry.md) | 1 |
| [P2-WP19-binance-depth-attestation-review-gate](strategy/work-packages/P2-WP19-binance-depth-attestation-review-gate.md) | 1 |
| [P2-WP20-binance-depth-review-record-key-policy](strategy/work-packages/P2-WP20-binance-depth-review-record-key-policy.md) | 1 |
| [P2-WP21-binance-depth-evidence-bundle](strategy/work-packages/P2-WP21-binance-depth-evidence-bundle.md) | 2 |
| [P2-WP22-binance-depth-fault-matrix](strategy/work-packages/P2-WP22-binance-depth-fault-matrix.md) | 2 |
| [P2-WP23-binance-depth-soak-series](strategy/work-packages/P2-WP23-binance-depth-soak-series.md) | 1 |
| [P2-WP24-binance-depth-soak-quality-gate](strategy/work-packages/P2-WP24-binance-depth-soak-quality-gate.md) | 1 |
