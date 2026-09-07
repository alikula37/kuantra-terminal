# Kuantra Terminal v1.4.0

[![Local merge gate](https://img.shields.io/badge/merge%20gate-local%20CI%20required-0ea5e9)](docs/strategy/LOCAL-CI-POLICY.md)

Kuantra is a **local-first Trade Forensics & Execution Intelligence workstation**.
It combines a trader's journal, recorded market context, deterministic risk
checks, replay, analytics, and provenance-aware review in one desktop shell.

The product boundary is intentionally narrow: the current release does not
claim unvalidated venue-grade latency, certified venue transport, or AI-controlled order submission,
chain transaction execution, biometric safety authority, or a remote extension marketplace.
Those surfaces return an explicit unavailable/experimental state until their
transport, source, security, and reconciliation contracts are implemented.

## Implemented core and validation boundaries

Implementation is not proof of complete perpetual-account reconciliation or improved
trading outcomes. There is no real-user pilot evidence yet. The current branch is not
automatically a new release of the version in this heading. See the
[current roadmap audit](docs/strategy/ROADMAP-REVIEW-2026-09-08.md) for open correctness
risks, evidence limits and the remaining P1 delivery order.

- SQLite WAL journal and transactional settings/metadata.
- DuckDB analytical projection for recorded candles/trades.
- Deterministic MAE/MFE, exit-efficiency, SQN, Sharpe/Sortino and compliance
  calculations when the required evidence exists.
- Replay and order-flow views that return `NO_DATA` instead of seeded market
  observations when no recorder/feed is connected.
- Fail-closed execution/risk boundary: missing price, compliance evidence,
  keychain, transport or reconciliation cannot become a fill.
- OS keychain credential storage (Windows Credential Manager, macOS Keychain or
  Linux Secret Service). Plaintext SQLite credential fallback is not supported.
- React + FastAPI + pywebview single-process desktop shell, with a browser
  development path and per-user data directory.
- EN/TR/DE i18n parity and a reproducible local build/smoke merge gate; cross-OS evidence is
  required before a release claim.

## Explicitly experimental/disabled

The following are retained only as research code or read-only UI placeholders;
they are not production capabilities:

- local GGUF/GPU telemetry, AI swarm and unverified model inference;
- DEX/RPC/DeFAI/loan-arbitrage opportunity or execution paths;
- wearable biometrics, FIDO/WebAuthn and stress lockout override;
- MT5, Polygon and TwelveData live transports;
- generic FIX/DMA, internal matching as a venue, and unvalidated venue-latency claims;
- reverse-skill agent deployment and unverified MCP source retrieval;
- remote ModStore download, hot-mount and arbitrary plugin execution.

See [`docs/strategy/`](docs/strategy/) for the decision log, ADRs, evidence
gates and work-package status. P0-WP08 is the current experimental-containment
package; a disabled surface is a deliberate truth result, not a failed demo.

## Runtime architecture

```text
KUANTRA TRUTH-SAFE DESKTOP
```

```text
React/WebView (desktop or browser dev)
        |
        v
FastAPI control plane + deterministic risk boundary
        |
  SQLite WAL  --->  DuckDB projection/query layer
        |
  recorded evidence / public market-data adapters
```

ModStore and REVERSE-SKILL remain visible only as experimental, disabled
surfaces; neither can download, hot-mount, deploy, or execute arbitrary code.

Append-only evidence ledger foundations, projections and Evidence Pack APIs/UI are
implemented. The complete future lifecycle (`Intent -> RiskDecision
-> OrderSubmitted -> Ack -> Fill -> Position -> JournalReview`), scaled Parquet
history and a read-only local AI Auditor are not implied by those foundations. A real data
plane or model sidecar is not implied by the current Python desktop build.

## Development

Prerequisites: Python 3.11+, Node.js 20+, and npm. Use a fresh data directory
for tests so local journal state cannot affect results.

```bash
# backend dependencies
uv venv --python python3.11 .venv
source .venv/bin/activate
uv pip install -r backend/requirements.lock

# isolated backend suite
KUANTRA_DATA_DIR="$(mktemp -d)" python -m pytest backend/tests -q

# frontend
npm --prefix frontend ci
npm --prefix frontend test -- --run
npm --prefix frontend run build
```

For a desktop build, use `scripts/build_desktop.py` followed by
`scripts/smoke_desktop.py`. Platform runbooks live in
[`docs/BUILD_WINDOWS.md`](docs/BUILD_WINDOWS.md), [`docs/BUILD_MACOS.md`](docs/BUILD_MACOS.md)
and [`docs/BUILD_LINUX.md`](docs/BUILD_LINUX.md).

For the current Mac move there is no real user data: start with a clean data directory,
let Kuantra create its SQLite schema, and do not copy Windows data, credentials or bundles.
Only when real user data exists, use the credential-safe, hash-verified migration
bundle documented in [`docs/MACOS_MIGRATION.md`](docs/MACOS_MIGRATION.md). The
bundle carries the canonical SQLite ledger and Parquet cold storage; DuckDB is
rebuilt locally and OS keychain credentials are re-entered on the destination.

Before merging to `main`, run the full local gate (the canonical CI source while GitHub
Actions quota is unavailable):

```bash
uv run --offline --no-project --with-requirements backend/requirements.lock python scripts/run_local_ci.py
```

The command writes `dist/local-ci-report.json` and must end with `MERGE READY`.
`uv --offline` run restricts dependency resolution, not runtime network: current startup
can connect to public market data. Initial dependency installation may require network
and is not offline proof. A packaged
smoke report can be green while the frozen renderer falls back; the gate rejects that
condition explicitly. Windows defaults to the Evergreen WebView2 host; Linux defaults to Qt
WebEngine. The production Windows payload intentionally excludes Qt; `PYWEBVIEW_GUI=qt` is
supported only by a source or separately-built diagnostic package and is not a production
fallback.

## Security and product truth

Never put exchange secrets in source control or SQLite. Configure an OS
credential manager before saving connector credentials. AI and experimental surfaces
have no execution authority. Do not interpret an `EXPERIMENTAL_DISABLED`, `NO_DATA`
or `UNAVAILABLE` response as a quote, fill, model decision or broker acknowledgement.

The repository is private during commercial product development. Contributions
and review ownership are documented in [`CONTRIBUTORS.md`](CONTRIBUTORS.md).

## License

`package.json` declares MIT, but this checkout has no repository `LICENSE` file.
The owner must resolve the intended license text and third-party notices before
public/commercial distribution; this documentation audit does not grant a license.
