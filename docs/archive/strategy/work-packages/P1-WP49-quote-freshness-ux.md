<!-- doc-role: archived -->
# P1-WP49 — Honest quote freshness and understandable tracking waits

```yaml
work_package: P1-WP49
status: Complete
date: 2026-10-02
branch: main
baseline: 765ab0a
```

Owner approved proceeding through the ordered UX findings; this first bounded package
addresses quote truth, not new data providers or broker execution. WP29 owner-host
obligations remain open. No release/tag update is authorized by this package.

## Contract

- `LIVE` requires provider event time, timezone, age -5..60 seconds; refresh/request
  time and candle start cannot establish freshness. Display expiry does not erase price.
- Biquote/Yahoo/Stooq candle close prices retain exact source identity and candle-start
  time/interval with delayed/EOD, display-only labels. Candle age is not quote latency.
- Crypto display uses the existing recent-trade adapter, not a timestamp-less ticker
  stamped with download time. Cache reads and UI ticks re-evaluate event age.
- Entry, edit, journal and dashboard share translated labels and Europe/Istanbul times.
  Saving a quote rechecks freshness; old payloads without time provenance are unknown.
- Tracking's deterministic eligibility rule remains unchanged. Display-only sources
  report why automation waits and use bounded retries, never fabricated closes.
- No schema migration, real orders, new provider/paid data, user data edits/reset,
  retroactive event rewriting or independent gold-source verification claims.

## Acceptance

- [x] Red → green: candle vs event time, age boundary/future/unknown, cache expiry,
  display-only monitor wait, no closure, exact source regressions.
- [x] UI: age expiry without network; shared source/time labels, unknown/old states,
  translation parity and same rules in all four quote surfaces.
- [x] Focused and full backend/frontend, typecheck/build, docs/release truth/diff checks.
- [x] Canonical native arm64 local CI, clean source commit, exact-DMG smoke.
- [x] Commit/push main; verified arm64 install preserving journal/preferences,
  installed source/hash/runtime proof. GitHub Release unchanged.

## Evidence

Initial red backend run: **11 failed**, exposing gold `LIVE/LAST`, download-time crypto,
cached stale `LIVE`, unknown/future timestamp claims and generic monitor waiting reason.
Frontend red run: shared quote-quality component missing (not a behavioral regression
claim); its four DOM tests exercise the new label and timer contract.
All tests use isolated synthetic data; fixtures deny real network after reproducing
the old crypto display path. A first red test issued one public BTCUSDT ticker request
before that deny was added; no credentials or user records were involved.

Green: 15 WP49 backend cases (including fetch-latency timing, both crypto event adapters
and structured rate-limit response); full backend **1209 passed / 3 warnings** with a
fresh isolated `KUANTRA_DATA_DIR`; frontend **45 files / 301 tests**, new component **4
DOM tests**, entry-save regression rechecks expiry; i18n **1252/1252/1252**, tsc/build,
docs (**135 documents / 183 links**) and release-truth PASS; `git diff --check` clean.
Commands: locked offline `python -m pytest backend/tests -q --tb=short`, `npm test`,
`npm run build`, `python3.11 scripts/check_docs.py`, `scripts/check_release_truth.py`.
An attempted full-suite rerun using a previously populated test directory produced 9
immutable-identity/import repeat failures; a fresh test directory passed all 1209.
The reused directory was not reset and production data was never used. Offline dependency
resolution is not a runtime network firewall.

## Clean-commit delivery (2026-10-02)

