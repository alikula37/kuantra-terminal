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
| Runtime baseline | `77b4997`; fresh Mac local CI `MERGE READY`: 595 backend, 51 frontend, i18n 480/480, arm64 build and native smoke passed. Smoke executable SHA `c5844d6d5697536dee1516c68fe3176887f64a6a597702c9be8b2bd90e61f133`; `build_commit=UNKNOWN` remains B4/N01 |
| Roadmap baseline | `03b7791`: G0–G7 proposal; no production/pilot gate passed by publishing a document |
| P1 foundations | Implementations recorded in historical packages; source completeness and financial accounting still open |
| Mac | App `.app` smoke observed `wkwebview`; ad-hoc signed DMG `83fee6a15f2abfea2ebe0c76dd1818d51c8231df7ebdaf9caa60af4b1d09b4f8` packaged and standalone signature verified. Exact mounted-DMG executable smoke, provenance binding and fail-closed native renderer gate remain open |
| P2 | Short gaps-free Spot observations; controlled-disconnect observations INVALID. No source/live promotion |
| Product | No real-user data/pilot evidence; Faz 1/2 user exits unfulfilled |

## Open obligations and blockers

| ID | Classification | Obligation | Next handling |
|---|---|---|---|
| B1 | CLOSED | Timestamp pagination can skip records and overstate completeness | Closed by P1-WP16 / `ef909d1`; historical package retained in archive |
| B2 | IMPLEMENTATION_REQUIRED | Fee currency/unknown handling, perps identity/accounting and economic dedup | P1-WP17–20 boundaries are closed; P1-WP21 propagation is the next code package. Full account PnL/tax accounting remains out of scope |
| B3/M1 | DEFERRED | Gap recovery waits for stream completion; bounded shutdown/injection tests missing | Complete before another long/24h soak; not primary product path |
| B4 | IMPLEMENTATION_REQUIRED | Runtime offline ≠ uv offline; artifact hash ≠ mounted executable; UNKNOWN commit; Mac renderer gate | N01 provenance, N02 exact mounted-DMG smoke, H03 degraded/network boundary |
| WIN | HOST_REQUIRED | Windows host/controller blocker | Historical P0-WP11 reference; verify on Windows before platform claim |
| VERIFY | HOST_REQUIRED | Historical P1-WP01 latest-SHA verification checkbox and remote/multi-OS evidence gaps | Preserve exact source criteria; current local gate is not a historical remote pass |
| OPS | HOST_REQUIRED / OWNER_DECISION_REQUIRED | Historical P2 network promotion, real disconnect, different-host bundle restore and remote verification | Reference archived open-item index; no automatic closure or permission for live work |
| PRODUCT | OWNER_DECISION_REQUIRED | Review/pilot metrics, MIT LICENSE/notices, signing/host access, support/incident readiness | G2–G7 and explicit product-owner decisions; `LICENSE`, `NOTICE` and `THIRD_PARTY_NOTICES.md` are currently absent |
| DEP | OWNER_DECISION_REQUIRED | Branch dependency audit is clean, but GitHub default branch retains five open npm alerts | Branch `npm audit`: 0 vulnerabilities. Default-branch alerts remain open until an approved PR merge or explicit repository action |

All historical unchecked criteria remain discoverable in the
[archive obligation index](../archive/README.md). The archive is not a completed-work list.
Only evidence or an explicit superseding decision can close an obligation. The
registry records unchecked counts so accidental checkbox deletion is detected.

## Latest maintenance handoff

P1-WP20 economic dedup/lifecycle contract was implemented in `5d691b9` and its
historical evidence record is archived. The fresh 2026-09-08 Mac audit used the locked
environment and temporary data directories: local CI was `MERGE READY`, with frontend
**51**, i18n **480/480**, full backend **595**, production build, arm64 desktop build,
native `wkwebview` smoke and packaging preflight. The `.app` smoke observed
`wkwebview`; it also attempted the public Binance WebSocket during startup. The smoke
report still has `build_commit=UNKNOWN`, and the exact mounted-DMG executable was not
smoked, so B4/N01/N02 remain open. DMG SHA-256 was recorded as
`83fee6a15f2abfea2ebe0c76dd1818d51c8231df7ebdaf9caa60af4b1d09b4f8`; standalone
ad-hoc signature verification passed. Branch `npm audit` reported zero findings, while
the GitHub default branch still exposes five open npm Dependabot alerts. Source identity
conflicts, unknown position mode, incomplete lifecycle, funding/transfer schema and
network-denied runtime remain fail-closed boundaries; no PnL, live execution or pilot
claim was opened. Next active contract: P1-WP21.

## Update protocol

Replace the relevant rows as work progresses; do not append a new full status report.
Each outcome must cite WP, code/evidence SHA, actual commands/results, platform,
unchecked criteria and next dependency. Keep this file concise; long history belongs
in completed packages/Git, not additional competing roadmaps.
