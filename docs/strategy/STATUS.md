<!-- doc-role: current-status -->
# Current development status

Updated: 2026-09-08. Branch: `codex/p1-wp01-evidence-ledger`.
Roadmap: [KPR-001](PRODUCTION-READINESS-PLAN.md), current planning source, still Proposed
for new scope/estimates. Selecting one roadmap does not approve its commercial assumptions.

## Selected next work

**P1-WP21 — Ready:**
[Journal, projection & evidence propagation contract](work-packages/P1-WP21-journal-evidence-propagation.md).
P1-WP16 timestamp completeness was verified in `ef909d1`; P1-WP17 source identity
and support boundary was verified in `930d25a`; P1-WP18 fee/precision/unit truth was
verified in `0c7d11f`; P1-WP19 funding/corrections/account coverage was verified in
`f67e732`; P1-WP20 economic dedup/lifecycle was verified in `5d691b9`. The next bounded
implementation is journal/projection/evidence propagation; it must not silently become
full tax/accounting scope or new venue scope. No other historical `Active` WP is
automatically queued. Next after P1-WP21: UX/review integration.

## Current evidence, not completion claims

| Area | Evidence / remaining boundary |
|---|---|
| Runtime baseline | `5d691b9`; P1-WP20 local CI: 595 backend, 51 frontend, build/smoke passed. Smoke `build_commit=UNKNOWN`; exact provenance remains B4 |
| Roadmap baseline | `03b7791`: G0–G7 proposal; no production/pilot gate passed by publishing a document |
| P1 foundations | Implementations recorded in historical packages; source completeness and financial accounting still open |
| Mac | Local build/smoke works; runtime offline, exact mounted-DMG provenance and fail-closed renderer verification remain open |
| P2 | Short gaps-free Spot observations; controlled-disconnect observations INVALID. No source/live promotion |
| Product | No real-user data/pilot evidence; Faz 1/2 user exits unfulfilled |

## Open obligations and blockers

| ID | Obligation | Next handling |
|---|---|---|
| B1 | Timestamp pagination can skip records and overstate completeness | Closed by P1-WP16 / `ef909d1`; historical package retained in archive |
| B2 | Fee currency/unknown handling, perps identity/accounting and economic dedup | P1-WP17 identity, P1-WP18 fee/precision, P1-WP19 funding/account and P1-WP20 economic dedup boundaries closed; propagation remains open |
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

P1-WP20 economic dedup/lifecycle contract was implemented in `5d691b9` and its
historical evidence record is archived. Focused WP20 tests passed **8**; full backend
suite passed **595** with 2 deprecation warnings. Canonical Mac local CI passed with
frontend **51**, i18n **480/480**, production build, arm64 desktop build, WKWebView
native smoke and packaging preflight; result `MERGE READY`. The smoke report still has
`build_commit=UNKNOWN`, so B4/N01 provenance is not closed. Source identity conflicts,
unknown position mode and incomplete lifecycle remain fail-closed; no PnL claim was
opened. The locked environment and fresh temporary data directory were used; this is
not a claim of real-user data or runtime network-isolation evidence. Next active
contract: P1-WP21.

## Update protocol

Replace the relevant rows as work progresses; do not append a new full status report.
Each outcome must cite WP, code/evidence SHA, actual commands/results, platform,
unchecked criteria and next dependency. Keep this file concise; long history belongs
in completed packages/Git, not additional competing roadmaps.
