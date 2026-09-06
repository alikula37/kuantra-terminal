# P0-WP06B — Order-flow/L2/FIX Truth Boundary

```yaml
document_id: KPS-P0-WP06B
status: Verified
version: 1.0.0
date: 2026-09-06
strategy: KPS-001@1.0.0
adr:
  - ADR-0002
  - ADR-0003
```

## Problem

Order-flow, seeded L2 liquidity and FIX/DMA surfaces currently return values that look
like recorded market or broker evidence even when no source feed or certified gateway
is connected. The in-memory matching book and FIX bridge also expose simulated success
paths. This creates a direct risk of a user mistaking demo output for market state or
an acknowledged/live execution.

## Goal

Make every order-flow/L2/FIX response truth-safe without implementing a live venue
adapter. Recorded/in-memory test fixtures remain usable only when explicitly created by
tests or a future capture pipeline.

## In scope

- Remove runtime seed liquidity, seed footprint bars, seed CVD and seed heatmap output.
- Return explicit `NO_DATA`, `UNAVAILABLE` or `EXPERIMENTAL_DISABLED` status plus
  provenance/caveat fields from order-flow, L2 and FIX surfaces.
- Ensure FIX/DMA status cannot claim an active/logged-on venue or microsecond latency
  without a real transport; order submission must never return a simulated fill.
- Keep pure FIX serialization/parsing and explicit in-memory order-book unit tests.
- Make UI defaults nullable and visibly truth-safe; disable dispatch when execution is
  unavailable.
- Add regression tests for no-seed, no-fake-fill and no-fake-latency behavior.

## Out of scope

- Native exchange or broker FIX transport, certification, TLS, resend/recovery or
  persistent sequence store.
- Rust data plane, canonical tick/order-book recorder, Arrow IPC or Parquet segments.
- Rewriting the matching algorithm or claiming an HFT latency SLA.
- Removing test-only synthetic load generation; it must be labelled as synthetic and
  cannot be used as a production performance claim.

## Acceptance criteria

1. Fresh order-flow engines return an explicit no-data response with empty arrays and no
   fabricated divergence/heatmap/footprint values.
2. Fresh global L2 state is empty; snapshot and sweep APIs cannot imply seeded liquidity.
3. FIX status is `EXPERIMENTAL`/unavailable unless a real transport is wired; it reports
   no logged-on session and no fabricated latency. Order submission never returns `FILLED`.
4. Existing pure parser, state-machine and explicit in-memory matching tests continue to
   pass after adapting assertions to the new contract.
5. Frontend order-flow and FIX widgets show no-data/unavailable states, do not initialize
   fake divergence or telemetry, and cannot dispatch an unavailable order.
6. Backend and frontend regression tests cover the above, and all local/remote release
   gates remain green.

## Migration and rollback

This is a response-contract tightening change. Existing consumers must handle the new
status/provenance fields and nullable metrics. Rollback is a single commit revert; no
database migration or data deletion is required.

## Verification record

- Backend: locked Python compileall + isolated-data full suite `333 passed, 1 skipped`.
- Focused WP06B/UAT truth suite: `20 passed`.
- Frontend: `45 passed` / 10 test files; i18n 478/478; production build successful.
- Dependency audit: `npm audit --audit-level=moderate` found 0 vulnerabilities.
- `git diff --check`: clean.
- Remote three-OS CI evidence is added after the implementation commit and must remain
  green before merge.

## Validation

- Full locked backend suite and compileall.
- Frontend unit/DOM suite, production build and npm audit.
- Three-OS GitHub CI including desktop smoke.
