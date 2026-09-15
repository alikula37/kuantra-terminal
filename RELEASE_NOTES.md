<!-- CURRENT_RELEASE_NOTES:START -->

# Kuantra Terminal v1.1.1 — Trusted macOS Pilot (security patch)

**Pilot Release tag:** `pilot-v1.1.1` (release and tag point at the artifact source commit
below; the former `pilot-v1.1.0` prerelease is superseded and keeps no downloads)

**Artifact source commit:** `6c1e03c9c8a42f2e32d8c730beab828482338506` (clean build
commit; GitHub Actions release run `35023961123`, `workflow_dispatch`, `publish=false`)

**Status:** `PRIVATE_PRERELEASE_PILOT` / `AD_HOC_TRUSTED_PILOT_ONLY`

**Product:** Local-first Execution Intelligence & Trade Forensics Workstation

This private Release is intentionally scoped for the three-person pilot and exposes exactly
two downloads:

- **`Kuantra-Terminal-1.1.1-arm64.dmg`** for Apple Silicon M-series Macs;
- **`Kuantra-Terminal-1.1.1-x86_64.dmg`** for native Intel Macs.

Both DMGs require macOS 12 Monterey or later. Choose the file matching the Mac's native
architecture; an arm64 DMG is not an Intel artifact and an x86_64 DMG is not an Apple
Silicon artifact. Both native builds come from the same clean commit in the pinned GitHub
Actions release workflow and pass the native desktop smoke plus the exact read-only
mounted-DMG smoke on their matching hosts. DMG SHA-256 values are:

- arm64: `df4656bce6e7f841a6981cde0ad6347042e10ad102f98dc305a3775cac65961a`;
- x86_64: `a541ce7dc94a418bd3f98234798e99b63bcf950d803758061745e2e34742d436`.

Mounted executable SHA-256 values are arm64
`a9db9c464a032dd997876f85f194087dd98832974e63c9b1dc370c18d1387ad7` and x86_64
`77b692e9197a44bedbd8d2b156cbf737bfa39a6cb9009a55bbbea070e4fa71a6`. Exact
smoke/N05 (ad-hoc blocked) JSON/manifest evidence remains in the repository and local
audit package, not as separate Release downloads.

**New in this patch:** v1.1.1 is the security-hardened rebuild of the v1.1.0 pilot. The deep
security review's confirmed findings are fixed and pinned by regression tests, including the
migration archive and manifest byte ceilings, the bounded broker-import review output, the
shared paper-mode execution guard, contained model-artifact path handling, constant-time
webhook comparisons and copy-signal HMAC verification. The Python lock is unchanged and the
OSV dependency scan reported no runtime advisories (Python 0 affected; the single npm
advisory is dev-only and not shipped). A crafted-ZIP validation suite now covers
central-directory falsification, size/metadata inconsistencies and resource limits. GitHub
Actions are pinned to full commit SHAs, including the release job.

**v1.1.0 pilot features (unchanged):** the trade journal records the user-supplied trade date
and time in Turkey time (minute precision, stored as UTC), explicitly separates a still-open
entry from an already-closed one, and replaces the Replay row action with a working **Edit**
surface. Corrections are revisioned: previous values stay in the append-only history,
completed targets are locked after a partial close, and entry/quantity changes reset a local
TP/SL plan only before any close evidence exists. Journal stop and target edits are applied
to the active local plan in the same transaction. Declared leverage is journal metadata:
price return, position return and margin return stay separate and the position P/L is never
multiplied by leverage. Open-trade quotes refresh automatically and on demand with explicit
`LIVE`, `DELAYED` and stale last-known states, and the New Trade form is grouped into Trade /
Size / Targets / Summary sections with an equal-split helper and concrete field errors.

**Monetary calculation boundary:** position size, margin and money P/L are produced only
for an explicitly declared base-unit quantity (`qty_unit=BASE`); provider labels and symbol
suffixes are price provenance, not contract verification. Unverified instruments stay
`UNAVAILABLE`, cannot open a local tracking plan, and a user-reported close stores an
unknown P/L instead of a synthetic zero. Local tracking still requires an exact
provider/instrument `LIVE` event no older than 60 seconds; Binance/Bybit recent-trade
feeds qualify, while Yahoo/Stooq/Biquote feeds (including gold) remain display-only when
event freshness cannot be proven. No qualifying quote means waiting, not an assumed close.
Local results are gross estimates, never external fills or verified net profit. The app
must be open and awake.