Implementation **84e7afd5d86e8ae51e0c0969be4885a61f012181**, pushed to main. Native
macOS 26.6.2 arm64 / Python 3.11.16 / Node 24.20.0 / npm 11.19.0 / uv 0.12.10 /
PyInstaller 6.22.2. Canonical CI **MERGE READY, 13/13 PASS, provenance COMPLETE**,
source tracked tree clean. Same full-suite counts as above. Evidence is preserved under
`artifacts/evidence/p1-wp49/` (not just the disposable build directory):
- `local-ci.json` SHA-256 `96660ad78ba25491d8adfa22ec9f85e1d776e27f42d1f04b0488b8760c27b169`.
- `exact-dmg-smoke.json` SHA-256 `dac8fb86a81630f760345f2f6238a99acfb32913ee0929c25eda7482180784b8`.
- `n05-preflight.json` SHA-256 `00503681a9508edf8c1e3d7014362a008e7a4c4a965a6c32e549844070ebb14e`.

DMG `dist/Kuantra-Terminal-1.1.6-wp49-arm64.dmg` SHA-256
`ec73f15c1ddd0b43d53203190db5edd894795a6eafd3dd6b1d38983196988570`;
read-only mounted-DMG WKWebView smoke PASS, image integrity PASS, mount detached.
Native CI, mounted executable, staged copy and installed `/Applications/Kuantra Terminal.app`
all match executable SHA-256
`61396fefa2660336aa92eb03fa8449249ff29ae73a496c4cde98257585fd3574`.
Codesign verification PASS (ad-hoc), version **1.1.6**, launch succeeded. This is a new
local source build, not a new published version; existing GitHub Releases/tags unchanged.
Previous app preserved at `/tmp/kuantra-wp49-update.WSISXP/Kuantra Terminal.app`.

Data preservation: the stopped journal database SHA-256 remained identical across the
app replacement (`4fc01ac57eebb7eb8a90a6e9c4a518bade5820be8fdc3012e74e4bb60dc4417e`).
After launch/read-only UI checks: **5 trades / 24 evidence events / 5 tracking projections**,
unchanged. No test trade saved; no journal reset, migration apply, credential or order.
TR locale/light theme and configured balance survived; user data/preferences directory
was not replaced. Public price fetches and ordinary startup connections are not offline
runtime evidence.

Installed UI check: new BTCUSDT quote shows **Canlı · 5s**, Binance/exact symbol and
provider event time in Türkiye time; gold journal quote shows **Gecikmeli**, Biquote/XAUUSD,
**Mum başlangıcı (1h)** and **Yalnız görüntüleme**; form closed without saving. Visual
journal review still finds the oversized sticky actions hiding the date/quote columns:
this pre-existing layout problem is the next bounded WP50, not claimed fixed here.
Edit/dashboard quote labels are covered by shared-component and existing DOM regressions;
this is not a claim of a four-surface manual pilot acceptance test.

**Open external boundaries:** N05 preflight is **BLOCKED**, not PASS: Developer ID and
notarization remain absent. Intel artifact/native proof and published-asset updates were
not performed. No new live gold feed, independent gold verifier or XM compatibility
claim. WP29 owner-host obligations stay open.

## Changed-file groups (implementation commit, 32 files)

- Backend: `api/endpoints.py`, `services/local_tracking_monitor.py`,
  `services/market_data/{public_fetcher,quote_quality}.py`, `services/quote_refresh.py`.
- Backend tests: `test_wp49_quote_freshness.py`, `test_p1_wp30_free_quote_external_journal.py`,
  `test_p1_wp32_pilot_journal_trust.py`, `test_portfolio_service.py`,
  `test_public_data_fetcher.py`, `test_wp44_identity_and_separation.py`.
- Frontend: `components/{JournalView,NewTradeModal,TradeEditModal,QuoteQuality}.tsx`,
  `components/dashboard/OpenPositionsTable.tsx`, `hooks/useOpenQuoteRefresh.ts`,
  `lib/quoteQuality.ts`, `types/index.ts`, `locales/{en,tr,de}.json`.
- Frontend tests: `components/__tests__/{JournalView.p1wp32,NewTradeModal,TradeEditModal,QuoteQuality}.dom.test.tsx`,
  `lib/__tests__/localizationKeys.test.ts`.
- Docs: registry, roadmap, STATUS, WP29 selection role and WP49.
