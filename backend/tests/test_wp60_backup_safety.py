"""All backup fixtures are isolated synthetic data, never the installed journal."""
import sqlite3
import zipfile
from pathlib import Path

import pytest
from app.db.sqlite_driver import SQLiteDriver
from app.services import macos_migration as migration
from app.services.local_tracking import LocalTrackingService
from app.services.weekly_review import WeeklyReviewService
from app.db.repositories.evidence_ledger_repo import EvidenceLedgerRepository


def source_rows(db):
    # Byte equality across a live WAL connection is not logical immutability: an
    # unrelated connection's checkpoint may rewrite the file without changing rows.
    with sqlite3.connect(Path(db).resolve().as_uri() + '?mode=ro', uri=True) as conn:
        return {t: conn.execute('SELECT * FROM '+t+' ORDER BY rowid').fetchall()
                for t in ['trades', 'evidence_events', 'local_tracking_projections',
                          'user_settings', 'exchange_credentials', 'exchange_credential_refs']}


@pytest.fixture
def source(tmp_path):
    root = tmp_path / 'synthetic'; root.mkdir()
    driver = SQLiteDriver(str(root / 'kuantra_oltp.sqlite3'))
    driver.record_trade_with_evidence(
        {'id': 'synthetic-wp60', 'symbol': 'BTCUSDT', 'side': 'BUY', 'qty': 2,
         'entry_price': 100, 'qty_unit': 'BASE', 'status': 'OPEN',
         'entry_time': '2026-10-04T08:00:00Z'},
        event_type='IntentRecorded', idempotency_key='synthetic-wp60',
        occurred_at='2026-10-04T08:00:00Z')
    LocalTrackingService(driver).edit('synthetic-wp60', {
        'enabled': True, 'source_id': 'binance_public', 'source_symbol': 'BTCUSDT',
        'targets': [{'price': 110, 'percent': 100}]}, expected_revision=0)
    service = WeeklyReviewService(ledger_repo=EvidenceLedgerRepository(driver.db_path))
    review = service.build_review(period_start='2026-10-04', period_end='2026-10-05',
                                  timezone_name='Europe/Istanbul', as_of_utc='2026-10-04T20:00:00Z')
    service.record_decision(review, decision='COMPLETE', note='synthetic backup review')
    return root


def test_destination_created_during_backup_is_never_overwritten(source, tmp_path, monkeypatch):
    target = tmp_path / 'backup.zip'
    original = migration._snapshot_sqlite
    def intervening(*args, **kw):
        result = original(*args, **kw)
        target.write_bytes(b'OTHER USER FILE')
        return result
    monkeypatch.setattr(migration, '_snapshot_sqlite', intervening)
    with pytest.raises((FileExistsError, migration.MigrationBundleError)):
        migration.create_migration_bundle(source, target)
    assert target.read_bytes() == b'OTHER USER FILE'
    assert not list(tmp_path.glob('.backup.zip.tmp-*'))


def test_projection_metadata_uses_same_snapshot_not_later_source(source, tmp_path, monkeypatch):
    original = migration._snapshot_sqlite
    def intervening(*args, **kw):
        result = original(*args, **kw)
        with sqlite3.connect(source / 'kuantra_oltp.sqlite3') as conn:
            conn.execute('DELETE FROM evidence_trade_projections')
        return result
    monkeypatch.setattr(migration, '_snapshot_sqlite', intervening)
    result = migration.create_migration_bundle(source, tmp_path / 'backup.zip')
    assert result['migration_ready'] is True
    assert migration.verify_migration_bundle(tmp_path / 'backup.zip')['migration_ready'] is True


def test_cancel_before_publication_leaves_no_artifact(source, tmp_path):
    target = tmp_path / 'cancel.zip'
    def cancelled():
        raise migration.MigrationBundleError('operation cancelled')
    with pytest.raises(migration.MigrationBundleError, match='cancelled'):
        migration.create_migration_bundle(source, target, cancel_check=cancelled)
    assert not target.exists()
    assert not list(tmp_path.glob('.cancel.zip.tmp-*'))


