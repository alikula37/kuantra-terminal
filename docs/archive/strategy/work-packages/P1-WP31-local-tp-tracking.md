<!-- doc-role: archived -->
# P1-WP31 — Local TP1/TP2/TP3 tracking

```yaml
work_package: P1-WP31
status: Completed
branch: main
```
Owner-approved scope: new manual entries default to enabled local tracking;
users specify target allocations. No broker dispatch. External fills/analytics
remain unchanged; local closes are gross estimates, not confirmed executions.

## Ordered acceptance

- [x] Package 1: atomic canonical plan/revision and disposable projection; legacy
  single TP unchanged; completed targets immutable; external history preserved.
- [x] Package 2: exact provider/instrument, provider-event age <=60 seconds,
  bounded shared polling/backoff and disabled/offline boundary.
- [x] Package 3: Decimal partial/full close, SL, manual close, replay/concurrency,
  rollback and projection/export/restore regression.
- [x] Package 4: creation/edit/history/local-result UI, EN/TR/DE, dark/light,
  keyboard and end-to-end synthetic quote lifecycle.
- [x] Full backend/frontend, docs/i18n and canonical Mac local CI.
- [x] Same-source native arm64/x86_64 exact DMGs, pilot Release refresh and
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
Package 3 adds four-writer concurrent observation, post-edit stale observation,
external correction/cancellation, actual SQLite backup/reopen/rebuild and Evidence
Pack equivalence, API revision/close and corrupted-chain tests. Schema changes
invalidate the append-tail verification cache before tracking can evaluate prices.
The existing external trade snapshot remains byte-for-byte equivalent in lifecycle
tests; no synthetic commission or external fill is created.
2026-09-13 owner instruction supersedes the initial branch: continuation is on
`main`, fast-forwarded to the existing history without a merge commit.
Package 3 focused backend: **26 passed / 2 warnings**. UI focused **18 passed**;
full frontend before the final validation fixture **152 passed**, build and
**813/813** translation parity PASS. Optional native tracking smoke uses isolated
synthetic data with market data disabled and exercises the real editor.
Native WKWebView lifecycle is functionally PASS on the Mac mini: create through
ASGI, inject a synthetic provider observation, partial close, render/edit/save,
completed-target lock, light/dark computed colors, local manual close and preserved
external OPEN status. Initial native run had a dirty test-only tree and is not
release provenance. Initial full CI was blocked by three default-network tests
because disabled-network settings were incorrectly applied to the entire suite;
the canonical gate is rerun with normal defaults, while native fixture runs stay
explicitly network-disabled. Additional fractional-allocation regression PASS.
Source `09d29e5` canonical Mac CI: **MERGE READY**, backend **880 passed / 2 warnings**,
frontend **153 passed**, **813/813** i18n, build/native WKWebView, COMPLETE provenance.
Final keyboard containment/Escape restoration also passes four editor DOM tests;
the final source is rebuilt for distribution rather than reusing the prior binary.
No build, runtime-offline or release claim follows from this dependency mode.

Final implementation source `4298acdbfa2e7de0028dcaf7a1c3780b4f69c1d0`:
canonical Mac local CI **MERGE READY**, **880 backend / 154 frontend** tests,
**813/813** translation parity, all 13 gate steps PASS and COMPLETE provenance.
Command: `uv run --offline --no-project --with-requirements backend/requirements.lock
python scripts/run_local_ci.py`; report `dist/tp-tracking-final-local-ci.json`,
SHA-256 `0bbd9a831c0fadd4d1e9f2d07c27f93479ef5b428d0ee8fbbbd3ffd4c6a61f70`.
Mac mini macOS 26.6.2 arm64; Python 3.11.16, Node 24.20.0, npm 11.19.0,
uv 0.12.10, PyInstaller 6.22.2. Isolated synthetic data only.
Local exact-DMG smoke also PASS with `KUANTRA_SMOKE_LOCAL_TRACKING=1`,
market data/gateway disabled, read-only mount and clean detach:
`dist/tp-tracking-final-dmg-smoke.json`; DMG SHA-256
`e9c5ac8766f398871977976c09e1d82d10dd2d4554ba235e5bf23d7ccbcb1720`,
mounted executable `1883e9a04f5acef9c6c80587fb7c6ba83e263e4ab7939adda12a90f582bb11cb`.
Packaging explicitly used `PYTHON_BIN=python3.11`; the first attempt selected
the unsupported system Python and failed before producing a DMG. The rerun passed.
These are local artifact hashes, not the separately built native CI distribution hashes.

