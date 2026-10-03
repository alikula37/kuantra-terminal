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

Seven demonstrated defect classes: failed lifespan loop/client leak; partial context setup
leak; failed window create/start bypassing cleanup; unbounded busy Evidence Pack join;
window/main concurrent shutdown treating started as finished (real source smoke orphaned
test-owned workers); failed CSV/PDF smoke still returning `ok=true`; macOS AppKit Quit
bypassing window-close cleanup entirely (native installed Cmd+Q reproduction).
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

## Candidate/native follow-up (not final acceptance)

Candidate `7fef432`: clean canonical arm64 13/13 COMPLETE; exact mounted DMG smoke passed
including synthetic partial-close/editor/local-close and spawned Evidence Pack. However the
installed Cmd+Q check left exact-owned PIDs 10519/10520 after parent 10487 exited. Worker
10520 was explicitly terminated (tracker then exited); not recorded as clean native acceptance.
Trade/event/tracking hashes and 5/24/5 counts remained unchanged. Existing pywebview Cocoa
`AppDelegate.applicationShouldTerminate_` checks close permissions but directly lets AppKit
terminate; it need not deliver windowWillClose or return start(). Follow-up subclass preserves
the existing permission/cancellation decision across all windows and synchronously completes
owned cleanup before granting native termination. Two callback contract reds, then green;
native Cmd+Q must be rerun from the final clean binary before closure.
Follow-up focused lifecycle/main/bridge/smoke **32 passed**; full backend **1230 passed /
3 warnings** (32.47s). Frontend unchanged by this native termination fix. Final clean
canonical gate and installed Cmd+Q acceptance still pending.
Candidate `b6b485d` canonical gate passed but emitted PyObjC's ObjCSuperWarning. Before
native termination acceptance the delegate was corrected to `objc.super`, with a red
dispatch assertion → focused green; no dependency change. Candidate report is retained
as superseded, not the final installed evidence.

Separate visible UI findings from this read-only native audit: Evidence Pack export row clips
the PDF action at 1440x900 light/TR; open-trade market-context explanation prints a raw English
message. Retain as explicit next review-surface follow-ups; NOT fixed or closed by backend
shutdown work. No all-screen UX acceptance is claimed.
