# Kuantra release truth contract

Release-facing claims are governed by the versioned matrix in
[`truth-matrix.v1.0.0.json`](truth-matrix.v1.0.0.json). The matrix is a contract, not a
marketing inventory: it records what the current product can prove, what remains disabled,
and which files are scanned before a build or GitHub Release.

The current release train targets v1.0.0 on macOS 12+ with separate native arm64 and x86_64
artifacts. A native `macos-15-intel` runner has now produced the x86_64 build, desktop
smoke and exact mounted-DMG smoke; both architectures are verified current candidates.
The existing private pilot Release
[`pilot-v1.0.0-arm64`](https://github.com/alikula37/kuantra-terminal/releases/tag/pilot-v1.0.0-arm64)
has been refreshed in place to carry both native DMGs; it remains ad-hoc and
trusted-pilot-only. The previous
v1.4.0 matrix and historical documentation remain in the repository for audit context only.
Its GitHub publication, tag and assets were removed on 2026-09-11; v1.4.0 is not a download
source or a current product description.

The three-person pilot distribution and technical validation path is documented in
[`PILOT-DISTRIBUTION-RESEARCH.md`](PILOT-DISTRIBUTION-RESEARCH.md) and
[`PILOT-INSTRUCTIONS.md`](PILOT-INSTRUCTIONS.md). The private GitHub Release now carries
the two native architecture DMGs, evidence and checksums for users with repository read
access. The earlier arm64-only package remains historical evidence; the current dual
package includes the same explicit architecture boundary for both M-series and Intel users.
The separate `pilot-v1.0.0-arm64` tag is a private prerelease transport identifier, not the
canonical `v1.0.0` product release tag. That transport does not provide Apple Developer ID
trust; an ad-hoc DMG remains trusted-pilot-only and requires manual Gatekeeper approval. The
current published dual-architecture pilot Release is
[`pilot-v1.0.0-arm64`](https://github.com/alikula37/kuantra-terminal/releases/tag/pilot-v1.0.0-arm64).
For pilot-user clarity, its download area contains only the two exact native DMGs.
Technical smoke/N05 evidence, manifest, instructions and checksums remain in the repository
and local audit package rather than as separate downloads. The x86_64 evidence gate is now
closed by native CI; N03, N05, H05 and pilot access remain separate gates. No canonical
`v1.0.0` product Release/tag has been created.

The proposed end-to-end delivery and release-readiness plan is
[KPR-001](../strategy/PRODUCTION-READINESS-PLAN.md). Its G6 checklist covers exact-source
final artifacts, recovery, security, product evidence and owner approval. It does not
grant release authority or change this truth matrix; an engineering gate alone is
not proof that the read-only product is ready for production.

The current matrix is `KTR-001@1.0.0`. The prior `KTR-001@1.0.1` matrix remains as
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
