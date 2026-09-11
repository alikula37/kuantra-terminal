<!-- CURRENT_RELEASE_NOTES:START -->
# Kuantra Terminal v1.0.0 — Mac Candidate Truth & Safety — M-series Trusted Pilot update

**Pilot Release tag:** `pilot-v1.0.0-arm64`
**Artifact source commit:** `7f1ad482d41c16f6ac8e7ddbe8dbb66e945f63be`
**Release status:** `PRIVATE_PRERELEASE_PILOT` / `AD_HOC_TRUSTED_PILOT_ONLY_ARM64`
**Product identity:** Local-first Execution Intelligence & Trade Forensics Workstation

The existing private GitHub Release at
[`pilot-v1.0.0-arm64`](https://github.com/alikula37/kuantra-terminal/releases/tag/pilot-v1.0.0-arm64)
is refreshed in place with the exact arm64 package built from the source commit above.
The tag and download URL are unchanged; this is a closed trusted-pilot transport, not the
canonical `v1.0.0` product Release, a public download or a production/commercial-support
artifact. The package targets macOS 12 Monterey or later on native Apple Silicon `arm64`.
Intel `x86_64` evidence is still pending and is not implied by this asset set.

The package contains the bounded P1-WP30 free multi-asset journal and quote provenance flow.
External journaling is the default; simulation is explicit only; exact free public quotes
remain source/status-bound; unavailable prices require manual entry; and TradingView alerts
remain immutable `PENDING_REVIEW` observations until explicit user confirmation. No paid
data service, live broker order or automatic simulation fallback is included.

The verified local core includes trade journaling and forensics, deterministic risk checks,
recorded-evidence analytics/replay, SQLite WAL plus DuckDB projection, OS keychain credential
references, and the React/FastAPI/pywebview desktop shell. This update also hardens the pilot
flow: unknown financial values stay visibly unknown, review decisions stay bound to the
displayed period/timezone/as-of snapshot, malformed successful responses are rejected before
rendering, journal pagination is non-destructive, and Evidence Pack JSON/HTML/CSV exports report
the actual native save/cancel/failure outcome.

Current verification evidence:

- Locked arm64 local CI: **MERGE READY**; backend **829 passed / 2 warnings**, frontend
  **27 test files / 121 tests**, EN/TR/DE **696/696**, TypeScript and production build pass,
  native PyInstaller/WKWebView smoke and `COMPLETE` provenance.
- DMG `Kuantra-Terminal-1.0.0-arm64.dmg`: SHA-256
  `eb7d8d8a9601086e86bf8113685f2274eb92dde20a29395585445b77d164890b`.
- Exact mounted executable: SHA-256
  `7247220e839f47a98f44f8f07fbd0b230c844781c4fc87cda2215bbe358ac765`.
- Final mounted-DMG smoke report: SHA-256
  `4f8f6c322d1e2902e068536f33673aa72dff24b56da2f1865144ee0810b7ba41`.
- Pilot manifest SHA-256: `13e3a821922ea08c9d0a50a831ed3c98ead9d4bd746570e4da5687cd8f31e83f`.
- `SHA256SUMS` SHA-256: `947c6e6c8a39ada91639bfb32baefbef9836edd876f51b598a71272759fd7137`.
- Tracked source tree SHA-256: `fadf647b0f0bcad7fecaef2b43c87d9db8d17212068ea015d33e9c9f16ef73ec`.
- Local-CI report SHA-256: `86b6f066447d8cced255c777ece1c937d02848039486e7e310d19380e11b627e`.
- N05 distribution preflight: structurally valid but intentionally
  `BLOCKED/OWNER_REVIEW_REQUIRED` because this zero-cost pilot DMG is ad-hoc and not
  Developer ID signed/notarized.

`PILOT-MANIFEST.json`, `SHA256SUMS` and the standalone
[`PILOT-INSTRUCTIONS-M-SERIES.md`](https://github.com/alikula37/kuantra-terminal/blob/main/docs/release/PILOT-INSTRUCTIONS-M-SERIES.md)
bind the package contents, source and hashes. Download integrity checks do not provide Apple
malware or Gatekeeper trust; users must verify the checksums and follow the manual Gatekeeper
procedure. `EXPERIMENTAL_DISABLED` surfaces remain unavailable and have no execution authority:
live broker submission/reconciliation, FIX/DMA transport, venue-grade order-flow latency, local
model/GPU telemetry, AI swarm, DEX/DeFAI, biometrics, external MCP retrieval and remote plugin
download/hot-mount. `NO_DATA`, `UNKNOWN` and `UNAVAILABLE` are not success, quotes, fills or
broker acknowledgements. OS keychain remains the only supported credential boundary; no
plaintext credential fallback is introduced.

The release body is generated from this marker-delimited section. Historical notes below remain
for repository audit only and are not included in the GitHub Release body. The prior v1.4.0
publication, tag and assets were removed from GitHub on 2026-09-11 and must not be used; any
remaining repository references are historical evidence only. The later dual-architecture
pilot still requires native x86_64 evidence, and N05 remains the owner-controlled
signing/notarization gate.
The exact canonical product tag is guarded by
`docs/release/truth-matrix.v1.0.0.json`.
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
