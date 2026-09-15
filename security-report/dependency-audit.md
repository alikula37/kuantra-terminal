# Kuantra Terminal — Dependency Audit

**Date:** 2026-09-15 (security-review follow-up) · security-check v1.2.0

## Method and data minimisation

- Python: `backend/requirements.lock` parsed locally (98 pinned entries; 82 installed for the
  macOS toolchain were queried, 16 platform-excluded entries were not sent).
- npm: `frontend/package-lock.json` parsed locally (289 entries).
- External service: **OSV.dev** (`POST https://api.osv.dev/v1/querybatch`, then
  `GET https://api.osv.dev/v1/vulns/{id}` for reported advisories).
- **Sent to the service:** only `{ecosystem, package name, version}` triples (82 PyPI + 289 npm).
  No source code, no lockfile bytes or hashes, no paths, no credentials, no environment values.
- No installs, no `npm audit fix --force`, no dependency or version changes were made.
- Raw payload/response files were kept outside the repository; their SHA-256 hashes and the full
  result summary are committed in `security-report/dependency-scan-2026-09-15.json`.

## Scope separation

| Ecosystem | Queried | Runtime (ships) | Build-only | Dev/test-only | Platform-excluded |
|-----------|---------|-----------------|------------|---------------|-------------------|
| PyPI (Python 3.11, macOS) | 82 | 71 | 6 | 5 | 16 (PyQt6/Qt on non-darwin, Windows-only, Linux-only) |
| npm | 289 | 37 | — | 252 | — |

## Results

| Ecosystem | Vulnerable packages | Advisories |
|-----------|---------------------|------------|
| PyPI | **0** | — |
| npm | 2 entries, 1 advisory | `GHSA-82fw-gwwq-j7x9` / `CVE-2026-84373` |

### The single npm advisory

- **Affected:** `vitest@3.2.7` and its bundled `@vitest/mocker@3.2.7` — **devDependency**, not part
  of `npm ci --omit=dev`, not bundled into the app; the packaged WebView runs the Vite production
  bundle only.
- **Issue:** path traversal / arbitrary file read via redirect mock (CVSS 3.1
  `AV:N/AC:H/PR:N/UI:N/S:U/C:H/I:N/A:N`, npm severity *moderate*).
- **Fix availability:** `4.1.11` / `5.0.0-rc.2` — only reachable through a **major** vitest upgrade
  (`npm audit fix --force`), which was deliberately not forced for a dev-only finding.
- **Disposition:** retained as a documented dev-toolchain finding; production distribution is not
  affected. A bounded vitest 4 upgrade can be scheduled separately with its own test run.

### Cross-check

The GitHub Release workflow run `35017352321` (commit `a235da2`) on the same lockfiles reported
`npm audit --omit=dev --audit-level=moderate` → **0 vulnerabilities**, and the full `npm audit` →
the same 2 moderate dev-only entries. Independent OSV query agrees.

## Controls re-verified locally

| Control | Result |
|---------|--------|
| CI/release/Docker install only from the hashed lock (`--require-hashes`) | PASS (`test_python_dependency_lock_contract.py`) |
| All workflow `uses:` pinned to full 40-char commit SHAs | PASS (same contract test) |
| No `--no-deps` / `--no-verify` / unpinned installs in workflows or Dockerfile | PASS |
| Frontend installs use the committed lock (`npm ci`) | PASS |

## Not verified (still open, not claimed clean)

- CVE freshness is a point-in-time result (OSV data as of 2026-09-15); it is not continuous
  monitoring. No CI job currently repeats this scan.
- The npm dev-only advisory remains open until a vitest major upgrade is scheduled.
- macOS signing / notarization remains a separate distribution-trust gap.
