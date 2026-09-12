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
- [ ] Package 2: exact provider/instrument, provider-event age <=60 seconds,
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
