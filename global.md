# 🏛️ KUANTRA TERMINAL — GLOBAL ARCHITECTURAL & AGENT RULES

All coding agents must follow current user instructions and the accepted strategy/ADRs.
See [current remaining work and evidence limits](docs/strategy/ROADMAP-REVIEW-2026-09-08.md).
These rules do not authorize live orders, credential access, data deletion or main merges.

## 🌍 1. STRICT INTERNATIONALIZATION (i18n) PROTOCOL (ZERO HARDCODED STRINGS)
- NEVER write hardcoded user-facing text (Turkish, English, or German) directly in JSX/TSX.
- All UI strings MUST be invoked via `useTranslation()` using `t('namespace.key')`.
- Every new or modified translation key MUST be added simultaneously to ALL locale dictionaries (`/frontend/src/locales/tr.json`, `/frontend/src/locales/en.json`, and `/frontend/src/locales/de.json`).
- Missing keys or hardcoded JSX strings constitute a build-breaking violation checked by `npm run i18n:check`.

## 🚫 2. ZERO-MOCK PRODUCTION DATA INTEGRITY
- `Math.random()` price walkers, synthetic candle generators, and fake balance arrays are strictly forbidden in production bundles.
- Market context must use implemented, permitted sources with provenance and coverage.
  Missing/unverified data stays explicit; do not add a new feed or open network merely to fill a view.
- Zero-trade databases must render authentic empty states. Unknown account balance is unknown,
  not an invented $0.00 balance or synthetic equity curve.
- Hardcoded default balances (e.g. $100,000) are forbidden; starting capital must be read dynamically from SQLite `user_initial_balance`.

## 🎛️ 3. PRODUCT SCOPE & PROGRESSIVE DISCLOSURE

The entry persona is discretionary crypto/perps; multi-asset universality is not a
current requirement. The historical Lite layout below is not permission to expand
or redesign the active P1 import/review workflow.
- The application header must prioritize Portfolio Equity, Open R-Risk, and Daily Score over single-asset ticker banners.
- In 'Kuantra Lite' mode:
  * Sidebar MUST display strictly the 6 core views (Dashboard, Journal, Charts, Analytics, ModStore, Settings).
  * All 20+ specialized tabs, HFT DOM widgets, GPU meters, and docking presets MUST be purged from the DOM.
  * Active modules badge must render `LITE ÇEKİRDEK (0 Eklenti)` / `LITE CORE (0 Plugins)`.
- Do not add heavy experimental libraries to the core installer. ModStore downloads,
  hot-mounting and arbitrary plugin execution remain disabled; on-demand streaming
  is not an available alternative. Dependencies follow the checked-in lock/spec.

## 📦 4. PACKAGING & LIFECYCLE MANAGEMENT
- The desktop app is a single pywebview + in-process FastAPI process frozen with PyInstaller (`packaging/kuantra.spec`); there is no local HTTP port between the UI and the backend.
- Installers and uninstallers MUST terminate any running `Kuantra Terminal` process before writing files, to prevent file-lock write errors (the NSIS installer does this).
- User data MUST live in the per-user data directory (`KUANTRA_DATA_DIR` / OS default), never inside the install tree.

## ✅ 5. DEFINITION OF DONE (DoD)
Use the bounded WP acceptance criteria and [local CI policy](docs/strategy/LOCAL-CI-POLICY.md).
Code changes require relevant regression tests, isolated data and risk-appropriate full
local CI; docs-only validation is reported as such. Preserve translation parity when
UI keys change. Commit/push only within user authorization and the requested feature
branch, never automatically to `origin/main`. Report exact tests, commit and blockers.
