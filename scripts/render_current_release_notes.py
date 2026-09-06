"""Render only the current marker-delimited release notes section."""

from __future__ import annotations

import argparse
from pathlib import Path

from release_truth import (
    DEFAULT_MATRIX_PATH,
    DEFAULT_RELEASE_NOTES_PATH,
    extract_current_release_notes,
    load_matrix,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render current Kuantra release notes")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX_PATH)
    parser.add_argument("--source", type=Path, default=DEFAULT_RELEASE_NOTES_PATH)
    parser.add_argument("--output", type=Path, default=Path("dist/CURRENT_RELEASE_NOTES.md"))
    args = parser.parse_args(argv)

    root = args.root.resolve()
    matrix_path = args.matrix if args.matrix.is_absolute() else root / args.matrix
    source_path = args.source if args.source.is_absolute() else root / args.source
    output_path = args.output if args.output.is_absolute() else root / args.output
    body = extract_current_release_notes(source_path, load_matrix(matrix_path.resolve()))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(body.rstrip() + "\n", encoding="utf-8")
    print(f"[release-notes] rendered current section to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
