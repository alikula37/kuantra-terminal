# Kuantra Terminal v1.0.0 (Mac candidate)

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
trading outcomes. There is no real-user pilot evidence yet. The current private
`pilot-v1.0.0-arm64` prerelease is a closed, trusted-pilot transport for the verified
Apple Silicon and Intel lanes; it is not a public or production release. See the
[current status](docs/strategy/STATUS.md) for open correctness risks, evidence limits
and the remaining P1 delivery order.

## v1.0.0 scope

The first supported release target is macOS 12 Monterey or later on arm64 and x86_64.
Each architecture is built and distributed as its own native DMG; Universal2 is not a
v1 artifact. The release artifact must be a Developer ID-signed and notarized DMG; the
current local artifacts remain ad-hoc and development-only until the owner supplies Apple
signing/notarization access. Windows and Linux are outside the v1.0.0 release claim.
For the three-person pilot, separate Apple Silicon / M-series and Intel DMGs are at the private
[`pilot-v1.0.0-arm64` Release](https://github.com/alikula37/kuantra-terminal/releases/tag/pilot-v1.0.0-arm64).
The Release notes identify the exact source commit and artifact hashes for both architectures.
Both paths use hash-verified ad-hoc DMGs and manual Gatekeeper approval; this is
trusted-pilot-only, not a public or production distribution. Pilot operators should read
[`PILOT-INSTRUCTIONS.md`](docs/release/PILOT-INSTRUCTIONS.md), the
[M-series instructions](docs/release/PILOT-INSTRUCTIONS-M-SERIES.md) for the arm64-only
package. Technical manifests/checksums remain in the audit package rather than the
two-download Release list. Read the
[distribution research](docs/release/PILOT-DISTRIBUTION-RESEARCH.md). A Mac must actually run
macOS 12 or later; not every older Intel model can run Monterey, so “all Macs from the last ten
years” is not a valid support claim. The pilot team may also supply native Intel runtime/N03
evidence when the x86_64 artifact is available; this does not turn a normal user profile into
clean-profile evidence or broaden the support claim.
The old v1.4.0 publication, older release entries and their version tags were removed from
GitHub on 2026-09-11 at the owner's request. Repository archive and truth files may still
mention them for audit history only; none is a current download source.

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
- External trade journal records are the default New Trade path. The form accepts a
  user-supplied symbol for any asset, uses only exact free public quotes when a source
  supports it, and asks for the actual price manually when the quote is unavailable.
  Quote freshness is explicit (`LIVE`, `DELAYED`, `EOD`, `UNAVAILABLE`); no paid data
  service, automatic simulation fallback or live order is involved. First setup does not
  collect exchange or market-data credentials; optional read-only connector settings are
  separately gated.
- EN/TR/DE i18n parity and a reproducible native build/smoke gate for the macOS arm64 and
  x86_64 candidate artifacts; no v1 release claim is made for other operating systems.
- Local TP1/TP2/TP3 and SL tracking for long/short journal entries, with explicit
  user-entered allocations, revision-checked editing and partial/full local closes.
  New manual entries enable tracking by default; historical/imported entries do not.
  Local gross estimates stay separate from external fills and actual-trade analytics.
  Tracking requires the app to be open and awake, plus a matching provider-event quote
  no older than 60 seconds. Binance/Bybit recent-trade adapters qualify; existing
  Yahoo/Stooq/Biquote feeds remain display-only for automatic tracking. Missing or
  delayed quotes wait; they never create an assumed fill. No broker order is sent.

## Explicitly experimental/disabled

The following are retained only as research code or read-only UI placeholders;
they are not production capabilities:

- local GGUF/GPU telemetry, AI swarm and unverified model inference;
- DEX/RPC/DeFAI/loan-arbitrage opportunity or execution paths;
- wearable biometrics, FIDO/WebAuthn and stress lockout override;
- MT5, Polygon and TwelveData live transports;
- paid market-data quote services or API-key-based quote fallbacks;
- generic FIX/DMA, internal matching as a venue, and unvalidated venue-latency claims;
- reverse-skill agent deployment and unverified MCP source retrieval;
- remote ModStore download, hot-mount and arbitrary plugin execution.

See [`docs/strategy/`](docs/strategy) for the decision log, ADRs, evidence
gates and work-package status. STATUS selects the current package and records exact
artifact evidence. P1-WP29 owns trusted-pilot distribution; P1-WP31 adds local TP
tracking. P1-WP30 is archived as the bounded free multi-asset journal implementation.
P1-WP28 has native Intel CI evidence; N03 clean-profile, N05 signing/notarization and
H05 commercial/dependency decisions remain separate production gates.
A disabled surface is a deliberate truth result, not a failed demo.

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

Coding agents start at [AGENTS.md](AGENTS.md), not the historical archive. It selects
the five current documents and defines how progress is updated after each task.

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

Before any release-candidate handoff, run the full local gate (the canonical CI source
while GitHub Actions quota is unavailable):

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