## Final distribution and installed-app evidence

GitHub Actions [run 34721385803](https://github.com/alikula37/kuantra-terminal/actions/runs/34721385803)
completed successfully from the final source above. Native arm64 (macOS 26.6.2) and
x86_64 (macOS 15.7.9) each passed **879 backend / 1 skipped / 2 warnings**, **154
frontend**, **813-key** i18n, build, desktop and exact read-only DMG smoke. Both
`checks.local_tracking=true`, native WKWebView/controller, clean detach, image integrity
and COMPLETE provenance passed. Python 3.11.9, Node 20.20.2, npm 10.8.2, uv 0.12.10,
PyInstaller 6.22.2; tracked tree hash matches the final local CI. Remote dependency
installation/audit/download required network; no runtime-offline claim follows.

| Native artifact | DMG SHA-256 | Mounted executable SHA-256 |
|---|---|---|
| arm64 | `03671ca814ba9299fcf47429cb0c585fbccd550e6201e747c5f2c2e5c32c5e93` | `ee5683af6c5571fb3da6797faac50bf5fd0cf7dc1840c360d46a98dd032b05b6` |
| x86_64 | `e43e0026c118bff9ed338e9e8560dc3758c64fa9052de83d1a23977e906240c2` | `9714d539a03dbf4a3eb363ed89ddc4cbeedfaf04af5846c82b7249fd9e65cdff` |

Reports and original package manifest/checksums are retained under
`artifacts/evidence/p1-wp31/4298acd/` (DMGs remain Release assets, not Git binaries).
Downloaded package `shasum -a 256 -c SHA256SUMS` passed all eight entries, and the
local release-facing source-identity validator independently accepted both exact DMGs.
The existing private `pilot-v1.0.0-arm64` Release was refreshed in place with exactly
two DMGs and current notes; no canonical product release/tag was created.

`/Applications/Kuantra Terminal.app` was replaced with the verified CI arm64 artifact,
codesign structure verified and the installed executable hash matched the table.
Normal launch confirmed PID 43343. No user-data files were reset/deleted/migrated.
The old application is recoverable at
`/tmp/kuantra-tp-update.A5TXWE/Kuantra Terminal.app.previous` until temporary-file cleanup.
The old app quit normally; two verified orphan multiprocessing children (parent PID 1)
were stopped with SIGTERM before replacing the bundle. No force-kill was needed.
N03 clean-profile and N05 Developer ID/notarization remain unproven; retained
development-only dependency findings and H05 commercial notices are production gates.
Final documentation-only close-out: `python3.11 scripts/check_docs.py` PASS
(116 documents / 160 local links), release truth and `git diff --check` PASS;
release-truth/manifest/pilot-package focused regression **16 passed**. The docs
commit follows the fixed artifact source; no binary was rebuilt from docs-only edits.

## Persistence contract

Versioned local snapshots use the existing `PositionProjectionUpdated` event type,
`local-journal` scope and trade correlation ID. A separate disposable projection
is initialized with the existing projection bootstrap and rebuilt from verified
events. No account event type or canonical source-table schema changes are needed.
External `trades` quantities/status/PnL are never rewritten by local closes.
Old records are not opted in. Edits use revision checks inside BEGIN IMMEDIATE.

Pending pilot obligations remain in [P1-WP29](../../../strategy/work-packages/P1-WP29-trusted-macos-pilot-package.md):
clean-profile/host evidence and owner-granted repository access. N05 ad-hoc signing
and commercial gates remain open; no production claim is added.