def test_in_app_backup_and_preview_keep_rows_and_exclusions(source, tmp_path):
    from app.services.local_backup import create_local_backup, preview_local_backup
    db = source / 'kuantra_oltp.sqlite3'
    with sqlite3.connect(db) as conn:
        conn.execute("INSERT INTO user_settings (key,value,updated_at) VALUES ('fake_API_SECRET','synthetic-secret','now')")
    before = source_rows(db)
    target = tmp_path / 'backup.zip'
    result = create_local_backup(source, target)
    assert result['status'] == 'SAVED'
    assert result['counts'] == {'trades': 1, 'events': 3, 'tracking_plans': 1, 'weekly_reviews': 1}
    payload = target.read_bytes()
    preview = preview_local_backup(target)
    assert preview['status'] == 'VERIFIED'
    assert preview['counts'] == result['counts']
    assert preview['sha256'] == result['sha256']
    assert preview['restore_applied'] is False
    assert source_rows(db) == before and target.read_bytes() == payload
    with zipfile.ZipFile(target) as archive:
        snapshot_bytes = archive.read('data/kuantra_oltp.sqlite3')
        assert b'synthetic-secret' not in snapshot_bytes
        snapshot = tmp_path / 'verify-only.sqlite3'; snapshot.write_bytes(snapshot_bytes)
    with sqlite3.connect(db) as a, sqlite3.connect(snapshot) as b:
        for table in ['trades', 'evidence_events', 'local_tracking_projections']:
            assert a.execute('SELECT * FROM '+table+' ORDER BY rowid').fetchall() == b.execute('SELECT * FROM '+table+' ORDER BY rowid').fetchall()


def test_preview_invalid_archive_has_no_active_data_or_apply_path(tmp_path):
    from app.services.local_backup import preview_local_backup
    target = tmp_path / 'bad.zip'; target.write_bytes(b'not zip')
    before = target.read_bytes()
    result = preview_local_backup(target)
    assert result['status'] == 'INVALID'
    assert result['restore_applied'] is False
    assert target.read_bytes() == before


def test_backup_permissions_and_snapshot_wal(source, tmp_path):
    target = tmp_path / 'backup.zip'
    with sqlite3.connect(source / 'kuantra_oltp.sqlite3') as writer:
        writer.execute('PRAGMA journal_mode=WAL')
        writer.execute("INSERT INTO user_settings(key,value,updated_at) VALUES ('wp60-wal','retained','now')")
        writer.commit()
        migration.create_migration_bundle(source, target)
        with zipfile.ZipFile(target) as archive:
            snap = tmp_path / 'snapshot.sqlite'; snap.write_bytes(archive.read('data/kuantra_oltp.sqlite3'))
        with sqlite3.connect(snap) as conn:
            assert conn.execute("SELECT value FROM user_settings WHERE key='wp60-wal'").fetchone()[0] == 'retained'
    assert target.stat().st_mode & 0o077 == 0


def test_disk_failure_cleans_partial_and_keeps_source(source, tmp_path, monkeypatch):
    before = source_rows(source / 'kuantra_oltp.sqlite3')
    def fail(*args, **kwargs):
        raise OSError('synthetic disk full')
    monkeypatch.setattr(zipfile.ZipFile, 'write', fail)
    target = tmp_path / 'full.zip'
    with pytest.raises(OSError):
        migration.create_migration_bundle(source, target)
    assert not target.exists() and not list(tmp_path.glob('.full.zip.tmp-*'))
    assert source_rows(source / 'kuantra_oltp.sqlite3') == before


