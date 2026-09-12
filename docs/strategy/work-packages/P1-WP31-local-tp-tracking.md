<!-- doc-role: current-work-package -->
# P1-WP31 — Local TP1/TP2/TP3 tracking

```yaml
work_package: P1-WP31
status: InProgress
branch: codex/p1-wp01-evidence-ledger
```
Owner-approved scope: new manual entries default to enabled local tracking;
users specify target allocations. No broker dispatch. External fills/analytics
remain unchanged; local closes are gross estimates, not confirmed executions.

## Ordered acceptance

- [x] Package 1: atomic canonical plan/revision and disposable projection; legacy
  single TP unchanged; completed targets immutable; external history preserved.
- [x] Package 2: exact provider/instrument, provider-event age <=60 seconds,
  bounded shared polling/backoff and disabled/offline boundary.
- [ ] Package 3: Decimal partial/full close, SL, manual close, replay/concurrency,
  rollback and projection/export/restore regression.
- [ ] Package 4: creation/edit/history/local-result UI, EN/TR/DE, dark/light,
  keyboard and end-to-end synthetic quote lifecycle.
- [ ] Full backend/frontend, docs/i18n and canonical Mac local CI.
- [ ] Same-source native arm64/x86_64 exact DMGs, pilot Release refresh and
  local installed application update preserving user data.

## Evidence

Initial red test: `uv run --offline --no-project --with-requirements
backend/requirements.lock python -m pytest backend/tests/test_local_tracking.py -q`
failed collection because the local tracking service did not exist (macOS arm64).
The same command is now green: **16 passed**, including atomic create rollback,
revision conflicts, immutable completed targets, short/SL/manual closure and rebuild.
Package 1 source `542ce6b`: full backend **869 passed / 2 warnings**. Package 2
monitor tests started red (missing module); combined tracking/market-truth regression
is **34 passed / 2 warnings** before additional provider fixtures. Polling shares
exact keys, caps four concurrent requests / twenty due keys per pass, backs off,
and respects market-data disabled. Public reference contracts:
[Binance recent trades](https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md#recent-trades-list),
[Bybit recent trades](https://bybit-exchange.github.io/docs/v5/market/recent-trade).
Only provider event timestamps qualify; Yahoo/Stooq/Biquote remain display-only
for automatic tracking until their <=60s observation contract can be established.
No build, runtime-offline or release claim follows from this dependency mode.

## Persistence contract

Versioned local snapshots use the existing `PositionProjectionUpdated` event type,
`local-journal` scope and trade correlation ID. A separate disposable projection
is initialized with the existing projection bootstrap and rebuilt from verified
events. No account event type or canonical source-table schema changes are needed.
External `trades` quantities/status/PnL are never rewritten by local closes.
Old records are not opted in. Edits use revision checks inside BEGIN IMMEDIATE.

Pending pilot obligations remain in [P1-WP29](P1-WP29-trusted-macos-pilot-package.md):
clean-profile/host evidence and owner-granted repository access. N05 ad-hoc signing
and commercial gates remain open; no production claim is added.
