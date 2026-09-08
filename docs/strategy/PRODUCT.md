<!-- doc-role: product-contract -->
# Current product contract

Kuantra is a local-first **Execution Intelligence & Trade Forensics workstation** for
discretionary crypto/perps traders. The initial value chain is import → explainable
reconciliation → source-linked Trade Evidence Pack → weekly review → versioned rule
evaluation. Improved decision quality is a goal to measure, not a proven profitability claim.

## Binding boundaries

- Entry market: Binance/OKX crypto perpetual users. Exact supported venue/market,
  settlement, position mode and source format must be stated and independently tested.
  Spot public testnet is not perps account reconciliation evidence.
- First production target is read-only forensics/review. AI, live orders, HFT/FIX,
  DEX, copy trading, remote plugins and broad multi-asset support are not prerequisites
  and must not be promoted from disabled placeholders into production capability.
- Deterministic risk is the authority; AI has no order tools or override authority.
- Canonical evidence is append-only SQLite, with deterministic rebuildable projections;
  DuckDB is not the source of truth. Corrections preserve lineage. Historical/source
  completeness and economic dedup are distinct from hash integrity.
- Missing fee/funding/price/coverage remains unknown or incomplete, never synthetic zero
  or successful reconciliation. Instrument/fee currencies cannot be silently mixed.
- Current desktop is Python/FastAPI + React/pywebview. Windows WebView2, Mac WKWebView,
  Linux Qt follow platform contracts. Rust/IPC/data-plane expansion needs measured demand.
- Local-first does not currently prove network isolation. Privacy, offline operation,
  restore and exact-artifact verification require their own tests.
- No real user migration data exists for the Mac move. No Windows data copy, migration
  ZIP, real credential transfer or destructive reset is authorized.
- First-user and production readiness are unproven until the roadmap gates pass.
  Current release claims are constrained by the release truth matrix. Same-candidate
  three-OS final artifact evidence and owner release approval remain required.
- Commercial scope, license text, signing accounts, pilot consent and prices are owner
  decisions. `package.json` MIT metadata does not resolve the missing LICENSE file.

## Relevant references, not mandatory startup reading

[ADR-0001: identity](adr/ADR-0001-product-identity-and-entry-market.md),
[ADR-0002: storage](adr/ADR-0002-evidence-ledger-and-storage.md),
[ADR-0003: execution authority](adr/ADR-0003-execution-authority-boundary.md),
[ADR-0004: Windows renderer](adr/ADR-0004-windows-webview2-renderer.md),
[release truth](../release/README.md).

This concise contract consolidates existing decisions; it does not supersede Accepted
ADRs or approve Proposed roadmap scope/estimates. The historical KPS audit/market
research is archived, not a second current development plan.
