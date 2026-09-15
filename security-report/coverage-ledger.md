# Kuantra Terminal — Coverage Ledger (Phases 1–4)

**Date:** 2026-09-15 · security-check v1.2.0
**Profile:** Deep · **Scope:** whole repository · **Validation:** sandboxed local checks
**Previous report:** none existed (`security-report/` was absent) → treated as a fresh audit.

## Execution summary

| Phase | Activity | Result |
|-------|----------|--------|
| 1 Recon | Architecture map, entry points, trust boundaries | `security-report/architecture.md` |
| 1 Dep audit | Lock/hash/pinning checks | `security-report/dependency-audit.md` |
| 2 Hunt | 5 independent hunter passes over HTTP/API, desktop+gateway+updater, webhook/WS, data/parsers/crypto, CI/CD+supply chain; each candidate kept only with ordered source traces | 10 skill candidate files, 22 confirmed candidates + 3 rejected claims |
| 3 Verify | Fresh read of every candidate against pre-fix source, root-cause merges, local reproduction where possible | `findings.json`, `verified-findings.md` |
| 4 Report | Severity mapping, needs-validation split, hardening notes, roadmap | `SECURITY-REPORT.md` |
| Follow-up | Dependency OSV scan + crafted-ZIP validation (2026-09-15) | resolved both former blockers; one new Medium finding (PATH-003) fixed |

## Coverage units

| # | Surface × boundary | Skills applied | Status | Candidates |
|---|--------------------|----------------|--------|------------|
| 1 | API input validation & resource bounds (B5) | sc-api-security, sc-mass-assignment | Covered | 5 confirmed |
| 2 | Filesystem containment (B5) | sc-path-traversal | Covered | 3 confirmed |
| 3 | Gateway/webhook exposure (B1/B2) | sc-authz, sc-api-security, sc-crypto | Covered | 3 confirmed (+1 merged) |
| 4 | P2P copy trust (B4) | sc-crypto, sc-business-logic | Covered | 2 confirmed |
| 5 | Kill-switch/biometrics (B5) | sc-business-logic, sc-crypto | Covered | 1 confirmed |
| 6 | Broker/statement import (B3) | sc-business-logic | Covered | 1 confirmed |
| 7 | Archive/migration (B5) | sc-path-traversal | Covered | 1 confirmed |
| 8 | Generated-code paths (B5) | sc-lang-python | Covered | 1 confirmed |
| 9 | Credentials/exchange (B5) | sc-data-exposure | Covered | 1 confirmed |
| 10 | CI/CD & packaging (B6) | sc-ci-cd, sc-docker | Covered | 5 confirmed |
| 11 | Frontend output handling (B1) | sc-xss (sampled) | Sampled | 0 confirmed — imported values render through React escaping; no `dangerouslySetInnerHTML` in the statement/broker UI paths reviewed |
| 12 | Desktop/local IPC (pywebview, single-instance, updater) | sc-local-ipc | Covered | 0 additional — gateway finding folded into AUTHZ-001; updater/manifest paths reviewed, no verified boundary failure |
| 13 | Secrets in repository | sc-secrets | Sampled | 0 confirmed — no committed live secrets found in reviewed configuration/build surfaces |
| 14 | Dependency CVEs | sc-dependency-audit | Covered (point-in-time) | 0 runtime, 1 dev-only npm advisory |

## Blocked / deferred / out of scope

| Item | Type | Reason | Safe next check |
|------|------|--------|-----------------|
| Continuous dependency monitoring | Open follow-up | The 2026-09-15 OSV scan is point-in-time; no CI job repeats it | Add an owner-approved OSV/`pip-audit` CI job |
| npm dev-only vitest advisory (`GHSA-82fw-gwwq-j7x9`) | Open follow-up (dev-only) | Fix requires a vitest 3.x → 4.x major upgrade; production installs unaffected (`npm audit --omit=dev` = 0) | Schedule a bounded vitest 4 upgrade with its own test run |
| macOS signing/notarization trust | Out of scope (known gap) | Pilot channel is unsigned by design; audit does not change distribution trust | Notarize before public distribution |
| Live network/penetration testing of provider APIs | Out of scope | Audit constraints prohibit live probing and credential use | Owner-approved staging probe |
| Real XM statement parsing correctness | Out of scope (product obligation) | No real sample available; already tracked in `docs/strategy/STATUS.md` | Anonymized XM report validation |

Resolved since the original ledger:

- **Dependency CVE freshness** — executed 2026-09-15 with an OSV.dev scan that sent only
  `{ecosystem, name, version}` triples: Python 0/82 installed packages vulnerable; npm one
  dev-only advisory (see `security-report/dependency-audit.md` and
  `security-report/dependency-scan-2026-09-15.json`). Cross-checked against release run
  `35017352321` (`npm audit --omit=dev`: 0).
- **SHA-pinned workflow execution** — executed as release run `35017352321`
  (`workflow_dispatch`, `release_tag=v1.1.0`, `publish=false`): both native runners green.
- **Crafted-ZIP validation** — executed as 14 synthetic-archive tests in
  `backend/tests/test_security_crafted_zip.py` (central-directory falsification, declared/actual
  size mismatch, member/total/count caps, manifest ceiling, symlink/traversal/duplicate/unlisted
  members, restore atomicity). It produced one new confirmed Medium finding (PATH-003), fixed
  with a dedicated streamed manifest ceiling.

## Artifacts

```
security-report/
├── architecture.md
├── coverage-ledger.md
├── dependency-audit.md
├── findings/
│   ├── sc-api-security.json
│   ├── sc-authz.json
│   ├── sc-business-logic.json
│   ├── sc-ci-cd.json
│   ├── sc-crypto.json
│   ├── sc-data-exposure.json
│   ├── sc-docker.json
│   ├── sc-lang-python.json
│   ├── sc-mass-assignment.json
│   └── sc-path-traversal.json
├── findings.json
├── verified-findings.md
├── dependency-scan-2026-09-15.json
└── SECURITY-REPORT.md
```