def test_cancel_during_archive_writes_cleans_partial(source, tmp_path, monkeypatch):
    state = {'cancelled': False}
    write = zipfile.ZipFile.write
    def intervene(*args, **kwargs):
        result = write(*args, **kwargs); state['cancelled'] = True; return result
    monkeypatch.setattr(zipfile.ZipFile, 'write', intervene)
    def check():
        if state['cancelled']:
            raise migration.MigrationBundleError('cancelled')
    target = tmp_path / 'cancel.zip'
    with pytest.raises(migration.MigrationBundleError):
        migration.create_migration_bundle(source, target, cancel_check=check)
    assert not target.exists() and not list(tmp_path.glob('.cancel.zip.tmp-*'))


def test_existing_and_symlink_destination_rejected(source, tmp_path):
    target = tmp_path / 'keep.zip'; target.write_bytes(b'KEEP')
    for path in [target, tmp_path / 'link.zip']:
        if path != target:
            path.symlink_to(target)
        with pytest.raises(migration.MigrationBundleError):
            migration.create_migration_bundle(source, path)
    assert target.read_bytes() == b'KEEP'
    with pytest.raises(migration.MigrationBundleError):
        migration.create_migration_bundle(source, source / 'wrong.zip')


def test_preview_oversized_file_rejected_before_verifier(tmp_path, monkeypatch):
    from app.services import local_backup
    monkeypatch.setattr(local_backup, 'MAX_ARCHIVE_BYTES', 2)
    monkeypatch.setattr(local_backup, 'verify_migration_bundle', lambda *_: (_ for _ in ()).throw(AssertionError('unbounded read')))
    target = tmp_path / 'big.zip'; target.write_bytes(b'big')
    assert local_backup.preview_local_backup(target)['status'] == 'INVALID'


def test_concurrent_backups_have_unique_staging_and_one_no_clobber_winner(source, tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    import threading
    barrier = threading.Barrier(2)
    original = migration._snapshot_sqlite
    def snapshot(*args, **kwargs):
        result = original(*args, **kwargs); barrier.wait(timeout=5); return result
    monkeypatch.setattr(migration, '_snapshot_sqlite', snapshot)
    target = tmp_path / 'race.zip'
    def create():
        try:
            migration.create_migration_bundle(source, target); return 'saved'
        except FileExistsError:
            return 'no-clobber'
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: create(), range(2)))
    assert sorted(results) == ['no-clobber', 'saved']
    assert migration.verify_migration_bundle(target)['valid'] is True
    assert not list(tmp_path.glob('.race.zip.tmp-*'))


def test_cold_storage_root_symlink_is_not_exported(source, tmp_path):
    outside = tmp_path / 'outside'; outside.mkdir(); (outside / 'private.parquet').write_bytes(b'outside')
    (source / 'cold_storage').symlink_to(outside, target_is_directory=True)
    with pytest.raises(migration.MigrationBundleError, match='symlink'):
        migration.create_migration_bundle(source, tmp_path / 'backup.zip')


def test_snapshot_during_pending_journal_transaction_is_coherent(source, tmp_path):
    import threading
    from concurrent.futures import ThreadPoolExecutor
    from app.services.local_backup import create_local_backup
    pending = threading.Event(); release = threading.Event()
    def hook(phase, _conn):
        if phase == 'before_commit':
            pending.set()
            assert release.wait(5)
    driver = SQLiteDriver(str(source / 'kuantra_oltp.sqlite3'), transaction_hook=hook)
    def write():
        driver.record_trade_with_evidence(
            {'id': 'concurrent-synthetic', 'symbol': 'BTCUSDT', 'qty': 1, 'entry_price': 10, 'side': 'BUY'},
            event_type='IntentRecorded', idempotency_key='concurrent-synthetic')
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(write)
        try:
            assert pending.wait(5)
            result = create_local_backup(source, tmp_path / 'during-write.zip')
            assert result['counts']['trades'] == 1 and result['counts']['events'] == 3
        finally:
            release.set()
        future.result(timeout=5)
    with sqlite3.connect(source / 'kuantra_oltp.sqlite3') as conn:
        assert conn.execute('SELECT COUNT(*) FROM trades').fetchone()[0] == 2
