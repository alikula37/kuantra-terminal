# Security Assessment Report

**Project:** Kuantra Terminal (local-first trader forensics desktop application)
**Date:** 2026-09-15
**Scanner:** security-check v1.2.0 (`ersinkoc/security-check`, bundle hash `4542ae21…f7512c`)
**Profile:** Deep · whole repository · sandboxed local checks
**Commit audited:** `2c961fe` + remediation working tree
**Risk Score:** 8.2/10 (High at scan time) → 0 confirmed findings remain unpatched; all 22 confirmed items remediated with regression coverage

## Executive Summary

A deep, whole-repository assessment was performed on Kuantra Terminal (167 backend Python
files / ~42.6k LOC, 123 frontend TS/TSX files / ~25.1k LOC, 155 HTTP routes, one WebSocket
route, GitHub Actions release pipeline). Five independent hunter passes covered the HTTP API,
desktop gateway/local IPC, webhook/WS surfaces, data/parsers/crypto paths, and CI/CD supply
chain. 21 candidates were verified as confirmed trust-boundary failures; 3 additional hunter
claims were disproved during independent verification; several coverage units produced no
confirmed findings. A 2026-09-15 follow-up (crafted-ZIP validation) added one more confirmed
Medium finding (PATH-003), bringing the total to 22.

The application intentionally has **no endpoint authentication** (single-user desktop, in-process
API); therefore the audit focused on whether each networkable surface is properly constrained by
binding, route-surface isolation, secret-based verification, and bounded inputs. The confirmed
findings cluster exactly there: an over-broad gateway mount, a length-only "signature" on the
P2P copy path, a kill switch that fabricated closing trades and shipped hardcoded disarm PINs,
path traversal in the model downloader, and multiple unbounded-input/resource paths. Supply-chain
hardening was also required: workflow actions were pinned to mutable tags inside a
`contents: write` release job.

All 22 confirmed findings are fixed in the working tree and pinned by tests
(`backend/tests/test_security_review_fixes.py`, 33 tests; `backend/tests/test_security_crafted_zip.py`,
14 tests; updated `test_python_dependency_lock_contract.py`, `test_phase14_p2p_copy.py`). No finding
remains unremediated; the residual risk items are runtime/deployment facts listed under Needs
Validation, not code defects.

### Key Metrics

| Metric | Value |
|--------|-------|
| Total verified findings | 22 |
| Critical | 0 |
| High | 4 |
| Medium | 12 |
| Low | 6 |
| Rejected hunter claims | 3 |
| Confirmed findings without a regression test | 2 (grep-verified workflow edits: CICD-002, CICD-003) |

### Top Risks

1. **Panic kill-switch fabricated forensic evidence and shipped hardcoded disarm PINs** (High) —
   a trigger wrote synthetic close records without broker authority, and lockdown could be
   removed with PIN-like constants present in source.
2. **Gateway mounted the full webhook router** (High) — any loopback-reachable process/browser
   page could write trade confirmations into the evidence journal.
3. **Copy-signal "signature" accepted by length only** (High) — a counterfeit master signal
   could pass verification and reach the order router.
4. **Model downloader path traversal** (High) — `model_name` was joined under `MODELS_DIR`
   without canonicalization, enabling arbitrary-path metadata reads and artifact writes.

## Scan Statistics

| Statistic | Value |
|-----------|-------|
| Files scanned (backend + frontend + scripts/workflows) | ~380 |
| Lines of code reviewed (backend + frontend) | ~67.7k |
| Languages detected | Python, TypeScript, TSX, YAML, Bash, Dockerfile |
| Frameworks detected | FastAPI, Pydantic v2, React, Vite, pywebview, SQLite, DuckDB |
| Skills executed | sc-orchestrator/recon/verifier/report, sc-api-security, sc-authz, sc-business-logic, sc-ci-cd, sc-crypto, sc-data-exposure, sc-docker, sc-lang-python, sc-mass-assignment, sc-path-traversal, sc-xss (sampled), sc-local-ipc, sc-secrets (sampled), sc-dependency-audit |
| Candidates before verification | 25 (22 confirmed + 3 rejected) |
| False positives eliminated | 3 |
| Final confirmed findings | 22 (all fixed and test-pinned) |

## Confirmed Findings (all remediated)

CVSS-style severity; "Residual" states the post-fix security position.

### High

**H1 — Panic kill-switch fabricated closes; hardcoded disarm PINs** (CWE-798, CWE-471)
`backend/app/services/biometrics/panic_switch.py` (pre-fix 31–46, 77–95).
`trigger_emergency_kill_switch` wrote synthetic close records for open positions although the
product has no order authority, and disarm compared against PIN hashes embedded in source.
**Remediation:** trigger now only locks down and records
`flattened_positions_count: 0`, `flattening: "DISABLED_NO_ORDER_AUTHORITY"`; disarm requires
`KUANTRA_PANIC_DISARM_SECRET` via `hmac.compare_digest`, otherwise `PANIC_DISARM_UNCONFIGURED`.
**Residual:** none; evidence integrity preserved, no in-code secrets.
**Tests:** `test_panic_trigger_does_not_write_fabricated_closes`, `test_panic_disarm_rejects_hardcoded_pins`, `test_panic_disarm_requires_the_configured_secret`.

