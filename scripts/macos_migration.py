"""Create, verify and restore a safe Kuantra-to-macOS migration bundle.

Examples:
    python scripts/macos_migration.py create \
        --source-data-dir "$HOME/Library/Application Support/Kuantra Terminal" \
        --output ./kuantra-macos-migration.zip
    python scripts/macos_migration.py verify --bundle ./kuantra-macos-migration.zip
    python scripts/macos_migration.py restore --bundle ./kuantra-macos-migration.zip \
        --target-data-dir "$HOME/Library/Application Support/Kuantra Terminal"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.macos_migration import (  # noqa: E402
    MigrationBundleError,
    create_migration_bundle,
    restore_migration_bundle,
    rebuild_duckdb_projection,
    upgrade_sqlite_schema,
    verify_migration_bundle,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Kuantra macOS migration bundles")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create", help="create a credential-safe migration bundle")
    create.add_argument("--source-data-dir", type=Path, required=True)
    create.add_argument("--output", type=Path, required=True)
    create.add_argument("--force", action="store_true", help="replace an existing output bundle")
    create.add_argument("--json", action="store_true", dest="as_json")

    verify = subparsers.add_parser("verify", help="verify hashes, SQLite integrity and archive safety")
    verify.add_argument("--bundle", type=Path, required=True)
    verify.add_argument("--json", action="store_true", dest="as_json")

    restore = subparsers.add_parser("restore", help="restore into an empty data directory")
    restore.add_argument("--bundle", type=Path, required=True)
    restore.add_argument("--target-data-dir", type=Path, required=True)
    restore.add_argument("--force", action="store_true", help="move a non-empty target aside first")
    restore.add_argument("--json", action="store_true", dest="as_json")

    rebuild = subparsers.add_parser(
        "rebuild-projection",
        help="rebuild DuckDB from the restored canonical SQLite ledger",
    )
    rebuild.add_argument("--data-dir", type=Path, required=True)
    rebuild.add_argument("--json", action="store_true", dest="as_json")

    upgrade = subparsers.add_parser(
        "upgrade-schema",
        help="upgrade a supported legacy SQLite file through an atomic staged swap",
    )
    upgrade.add_argument("--db-path", type=Path, required=True)
    upgrade.add_argument("--json", action="store_true", dest="as_json")
    return parser


def _print_result(result: dict, *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, indent=2, sort_keys=True))
        return
    if "manifest" in result and result.get("bundle_path"):
        manifest = result["manifest"]
        print(
            f"[macos-migration] created={result['bundle_path']} "
            f"files={len(manifest.get('files', []))} "
            f"migration_ready={result.get('migration_ready')} sha256={result['bundle_sha256']}"
        )
    elif "errors" in result:
        print(
            f"[macos-migration] valid={result['valid']} "
            f"migration_ready={result.get('migration_ready')} "
            f"files_checked={result['files_checked']} sha256={result['bundle_sha256']}"
        )
        for error in result["errors"]:
            print(f"  error={error}", file=sys.stderr)
    elif "hydration" in result:
        print(
            f"[macos-migration] rebuilt={result['duckdb_path']} "
            f"status={result['hydration'].get('status')} "
            f"trades={result['hydration'].get('recovered_trades_count', 0)}"
        )
    elif result.get("status") in {"CURRENT", "UPGRADED"}:
        print(
            f"[macos-migration] schema_status={result['status']} "
            f"changed={result.get('changed')} target={result['target']}"
        )
        if result.get("backup_path"):
            print(f"  backup={result['backup_path']} sha256={result.get('backup_sha256')}")
    else:
        print(
            f"[macos-migration] restored={result['target_data_dir']} "
            f"files={len(result['restored_files'])} "
            f"migration_ready={result.get('migration_ready')} "
            f"duckdb_rebuild_required={result['duckdb_rebuild_required']}"
        )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "create":
            result = create_migration_bundle(args.source_data_dir, args.output, force=args.force)
        elif args.command == "verify":
            result = verify_migration_bundle(args.bundle)
        elif args.command == "restore":
            result = restore_migration_bundle(args.bundle, args.target_data_dir, force=args.force)
        elif args.command == "upgrade-schema":
            result = upgrade_sqlite_schema(args.db_path)
        else:
            result = rebuild_duckdb_projection(args.data_dir)
        _print_result(result, as_json=args.as_json)
        return 0 if result.get("valid") is True else 1
    except (OSError, MigrationBundleError, ValueError) as exc:
        print(f"[macos-migration] FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
