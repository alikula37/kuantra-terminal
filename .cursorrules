# 🏛️ KUANTRA TERMINAL — GLOBAL ARCHITECTURAL & AGENT RULES

All AI coding agents (Antigravity, Cursor, Copilot) operating on this repository MUST strictly abide by the following non-negotiable rules:

## 🌍 1. STRICT INTERNATIONALIZATION (i18n) PROTOCOL (ZERO HARDCODED STRINGS)
- NEVER write hardcoded user-facing text (Turkish, English, or German) directly in JSX/TSX.
- All UI strings MUST be invoked via `useTranslation()` using `t('namespace.key')`.
- Every new or modified translation key MUST be added simultaneously to ALL locale dictionaries (`/frontend/src/locales/tr.json`, `/frontend/src/locales/en.json`, and `/frontend/src/locales/de.json`).
- Missing keys or hardcoded JSX strings constitute a build-breaking violation checked by `npm run i18n:check`.

## 🚫 2. ZERO-MOCK PRODUCTION DATA INTEGRITY
- `Math.random()` price walkers, synthetic candle generators, and fake balance arrays are strictly forbidden in production bundles.
- Historical candle data MUST be fetched via unauthenticated public REST endpoints (Binance, Bybit, Yahoo Finance, Stooq) and cached locally in SQLite (`market_candles_cache`).
- Zero-trade databases must render authentic Empty State CTAs ($0.00 balance / 0 trades), never synthetic sinusoidal curves.
- Hardcoded default balances (e.g. $100,000) are forbidden; starting capital must be read dynamically from SQLite `user_initial_balance`.

## 🎛️ 3. MULTI-ASSET UNIVERSALITY & PROGRESSIVE PERSONA DISCLOSURE
- The application header must prioritize Portfolio Equity, Open R-Risk, and Daily Score over single-asset ticker banners.
- In 'Kuantra Lite' mode:
  * Sidebar MUST display strictly the 6 core views (Dashboard, Journal, Charts, Analytics, ModStore, Settings).
  * All 20+ specialized tabs, HFT DOM widgets, GPU meters, and docking presets MUST be purged from the DOM.
  * Active modules badge must render `LITE ÇEKİRDEK (0 Eklenti)` / `LITE CORE (0 Plugins)`.
- Heavy specialized libraries (PyTorch, DuckDB, Web3, Bleak, QuickFIX) must never be bundled in the core installer; they must be streamed on-demand via ModStore `.kmod` packages.

## 📦 4. ULTRA-LIGHT PACKAGING & LIFECYCLE MANAGEMENT (<30 MB)
- Windows (`.exe`) and macOS (`.dmg`) installers must strictly remain under 30 MB.
- NSIS installer and macOS lifecycle handlers MUST terminate running `kuantra-backend` and `Kuantra Terminal` instances prior to installation/update to prevent file-lock write errors.

## ✅ 5. DEFINITION OF DONE (DoD)
A task is complete ONLY when all 4 conditions are met:
1. `npm --prefix frontend run build` completes with 0 errors (including i18n parity check).
2. `pytest -v --tb=short` passes with 100% success rate across all test suites.
3. Complete translation parity between `tr.json`, `en.json`, and `de.json`.
4. Changes committed atomically with descriptive semantic messages and pushed to `origin/main`.
