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

**Assessment (2026-09-15, from the official GitHub advisory `GHSA-82fw-gwwq-j7x9` /
`CVE-2026-84373`, CVSS 5.9 moderate):** the flaw is in `@vitest/mocker`'s standalone
`mockerPlugin` / `interceptorPlugin`: a redirect mock's target path is registered from client
input on Vite's **unauthenticated HMR WebSocket** without a `server.fs.allow`/root boundary
check, so a reachable dev server can be driven into reading local files. Preconditions from the
advisory: a development server that uses those public plugin exports and is reachable (localhost
by default, network only if exposed); Vitest's own browser mode registers mocks over a
**token-authenticated** RPC and is not remotely reachable by default.

**Fit with this repository (verified locally):**
- `frontend/vitest.config.ts` runs the **node** environment; the command is `vitest run`
  (non-watch) in CI and locally, so no persistent, exposed dev server is started.
- No source or test imports `@vitest/mocker`, `mockerPlugin` or `interceptorPlugin`; the
  installed `vitest` core does not load the interceptor plugin path, and no `--browser`,
  `--api`, `--host` or `server.host` configuration exists in scripts or workflows.
- CI runs on ephemeral GitHub-hosted runners with no inbound exposure; local runs bind nothing
  beyond the developer's own machine.
- Result: **no reachable exploit path demonstrated** in the current developer/CI usage. This is
  a dev-toolchain exposure item, not an application-runtime vulnerability, and it is not
  shipped in the app bundle.

**Deferral rationale and fix check:** the advisory states that older majors (2.x, 3.x) are
unmaintained and will not receive the fix; the npm registry confirms `vitest@3` tops out at
3.2.7 while the patched line is 4.1.11 (and 5.0.x). There is therefore **no narrower fix than a
major upgrade**, which was intentionally not forced for a dev-only tool with no reachable path.

**Resolved (2026-09-16):** the dev-only `vitest` toolchain was upgraded from 3.2.7 to the
patched **4.1.11** (`@vitest/mocker@4.1.11`) in `frontend/package.json` + lockfile; npm registry
verified the patched version from the official advisory line. `npm audit` now reports **0
vulnerabilities** (both `--omit=dev` and full), and the complete frontend suite
(40 files / 240 tests), typecheck, i18n parity and production build pass on vitest 4. The
former bounded-fix proposal is therefore implemented; no `audit fix --force` was used. No
app/runtime dependency or binary content changed by this dev-toolchain upgrade.

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

## P1-WP41 additions (2026-09-16, targeted check)

The journal export/report feature added three locked packages:

| Package | Version | Role | License (official source) | Targeted OSV query |
|---------|---------|------|---------------------------|--------------------|
| reportlab | 5.0.1 | runtime (PDF rendering) | BSD-3-Clause (PyPI metadata) | no advisories |
| pillow | 12.3.0 | runtime (reportlab dependency) | MIT-CMU (PyPI license expression) | no advisories |
| pypdf | 6.19.0 | test-only (PDF text extraction) | BSD-3-Clause (repository LICENSE) | no advisories |

Only `{ecosystem, name, version}` triples were sent to `api.osv.dev`; payload SHA-256
`7343d6aa6b4b062ef61e3215076b04dcc3f43386e3236470c711e8bf54d2af5a`. The lockfile was
regenerated with the documented `uv pip compile --universal` command and the packaging spec
now collects `app/assets/fonts/*.ttf` (vendored Bitstream Vera Sans, Bitstream Vera license
included) while the legacy `PIL` exclusion was removed because reportlab imports it at
module load. Continuous monitoring remains an open follow-up.