**H2 — Gateway exposed unauthenticated confirmation/observation routes** (CWE-306)
`backend/desktop/gateway.py` (pre-fix 28–36) mounted `webhook_router`, including the manual
trade-confirmation write path, on `127.0.0.1:8765` with no auth dependency.
**Remediation:** gateway mounts `webhook_ingest_router` only; review/list routes remain on the UI
app; non-loopback bind refused unless `KUANTRA_ALLOW_NON_LOOPBACK_GATEWAY=1`.
**Residual:** local processes can still reach the ingest route but can no longer write confirmed
trades directly.
**Tests:** `test_gateway_mounts_only_ingest_ws_and_health`, `test_review_routes_remain_on_the_ui_app`, `test_gateway_refuses_non_loopback_bind`.

**H3 — Copy-signal signature accepted by length** (CWE-347)
`backend/app/services/p2p/copy_engine.py` (pre-fix 97–121): verification compared only
`len(signature) == 64`; success routed orders via `order_router.route_order`.
**Remediation:** shared-secret HMAC-SHA256 over canonical fields with `compare_digest`; fail
closed without `KUANTRA_COPY_SIGNAL_SECRET`; broadcast endpoint returns 503 when unconfigured.
**Residual:** none for signature forgery; operator must configure the secret to use copy features.
**Tests:** `test_copy_engine_rejects_length_only_signature`, `test_copy_engine_accepts_valid_hmac`, `test_copy_broadcast_requires_configured_secret`, `test_phase14_p2p_copy.py`.

**H4 — Model artifact path traversal** (CWE-22)
`backend/app/core/model_downloader.py` (pre-fix 35–115): `MODELS_DIR / model_name` without
canonicalization; status exposed metadata of any path; download wrote to attacker-chosen paths.
**Remediation:** `_safe_model_name()` rejects empty/absolute/separator/>128-char names and
requires `resolve().is_relative_to(MODELS_DIR)`; endpoints return 400 `MODEL_NAME_INVALID`.
**Residual:** none.
**Tests:** `test_model_downloader_rejects_names_outside_models_dir`, `test_model_downloader_status_hides_arbitrary_paths`, `test_model_endpoint_rejects_traversal`.

### Medium

**M1 — Webhook body unbounded for chunked requests** (CWE-400) — `webhook_tv.py`
(pre-fix 141–157); header-only size check, `await request.body()` unbounded. Fixed with a
streaming 64KB cap before HMAC verification. Test: `test_webhook_rejects_chunked_oversize_body`.

**M2 — Live-execution guard missing on cancel/open-order/model routes** (CWE-693) —
`endpoints.py`; only dispatch enforced paper mode. Fixed with a shared
`_require_paper_execution_mode` guard on dispatch, cancel, and open-order routes. Test:
`test_live_mode_is_rejected_on_cancel_and_open_order_routes`.

**M3 — Reconciliation correction numbers unvalidated** (CWE-20) — NaN/Inf/huge values accepted
into corrections. Fixed with per-field finite bounds. Test:
`test_reconciliation_correction_requires_bounded_numbers`.

**M4 — TradeCloseSchema non-finite/huge values** (CWE-20) — `exit_price`/`commission` bounded,
`allow_inf_nan=False`. Tests: `test_trade_close_schema_rejects_unbounded_values`,
`test_trade_close_schema_rejects_non_finite_commission`.

**M5 — `update_trade` column-name interpolation** (CWE-89) — column names came from caller
mappings. Fixed with a frozen allowlist; unknown columns raise `ValueError`. Test:
`test_update_trade_rejects_unknown_columns`.

**M6 — Broker import discrepancy amplification** (CWE-400) — reconciliation produced 450
discrepancies for a 150-row probe and copied them wholesale into the response. Fixed: at most
100 returned + `discrepancy_count` + `discrepancies_truncated`. Test:
`test_broker_import_review_discrepancies_are_count_bounded`.

**M7 — Migration archive member reads unbounded** (CWE-409) — declared sizes were trusted.
Fixed with streamed bounded reads for verify and restore. Test:
`test_migration_member_read_is_byte_bounded`.

**M8 — Generated-code string injection** (CWE-94) — reverse-skill generator interpolated raw
`strategy_id`/`strategy_name` into Python literals. Fixed with `json.dumps`. Test:
`test_generated_python_string_escapes_injection`.

**M9 — Workflow actions pinned to mutable tags** (CWE-1357) — all `uses:` pinned to full
40-char SHAs resolved with `git ls-remote`, including `softprops/action-gh-release` in the
`contents: write` job; contract test now requires SHA pins.

