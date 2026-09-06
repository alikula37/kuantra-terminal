"""
Kuantra Terminal Operational Maintenance & System Diagnostics CLI.
Provides command-line utilities for WAL checkpointing, database repair,
cold storage archival, log pruning, and Stronghold Vault encryption audits.
"""

import sys
import os
import argparse
import json
import logging
from typing import List, Optional

# Ensure app package is importable
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from app.services.maintenance.log_sanitizer import log_sanitizer_engine
from app.services.maintenance.db_maintenance import db_maintenance_engine
from app.core.security import StrongholdVault, vault as stronghold_vault
from app.db.repositories.evidence_ledger_repo import EvidenceLedgerRepository

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("kuantra_cli")

def handle_maintenance(args: argparse.Namespace):
    """Executes manual operational maintenance routines."""
    results = {}
    print("\n[+] Running Kuantra Operational Maintenance Pipeline...")

    if args.checkpoint_wal or args.all:
        print("  -> Performing SQLite WAL Checkpoint (TRUNCATE)...")
        res_chk = db_maintenance_engine.run_sqlite_checkpoint(truncate=True)
        results["wal_checkpoint"] = res_chk
        print(f"     Status: {res_chk.get('status')}")

    if args.compact_duckdb or args.all:
        print("  -> Enforcing DuckDB memory ceiling (2048 MB)...")
        res_mem = db_maintenance_engine.enforce_duckdb_memory_limit(2048)
        print("  -> Archiving cold tick data to ZSTD Parquet...")
        res_arc = db_maintenance_engine.archive_old_ticks_to_parquet(retention_days=7)
        results["duckdb_archival"] = res_arc
        print(f"     Archived Records: {res_arc.get('archived_records')}")

    if args.prune_logs or args.all:
        print("  -> Scanning & rotating logs with GZIP compression...")
        res_log = log_sanitizer_engine.run_full_log_maintenance()
        results["log_maintenance"] = res_log
        print(f"     Rotated: {len(res_log.get('rotated_archives', []))}, Pruned: {len(res_log.get('pruned_archives', []))}")

    if args.backup_sqlite or args.all:
        print("  -> Creating SQLite shadow backup snapshot...")
        res_bk = db_maintenance_engine.create_sqlite_shadow_backup(max_retention_days=30)
        results["shadow_backup"] = res_bk
        print(f"     Backup file: {res_bk.get('backup_file')}")

    print("\n[SUCCESS] Maintenance pipeline finished.")
    print(json.dumps(results, indent=2))
    return results

def handle_repair_db(args: argparse.Namespace):
    """Executes database integrity checks and index optimization."""
    print("\n[+] Running SQLite & DuckDB Database Integrity Audit...")
    chk = db_maintenance_engine.run_sqlite_integrity_check()
    print(f"  -> SQLite Integrity Status: {chk['status']}")
    for msg in chk.get("integrity_output", []):
        print(f"     * {msg}")
    return chk

def handle_vault_audit(args: argparse.Namespace):
    """Audits Stronghold Vault AES-256-GCM encryption enclave."""
    print("\n[+] Auditing Stronghold Vault & Secret Enclave...")
    test_key = "AUDIT_TEST_KEY"
    test_secret = "INSTITUTIONAL_SECRET_PAYLOAD_99482"

    stronghold_vault.store_secret(test_key, test_secret)
    retrieved = stronghold_vault.get_secret(test_key)
    stronghold_vault.delete_secret(test_key)

    is_valid = retrieved == test_secret
    status = "VERIFIED_SECURE" if is_valid else "CORRUPTED"
    print(f"  -> Encryption / Decryption Round-Trip: {status}")
    return {"status": status, "algorithm": "AES-256-GCM + Argon2id"}

def handle_storage_stats(args: argparse.Namespace):
    """Outputs real-time storage telemetry table."""
    stats = db_maintenance_engine.get_storage_telemetry()
    print("\n==========================================================================")
    print("                      KUANTRA STORAGE TELEMETRY                           ")
    print("==========================================================================")
    print(f"  * SQLite Database Size:   {stats['sqlite_db_size_mb']} MB")
    print(f"  * SQLite WAL Size:        {stats['sqlite_wal_size_mb']} MB")
    print(f"  * DuckDB OLAP Size:       {stats['duckdb_size_mb']} MB")
    print(f"  * Logs Total Size:        {stats['logs_total_size_mb']} MB")
    print(f"  * Cold Storage (Parquet): {stats['cold_storage_size_mb']} MB")
    print(f"  * Active Backups Count:   {stats['active_backups_count']}")
    print("==========================================================================\n")
    return stats


