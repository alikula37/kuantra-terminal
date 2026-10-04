"""Offline preparation of a fixed native profile. No promotion in this module.

All writes are private staging/operational records outside the active profile.
The caller must own its actual OS lease, not merely supply a PID/sentinel.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import sqlite3
import stat
import time
import uuid
from contextlib import closing

from app.core.profile_safety import (
    ProfileLease, ProfileSafetyError, assert_boot_allowed, private_workspace,
    read_operation, sync_directory, write_operation,
)
from app.core.input_limits import MAX_ARCHIVE_BYTES

MAX_PROFILE_BYTES = 2 * 1024**3
MAX_PROFILE_FILES = 20000
INTENT_LIFETIME_SECONDS = 900
UI_SETTINGS = frozenset({'active_theme', 'active_locale', 'first_boot_completed', 'telemetry_opt_in'})
JOURNAL_SETTINGS = frozenset({'user_initial_balance', 'initial_balance', 'paper_balance'})
INACTIVE_SETTINGS = {'ai_mode': 'disabled', 'trading_mode': 'paper'}
ROOT_FILES = frozenset({'kuantra_oltp.sqlite3', 'kuantra_oltp.sqlite3-wal', 'kuantra_oltp.sqlite3-shm',
                        'kuantra_olap.duckdb', 'kuantra_olap.duckdb.wal', 'telemetry_queue.json', '.DS_Store'})
ROOT_DIRS = frozenset({'webview', 'logs', 'cold_storage', 'backups', 'plugins', 'models'})
TABLES = frozenset({'trades', 'tags', 'trade_tags', 'user_settings', 'exchange_credentials',
                   'exchange_credential_refs', 'market_candles_cache', 'evidence_events',
                   'evidence_trade_projections', 'local_tracking_projections', 'broker_observation_log',
                   'broker_projection_state', 'playbooks', 'playbook_rules', 'playbook_versions',
                   'risk_policy_versions', 'trade_rule_checks', 'installed_plugins',
                   'verified_instruments', 'sqlite_sequence', 'alembic_version'})


def digest_file(path: Path, limit=MAX_PROFILE_BYTES) -> str:
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    result = hashlib.sha256(); total = 0
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > limit:
            raise ProfileSafetyError('FILE_LIMIT_OR_TYPE')
        while chunk := stream.read(65536):
            total += len(chunk)
            if total > limit:
                raise ProfileSafetyError('FILE_LIMIT')
            result.update(chunk)
        after = os.fstat(stream.fileno())
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ProfileSafetyError('FILE_CHANGED')
    return result.hexdigest()


def copy_private_file(source: Path, destination: Path, *, limit=MAX_PROFILE_BYTES):
    fd = os.open(source, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    out = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    total = 0
    with os.fdopen(fd, 'rb') as stream, os.fdopen(out, 'wb') as target:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ProfileSafetyError('FILE_TYPE')
        while chunk := stream.read(65536):
            total += len(chunk)
            if total > limit:
                raise ProfileSafetyError('FILE_BYTE_LIMIT')
            target.write(chunk)
        target.flush(); os.fsync(target.fileno())


def fingerprint(root: Path) -> dict:
    """Rename-stable exact content identity; rejects links/special files/budgets."""
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ProfileSafetyError('PROFILE_TYPE')
    rows = []; total = 0
    for path in root.rglob('*'):
        info = path.lstat(); relative = path.relative_to(root).as_posix()
        if stat.S_ISDIR(info.st_mode):
            rows.append([relative, 'directory'])
        elif stat.S_ISREG(info.st_mode) and info.st_nlink == 1:
            total += info.st_size
            if total > MAX_PROFILE_BYTES:
                raise ProfileSafetyError('PROFILE_BYTE_LIMIT')
            rows.append([relative, info.st_size, digest_file(path)])
        else:
            raise ProfileSafetyError('PROFILE_LINK_OR_SPECIAL_FILE')
        if len(rows) > MAX_PROFILE_FILES:
            raise ProfileSafetyError('PROFILE_FILE_LIMIT')
    info = root.stat()
    return {'device': info.st_dev, 'inode': info.st_ino, 'bytes': total,
            'sha256': hashlib.sha256(json.dumps(sorted(rows), separators=(',', ':')).encode()).hexdigest()}


def ro_connect(path: Path):
    connection = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA query_only=ON')
    return connection


def settings_inventory(db: Path) -> dict:
    from app.services.macos_migration import _is_sensitive_setting
    connection = ro_connect(db)
    try:
        tables = {r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if tables - TABLES:
            raise ProfileSafetyError('UNCLASSIFIED_TABLE')
        settings = dict(connection.execute('SELECT key,value FROM user_settings'))
        for key in settings:
            if (key not in UI_SETTINGS | JOURNAL_SETTINGS | INACTIVE_SETTINGS.keys()
                    and not re.fullmatch(r'layout_[A-Za-z0-9_-]{1,64}', key)
                    and not _is_sensitive_setting(key)):
                raise ProfileSafetyError('UNCLASSIFIED_SETTING')
        return settings
    finally:
        connection.close()


def file_inventory(profile: Path):
    for path in profile.iterdir():
        if path.is_symlink() or (path.is_file() and path.name not in ROOT_FILES) or (
                path.is_dir() and path.name not in ROOT_DIRS) or not (path.is_file() or path.is_dir()):
            raise ProfileSafetyError('UNCLASSIFIED_PROFILE_FILE')
    return fingerprint(profile)


def financial_hashes(db: Path) -> dict:
    connection = ro_connect(db)
    try:
        tables = {r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        result = {}
        for table in sorted(tables - {'user_settings', 'installed_plugins', 'verified_instruments', 'market_candles_cache',
                                     'exchange_credentials', 'exchange_credential_refs', 'sqlite_sequence', 'alembic_version'}):
            if table not in TABLES:
                raise ProfileSafetyError('UNCLASSIFIED_TABLE')
            if connection.execute('SELECT count(*) FROM "'+table+'"').fetchone()[0] > 250000:
                raise ProfileSafetyError('FINANCIAL_ROW_LIMIT')
            serial = []; size = 0
            for row in connection.execute('SELECT * FROM "' + table + '"'):
                value = dict(row); value.pop('projected_at_utc', None)
                encoded = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)
                size += len(encoded.encode())
                if len(encoded) > 1024**2 or size > 256 * 1024**2:
                    raise ProfileSafetyError('FINANCIAL_CONTENT_LIMIT')
                serial.append(encoded)
            serial.sort()
            result[table] = hashlib.sha256('\n'.join(serial).encode()).hexdigest()
        return result
    finally:
        connection.close()


def validate_financial_copy(db: Path, *, credentials_allowed=False) -> dict:
    """Only a private copy may be passed: deterministic projection check writes it."""
    from app.services import macos_migration as migration
    from app.db.repositories.evidence_projection_repo import EvidenceTradeProjectionRepository
    from app.services.local_tracking import LocalTrackingService
    before = financial_hashes(db)
    report = (migration._verify_upgrade_database(db) if credentials_allowed
              else migration._verify_sqlite_snapshot(db))
    if not report.get('valid') or report.get('schema', {}).get('status') != 'current':
        raise ProfileSafetyError('INVALID_CURRENT_SCHEMA_OR_CHAIN')
    EvidenceTradeProjectionRepository(str(db)).rebuild(dry_run=False)
    if financial_hashes(db) != before:
        raise ProfileSafetyError('PROJECTION_CONTENT_MISMATCH')
    connection = ro_connect(db)
    try:
        for row in connection.execute('SELECT * FROM local_tracking_projections'):
            state, event_id, _ = LocalTrackingService._load(connection, row['trade_id'])
            if state != json.loads(row['snapshot_json']) or event_id != row['source_event_id']:
                raise ProfileSafetyError('TRACKING_LINEAGE_MISMATCH')
            event = connection.execute('SELECT event_hash FROM evidence_events WHERE event_id=?', (event_id,)).fetchone()
            if not event or event[0] != row['source_event_hash']:
                raise ProfileSafetyError('TRACKING_EVENT_HASH_MISMATCH')
        counts = {'trades': connection.execute('SELECT count(*) FROM trades').fetchone()[0],
                  'events': connection.execute('SELECT count(*) FROM evidence_events').fetchone()[0],
                  'tracking_plans': connection.execute('SELECT count(*) FROM local_tracking_projections').fetchone()[0],
                  'weekly_reviews': sum(json.loads(r[0]).get('review_kind') == 'WEEKLY_REVIEW' for r in connection.execute(
                      "SELECT normalized_payload_json FROM evidence_events WHERE event_type='JournalReviewAdded'"))}
        return {'counts': counts, 'schema_version': report['schema']['version'], 'financial_hashes': before}
    finally:
        connection.close()


def sync_tree(root: Path):
    for path in root.rglob('*'):
        if path.is_file():
            path.chmod(0o600)
            fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        elif path.is_dir():
            path.chmod(0o700)
    for directory in sorted((p for p in root.rglob('*') if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
        sync_directory(directory)
    root.chmod(0o700); sync_directory(root)


class RestorePreparation:
    def __init__(self, profile: Path, lease: ProfileLease):
        self.profile = Path(profile).parent.resolve() / Path(profile).name
        if lease.fd is None or lease.profile.resolve() != self.profile.resolve():
            raise ProfileSafetyError('OWNED_PROFILE_LEASE_REQUIRED')
        self.lease = lease
        self.root = private_workspace(self.profile)

    def directory(self, state):
        operation = state.get('operation_id')
        if not isinstance(operation, str) or not re.fullmatch('[0-9a-f]{32}', operation):
            raise ProfileSafetyError('INVALID_OPERATION_ID')
        path = self.root / ('op-' + operation)
        if path.is_symlink():
            raise ProfileSafetyError('UNSAFE_OPERATION_DIRECTORY')
        return path

    def state(self, operation_id, phases):
        state = read_operation(self.profile)
        if not state or state['operation_id'] != operation_id or state['phase'] not in phases:
            raise ProfileSafetyError('STALE_OR_REPLAYED_OPERATION')
        if time.time() > state.get('expires_at', 0):
            raise ProfileSafetyError('OPERATION_EXPIRED')
        return state

    def select(self, source: Path) -> dict:
        assert_boot_allowed(self.profile)
        operation = uuid.uuid4().hex
        state = {'version': 1, 'operation_id': operation, 'phase': 'INTENT',
                 'expires_at': time.time() + INTENT_LIFETIME_SECONDS}
        directory = self.directory(state); directory.mkdir(mode=0o700)
        write_operation(self.profile, state)
        try:
            fd = os.open(source, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
            with os.fdopen(fd, 'rb') as stream, (directory / 'selected.zip').open('xb') as target:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_ARCHIVE_BYTES:
                    raise ProfileSafetyError('BUNDLE_LIMIT_OR_TYPE')
                total = 0
                while chunk := stream.read(65536):
                    total += len(chunk)
                    if total > MAX_ARCHIVE_BYTES:
                        raise ProfileSafetyError('BUNDLE_BYTE_LIMIT')
                    target.write(chunk)
                target.flush(); os.fsync(target.fileno())
            (directory / 'selected.zip').chmod(0o400)
            state['source_sha256'] = digest_file(directory / 'selected.zip', MAX_ARCHIVE_BYTES)
            write_operation(self.profile, state)
            return state
        except BaseException:
            state['phase'] = 'FAILED'; write_operation(self.profile, state)
            raise

    def cancel(self, operation_id):
        state = read_operation(self.profile)
        if not state or state['operation_id'] != operation_id or state['phase'] not in {'INTENT', 'PREPARING', 'PREPARED', 'FAILED'}:
            raise ProfileSafetyError('CANCELLATION_NOT_AVAILABLE')
        state['phase'] = 'CANCELLED'; state.pop('confirmation', None)
        write_operation(self.profile, state)
        return {'phase': 'CANCELLED'}

    def prepare(self, operation_id):
        state = self.state(operation_id, {'INTENT'})
        directory = self.directory(state)
        state['phase'] = 'PREPARING'; write_operation(self.profile, state)
        try:
            if digest_file(directory / 'selected.zip', MAX_ARCHIVE_BYTES) != state['source_sha256']:
                raise ProfileSafetyError('SOURCE_CHANGED')
            original = file_inventory(self.profile)
            if shutil.disk_usage(self.root).free < 4 * original['bytes'] + 3 * MAX_ARCHIVE_BYTES:
                raise ProfileSafetyError('DISK_SPACE_REQUIRED')
            # No normal runtime starts. Dependency globals, if first imported,
            # initialize only a disposable private validation scratch profile.
            scratch = directory / 'validation'; scratch.mkdir(mode=0o700)
            previous = os.environ.get('KUANTRA_DATA_DIR')
            os.environ['KUANTRA_DATA_DIR'] = str(scratch)
            try:
                from app.services import macos_migration as migration
                verification = migration.verify_migration_bundle(directory / 'selected.zip')
                if not verification.get('valid') or not verification.get('migration_ready'):
                    raise ProfileSafetyError('BUNDLE_NOT_CURRENT_OR_COMPLETE')
                for item in verification['manifest']['files']:
                    name = item['path']
                    if name != 'data/kuantra_oltp.sqlite3' and not (
                            name.startswith('data/cold_storage/') and name.endswith('.parquet')):
                        raise ProfileSafetyError('BUNDLE_CONTENT_POLICY')
                safety = directory / 'safety.sqlite3'
                # Even a mode=ro SQLite connection can update SHM read marks.
                # Quiesced DB/WAL/SHM bytes are copied first; SQLite opens ONLY
                # that private copy, never the original generation.
                raw = directory / 'current-raw'; raw.mkdir(mode=0o700)
                for name in ('kuantra_oltp.sqlite3', 'kuantra_oltp.sqlite3-wal', 'kuantra_oltp.sqlite3-shm'):
                    if (self.profile / name).exists():
                        copy_private_file(self.profile / name, raw / name)
                if file_inventory(self.profile) != original:
                    raise ProfileSafetyError('ORIGINAL_CHANGED_DURING_COPY')
                migration._copy_sqlite_snapshot(raw / 'kuantra_oltp.sqlite3', safety)
                safety.chmod(0o600)
                # Validate a second copy, leaving the recovery snapshot unchanged.
                check = directory / 'current-check.sqlite3'
                migration._copy_sqlite_snapshot(safety, check)
                before_report = validate_financial_copy(check, credentials_allowed=True)
                current_settings = settings_inventory(safety)
                candidate = directory / 'candidate'
                migration.restore_migration_bundle(directory / 'selected.zip', candidate)
                file_inventory(candidate)
                candidate_db = candidate / 'kuantra_oltp.sqlite3'
                saved_settings = settings_inventory(candidate_db)
                with closing(sqlite3.connect(candidate_db)) as connection:
                    for key in saved_settings:
                        if key in UI_SETTINGS or key.startswith('layout_'):
                            connection.execute('DELETE FROM user_settings WHERE key=?', (key,))
                    for key, value in current_settings.items():
                        if key in UI_SETTINGS or key.startswith('layout_'):
                            connection.execute('INSERT OR REPLACE INTO user_settings(key,value,updated_at) VALUES (?,?,?)', (key, value, 'restore-machine-policy'))
                    for key, value in INACTIVE_SETTINGS.items():
                        connection.execute('INSERT OR REPLACE INTO user_settings(key,value,updated_at) VALUES (?,?,?)', (key, value, 'restore-inactive-policy'))
                    for table in ('installed_plugins', 'verified_instruments'):
                        if connection.execute("SELECT 1 FROM sqlite_master WHERE name=? AND type='table'", (table,)).fetchone():
                            connection.execute('DELETE FROM '+table)
                    connection.commit()
                after_report = validate_financial_copy(candidate_db)
                migration.rebuild_duckdb_projection(candidate)
                if financial_hashes(candidate_db) != after_report['financial_hashes']:
                    raise ProfileSafetyError('HYDRATION_CHANGED_HISTORY')
                # Browser preferences are current machine-local data, never ZIP data.
                if (self.profile / 'webview').exists():
                    shutil.copytree(self.profile / 'webview', candidate / 'webview')
                sync_tree(candidate)
            finally:
                if previous is None:
                    os.environ.pop('KUANTRA_DATA_DIR', None)
                else:
                    os.environ['KUANTRA_DATA_DIR'] = previous
            if file_inventory(self.profile) != original:
                raise ProfileSafetyError('ORIGINAL_CHANGED_DURING_PREPARATION')
            if digest_file(directory / 'selected.zip', MAX_ARCHIVE_BYTES) != state['source_sha256']:
                raise ProfileSafetyError('SOURCE_CHANGED')
            state.update(phase='PREPARED', original_fingerprint=original,
                         candidate_fingerprint=fingerprint(candidate), safety_sha256=digest_file(safety),
                         before_counts=before_report['counts'], after_counts=after_report['counts'],
                         schema_version=after_report['schema_version'], financial_hashes=after_report['financial_hashes'],
                         confirmation=secrets.token_hex(32), recovery_location=str(directory / 'original'))
            write_operation(self.profile, state)
            return state
        except BaseException:
            state['phase'] = 'FAILED'; state.pop('confirmation', None)
            write_operation(self.profile, state)
            raise

    def validate_prepared(self, operation_id, confirmation):
        state = self.state(operation_id, {'PREPARED'})
        if not isinstance(confirmation, str) or not re.fullmatch('[0-9a-f]{64}', confirmation) or not secrets.compare_digest(confirmation, state['confirmation']):
            raise ProfileSafetyError('INVALID_CONFIRMATION')
        directory = self.directory(state)
        if (digest_file(directory / 'selected.zip', MAX_ARCHIVE_BYTES) != state['source_sha256']
                or digest_file(directory / 'safety.sqlite3') != state['safety_sha256']
                or fingerprint(self.profile) != state['original_fingerprint']
                or fingerprint(directory / 'candidate') != state['candidate_fingerprint']):
            raise ProfileSafetyError('PREPARED_GENERATION_CHANGED')
        return state
