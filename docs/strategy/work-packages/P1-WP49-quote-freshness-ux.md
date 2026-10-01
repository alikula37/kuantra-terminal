<!-- doc-role: current-work-package -->
# P1-WP49 — Honest quote freshness and understandable tracking waits

```yaml
work_package: P1-WP49
status: InProgress
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
- [ ] Canonical native arm64 local CI, clean source commit, exact-DMG smoke.
- [ ] Commit/push main; verified arm64 install preserving journal/preferences,
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
resolution is not a runtime network firewall. Build/install evidence is still pending.
