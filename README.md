# Kuantra Terminal v1.4.0

[![CI truth gates](https://img.shields.io/badge/CI-truth%20gates%20required-0ea5e9)](https://github.com/alikula37/kuantra-terminal/actions)

Kuantra is a **local-first Trade Forensics & Execution Intelligence workstation**.
It combines a trader's journal, recorded market context, deterministic risk
checks, replay, analytics, and provenance-aware review in one desktop shell.

The product boundary is intentionally narrow: the current release does not
claim unvalidated venue-grade latency, certified venue transport, or AI-controlled order submission,
chain transaction execution, biometric safety authority, or a remote extension marketplace.
Those surfaces return an explicit unavailable/experimental state until their
transport, source, security, and reconciliation contracts are implemented.

## Verified core in this release

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
- EN/TR/DE i18n parity and a 3-OS build/smoke CI gate.

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

The long-term target is an append-only evidence ledger (`Intent -> RiskDecision
-> OrderSubmitted -> Ack -> Fill -> Position -> JournalReview`) with canonical
event hashes, Parquet history and a read-only local AI Auditor. A real data
plane or model sidecar is not implied by the current Python desktop build.

## Development

Prerequisites: Python 3.11+, Node.js 20+, and npm. Use a fresh data directory
for tests so local journal state cannot affect results.

```bash
# backend dependencies
pip install -r backend/requirements.txt -r backend/requirements-desktop.txt

# isolated backend suite
KUANTRA_DATA_DIR="$(mktemp -d)" python -m pytest backend/tests -q

# frontend
npm --prefix frontend install
npm --prefix frontend test -- --run
npm --prefix frontend run build
```

For a desktop build, use `scripts/build_desktop.py` followed by
`scripts/smoke_desktop.py`. Platform runbooks live in
[`docs/BUILD_WINDOWS.md`](docs/BUILD_WINDOWS.md), [`docs/BUILD_MACOS.md`](docs/BUILD_MACOS.md)
and [`docs/BUILD_LINUX.md`](docs/BUILD_LINUX.md).

## Security and product truth

Never put exchange secrets in source control or SQLite. Configure an OS
credential manager before saving connector credentials. AI and experimental surfaces
have no execution authority. Do not interpret an `EXPERIMENTAL_DISABLED`, `NO_DATA`
or `UNAVAILABLE` response as a quote, fill, model decision or broker acknowledgement.

The repository is private during commercial product development. Contributions
and review ownership are documented in [`CONTRIBUTORS.md`](CONTRIBUTORS.md).

## License

This repository currently retains the MIT license in [`LICENSE`](LICENSE).
