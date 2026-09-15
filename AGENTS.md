# Kuantra — coding agent entry point

<!-- doc-role: agent-entry -->

## Read first, in this order

1. This file: working rules and document precedence.
2. [Product contract](docs/strategy/PRODUCT.md): identity, scope and safety boundaries.
3. [Current roadmap](docs/strategy/PRODUCTION-READINESS-PLAN.md): phases/dependencies.
4. [Current status](docs/strategy/STATUS.md): active work, blockers and latest evidence.
5. The active work package linked from STATUS: acceptance criteria and file scope.

Do not recursively read every strategy/work-package/archive document at startup.
Read relevant code/tests before implementing. Load an Accepted ADR, local CI policy,
platform runbook or historical package only when needed by the current task. Documents
describe contracts; implemented behavior still requires inspection and tests.

## Owner standing instruction (2026-09-15)

After every successful bounded development, commit it and update the installed
application on this Mac — every time, without waiting for a separate request:
commit the verified change on `main`, push it, build the native arm64 artifact
from the clean commit, verify its exact hashes, and replace
`/Applications/Kuantra Terminal.app` while preserving user data (the journal
database and preferences are never deleted or reset). The built app's local
runtime status/version and executable hash are reported after the install.
GitHub Release/tag refreshes remain a separate explicit owner decision.

## Authority and scope

- Current user instructions take precedence over repository guidance. The product
  owner approves market/authority changes, main merges, releases and tags.
- PRODUCT defines current product boundaries; the roadmap defines sequencing; STATUS
  records evidence and selection; the active WP defines the bounded change. Accepted
  ADRs constrain implementation. If they conflict, report the conflict rather than
  silently selecting a convenient rule. Proposed scope/estimates are not approved features.
- Archive content, old checkboxes and historical `Active` metadata are not work orders.
  Unchecked historical acceptance items remain open until evidence or an explicit
  superseding decision closes them; archiving does not make them Verified.
- The owner has moved this continuation to `main`; work directly on `main` for the
  current Mac-only v1. No merge, release/tag or workflow/billing changes without
  explicit authorization.
- No real broker orders, requested exchange secrets or real Keychain credential writes.
  No user data reset/delete/migration apply without explicit approval. With no real
  migration data, start clean; do not copy Windows data or create migration bundles.
- AI has no order authority. Deterministic risk is fail-closed authority. Experimental,
  disabled and unavailable surfaces stay so. Missing evidence is never invented success.
- Preserve unrelated user changes (including `.codex/`). Use isolated test data.
  Never request passwords/tokens in chat; required OS approvals are performed by the user.
- Use relevant regression tests and risk-appropriate local CI. Follow
  [LOCAL-CI-POLICY](docs/strategy/LOCAL-CI-POLICY.md). `uv --offline` is not a runtime
  network firewall. A previous test run is not evidence for a new binary.
- No hardcoded user-facing JSX text: keep EN/TR/DE translation keys in parity.
- Subagents are optional. If requested for this continuation, use GPT-5.6 Luna.

## Finish each bounded task

1. Update the active WP checkboxes with actual acceptance/test evidence; never close
   a criterion merely because code was written. Record commands, platform and limitations.
2. Update STATUS in the same change: outcome, blockers, next dependency, evidence refs.
   Do not create a new dated status/roadmap report for every task.
3. Change the roadmap only when scope/order/dependencies change. Product/ADR changes
   need the applicable owner decision, not an automatic consequence of a new feature.
4. Archive a genuinely completed WP with evidence. If incomplete work is deferred,
   retain its unchecked items and a visible blocker/obligation link in STATUS.
5. Update `docs/documentation.json` when roles/paths/active WP change. There must be
   one current roadmap and one selected current WP, not competing entry points.
6. Run `python3.11 scripts/check_docs.py` plus relevant tests. Report exact outcomes,
   changed files, commit/push and blockers. Commit/push only within user authorization.

For commit evidence in STATUS, use the preceding implementation SHA or `this change`
with file/test references; resolve the latter from Git history when starting the next
task. Do not create an endless follow-up commit solely to record its own hash.
