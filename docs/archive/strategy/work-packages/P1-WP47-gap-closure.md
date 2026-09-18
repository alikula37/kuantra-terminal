<!-- doc-role: archived -->
# P1-WP47 — Gap closure: TP live proof, forensic cadence, USD analytics/export tests, endpoint metadata, dynamic i18n audit, WS TLS

```yaml
work_package: P1-WP47
status: Complete
branch: main
baseline: 59a5e46
```

Owner instruction (2026-09-18): close the gaps the previous delivery honestly reported.

## Ordered acceptance

- [x] **TP-specific live automatic close** demonstrated on the installed app with a NEW labelled
  simulation record whose take-profit is valid, above entry and already reached at save time;
  the pre-save `role=alert` warning and the value-based single closure are captured.
- [x] **Forensic cadence reconstruction** documented and tested: the surviving pre-fix cadence
  (31/61/105/127 s) is compared against the old exponential backoff arithmetic
  (30/60/120 s + poll drift) and the new stale-retry behaviour (5 s, no failure increment);
  the attribution is labelled "consistent with", never "proven".
- [x] **USD analytics/export end-to-end tests**: a closed USD trade flows through portfolio
  summary/breakdown/equity/heatmap, the pivot grid and the journal export snapshot with
  value-based results and explicit units (no base-quantity artifacts).
- [x] **`/trades/open` metadata regression**: the endpoint payload carries `qty_unit`,
  `record_mode` and value-based sizing for a USD trade.
- [x] **Dynamic localization audit**: content tests cover every dynamically composed key
  family discovered in the frontend source, plus a source-scan guard that fails when a new
  dynamic family appears without coverage.
- [x] **Desktop websocket TLS**: the Binance stream uses an explicit certifi-based SSL context
  (the packaged app previously logged `CERTIFICATE_VERIFY_FAILED` while REST worked); the
  installed app log shows a successful stream connection after the update.
- [x] Full suites, i18n/docs checks, canonical Mac local CI, commit/push, clean-commit arm64
  package, exact-DMG verification, data-preserving install. Release/tag unchanged.

## Scope boundaries

- No eligibility/freshness loosening; no changes to existing user records (new labelled
  simulation records only); release/tag untouched.

## Delivery verification (2026-09-18)

Commits `f70fa36` (TLS + analytics/endpoint tests), `f07d5f6` (localization audit + missing
keys), `f0bf150` (docs) pushed. Red-first evidence: the four new backend areas failed before
their changes (endpoint metadata via the isolated reader, export `pnl_recorded`/units, pivot
value result, `_build_ssl_context`), and the extended audit failed on the three real missing
keys before they were added. Full suites: backend **1187 passed**, frontend **43 files / 295
tests** plus the extended audit (source-scan guard green), i18n **1238/1238/1238**,
`tsc`/build clean, `check_docs` PASS. Canonical arm64 local CI on the clean commit **MERGE
READY** (`dist/p1-wp47-local-ci.json`, executable
`d8a20f48f462a0c503beb1d89c97b8a99180434b9b0d985516dd744aa7658d85`).

**Installed-app proof (new labelled simulation record `TRD-1789717224982`, note
QA-WP47-TP-RETEST; existing records untouched):**
- **Websocket TLS:** the installed app logs `Connected to Binance live market stream.` with
  no `CERTIFICATE_VERIFY_FAILED` (previously it failed the handshake).
- **TP-specific automatic close:** created with a pending TP; the tracking editor then set a
  valid already-reached TP (78,238.25) and showed the `role=alert` pre-save warning; after
  saving at 10:45:52Z the monitor fetched on schedule and closed the plan at the next
  eligible provider event (10:46:06.121Z, price 78,242.98) — **TP1**, value 100 USD, gross
  **+0.1084 USD** exactly matching `value × return`, **single** closure, external record
  still OPEN, `USD_NOTIONAL`. The waiting reason was visible after saving ("ilk sağlayıcı
  gözlemi bekleniyor · sonraki deneme ~14 sn").
- **Cadence reconstruction:** the surviving pre-fix gaps (31/61/122 s) match the old
  30/60/120 s arithmetic within poll drift; labelled "consistent with", not proven (DEBUG
  logs from those sessions are gone). New stale-retry policy is pinned (5 s, no failure
  increment).
- Evidence and screenshots: `artifacts/evidence/p1-wp47-retest/`. Known limit: a second
  backend sharing the data directory logs a DuckDB candle-persistence lock conflict; the
  installed app alone owns the lock in normal use.
