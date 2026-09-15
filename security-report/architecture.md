# Kuantra Terminal — Architecture Map (Phase 1 Recon)

**Scan:** Deep profile, whole repository, sandboxed local checks
**Date:** 2026-09-15
**Scanner:** security-check v1.2.0 (`ersinkoc/security-check`, skill hash `4542ae2157a6a66ba7e06e34a0bd25198a6e145a9d193f9f23bca24505f7512c`, `skills-lock.json`)
**Codebase at scan time:** `2c961fe` (WP40 MT5 preview), working tree fixes applied during the scan

## Application type

Local-first desktop forensics terminal for retail futures traders, plus a dormant P2P copy
engine. Two ways to run the API layer:

| Mode | Process / interface | Bind | Principal |
|------|---------------------|------|-----------|
| Desktop (shipping) | pywebview WKWebView over in-process FastAPI (httpx ASGITransport); no socket | in-process | local user |
| Dev server | `uvicorn backend.main:app` | `127.0.0.1:8000` | local user |
| Integrations gateway | FastAPI app `desktop.gateway:build_gateway_app` | `127.0.0.1:8765` (non-loopback refused unless `KUANTRA_ALLOW_NON_LOOPBACK_GATEWAY=1`) | any process on the host / any browser page that can reach loopback |

Data: SQLite evidence ledger (+ migrations), DuckDB analytics projection, filesystem artifacts
under `KUANTRA_DATA_DIR` / user data dir.

## Tech stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.11, FastAPI, Pydantic v2, SQLite, DuckDB, hmac/hashlib, pywebview |
| Frontend | React + TypeScript, Vite, i18next (EN/TR/DE) |
| Packaging | PyInstaller (`packaging/kuantra.spec`), macOS DMG script, AppImage (Linux), Docker smoke image |
| CI/CD | GitHub Actions (`ci.yml`, `release.yml`), uv-locked Python deps with hashes, npm |

## Size

| Metric | Value |
|--------|-------|
| Backend Python files / LOC | 167 / ~42.6k |
| Frontend TS/TSX files / LOC | 123 / ~25.1k |
| Scripts (build/smoke/release) | 44 |
| HTTP routes (`@router.get/post/put/delete`) | 155 |
| WebSocket routes | 1 (`/ws/tv-sync`, origin-allowlisted) |

## Entry points

- REST: 155 routes under `/api/v1` (trades, journal, analytics, broker import, model download,
  reconciliation inbox, P2P copy, system/biometrics, ...). **No authentication dependency exists
  by design** — the desktop app is single-user and in-process; therefore every networkable
  surface must be constrained by binding + explicit guards.
- Webhooks: `POST /api/v1/webhook/tradingview` (HMAC or passphrase when configured).
- WebSocket: `/ws/tv-sync` (TradingView extension companion; origin allowlist
  `is_allowed_gateway_origin`, `backend/app/api/tv_sync_ws.py`).
- Gateway app (127.0.0.1:8765): webhook ingest router + TV sync WS only (after fix F2).
- Desktop IPC: pywebview JS API, local file dialogs; statement preview parses uploaded files
  in memory without persistence.

## Trust boundaries

| # | Lower-trust side | Higher-trust side | Control(s) |
|---|------------------|-------------------|------------|
| B1 | Browser page / local process → loopback gateway | Evidence journal, webhook ingest | loopback bind, route-surface isolation, HMAC/passphrase constant-time checks, bounded body |
| B2 | TradingView webhook sender → journal | Trade confirmations / observations | HMAC signature or passphrase; fail closed when unset |
| B3 | Imported broker/csv/mt5 files → parsers | Ledger / projections | strict template validation, row/size limits, no persistence for preview, provenance |
| B4 | P2P peer / master signal → copy engine | Follower order routing | shared-secret HMAC (fail closed), reject on invalid |
| B5 | Caller-supplied API payloads → endpoints | SQLite/DuckDB state, model downloader, migrations | Pydantic bounds, allowlists, path containment |
| B6 | Workflows / build scripts → release artifacts | GitHub Release (contents:write), DMGs | SHA-pinned actions, narrowed credentials, no silent binaries |

## Coverage units (material surface × boundary × attack class)

1. API input validation & resource bounds (B5) — schema bounds, list limits, body caps.
2. Filesystem containment (B5) — model artifact names, migration archive members.
3. Gateway & webhook exposure (B1/B2) — route surface, auth, constant-time, body limits.
4. P2P copy trust (B4) — signature verification, secret configuration, order routing.
5. Kill-switch / biometrics (B5) — no fabricated evidence, no hardcoded disarm secrets.
6. Broker/statement import (B3) — provenance amplification, output bounds.
7. Archive/migration (B5) — zip member extraction bounds, declared-size bypass.
8. Generated-code paths (B5) — reverse-skill codegen string handling.
9. Credentials/exchange integration (B5) — error surface, upstream detail echo.
10. CI/CD & packaging (B6) — action pinning, credentials persistence, tag input validation,
    binary provenance, shell strictness.
11. Frontend (B1) — i18n/DOM output encoding of imported values (sampled).

## Explicit out-of-scope / not exercised

- Live network probing, external pentest, or credential use (per audit constraints).
- macOS code signing / notarization trust chain (known unresolved distribution gap).
- Real broker endpoints and real XM statement parsing (no sample available; product obligation).
- GitHub-hosted runner execution of the hardened workflows (not runnable locally).
