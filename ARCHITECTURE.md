# Kuantra Terminal Architectural Deep-Dive

This document provides a comprehensive technical breakdown of Kuantra Terminal's single-process
desktop architecture, in-process request dispatch and push streaming, dual-engine storage model,
and AI Swarm decision pipelines.

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
| Windows | `qt` | PyQt6 + PyQt6-WebEngine | none — the engine is bundled; WebView2 is **not** required |
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

### Integrations Gateway (the only socket)

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
directory holds the SQLite/DuckDB databases, logs, downloaded plugins and the WebView
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
| • User Preferences  |                       | • Sub-ms Aggregates |
+=====================+                       +=====================+
```

### Shadow Hydration Recovery Engine
DuckDB acts as an ephemeral, ultra-fast vectorized cache. If the DuckDB file is deleted, corrupted, or schema-modified:
1. `DuckDBHydrator` detects the anomaly automatically.
2. Extracts canonical historical trade records from SQLite OLTP.
3. Vectorizes and reconstitutes the DuckDB database in under **150ms** with zero data loss.

---

## 3. Financial MCP Gateway & Reverse-Skill Engine

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

Every order proposal passes through 4 deterministic safety gates prior to broker transmission:

1. **Panic Circuit-Breaker**: Verifies terminal is not in `READ_ONLY_LOCKDOWN`.
2. **Biometric Wearable Interceptor**: Blocks execution if Physiological Tilt Score $\ge 75$ ($S_{bio} = \frac{BPM}{1.5} + (100 - HRV) \times 0.6$).
3. **Multi-Agent Swarm Consensus**: Conducts debate round-robin between `MacroAgent`, `QuantAgent`, and `RiskAgent`. If `RiskAgent` dissents, the order is vetoed.
4. **Prop Firm Compliance Shield**: Enforces max daily drawdown and total account loss limits.