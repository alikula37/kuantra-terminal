# Kuantra Terminal Architectural Deep-Dive

This document provides a comprehensive technical breakdown of Kuantra Terminal's multi-process desktop architecture, IPC streaming protocols, dual-engine storage model, and AI Swarm decision pipelines.

---

## 1. Process Isolation & Dynamic Port Handshake

```
+-----------------------------------------------------------------------------------+
| Tauri 2.0 Rust Process                                                            |
|  ├── Spawns Nuitka C++ Compiled Sidecar: `kuantra-backend`                        |
|  ├── Listens to stdout line: `KUANTRA_BACKEND_PORT:<port>`                        |
|  └── Injects dynamic port into Webview runtime & WebView window                   |
+-----------------------------------------------------------------------------------+
                                    │
                        IPC Child Process Pipe (stdin/stdout)
                                    │
+-----------------------------------v-----------------------------------------------+
| Python / FastAPI Sidecar Process                                                  |
|  ├── Dynamic Port Allocator (binds to ephemeral port 0)                           |
|  ├── Parent Process Watcher (monitors parent PID; terminates cleanly on exit)     |
|  └── Asyncio REST & WebSocket Event Loop                                          |
+-----------------------------------------------------------------------------------+
```

### Parent Watcher & Zero-Zombie Guarantee
The Python sidecar initializes a daemon thread `ParentProcessWatcher`. If the parent Tauri PID terminates (or is killed via Task Manager / SIGKILL), the sidecar terminates all worker threads, cancels open network sockets, and exits immediately (`sys.exit(0)`), guaranteeing zero orphan zombie processes.

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