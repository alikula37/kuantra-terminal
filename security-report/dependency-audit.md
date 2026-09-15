# Kuantra Terminal — Dependency Audit

**Date:** 2026-09-15 · security-check v1.2.0 · sandboxed local checks

## What was verified locally

| Control | Result |
|---------|--------|
| Python lockfile exists (`backend/requirements.lock`) | PASS |
| CI/release/Docker install only from the hashed lock (`pip install --require-hashes -r backend/requirements.lock`) | PASS (`backend/tests/test_python_dependency_lock_contract.py`) |
| No `--no-deps`, `--no-verify`, `--require-hashes=false`, or unpinned `requirements.txt` installs in workflows/Dockerfile | PASS |
| All workflow `uses:` actions pinned to full 40-char commit SHAs (was mutable tags) | PASS after fix F13 (`ci.yml`, `release.yml`, contract test updated) |
| SHA pins resolved from upstream tags via `git ls-remote` (network, tag → commit dereference) | PASS for `actions/checkout v7`, `actions/setup-python v7`, `actions/setup-node v7`, `actions/upload-artifact v7`, `actions/download-artifact v8`, `astral-sh/setup-uv v10.1.0`, `softprops/action-gh-release v2` |
| Frontend dependency install (`npm ci`) uses committed lockfile | PASS (unchanged) |

## Supply-chain notes

- `softprops/action-gh-release` runs in a `contents: write` job; pinning (F13) plus
  `persist-credentials: false` on that checkout (F13b) and a strict `release_tag` input
  format check (F13c) narrow the release blast radius.
- `scripts/package_linux.sh` no longer downloads `appimagetool` silently; it fails closed
  and requires an explicitly supplied, verified tool (F14).

## Not verified (needs_validation)

- **CVE freshness of locked dependencies and npm packages.** No local vulnerability database
  or scanner (`pip-audit`, `osv-scanner`) is installed, and the audit constraints prohibit
  sending the dependency graph to external audit services. Version-pinned hashes protect
  integrity of the supply chain, not known-CVE status.
- **GitHub-hosted execution of the pinned workflows.** Pins were resolved locally with
  `git ls-remote`; no workflow run was performed as part of this audit (cannot be run locally).
- **macOS code signing / notarization.** Still absent by design of the pilot channel; this
  review does not change the distribution trust level.