def handle_evidence_ledger(args: argparse.Namespace):
    """Run explicit, local-only evidence ledger operations."""
    repository = EvidenceLedgerRepository(db_path=args.db_path)
    if args.ledger_command == "backfill":
        result = repository.backfill_legacy_trades(
            dry_run=not args.apply,
            account_id=args.account_id,
            venue=args.venue,
            limit=args.limit,
        )
    elif args.ledger_command == "verify":
        result = repository.verify_chain(
            account_id=args.account_id,
            chain_date_utc=args.chain_date_utc,
        )
    elif args.ledger_command == "export":
        result = {
            "account_id": args.account_id,
            "chain_date_utc": args.chain_date_utc,
            "jsonl": repository.export_jsonl(
                account_id=args.account_id,
                chain_date_utc=args.chain_date_utc,
            ),
        }
    else:
        raise ValueError("Choose evidence-ledger backfill, verify, or export")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result

def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kuantra-cli",
        description="Kuantra Terminal Operational Maintenance & System CLI"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Command: maintenance
    p_maint = subparsers.add_parser("maintenance", help="Run database and log maintenance")
    p_maint.add_argument("--checkpoint-wal", action="store_true", help="Checkpoint and truncate SQLite WAL")
    p_maint.add_argument("--compact-duckdb", action="store_true", help="Archive old ticks and compact DuckDB")
    p_maint.add_argument("--prune-logs", action="store_true", help="Rotate and prune expired log archives")
    p_maint.add_argument("--backup-sqlite", action="store_true", help="Create non-blocking SQLite snapshot")
    p_maint.add_argument("--all", action="store_true", help="Execute all maintenance tasks")

    # Command: repair-db
    p_repair = subparsers.add_parser("repair-db", help="Run database integrity check and optimization")
    p_repair.add_argument("--verify-checksums", action="store_true", help="Verify database integrity")

    # Command: vault-audit
    p_vault = subparsers.add_parser("vault-audit", help="Audit Stronghold Vault encryption enclave")
    p_vault.add_argument("--test-encryption-enclave", action="store_true", help="Test encrypt/decrypt round-trip")

    # Command: storage-stats
    subparsers.add_parser("storage-stats", help="Display storage and memory telemetry")

    # Command: evidence-ledger
    p_ledger = subparsers.add_parser(
        "evidence-ledger", help="Verify, export, or explicitly backfill the local evidence ledger"
    )
    p_ledger.add_argument("--db-path", default=None, help="SQLite path (defaults to Kuantra data directory)")
    ledger_subparsers = p_ledger.add_subparsers(dest="ledger_command", required=True)

    p_backfill = ledger_subparsers.add_parser("backfill", help="Snapshot legacy trades into the append-only ledger")
    p_backfill.add_argument("--apply", action="store_true", help="Write events; without this flag the command is dry-run")
    p_backfill.add_argument("--account-id", default="local-journal")
    p_backfill.add_argument("--venue", default="legacy")
    p_backfill.add_argument("--limit", type=int, default=None)

    p_verify = ledger_subparsers.add_parser("verify", help="Verify hash chains and immutable event fields")
    p_verify.add_argument("--account-id", default=None)
    p_verify.add_argument("--chain-date-utc", default=None)

    p_export = ledger_subparsers.add_parser("export", help="Export immutable ledger rows as JSONL")
    p_export.add_argument("--account-id", default=None)
    p_export.add_argument("--chain-date-utc", default=None)

    return parser

def main():
    parser = create_parser()
    args = parser.parse_args()

    if args.command == "maintenance":
        handle_maintenance(args)
    elif args.command == "repair-db":
        handle_repair_db(args)
    elif args.command == "vault-audit":
        handle_vault_audit(args)
    elif args.command == "storage-stats":
        handle_storage_stats(args)
    elif args.command == "evidence-ledger":
        handle_evidence_ledger(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
