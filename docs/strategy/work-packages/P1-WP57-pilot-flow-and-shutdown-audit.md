<!-- doc-role: current-work-package -->
# P1-WP57 — Synthetic pilot flow and shutdown reliability

```yaml
work_package: P1-WP57
status: InProgress
date: 2026-10-03
branch: main
baseline: 0118367
```

Owner approved the proposed sequence on 2026-10-03. First bounded package: audit the
existing create/edit/local tracking/chart/export chain with isolated labelled synthetic
data, and reproduce shutdown resource failures. Fix only demonstrated defects.
Real three-person pilot acceptance is an external obligation, not synthetic evidence.

## Scope and boundaries

- Inspect Evidence Pack worker ownership, bounded normal shutdown and startup failure cleanup.
- Test only disposable data; no user trade saves/edits/cancels, credentials or migration apply.
- Local estimates remain separate from external records; only eligible exact LIVE observations
  trigger closure, delayed gold remains display-only. No new provider, execution or financial math.
- No Release/tag/workflow/signing changes. Native arm64 installed update follows AGENTS.
- Later approved order: revision-aware chart review → useful weekly review → safe in-app
  backup/restore. Each requires its own bounded contract before implementation. XM import
  stays conditional on a real anonymized sample; multi-trade comparison stays demand-gated.

## Acceptance

- [x] Baseline red tests demonstrate actual shutdown/startup failure paths.
- [x] Bounded cleanup terminates only owned read-only evidence workers; normal completion,
      pending jobs, repeated close and startup exceptions preserve data and release resources.
- [x] Existing create/edit/partial-close/replay/export regressions run on isolated synthetic data;
      record any uncovered flow separately, without calling this real pilot acceptance.
- [ ] Full backend/frontend/docs and canonical arm64 CI pass from a clean commit.
- [ ] Exact mounted-DMG smoke and installed matching hash, normal quit/reopen and user-data
      preservation verified. STATUS/registry evidence updated; next bounded package selected.

## Implementation evidence (this change)

Six demonstrated defect classes: failed lifespan loop/client leak; partial context setup
leak; failed window create/start bypassing cleanup; unbounded busy Evidence Pack join;
window/main concurrent shutdown treating started as finished (real source smoke orphaned
test-owned workers); failed CSV/PDF smoke still returning `ok=true`.
The first reproduction had a test typo/non-running job and was repaired before recording
the actual three baseline failures (3.18s). Export reproduction was corrected to reach the
success path and then failed `assert True is False`; it is not a collection-only red claim.
Other red failures: partial setup missing stop calls; concurrent second caller returned early.

`uv run --offline --no-project --with-requirements backend/requirements.lock python -m
pytest` focused shutdown/runtime/bridge/main/smoke/tracking/status-edit/replay/export set:
**138 passed / 2 warnings**, including native source smoke; no orphaned workers after final
run. Superseded candidate needed explicit termination of two exact test-owned workers and
is NOT normal-shutdown acceptance. The worker is a logical read operation; existing adapter
constructors may idempotently bootstrap schema, so no filesystem-read-only claim is made.
Busy worker grace: 3 seconds, then only captured owned handles terminate/kill/join (bounded);
unrelated-child survival, repeat close and rejected new jobs tested. Shell callers serialize
cleanup; completion flag set after cleanup, not before. No financial rules changed.
Frontend **51 files / 375 tests**; EN/TR/DE **1318 keys**; docs **143/190/5**, diff/truth/
packaging pass. Final full suite **1228 passed / 3 warnings** (32.31s). Clean source/artifact/
install evidence follows before closure; unchecked criteria remain unchecked until measured.
Synthetic regressions cover the constituent create/edit/partial-close/chart/export contracts;
they do not prove three-person usability or an all-screen click-through. Public startup network
was possible; uv offline proves dependency resolution only. No real user trade writes occurred.
