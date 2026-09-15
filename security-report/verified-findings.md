# Kuantra Terminal — Verified Findings (Phase 3)

**Date:** 2026-09-15 · security-check v1.2.0 · Deep profile / whole repository / sandboxed local checks
**Source candidates:** `security-report/findings/*.json` (8 skill files, 21 candidates)
**Result:** 21 confirmed · 0 needs_validation candidates · 0 rejected candidates · 3 rejected coverage claims (below)

Every confirmed finding was verified against the pre-fix source at `2c961fe` (`git diff HEAD`
shows each removal), reproduced with a failing regression test where technically possible, and
is now pinned by a passing test in `backend/tests/test_security_review_fixes.py` (33 tests) plus
the updated contract tests. Verification was performed by fresh code reading and local test
runs; the original hunter agents did not mark their own candidates.

## Confirmed (21)

| ID | Skill | Severity | Title | Fix site | Verification |
|----|-------|----------|-------|----------|--------------|
| PATH-001 | sc-path-traversal | High | Model artifact name path traversal | `backend/app/core/model_downloader.py` | Traversal/absolute/empty names raise ValueError and 400 at the API; status no longer exposes arbitrary file metadata |
| PATH-002 | sc-path-traversal | Medium | Migration archive member reads unbounded | `backend/app/services/macos_migration.py` | Streamed `_read_member_bounded` cap; oversized-member test passes |
| AUTHZ-001 | sc-authz | High | Gateway mounted the full webhook router | `backend/desktop/gateway.py` | Gateway app now exposes only ingest + TV sync + health; confirm routes remain on the UI app; non-loopback bind refused |
| CRYPTO-001 | sc-crypto | High | Copy signal accepted by signature length | `backend/app/services/p2p/copy_engine.py` | HMAC-SHA256 over canonical payload; without secret verify fails closed; broadcast 503 |
| CRYPTO-002 | sc-crypto | Low | Non-constant-time webhook secret comparisons | `backend/app/api/webhook_tv.py` | `hmac.compare_digest` for HMAC, passphrase, tunnel auth |
| LOGIC-001 | sc-business-logic | High | Panic switch fabricated closes + hardcoded PIN | `backend/app/services/biometrics/panic_switch.py` | Trigger writes no trades; disarm needs `KUANTRA_PANIC_DISARM_SECRET` |
| LOGIC-002 | sc-business-logic | Medium | Live-mode guard missing on cancel/open routes | `backend/app/api/endpoints.py` | Shared `_require_paper_execution_mode` on dispatch/cancel/open |
| LOGIC-003 | sc-business-logic | Medium | Import discrepancy amplification | `backend/app/services/broker_import_service.py` | Probe: 450 discrepancies counted, 100 returned, truncation flag set |
| LOGIC-004 | sc-business-logic | Low | Broadcast without configured secret | `backend/app/api/endpoints.py` | 503 `COPY_SIGNAL_SECRET_UNCONFIGURED` |
| API-001 | sc-api-security | Medium | Webhook body unbounded for chunked requests | `backend/app/api/webhook_tv.py` | Streaming 64KB cap independent of headers |
| API-002 | sc-api-security | Medium | Reconciliation correction numbers unvalidated | `backend/app/services/reconciliation_inbox.py` | Per-field finite/bounded validation |
| API-003 | sc-api-security | Medium | TradeCloseSchema non-finite/huge values | `backend/app/api/endpoints.py` | Pydantic Field bounds, `allow_inf_nan=False` |
| API-004 | sc-api-security | Low | Trade list pagination unbounded | `backend/app/api/endpoints.py` | `limit` 1..1000, `offset` >= 0 |
| MASS-001 | sc-mass-assignment | Medium | `update_trade` column interpolation | `backend/app/db/sqlite_driver.py` | Frozen allowlist; unknown field raises ValueError |
| PY-001 | sc-lang-python | Medium | Generated-code string injection | `backend/app/services/ai/reverse_skill.py` | `json.dumps` literal emission test |
| EXPO-001 | sc-data-exposure | Low | Credential probe error echo | `backend/app/services/exchange/credentials_manager.py` | Generic per-type messages; detail not returned |
| CICD-001 | sc-ci-cd | Medium | Actions on mutable tags (contents:write job) | `.github/workflows/ci.yml`, `release.yml` | All uses pinned to 40-char SHAs; contract test requires pins |
| CICD-002 | sc-ci-cd | Medium | Publish checkout persisted credentials | `.github/workflows/release.yml` | `persist-credentials: false` in publish job |
| CICD-003 | sc-ci-cd | Low | `release_tag` dispatch input unvalidated | `.github/workflows/release.yml` | `^[A-Za-z0-9._-]{1,40}$` gate before shell use |
| CICD-004 | sc-ci-cd | Medium | `package_linux.sh` silent tool download | `scripts/package_linux.sh` | No download path; requires explicit `APPIMAGETOOL`; test asserts absence of curl |
| DOCKER-001 | sc-docker | Low | Dockerfile missing pipefail | `packaging/linux/Dockerfile.smoke` | `SHELL ["/bin/bash","-o","pipefail","-c"]` |

## Rejected coverage claims (disproved during verification)

| Claim (hunter source) | Rejection reason |
|-----------------------|------------------|
| "Dev WebSocket endpoints `/ws/stream` and `/ws/replay` lack origin checks" | Those routes do not exist. The only WS route is `/ws/tv-sync`, and it already enforces `is_allowed_gateway_origin()` before accepting (`backend/app/api/tv_sync_ws.py`). |
| "Chunked body bypasses webhook HMAC verification" | HMAC verification consumes the same bounded raw body that `_read_bounded_body` returns; there is no alternate verification path. The confirmed defect was only the unbounded read (API-001). |
| "Gateway observations list endpoint leaks journal data unauthenticated" | The gateway no longer mounts any observation/list route; the entire review surface stays on the UI app (desktop in-process/dev loopback). |

## Verification limitations

- Fix evidence is source + local test runs; no network penetration test, no live provider calls,
  no GitHub workflow execution (un-runnable locally).
- Confidence values in `findings.json` reflect the strength of the source trace and local
  reproduction, not runtime exploitation.
