# Kuantra release truth contract

Release-facing claims are governed by the versioned matrix in
[`truth-matrix.v1.4.0.json`](truth-matrix.v1.4.0.json). The matrix is a contract, not a
marketing inventory: it records what the current product can prove, what remains disabled,
and which files are scanned before a build or GitHub Release.

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
