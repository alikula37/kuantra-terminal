"""Desktop-only local backup/preview operations. No restore/apply entry point."""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Callable

from app.services.macos_migration import (
    MAX_ARCHIVE_BYTES, MigrationBundleError, create_migration_bundle, verify_migration_bundle,
)


def _summary(report: dict, *, status: str, name: str) -> dict:
    sqlite = report.get('sqlite') or {}
    manifest = report.get('manifest') or {}
    return {
        'status': status, 'name': name, 'sha256': report.get('bundle_sha256'),
        'schema_version': sqlite.get('schema', {}).get('version'),
        'bundle_schema_version': manifest.get('schema_version'),
        'counts': sqlite.get('record_counts'),
        'files_checked': report.get('files_checked', 0),
        'restore_applied': False,
        # Diagnostic text is bounded, untrusted, and rendered only as escaped text.
        'errors': [str(error)[:500] for error in report.get('errors', [])[:20]],
    }


def preview_local_backup(bundle: str | Path) -> dict:
    """Verify a bounded disposable copy, not a moving or untrusted active source.

    The verifier extracts only in its own temporary directory. No active data directory
    is an argument, and no restore function is imported or invoked here.
    """
    path = Path(bundle)
    if not path.is_file() or path.stat().st_size > MAX_ARCHIVE_BYTES:
        return {'status': 'INVALID', 'name': path.name, 'restore_applied': False,
                'errors': ['FILE_SIZE_OR_TYPE_REJECTED']}
    with tempfile.TemporaryDirectory(prefix='kuantra-backup-preview-') as tmp:
        snapshot = Path(tmp) / 'selected.zip'
        total = 0
        with path.open('rb') as source, snapshot.open('xb') as target:
            while chunk := source.read(64 * 1024):
                total += len(chunk)
                if total > MAX_ARCHIVE_BYTES:
                    raise MigrationBundleError('selected bundle exceeds size limit')
                target.write(chunk)
        report = verify_migration_bundle(snapshot)
    status = 'VERIFIED' if report['valid'] and report['migration_ready'] else (
        'LIMITED' if report['valid'] else 'INVALID')
    return _summary(report, status=status, name=path.name)


def create_local_backup(source: str | Path, destination: str | Path,
                        *, cancel_check: Callable[[], None] | None = None) -> dict:
    report = create_migration_bundle(source, destination, force=False,
                                     require_ready=True, cancel_check=cancel_check)
    # The verified manifest describes the same staged SQLite snapshot that was saved.
    summary = _summary({
        'manifest': report['manifest'], 'bundle_sha256': report['bundle_sha256'],
        'sqlite': report['manifest']['sqlite_preflight'],
        'files_checked': len(report['manifest']['files']),
    }, status='SAVED', name=Path(destination).name)
    summary['path'] = str(Path(destination))
    return summary
