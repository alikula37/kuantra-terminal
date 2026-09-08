# Kuantra Terminal Architectural Deep-Dive

This document provides a comprehensive technical breakdown of Kuantra Terminal's single-process
desktop architecture, in-process request dispatch and push streaming, dual-engine storage model,
and explicit experimental boundaries. Current priorities and evidence limitations are
defined in the [current status](docs/strategy/STATUS.md). Coding starts at [AGENTS.md](AGENTS.md).

---

## 1. Single-Process Desktop Shell (pywebview + in-process FastAPI)

The desktop application is one OS process. A pywebview window renders the React bundle from a
`file://` URL and calls Python directly through `window.pywebview.api`; the FastAPI application
runs on a dedicated asyncio loop inside the same process and is dispatched over ASGI. **No local
HTTP port sits between the UI and the backend.**

```
+------------------------------ one OS process ------------------------------+
|  backend/desktop_main.py                                                    |
|  +--------------+   js_api (thread per call)  +-------------------------+   |
|  | pywebview    | --------------------------> | DesktopBridge           |   |
|  | window(s)    | <----- run_js push batches -|  request()  stream_open |   |
|  | file://.../  |                             |  save_file() download() |   |
|  | index.html   |                             |  open_popout() ...      |   |
|  +--------------+                             +------------+------------+   |
|                                                            | run_coroutine_threadsafe
|  +---------------------------------------------------------v--------------+ |
|  | BackendRuntime: dedicated asyncio loop thread                          | |
|  |   FASTAPI app (create_app())  <-- httpx.ASGITransport (in-process)      | |
|  |   lifespan: binance_client.start()/stop()                              | |
|  |   ws_manager.broadcast() --> PushChannel sink --> window.__kuantraPush  | |
|  |   IntegrationsGateway (optional uvicorn on 127.0.0.1:8765)              | |
|  |      /ws/tv-sync  (Chrome extension)   /api/v1/webhook/tradingview      | |
|  +------------------------------------------------------------------------+ |
+-----------------------------------------------------------------------------+
```

### GUI Backends

| Platform | pywebview backend | Engine | Runtime prerequisite |
|:---|:---|:---|:---|
| macOS | `cocoa` | WKWebView | none (OS component) |
| Windows | `edgechromium` | WebView2 Evergreen | WebView2 runtime; see Accepted ADR-0004 |
| Linux | `qt` | PyQt6 + PyQt6-WebEngine | X11/XCB system libraries (see `docs/BUILD_LINUX.md`) |

### JS to Python Bridge

`DesktopBridge` is exposed as `window.pywebview.api`. Every method is a synchronous Python
function that pywebview runs on its own thread and surfaces to JS as a Promise:

- `request(req)` — serialized HTTP request (method, path, query, headers, body, multipart files)
  dispatched through `httpx.ASGITransport` and returned as `{status, headers, body|body_b64}`.
  The frontend adapter `frontend/src/lib/backend.ts` rebuilds a real `Response`, so all call sites
  keep `fetch` semantics.
- `stream_open()` — returns the initial snapshot and registers the push sink.
- `open_popout`, `save_file`, `download`, `copy_text`, `open_external`, `get_app_info`.

Push streaming replaces the old WebSocket: `ws_manager` broadcasts into a `PushChannel` sink that
flushes batched message arrays to `window.__kuantraPush(batch)` every 50 ms, in the exact message
shapes the WebSocket used (`TICK`, `CANDLE_UPDATE`, `SNAPSHOT`, `COMPLIANCE_ALERT`,
`TV_SYNC_UPDATE`).

In a browser dev session (`npm run dev` + `python backend/main.py`) `window.pywebview` is absent
and the adapter falls back to real `fetch` and a real `WebSocket` against `127.0.0.1:8000`.

### Optional Integrations Gateway

Two features are consumed by *other programs* and therefore still need a socket: the TradingView
Chrome extension (`/ws/tv-sync`) and TradingView alert webhooks
(`/api/v1/webhook/tradingview`). They are served by a small FastAPI sub-app on uvicorn bound to
`127.0.0.1:8765` (`KUANTRA_GATEWAY_PORT`, `KUANTRA_GATEWAY_HOST`, `KUANTRA_GATEWAY_ENABLED`). The
port is pre-bound at startup; if it is busy the gateway is disabled, the event is logged, and the
application still starts. The frontend never talks to this port.