**M10 — `package_linux.sh` silent appimagetool download** (CWE-494) — unverified binary
fetched and executed when missing. Fixed: fail closed unless `APPIMAGETOOL` is supplied. Test:
`test_package_linux_never_downloads_unverified_tool`.

**M11 — Release publish checkout persisted credentials** (CWE-522) — the `contents: write`
publish job left the `GITHUB_TOKEN` in the checkout's git config. Fixed with
`persist-credentials: false` (verified by workflow inspection in the committed diff).

**M12 — Migration manifest read unbounded before JSON parsing** (CWE-409) — crafted-ZIP
follow-up: `_read_manifest` used `archive.read("manifest.json")`, so a compressed manifest bomb
could force a full member-cap-sized decompression plus JSON parse before any bound applied.
Fixed with a dedicated streamed `MAX_ARCHIVE_MANIFEST_BYTES` (1MB) ceiling. Tests:
`test_oversized_manifest_is_bounded_before_parsing` plus the 14-test crafted-archive suite.

### Low

**L1 — Non-constant-time webhook secret comparisons** (CWE-208) — HMAC, passphrase, and tunnel
token comparisons now use `hmac.compare_digest`, tolerant of non-ASCII input.

**L2 — Credential probe error echo** (CWE-209) — generic per-type messages at the boundary.

**L3 — Trade list pagination unbounded** (CWE-400) — `limit` 1..1000, `offset` >= 0.

**L4 — `release_tag` dispatch input unvalidated** (CWE-20) — anchored
`^[A-Za-z0-9._-]{1,40}$` gate before shell use.

**L5 — Dockerfile missing pipefail** (CWE-1188) — strict shell added to the smoke image.

**L6 — Copy broadcast without configured secret** (CWE-347) — 503 fail-closed instead of
emitting unverifiable signals.

## Needs Validation (no severity)

Resolved since the original report: dependency CVE freshness was checked with an OSV.dev scan
(only package name/version pairs sent; Python 0/82, npm one dev-only advisory retained —
see `security-report/dependency-audit.md` and `security-report/dependency-scan-2026-09-15.json`);
the crafted-ZIP validation ran as 14 synthetic-archive regression tests and produced and fixed
one additional Medium finding (M12); the SHA-pinned workflows were then executed for real in
release run `35017352321` (`publish: false`, both native runners green).

| Item | Blocker | Safe next check |
|------|---------|-----------------|
| Continuous dependency monitoring | The OSV scan is point-in-time; no CI job repeats it | Add an owner-approved `pip-audit`/OSV job to CI where network use is acceptable |
| npm dev-only vitest advisory | **Resolved 2026-09-16:** vitest upgraded to the patched 4.1.11; `npm audit` (production and full) reports 0 vulnerabilities, full frontend suite green | — |
| macOS signing/notarization | Unsigned pilot channel; unchanged by this review | Notarize before public distribution |
| Real XM statement parser correctness | No real sample (tracked product obligation) | Anonymized XM report validation |
| Live network probing of provider APIs | Audit constraints prohibit live probing and credential use | Owner-approved staging probe |

## Hardening Notes (positive controls / recommendations)

- Present and working: loopback gateway bind with explicit override, TV-sync WS origin
  allowlist, CORS origin allowlist, hashed Python dependency installs, idempotent webhook
  ingestion, bot/allowlist-free design for a local single-user app.
- Recommended next (not findings): add a small owner-approved `pip-audit`/OSV job in CI where
  network use is acceptable; consider a per-launch random gateway token so even loopback
  processes cannot post forged ingest payloads; document the `KUANTRA_COPY_SIGNAL_SECRET` /
  `KUANTRA_PANIC_DISARM_SECRET` / `KUANTRA_ALLOW_NON_LOOPBACK_GATEWAY` operating requirements
  in the deployment docs; plan the bounded vitest 4 dev-toolchain upgrade.

## Coverage Totals

14 coverage units: 13 covered, 1 sampled (frontend output handling, 0 findings), 0 blocked
(the former dependency-CVE blocker is resolved as a point-in-time scan). Full detail:
`security-report/coverage-ledger.md`.
Rejected claims and duplicate root causes are recorded in `security-report/verified-findings.md`.

## Remediation Roadmap

- **Phase 0 (this scan, complete):** all 4 High, 12 Medium, 6 Low findings fixed; 33 security
  regression tests plus the 14-test crafted-archive suite green; contract tests updated; full
  backend suite green; canonical local CI run on the remediation commit.
- **Phase 1 (before the next pilot release, complete):** canonical CI on the clean commit;
  SHA-pinned workflow dry-run executed as release run `35017352321` (both native runners green);
  crafted-ZIP validation executed and its one new finding fixed.
- **Phase 2 (before broader distribution):** dependency monitoring job in CI; bounded vitest 4
  dev-toolchain upgrade; per-launch gateway token; notarized macOS builds.
- **Phase 3 (ongoing):** keep SHA pins updated (comment-documented versions); re-run this audit
  on any change to gateway/webhook/copy/import surfaces; repeat the OSV scan or add CI monitoring.
