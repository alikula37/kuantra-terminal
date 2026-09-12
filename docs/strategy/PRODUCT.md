<!-- doc-role: product-contract -->
# Current product contract

Kuantra is a local-first **Execution Intelligence & Trade Forensics workstation** for
discretionary traders. Account reconciliation initially targets the declared crypto/perps
market, while the journal also accepts manually recorded trades for any user-supplied
asset symbol. The initial value chain is import → explainable reconciliation → source-linked
Trade Evidence Pack → weekly review → versioned rule evaluation. Improved decision quality
is a goal to measure, not a proven profitability claim.

## Binding boundaries

- Entry market for automated account evidence: Binance/OKX crypto perpetual users.
  Exact supported venue/market, settlement, position mode and source format must be
  stated and independently tested. Spot public testnet is not perps account
  reconciliation evidence. This does not prevent a user from journaling another asset
  manually or with an exact free quote when one is available.
- Manual journal entries distinguish spot purchases from long/short positions through
  an explicit `position_type`. This is user-declared journal metadata, not broker
  verification or expanded account reconciliation. Older entries remain `UNKNOWN`.
- First production target is read-only forensics/review. The New Trade surface records
  an external fill by default; explicit simulation is available for testing, and neither
  path sends an order. AI, live orders, HFT/FIX, DEX, copy trading and remote plugins are
  not production capabilities. Multi-asset journal input is not a claim of broad
  multi-asset broker reconciliation.
- Deterministic risk is the authority; AI has no order tools or override authority.
- Canonical evidence is append-only SQLite, with deterministic rebuildable projections;
  DuckDB is not the source of truth. Corrections preserve lineage. Historical/source
  completeness and economic dedup are distinct from hash integrity.
- Missing fee/funding/price/coverage remains unknown or incomplete, never synthetic zero
  or successful reconciliation. Instrument/fee currencies cannot be silently mixed.
  A free quote is accepted only with explicit source identity and `LIVE`, `DELAYED` or
  `EOD` status; otherwise price status is `UNAVAILABLE` and the actual price must be
  entered manually.
- Free quote sources are limited to the unauthenticated public Binance, Bybit, Yahoo
  Finance and Stooq adapters. Paid market-data services and quote API keys are not
  integrated. A symbol is never silently rewritten to a different instrument; a
  TradingView alert is a pending observation until the user confirms the external fill.
- First setup does not collect exchange secrets or market-data credentials. Optional
  read-only connector settings remain separately gated and do not grant New Trade any
  live-order authority.
- Current desktop is Python/FastAPI + React/pywebview. Windows WebView2, Mac WKWebView,
  Linux Qt follow platform contracts. Rust/IPC/data-plane expansion needs measured demand.
- Local-first does not currently prove network isolation. Privacy, offline operation,
  restore and exact-artifact verification require their own tests.
- No real user migration data exists for the Mac move. No Windows data copy, migration
  ZIP, real credential transfer or destructive reset is authorized.
- Owner decision (2026-09-10): the first production release is macOS-only and is planned
  for direct distribution as separate native arm64 and x86_64 DMGs on macOS 12 Monterey or
  later. Intel support is closed by native Intel CI build and exact mounted-DMG smoke
  evidence; a physical Intel pilot is useful additional confidence but is not a release
  prerequisite. Universal2, Windows and Linux are not v1 artifacts. Apple membership/
  signing access is a release-candidate gate, not a development prerequisite.
- First-user and production readiness are unproven until the roadmap gates pass.
  Current release claims are constrained by the release truth matrix. For v1, exact
  macOS artifact evidence and owner release approval remain required; the existing
  three-OS policy is retained only for a future multi-platform release.
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
