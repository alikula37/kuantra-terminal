# Kuantra release truth contract

Release-facing claims are governed by the versioned matrix in
[`truth-matrix.v1.0.0.json`](truth-matrix.v1.0.0.json). The matrix is a contract, not a
marketing inventory: it records what the current product can prove, what remains disabled,
and which files are scanned before a build or GitHub Release.

The current release train targets v1.0.0 on macOS 12+ with separate native arm64 and x86_64
artifacts. At this revision arm64 is the verified current candidate; x86_64 remains
`PENDING_NATIVE_CI` until a native Intel runner produces its own exact evidence. The previous
v1.4.0 matrix and publication are retained as immutable historical records, but v1.4.0 is
withdrawn and must not be installed or used as a current product description.

The three-person pilot distribution path is documented in
[`PILOT-DISTRIBUTION-RESEARCH.md`](PILOT-DISTRIBUTION-RESEARCH.md) and
[`PILOT-INSTRUCTIONS.md`](PILOT-INSTRUCTIONS.md). A private GitHub Release can carry the
two DMGs, evidence and checksums for users with repository read access. That transport does
not provide Apple Developer ID trust; an ad-hoc DMG remains trusted-pilot-only and requires
manual Gatekeeper approval. No pilot Release or tag has been created.

The proposed end-to-end delivery and release-readiness plan is
[KPR-001](../strategy/PRODUCTION-READINESS-PLAN.md). Its G6 checklist covers exact-source
final artifacts, recovery, security, product evidence and owner approval. It does not
grant release authority or change this truth matrix; an engineering gate alone is
not proof that the read-only product is ready for production.

The current matrix is `KTR-001@1.0.0`. The prior `KTR-001@1.0.1` matrix remains bound to the
withdrawn v1.4.0 publication; it is not overwritten because release truth is immutable per
product version.

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
