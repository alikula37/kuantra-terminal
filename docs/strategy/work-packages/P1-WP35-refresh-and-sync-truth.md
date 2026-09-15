<!-- doc-role: current-work-package -->
# P1-WP35 — Refresh and sync button truth

```yaml
work_package: P1-WP35
status: InProgress
branch: main
baseline: cf97498
```

Owner report (2026-09-15): "check the refresh / refresh-all buttons on every page; some
seem not to work." Every refresh control was traced to its handler:

| Control | Owner-visible behavior | Verdict |
| --- | --- | --- |
| Dashboard "Refresh" | reloads portfolio aggregates but leaves open-position quotes frozen until the table's own 20s poll | misleading |
| Open-positions "Refresh all" | real `POST /trades/quotes/refresh` with age/last-known states | works |
| Journal "Refresh all" | same real quote refresh | works |
| Edit trade "Refresh price" | real single-trade quote refresh | works |
| Market chart "Refresh" | real bounded candle fetch | works |
| Settings "telemetry Refresh" | real `GET /telemetry/status` | works |
| Plugin store "Reload registry" | real `GET /plugins/installed` | works |
| GPU telemetry "Refresh" | real `GET /hardware/gpu-status` | works |
| Biometrics "Refresh" | real devices + telemetry reads | works |
| Settings "TRIGGER FULL DUAL-DB SYNC" | **only a 600ms `setTimeout` that printed "sync completed successfully"** — no request, no sync | fabricated |

## Ordered acceptance

- [x] Settings dual-DB sync runs for real: `SyncPipeline.full_sync_report()` reports
  whether DuckDB is available in this build, whether the evidence coverage gate
  allowed the bulk write, and how many trades were synchronized; the new
  `POST /api/v1/system/sync/full` exposes it.
- [x] The Settings button shows the honest outcome for all four states — synced
  count, DuckDB unavailable, coverage blocked, transport/HTTP failure — instead of
  a timer-driven success claim, and disables itself while the request is running.
- [x] Dashboard "Refresh" also refreshes open-position quotes: the button bumps a
  `refreshNonce` that the open-positions table consumes, so prices, ages and
  unrealized K/Z move together with the KPI cards instead of waiting for the
  20s poll.
- [x] EN/TR/DE strings for the new sync states; i18n parity check.
- [x] Tests: backend endpoint outcomes (unavailable / synced / blocked) and
  frontend DOM tests for the sync states, the dashboard cascade and the nonce.

## Scope boundaries

- No fabricated success is ever reintroduced: a sync that did not run returns a
  reason and the UI shows it.
- Other working refresh controls are untouched; the plugin/GPU/biometric surfaces
  keep their existing truthful error handling.
- No new background timers and no polling-rate changes.

## Evidence

- `backend/tests/test_system_sync.py` **3 passed**: unavailable DuckDB reports
  `DUCKDB_UNAVAILABLE`, a ready evidence projection syncs and reports the count,
  and incomplete coverage is blocked without ever reaching DuckDB.
- Existing `test_p1_wp02_trade_projection.py` full-sync tests keep passing through
  the refactored `full_sync()` delegation.
- Frontend **39 files / 214 tests**: SettingsView reports real success/unavailable/
  blocked/failure states, the dashboard refresh increments the position-table
  nonce, and the table issues a fresh quote refresh on a nonce bump.
- Full backend **960 passed / 2 warnings**; i18n **993/993/993**; `npx tsc --noEmit`
  clean.

### Clean build and installed-app update

Per the owner standing instruction, the verified change was committed (`ef89ae6`,
pushed) and the Mac's installed application was rebuilt from the clean commit:

- Canonical arm64 local CI on `ef89ae6`: **MERGE READY**, provenance **COMPLETE**,
  clean tree; report `dist/p1-wp35-clean-local-ci.json` SHA-256
  `7903e0401ba9a7a4f9da203577a3bab2fab2383503222e13664ac014bf3875bd`, executable
  `a51f290f5f5ab46a121b0a6c830fa1eaf54b2bbbd66a9a73f40b168f67b78f5c`.
- arm64 DMG `dist/Kuantra-Terminal-1.1.0-arm64-wp35.dmg`: `hdiutil verify` VALID,
  SHA-256 `66ae08f1c368887d99db448458c2f2969c35f664d06e6d37c223f1f3d2c654bd`;
  exact read-only mounted-DMG smoke **PASS** (`dist/p1-wp35-dmg-smoke.json`).
- `/Applications/Kuantra Terminal.app` replaced after a graceful quit; installed
  executable matches the CI build, `codesign --verify --deep --strict` passes,
  launched PID `52143`, runtime `{"status":"online","gateway":true,"version":"1.1.0"}`.
  User data was preserved (5 trades).

### Live verification

- Against a copy of the owner database (same build): `POST /api/v1/system/sync/full`
  returned `{"available": true, "coverage_ready": true, "synced": 5}` — the button
  now performs the real sync it claims (previously it made no request).
- The same build's quote refresh returned `LIVE 2481.13` for the owner's open
  ETHUSDT trade, confirming the journal/positions refresh path end to end.
