<!-- doc-role: current-status -->
# Current development status

Updated: 2026-09-08. Branch: `codex/p1-wp01-evidence-ledger`.
Roadmap: [KPR-001](PRODUCTION-READINESS-PLAN.md), current planning source, still Proposed
for new scope/estimates. Selecting one roadmap does not approve its commercial assumptions.

## Selected next work

**P1-WP16 — Ready, not implemented:**
[Read-only snapshot completeness](work-packages/P1-WP16-read-only-snapshot-completeness.md).
Start with same-timestamp pagination reproduction, then bounded fail-closed fix and tests.
No other historical `Active` WP is automatically queued. Next: D02 identity/support
contract → D03 fee/precision → D04 funding → D05/D06 lifecycle/evidence → review UX.

## Current evidence, not completion claims

| Area | Evidence / remaining boundary |
|---|---|
| Runtime baseline | `b1ceba6`; prior Mac full local CI recorded 550 backend / 51 frontend. Not rerun evidence for this documentation/tooling change |
| Roadmap baseline | `03b7791`: G0–G7 proposal; no production/pilot gate passed by publishing a document |
| P1 foundations | Implementations recorded in historical packages; source completeness and financial accounting still open |
| Mac | Local build/smoke works; runtime offline, exact mounted-DMG provenance and fail-closed renderer verification remain open |
| P2 | Short gaps-free Spot observations; controlled-disconnect observations INVALID. No source/live promotion |
| Product | No real-user data/pilot evidence; Faz 1/2 user exits unfulfilled |

## Open obligations and blockers

| ID | Obligation | Next handling |
|---|---|---|
| B1 | Timestamp pagination can skip records and overstate completeness | Current P1-WP16 |
| B2 | Fee currency/unknown handling, perps identity/accounting and economic dedup | Roadmap D02–D06; choose supported subset before implementation |
| B3/M1 | Gap recovery waits for stream completion; bounded shutdown/injection tests missing | Before further long/24h soak; not primary product path |
| B4 | Runtime offline ≠ uv offline; artifact hash ≠ mounted executable; UNKNOWN commit; Mac renderer gate | H03/N01/N02 |
| WIN | Windows host/controller blocker | Historical P0-WP11 reference; verify on Windows before platform claim |
| VERIFY | Historical P1-WP01 latest-SHA verification checkbox and remote/multi-OS evidence gaps | Preserve exact source criteria; current local gate is not a historical remote pass |
| OPS | Historical P2 network promotion, real disconnect, different-host bundle restore and remote verification | Reference archived open-item index; no automatic closure or permission for live work |
| PRODUCT | Review/pilot metrics, LICENSE/notices, signing/host access, support/incident readiness | G2–G7 and owner decisions |

All historical unchecked criteria remain discoverable in the
[archive obligation index](../archive/README.md). The archive is not a completed-work list.
Only evidence or an explicit superseding decision can close an obligation. The
registry records unchecked counts so accidental checkbox deletion is detected.

## Latest maintenance handoff

This change: documentation consolidation, historical archive, one agent entry point,
role registry and documentation gate. Runtime capabilities are unchanged. Exact
commit is the Git commit containing this section; resolve it with file history.
Validation: 11 documentation contract regression tests passed; isolated full backend
suite **561 passed, 2 deprecation warnings** (11.06s). `check_docs.py`, release-truth,
packaging preflight and `git diff --check` passed. Current/reference inline links:
114 checked; an additional one-off archive link check resolved 200 targets.
Frontend/build/native full local CI was not rerun: no application behavior changed.
The full backend run used the locked offline dependency environment and a fresh
temporary data directory; it is not runtime network-isolation proof.

## Update protocol

Replace the relevant rows as work progresses; do not append a new full status report.
Each outcome must cite WP, code/evidence SHA, actual commands/results, platform,
unchecked criteria and next dependency. Keep this file concise; long history belongs
in completed packages/Git, not additional competing roadmaps.