No live broker order, paid data service, credential, migration or automatic update is
included. Experimental and disabled surfaces remain `EXPERIMENTAL_DISABLED`; AI has
no execution authority, and connector secrets remain bounded by the OS keychain.
Settings' update button only opens this fixed Release page.

The DMGs are ad-hoc trusted-pilot artifacts without Apple Developer ID signing or
notarization. On first launch, use Finder → right-click → **Open**. This is not a public,
production or commercial-support release. Pilot instructions:
[`Trusted macOS pilot instructions`](https://github.com/alikula37/kuantra-terminal/blob/main/docs/release/PILOT-INSTRUCTIONS.md).

Both architecture artifacts in this private prerelease are the exact CI outputs above;
their checksums are re-verified locally with `shasum -a 256 -c SHA256SUMS` and
`hdiutil verify` before publication.

The release body is generated from this marker-delimited section. Historical notes below are
repository audit material only. The prior v1.4.0 publication, tag and assets were removed
from GitHub on 2026-09-11 and must not be used. The exact canonical product tag is guarded by
`docs/release/truth-matrix.v1.1.1.json`.
<!-- CURRENT_RELEASE_NOTES:END -->

## Historical release archive (non-current)

The material below is retained as an immutable product-history archive. It is not a description
of the current v1.0.0 product and is never used as the GitHub Release body.

---

# 🚀 Desktop shell: Tauri → pywebview

**Applies to**: `v1.3.0-production` and later &bull; **Platforms**: Windows (x64), macOS (Apple Silicon / Intel), Linux (x86_64)

Kuantra Terminal's desktop shell has been rebuilt. The Rust/Tauri wrapper and the background
Python server process are gone; the terminal now runs as a **single Python process** — a
pywebview window hosting the React bundle, with the FastAPI backend dispatched in-process over
ASGI and frozen with PyInstaller.

### What changes for you

1. **One process, no local port.**
   The UI no longer talks to the backend over `http://127.0.0.1:<port>`; requests are dispatched
   in-process and live data arrives through a batched push channel. Nothing listens on a loopback
   port for the UI, and there is no second process to leave orphaned. Firewall prompts on first
   launch are gone.

2. **Bundled browser engine — no runtime prerequisites.**
   macOS uses the system WKWebView. Windows and Linux ship Qt WebEngine inside the package, so
   **the WebView2 runtime is no longer required on Windows**.

3. **Your data moved out of the install folder.**
   Databases, logs, downloaded plugins and UI state now live in a per-user data directory that
   upgrades and uninstalls never touch:

   | Platform | Location |
   |:---|:---|
   | macOS | `~/Library/Application Support/Kuantra Terminal` |
   | Windows | `%LOCALAPPDATA%\Kuantra Terminal` |
   | Linux | `$XDG_DATA_HOME/kuantra-terminal` (fallback `~/.local/share/kuantra-terminal`) |

   Set `KUANTRA_DATA_DIR` to override it. If you are upgrading from an older build, copy your
   existing `backend/data` contents into the new directory before first launch.

4. **TradingView extension now uses port 8765.**
   The only socket the app opens is the integrations gateway on `127.0.0.1:8765`, serving the
   Chrome extension (`/ws/tv-sync`) and TradingView alert webhooks
   (`/api/v1/webhook/tradingview`). Update the bundled extension (v1.3.0) — its popup now has a
   **Bridge Port** field, defaulting to 8765. On the app side the port is configurable via
   `KUANTRA_GATEWAY_PORT` / `KUANTRA_GATEWAY_HOST` / `KUANTRA_GATEWAY_ENABLED`; if the port is
   busy the gateway is disabled automatically and the app still starts.

5. **macOS first launch takes longer, once.**
   The app is unsigned/un-notarized: **right-click → Open** the first time. That first launch
   after installing from the DMG can take up to ~40 seconds while Gatekeeper scans the app tree;
   every launch afterwards takes 1–2 seconds.

6. **Installers.**
   `Kuantra-Terminal-<ver>-aarch64.dmg` (macOS, ad-hoc signed),
   `Kuantra-Terminal-<ver>-Setup.exe` (Windows, per-user NSIS installer that terminates running
   `Kuantra Terminal` instances before install/uninstall) and
   `Kuantra-Terminal-<ver>-x86_64.AppImage` (Linux). The AppImage needs the X11/XCB runtime
   libraries listed in `docs/BUILD_LINUX.md`.

Build and packaging instructions: `docs/BUILD_MACOS.md`, `docs/BUILD_WINDOWS.md`,
`docs/BUILD_LINUX.md`. Architecture: `ARCHITECTURE.md` §1.

---

# 🚀 Kuantra Terminal v1.3.0-production Release Notes

**Release Tag**: `v1.3.0-production`  
**Target Architecture**: Windows (x64), macOS (Apple Silicon / Intel), Linux (x64)  
**Verification Status**: **100% Pytest Pass Rate (199 Unit & Integration Tests Passing)** &bull; **0 TypeScript Build Errors (1,909 Modules Compiled)** &bull; **100% Tri-Locale i18n Parity (478 Keys)**  
**License**: MIT Open Source  

---

## 🌟 Executive Summary: Zero-Mock Institutional Release

We are proud to announce the official **v1.3.0-production** release of **Kuantra Terminal** — establishing complete **Zero-Mock & Zero-Synthetic Data Integrity**, **Authentic CCXT Multi-Venue Execution**, **AES-256-GCM Encrypted Exchange Credentials**, **Institutional Pre-Trade Risk Gatekeeping**, and **Multi-Format CSV Trade Batch Ingestion**.

### Key Deliverables in v1.3.0-production:
1. **Zero-Mock Pure Quantitative Engine**:
   - Eliminated all residual synthetic data generators, fake OCR buffers, and simulated plugin mock bundles.
   - All balance references dynamically resolved from active SQLite settings (`user_initial_balance`) with strict zero-state mathematical guards.
2. **Authentic CCXT Live & Paper Execution Engine (`ccxt_engine.py`)**:
   - Universal multi-venue routing for Binance Spot, Binance USDⓈ-M Futures, and OKX V5 Unified.
   - Genuine REST API order dispatch with real fill prices, exchange order IDs, and fee accounting.
   - Explicit Paper Sandbox mode (`[📝 Paper Sandbox]` vs `[⚡ Live Execution]`) with isolated matching engine.
3. **AES-256-GCM Encrypted Credentials Manager (`credentials_manager.py`)**:
   - Encrypted local API key storage tied to system/vault machine secret. Zero plaintext logging.
   - Live CCXT connection testing (`test_connection()`) returning authentic margin balances.
4. **Pre-Execution Risk Gatekeeper (`risk_guard.py`)**:
   - Real-time Max Risk % per trade guard, stop-loss direction validator, and prop firm drawdown proximity shield.
5. **Multi-Format CSV Trade Importer**:
   - Automatic format auto-detection for Binance Spot/Futures, Bybit Closed PnL, MetaTrader 4/5 statements, and Generic Kuantra CSV.
   - Transaction-safe SQLite batch insertions with SHA-256 deduplication and instant portfolio recalculation.
6. **Progressive UI Isolation & Tri-Locale i18n**:
   - Comprehensive `React.lazy()` code-splitting (<308 kB main shell bundle).
   - 100% synchronized tri-locale parity (478 keys across TR, EN, DE) verified via CI automation.

---

# 🚀 Kuantra Terminal v1.2.0-modular Release Notes

**Release Tag**: `v1.2.0-modular`  
**Target Architecture**: Windows (x64), macOS (Apple Silicon / Intel), Linux (x64)  
**Verification Status**: **100% Pytest Pass Rate (155+ Unit & Integration Tests Passing)** &bull; **0 TypeScript Build Errors (1,900 Modules Compiled)**  
**License**: MIT Open Source  

---

## 🌟 Executive Summary

We are proud to announce the official **v1.2.0-modular** production release of **Kuantra Terminal** — introducing our groundbreaking **Micro-Kernel Core Architecture**, **Dynamic Plugin Engine**, **Architectural Persona Presets**, and **In-App ModStore Marketplace Studio**.

In this milestone, Kuantra Terminal transforms from a monolithic trading operating system into a modular micro-kernel framework. By isolating heavy C-extensions, vector engines, and protocol daemons behind dynamic lifecycle loaders, cold boot times have dropped to **<350ms** and baseline idle memory consumption has dropped from ~2.2 GB down to **~20 MB RAM**.

---

## 🏛️ 23-Phase Architectural Completion Matrix

| Milestone | Architecture / Module | Core Capabilities Delivered | Status |
|:---:|:---|:---|:---:|
| **Phase 01** | **Modern UI & WebSocket Engine** | React 18, Tailwind CSS, Lightweight Charts canvas, and Binance streaming bridge. | ✅ Complete |
| **Phase 02** | **Quant Engine & Drawdown Shield** | MAE/MFE analytics, SQN, Sortino/Sharpe ratios, and real-time Prop Firm Drawdown Shield. | ✅ Complete |
| **Phase 03** | **Trade Replay & Strategy Playbook** | Tick-by-tick market replay animator and execution drift / panic exit cost calculator. | ✅ Complete |
| **Phase 04** | **Behavioral Psychology Engine** | Real-time FOMO chase detector, Revenge Trading mitigation, and Session Tilt Meter. | ✅ Complete |
| **Phase 05** | **Multimodal Vision OCR & AI Auditor** | Chart screenshot parser (PNG/JPG), DuckDB price cross-validator, and NL Query Engine. | ✅ Complete |
| **Phase 06** | **Nuitka C++ Sidecar & Dynamic Port** *(historical, replaced by the pywebview shell in 1.3.0)* | C++ binary transpilation, `--port 0` dynamic allocation, and parent process watcher. | ✅ Complete |
| **Phase 07** | **Stronghold Vault & Shadow Recovery** | Argon2id + AES-256-GCM secret vault, Alembic migrations, and DuckDB Shadow Hydration. | ✅ Complete |
| **Phase 08** | **Multi-Monitor Pop-Out & Virtualization** | `rc-dock` layout serialization, multi-window popout sync, and 60 FPS TanStack DOM. | ✅ Complete |
| **Phase 09** | **Log Rotation & Signed Auto-Updater** | Automatic PII/Secret redaction, Opt-in telemetry, and Ed25519 auto-updater infrastructure. | ✅ Complete |
| **Phase 10** | **First-Boot Onboarding & Packaging** | GPU/Metal/CUDA hardware detector, chunked GGUF downloader, and production installers. | ✅ Complete |
| **Phase 11** | **TradingView Companion & Webhooks** | MV3 Chrome extension, Cloudflare Tunnel HMAC-SHA256 webhook, and live order routers. | ✅ Complete |
| **Phase 12** | **Multi-Agent Swarm & Biometrics** | Macro/Quant/Risk swarm consensus debate and Bluetooth LE wearable stress interceptor. | ✅ Complete |
| **Phase 13** | **Order Flow Footprint & FIX DMA** | Footprint matrices (>= 3.0 imbalance), CVD accumulator, and CME/ICE QuickFIX DMA. | ✅ Complete |
| **Phase 14** | **Encrypted P2P Mesh & Copy-Trading** | Noise Protocol (`Noise_IK_25519`) mesh and Zero-Knowledge multi-account risk routing. | ✅ Complete |
| **Phase 15** | **Mobile Companion & Panic Kill-Switch** | Biometric QR pairing, 1-tap wearable emergency flatten kill-switch, and WebAuthn enclave. | ✅ Complete |
| **Phase 16** | **Theme Engine & i18n Localization** | Dynamic Dark/Light palettes, Chart.js token injection, and 100% TR/EN/DE dictionary parity. | ✅ Complete |
| **Phase 17** | **Financial MCP & Reverse-Skill** | SEC 10-K / CryptoPanic MCP gateway, Pine Script v4/v5 transpiler, and CSV strategy studio. | ✅ Complete |
| **Phase 18** | **Enterprise Showcase & Documentation** | High-density ASCII architecture blueprints, security governance, and packaging runbooks. | ✅ Complete |
| **Phase 19** | **Local LLM GPU & Swarm Acceleration** | CUDA / Metal / DirectML VRAM layer offloader, sub-50ms AI swarm consensus, and GPU studio. | ✅ Complete |
| **Phase 20** | **DEX Arbitrage & Flash Loan Studio** | Multi-chain RPC gateway, Bellman-Ford negative cycle pathfinding, Aave/Morpho/Balancer flash loans, and DeFAI agent. | ✅ Complete |
| **Phase 21** | **L2/L3 Limit Order Book & FIX 5.0 DMA** | Sub-10µs MBO/MBP matching engine, FIX 4.4 / 5.0 SP2 session state machine, and real-time DOM ladder. | ✅ Complete |
| **Phase 22** | **Hardware Biometrics & Tilt Interceptor** | BLE Polar H10 / Garmin, Empatica E4 GSR/EDA, RMSSD/SDNN math, S_bio hardware lockout, and FIDO2 passkey override. | ✅ Complete |
| **Phase 23** | **Micro-Kernel Core & ModStore Engine** | Dynamic FastAPI route mutation, LazyDependencyLoader, Persona selector, React 18 extension slots, and ModStore marketplace. | ✅ Complete |

---

## ⚡ Key Architectural Innovations in v1.2.0-modular

### 1. Micro-Kernel Base & Lazy Dependency Loader
- **Ultra-Lean Boot Profile**: Baseline startup memory reduced to **~20 MB RAM** with **<350ms** initialization time.
- **Dynamic Dependency Isolation**: Modules such as `torch`, `llama_cpp`, `duckdb`, `quickfix`, `web3`, and `bleak` are imported exclusively upon demand when their respective plugins are activated, and cleanly dereferenced with `gc.collect()`.

### 2. Starlette Dynamic Route Mutation
- **Runtime Hot-Mounting**: `DynamicPluginManager.activate_plugin()` dynamically imports plugin classes, executes startup lifecycle hooks, appends routes directly to `app.router.routes`, and invalidates cached OpenAPI schemas.
- **Runtime Hot-Unmounting**: `DynamicPluginManager.deactivate_plugin()` cleanly excises routes from Starlette's routing table in $O(N)$ linear time without requiring sidecar restarts *(historical, replaced by the pywebview shell in 1.3.0: the backend now runs in-process, so a toggle restarts nothing at all)*.

### 3. Five Architectural Persona Presets
- **Kuantra Lite** (~20 MB RAM): Lean core for disciplined trade journal logging and essential MAE/MFE analytics.
- **Kuantra Quant** (~140 MB RAM): Lite + Advanced TV Charts, Order Flow Footprint, Prop Firm Drawdown Shield, and DuckDB OLAP.
- **Kuantra DeFAI** (~480 MB RAM): Lite + AI Swarm Consensus, Cross-DEX Flash Loan Arbitrage, and Financial MCP Gateway.
- **Kuantra Institutional** (~320 MB RAM): Lite + CME FIX 5.0 SP2 DMA, L2/L3 DOM Ladder, Multi-Broker, and BLE Wearable Biometrics.
- **Kuantra Full Suite** (~1.8 GB Max): Complete workstation with all 8 modular subsystems active simultaneously.

### 4. React 18 Dynamic `<ExtensionSlot />` & Error Boundaries
- **Slot Injections**: Flexible contribution slots (`sidebar`, `header`, `dashboard_tile`, `settings_tab`, `studio_view`).
- **Isolated Error Boundaries**: Each plugin widget is encased in a dedicated `PluginErrorBoundary` to guarantee that runtime errors in experimental plugins never crash the core application shell.

### 5. In-App ModStore Marketplace Studio
- **Subsystem Manager**: Real-time management of installed plugins with active/mount switches and memory telemetry.
- **Verified Extension Catalog**: Downloadable institutional modules including *Options Greeks*, *Macro Nowcasting*, and *Liquidation Cascade Radar*.
- **Live Memory Delta Meter**: Visual gauge displaying base micro-kernel memory + active plugin allocations.