### Data Directory

Long-lived state lives outside the install tree so upgrades and uninstalls never destroy it:

| Platform | Location |
|:---|:---|
| macOS | `~/Library/Application Support/Kuantra Terminal` |
| Windows | `%LOCALAPPDATA%\Kuantra Terminal` |
| Linux | `$XDG_DATA_HOME/kuantra-terminal` (fallback `~/.local/share/kuantra-terminal`) |

`KUANTRA_DATA_DIR` overrides it. A non-frozen dev checkout keeps using `backend/data`. The
directory holds the SQLite/DuckDB databases, logs, plugin-directory metadata and the WebView
`localStorage` store.

### Packaging

PyInstaller freezes the process into a `--onedir --windowed` tree from the checked-in spec
`packaging/kuantra.spec`, which is then wrapped per platform: ad-hoc signed `.app` inside a DMG
(macOS), per-user NSIS installer that kills running instances (Windows), and an AppImage (Linux).
Every build ends with a headless `--smoke` self-test that mounts React, performs a JS to Python
roundtrip and an in-process `/health` call. `backend/app/version.py` is the single source of
truth for the version.

---

## 2. Dual-Engine Storage Architecture

Kuantra implements a specialized dual-database topology separating OLTP transaction processing from OLAP columnar analytics:

```
[ Realtime Orders & UI ]               [ Market Ticks & Vectorized Queries ]
           │                                             │
           v                                             v
+=====================+                       +=====================+
|  SQLite 3 OLTP      |                       |  DuckDB OLAP        |
|  (WAL Journal Mode) | === Shadow Sync ===>  |  (Columnar Store)   |
+=====================+                       +=====================+
| • ACID Transactions |                       | • Multi-GB Candles  |
| • Playbook Rules    |                       | • MAE / MFE Grid    |
| • User Preferences  |                       | • Measured Queries |
+=====================+                       +=====================+
```

### Shadow Hydration Recovery Engine
DuckDB trade hydration is a rebuildable analytical projection gated by canonical
evidence coverage (P1-WP05/06). Incomplete coverage must block hydration rather than
silently mix unverified records. A rebuild does not imply recovery of missing market
observations, and there is no universal 150ms/zero-loss claim. Do not delete a user's
DuckDB file to test recovery. Use isolated fixtures and explicit migration approval.

---

## 3. Financial MCP Gateway & Reverse-Skill Engine

**Historical design sketch, not runtime capability.** The diagram below is retained
only for context: remote MCP retrieval, reverse deployment and AI Swarm execution are
experimental/disabled. It is not an integration backlog or authority chain. A future
AI auditor, if separately approved, is read-only and cannot issue orders.

```
[ External Quant Feeds ]
 ├── SEC EDGAR (10-K Filings & Item 1A Risks)
 ├── Macro Fundamentals (Treasury 10Y/2Y Yields, CPI)
 ├── CryptoPanic Real-time Sentiment NLP
 └── On-Chain Network Flow (Gas, Whale Transfers)
           │
           v
+===================================================================================+
| Financial Model Context Protocol (MCP) Gateway                                    |
|  └── Asynchronous Client Dispatcher (BlockRunAI/awesome-finance-mcp)              |
+===================================================================================+
                                    │
                        Normalized Market Context
                                    │
                                    v
+===================================================================================+
| Reverse-Skill Strategy Transpiler & AI Swarm Studio                               |
|  ├── Pine Script v4/v5 AST Tokenizer (RSI, EMA, MACD, BB, ATR)                    |
|  ├── Kuantra Swarm DSL Generator & Python Agent Transpiler                        |
|  └── Statistical CSV Trade Log Reverse-Engineer (Archetype Inference)            |
+===================================================================================+
```

---

## 4. Multi-Layer Pre-Trade Risk Guardrail Interceptor

The deterministic risk/compliance boundary is the authority; AI consensus and wearable
scores are not risk gates. Missing price, compliance evidence, transport or reconciliation
must fail closed. A passing local risk verdict is not proof of broker acceptance or
permission to enable live execution. Follow [ADR-0003](docs/strategy/adr/ADR-0003-execution-authority-boundary.md)
and the [release truth matrix](docs/release/README.md); experimental broker/AI/biometric
surfaces remain unavailable. No real order is authorized by this architecture document.
