# Kuantra release truth contract

Release-facing claims are governed by the versioned matrix in
[`truth-matrix.v1.1.4.json`](truth-matrix.v1.1.4.json). The matrix is a contract, not a
marketing inventory: it records what the current product can prove, what remains disabled,
and which files are scanned before a build or GitHub Release.

The current release train targets v1.1.4 on macOS 12+ with separate native arm64 and x86_64
artifacts; v1.1.4 adds the read-only chart review (closed-trade candles and a
provider-matched open-position review whose refresh fetches only the declared free provider
and exact provider symbol, never a cache row or a substituted product), an independent
one-request spot-product consistency check with measured overlap/deviation, the separation
of the confirmed provider identity from a manually typed entry price, explicit simulation
labelling with a separate local-plan status (simulations excluded from real monetary
aggregates), and journal row actions that stay reachable and keyboard focusable at the
pilot's window sizes. v1.1.3 added the journal bulk CSV export and readable PDF reports
(explicit filtered/all scope, Europe/Istanbul period with entry/close basis, separated
open/closed/canceled performance, unknown-PnL and unverified-currency accounting, separate
local TP/SL estimates, and a direct PDF artifact in the single-trade Evidence Pack).
v1.1.2 fixed the in-app update notifier to open this repository's Releases list instead of a
version-pinned page and upgraded the dev-only vitest toolchain to the patched 4.1.11 release.
v1.1.1 was the security-hardened rebuild of the v1.1.0 pilot (deep security
review follow-up, dependency OSV scan, crafted-ZIP validation), and the v1.1.0 pilot added
user-supplied Turkey-time trade dates, revisioned journal
editing with local TP/SL plan synchronization, declared-leverage sizing, bounded open-trade
quote refresh, and a fail-closed monetary boundary that requires an explicit base-unit
declaration. Both architectures are verified current candidates; Intel evidence comes from
the native `macos-15-intel` release workflow lane, arm64 from the native Apple Silicon host.

The private pilot Release
[`pilot-v1.1.4`](https://github.com/alikula37/kuantra-terminal/releases/tag/pilot-v1.1.4)
carries both native DMGs; it remains ad-hoc and trusted-pilot-only. Its tag points at the
verified build commit. The former `pilot-v1.1.0` prerelease is superseded, keeps no downloads
and directs users to `pilot-v1.1.1`; `pilot-v1.1.1` keeps its historical 1.1.1 packages and
directs users to `pilot-v1.1.2`; `pilot-v1.1.2` keeps its historical 1.1.2 packages and
directs users to `pilot-v1.1.3`; `pilot-v1.1.3` keeps its historical 1.1.3 packages and
directs users to `pilot-v1.1.4`. The previous
`pilot-v1.0.0-arm64` transport is historical. The prior
v1.4.0 matrix and historical documentation remain in the repository for audit context only.
Its GitHub publication, tag and assets were removed on 2026-09-11; v1.4.0 is not a download
source or a current product description, and the earlier `truth-matrix.v1.0.0.json` is kept
only as a prior-train record.

The three-person pilot distribution and technical validation path is documented in
[`PILOT-DISTRIBUTION-RESEARCH.md`](PILOT-DISTRIBUTION-RESEARCH.md) and
[`PILOT-INSTRUCTIONS.md`](PILOT-INSTRUCTIONS.md). The private GitHub Release carries
only the two native architecture DMGs for users with repository read access.
Evidence and checksums remain in the audit package and Release notes. The separate
`pilot-v1.1.4` tag is a private prerelease transport identifier, not a canonical product
release tag. That transport does not provide Apple Developer ID trust; an ad-hoc DMG remains
trusted-pilot-only and requires manual Gatekeeper approval. Technical smoke/N05 evidence,
manifest, instructions and checksums remain in the repository and local audit package rather
than as separate downloads. N03, N05, H05 and pilot access remain separate gates.

The proposed end-to-end delivery and release-readiness plan is
[KPR-001](../strategy/PRODUCTION-READINESS-PLAN.md). Its G6 checklist covers exact-source
final artifacts, recovery, security, product evidence and owner approval. It does not
grant release authority or change this truth matrix; an engineering gate alone is
not proof that the read-only product is ready for production.

The current matrix is `KTR-001@1.1.4`. The prior `KTR-001@1.0.1` matrix remains as
repository-only historical evidence for the withdrawn v1.4.0 line; it is not overwritten
because release truth is immutable per product version.

## Naming and versioning

- `truth-matrix.<product-version>.json` is immutable for that product version. A new product
  version gets a new matrix file; a same-version wording correction increments the matrix
  `version` field and is recorded in Git history.
- `document_id` (`KTR-001`) is stable across matrix revisions. It must not be reused for a
  different product identity or execution-authority boundary.
- `product.version`, `backend/app/version.py`, package metadata and the accepted release tag
  must match exactly. The checker rejects a tag that is not the matrix's `release_tag`.
- `RELEASE_NOTES.md` may retain historical notes, but only the marker-delimited current section
  is rendered into a GitHub Release body.

## Verification command

```text
python scripts/check_release_truth.py
```

The command is dependency-free, read-only and runs in CI before backend/frontend builds. A
tagged release additionally passes `--tag <exact-matrix-release-tag>`.
