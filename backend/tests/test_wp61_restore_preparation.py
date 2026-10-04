"""Synthetic cold profiles; preparation never replaces active records."""
import sqlite3
from pathlib import Path
from contextlib import closing

import pytest

from app.core.profile_safety import ProfileLease, ProfileSafetyError, read_operation
from app.services.desktop_restore import RestorePreparation, fingerprint
from app.db.sqlite_driver import SQLiteDriver
from app.services.macos_migration import create_migration_bundle


@pytest.fixture
def pair(tmp_path):
    profiles = []
    for name, price, capital in [('original', 100, '5000'), ('saved', 90, '1000')]:
        root = tmp_path / name; root.mkdir()
        driver = SQLiteDriver(str(root / 'kuantra_oltp.sqlite3'))
        driver.record_trade_with_evidence(
            {'id': 'SYNTHETIC-'+name, 'symbol': 'BTCUSDT', 'side': 'BUY', 'qty': 1,
             'entry_price': price, 'qty_unit': 'BASE', 'status': 'OPEN',
             'entry_time': '2026-10-04T08:00:00Z'}, event_type='IntentRecorded',
            idempotency_key='SYNTHETIC-'+name, occurred_at='2026-10-04T08:00:00Z')
        driver.set_setting('user_initial_balance', capital)
        driver.set_setting('active_theme', 'light' if name == 'original' else 'dark')
        from app.services.local_tracking import LocalTrackingService
        from app.services.weekly_review import WeeklyReviewService
        from app.db.repositories.evidence_ledger_repo import EvidenceLedgerRepository
        LocalTrackingService(driver).edit('SYNTHETIC-'+name, {
            'enabled': True, 'source_id': 'binance_public', 'source_symbol': 'BTCUSDT',
            'targets': [{'price': 110, 'percent': 100}]}, expected_revision=0)
        reviews = WeeklyReviewService(ledger_repo=EvidenceLedgerRepository(driver.db_path))
        review = reviews.build_review(period_start='2026-10-04', period_end='2026-10-05',
                                      timezone_name='Europe/Istanbul', as_of_utc='2026-10-04T20:00:00Z')
        reviews.record_decision(review, decision='COMPLETE', note='synthetic restore review')
        profiles.append(root)
    bundle = tmp_path / 'saved.zip'; create_migration_bundle(profiles[1], bundle)
    # Driver context managers can leave connection cycles pending. A cold
    # profile models the already-exited desktop, not an unleased live writer.
    import gc
    gc.collect()
    return profiles[0], profiles[1], bundle


def test_prepare_uses_immutable_bytes_preserves_capital_ui_and_safety(pair):
    original, saved, bundle = pair
    before = fingerprint(original)
    with ProfileLease(original) as lease:
        service = RestorePreparation(original, lease)
        intent = service.select(bundle)
        source_hash = intent['source_sha256']
        bundle.write_bytes(b'changed external selection')
        result = service.prepare(intent['operation_id'])
        assert result['phase'] == 'PREPARED' and result['source_sha256'] == source_hash
        state = read_operation(original)
        candidate = service.directory(state) / 'candidate'
        with closing(sqlite3.connect(candidate / 'kuantra_oltp.sqlite3')) as c:
            settings = dict(c.execute('SELECT key,value FROM user_settings'))
            assert settings['user_initial_balance'] == '1000'
            assert settings['active_theme'] == 'light'
        assert (candidate / 'kuantra_olap.duckdb').is_file()
        safety = service.directory(state) / 'safety.sqlite3'
        assert safety.is_file() and safety.stat().st_mode & 0o077 == 0
        assert result['before_counts']['trades'] == result['after_counts']['trades'] == 1
        assert result['after_counts']['tracking_plans'] == result['after_counts']['weekly_reviews'] == 1
        assert result['recovery_location'].endswith('/original')
        assert fingerprint(original) == before


@pytest.mark.parametrize('kind', ['unknown_setting', 'unknown_file', 'symlink'])
def test_inventory_unknowns_block_without_active_changes(pair, kind):
    original, _, bundle = pair
    if kind == 'unknown_setting':
        with sqlite3.connect(original / 'kuantra_oltp.sqlite3') as c:
            c.execute("INSERT INTO user_settings(key,value,updated_at) VALUES ('mystery','unknown','now')")
    elif kind == 'unknown_file':
        (original / 'mystery.bin').write_bytes(b'unknown')
    else:
        (original / 'linked').symlink_to(bundle)
    before = (original / 'kuantra_oltp.sqlite3').read_bytes()
    with ProfileLease(original) as lease:
        service = RestorePreparation(original, lease)
        with pytest.raises(ProfileSafetyError):
            state = service.select(bundle); service.prepare(state['operation_id'])
    assert (original / 'kuantra_oltp.sqlite3').read_bytes() == before


def test_changed_staged_input_expiry_and_replay_fail_closed(pair, monkeypatch):
    original, _, bundle = pair
    with ProfileLease(original) as lease:
        service = RestorePreparation(original, lease)
        state = service.select(bundle)
        selected = service.directory(state) / 'selected.zip'
        selected.chmod(0o600); selected.write_bytes(b'changed immutable input')
        with pytest.raises(ProfileSafetyError):
            service.prepare(state['operation_id'])
        service.cancel(state['operation_id'])
        with pytest.raises(ProfileSafetyError):
            service.prepare(state['operation_id'])
        state = service.select(bundle)
        monkeypatch.setattr('app.services.desktop_restore.time.time', lambda: state['expires_at'] + 1)
        with pytest.raises(ProfileSafetyError, match='EXPIRED'):
            service.prepare(state['operation_id'])


def test_candidate_or_target_change_invalidates_confirmation(pair):
    original, _, bundle = pair
    with ProfileLease(original) as lease:
        service = RestorePreparation(original, lease)
        state = service.select(bundle); state = service.prepare(state['operation_id'])
        assert service.validate_prepared(state['operation_id'], state['confirmation'])['phase'] == 'PREPARED'
        (original / 'logs').mkdir(); (original / 'logs' / 'external.log').write_text('external change')
        with pytest.raises(ProfileSafetyError, match='CHANGED'):
            service.validate_prepared(state['operation_id'], state['confirmation'])


def test_invalid_archive_and_disk_failure_leave_original_intact(pair, monkeypatch):
    original, _, bundle = pair
    with ProfileLease(original) as lease:
        service = RestorePreparation(original, lease)
        state = service.select(bundle)
        import app.services.desktop_restore as module
        monkeypatch.setattr(module.shutil, 'disk_usage', lambda _: type('Usage', (), {'free': 0})())
        with pytest.raises(ProfileSafetyError, match='DISK'):
            service.prepare(state['operation_id'])
        assert original.is_dir()
        assert read_operation(original)['phase'] == 'FAILED'


def test_reject_without_owned_profile_lease(pair):
    original, _, _ = pair
    with pytest.raises(ProfileSafetyError, match='LEASE'):
        RestorePreparation(original, ProfileLease(original))


@pytest.mark.parametrize('kind', ['invalid_zip', 'duplicate', 'symlink_source'])
def test_unsafe_selection_or_archive_rejected_before_target_move(pair, kind, tmp_path):
    import zipfile
    original, _, bundle = pair
    if kind == 'invalid_zip':
        bundle.write_bytes(b'not a ZIP')
    elif kind == 'duplicate':
        with zipfile.ZipFile(bundle, 'a') as archive:
            archive.writestr('manifest.json', '{}')
    else:
        link = tmp_path / 'link.zip'; link.symlink_to(bundle); bundle = link
    before = fingerprint(original)
    with ProfileLease(original) as lease:
        service = RestorePreparation(original, lease)
        with pytest.raises((ProfileSafetyError, OSError)):
            state = service.select(bundle); service.prepare(state['operation_id'])
    assert fingerprint(original) == before


def test_staged_candidate_change_and_invalid_token_never_accept(pair):
    original, _, bundle = pair
    with ProfileLease(original) as lease:
        service = RestorePreparation(original, lease)
        state = service.select(bundle); state = service.prepare(state['operation_id'])
        before = fingerprint(original)
        for token in [None, '', 'f'*64, 'x'*10000]:
            with pytest.raises(ProfileSafetyError, match='CONFIRMATION'):
                service.validate_prepared(state['operation_id'], token)
        candidate = service.directory(state) / 'candidate'
        (candidate / 'extra').write_text('external interference')
        with pytest.raises(ProfileSafetyError, match='CHANGED'):
            service.validate_prepared(state['operation_id'], state['confirmation'])
        service.cancel(state['operation_id'])
        assert fingerprint(original) == before


def test_quiesced_hot_wal_is_copied_without_opening_original(pair):
    import os
    import subprocess
    import sys
    original, _, bundle = pair
    code = ('import sqlite3,os; c=sqlite3.connect(os.environ["SYNTHETIC_DB"]); '
            'c.execute("PRAGMA journal_mode=WAL"); '
            'c.execute("INSERT OR REPLACE INTO user_settings(key,value,updated_at) VALUES '
            '(\'paper_balance\',\'1234\',\'synthetic\')"); c.commit(); os._exit(0)')
    subprocess.run([sys.executable, '-c', code], env=dict(os.environ, SYNTHETIC_DB=str(original / 'kuantra_oltp.sqlite3')), check=True, timeout=10)
    assert (original / 'kuantra_oltp.sqlite3-wal').is_file()
    before = fingerprint(original)
    with ProfileLease(original) as lease:
        service = RestorePreparation(original, lease)
        state = service.select(bundle); state = service.prepare(state['operation_id'])
        with closing(sqlite3.connect(service.directory(state) / 'safety.sqlite3')) as c:
            assert c.execute("SELECT value FROM user_settings WHERE key='paper_balance'").fetchone()[0] == '1234'
        assert fingerprint(original) == before


def test_fresh_maintenance_process_initializes_only_private_validation(pair):
    import os
    import subprocess
    import sys
    original, _, bundle = pair
    with ProfileLease(original) as lease:
        service = RestorePreparation(original, lease)
        state = service.select(bundle)
    before = fingerprint(original)
    code = ('import sys; '
            'sys.addaudithook(lambda event,args: (_ for _ in ()).throw(RuntimeError("network denied")) '
            'if event in {"socket.connect", "socket.getaddrinfo"} else None); '
            'from desktop.restore_maintenance import main; '
            'raise SystemExit(main(["--restore-maintenance", "--restore-prepare", sys.argv[1]]))')
    result = subprocess.run([sys.executable, '-c', code, state['operation_id']],
                            env=dict(os.environ, KUANTRA_DATA_DIR=str(original),
                                     PYTHONPATH=str(Path(__file__).parents[1])),
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'PREPARED' in result.stdout
    assert 'Backend runtime started' not in result.stdout
    assert not (original / 'logs').exists()
    assert fingerprint(original) == before


def test_valid_but_unclassified_bundle_content_never_enters_candidate(pair):
    import hashlib
    import json
    import zipfile
    original, _, bundle = pair
    with zipfile.ZipFile(bundle) as archive:
        members = {name: archive.read(name) for name in archive.namelist()}
    manifest = json.loads(members['manifest.json'])
    name = 'data/.env'; payload = b'UNCLASSIFIED=synthetic'
    manifest['files'].append({'path': name, 'size_bytes': len(payload), 'sha256': hashlib.sha256(payload).hexdigest()})
    members[name] = payload; members['manifest.json'] = json.dumps(manifest).encode()
    with zipfile.ZipFile(bundle, 'w') as archive:
        for name, data in members.items():
            archive.writestr(name, data)
    before = fingerprint(original)
    with ProfileLease(original) as lease:
        service = RestorePreparation(original, lease); state = service.select(bundle)
        with pytest.raises(ProfileSafetyError, match='CONTENT_POLICY'):
            service.prepare(state['operation_id'])
    assert fingerprint(original) == before


def test_machine_credential_references_stay_only_in_private_recovery_material(pair):
    import gc
    original, _, bundle = pair
    with closing(sqlite3.connect(original / 'kuantra_oltp.sqlite3')) as connection:
        connection.execute("INSERT INTO exchange_credential_refs(exchange_id,name,api_key_ref,api_secret_ref,created_at,updated_at) VALUES ('synthetic','synthetic','test-key-ref','test-secret-ref','now','now')")
        connection.commit()
    gc.collect()
    before = fingerprint(original)
    with ProfileLease(original) as lease:
        service = RestorePreparation(original, lease)
        state = service.select(bundle); state = service.prepare(state['operation_id'])
        root = service.directory(state)
        with closing(sqlite3.connect(root / 'candidate' / 'kuantra_oltp.sqlite3')) as connection:
            assert connection.execute('SELECT count(*) FROM exchange_credential_refs').fetchone()[0] == 0
        with closing(sqlite3.connect(root / 'safety.sqlite3')) as connection:
            assert connection.execute('SELECT count(*) FROM exchange_credential_refs').fetchone()[0] == 1
        assert fingerprint(original) == before


@pytest.mark.parametrize('kind', ['future', 'legacy', 'chain', 'projection'])
def test_schema_chain_and_projection_rejections_reach_preparation(pair, tmp_path, kind):
    original, saved, _ = pair
    with closing(sqlite3.connect(saved / 'kuantra_oltp.sqlite3')) as connection:
        if kind == 'future':
            connection.execute('PRAGMA user_version=999')
        elif kind == 'legacy':
            connection.execute('DROP TABLE evidence_trade_projections')
            connection.execute('PRAGMA user_version=2')
        elif kind == 'chain':
            connection.execute('DROP TRIGGER evidence_events_no_update')
            connection.execute("UPDATE evidence_events SET normalized_payload_json='{}' WHERE chain_sequence=1")
        else:
            connection.execute("UPDATE evidence_trade_projections SET entry_price=9999")
        connection.commit()
    bundle = tmp_path / ('unsupported-'+kind+'.zip')
    create_migration_bundle(saved, bundle)
    before = fingerprint(original)
    with ProfileLease(original) as lease:
        service = RestorePreparation(original, lease); state = service.select(bundle)
        with pytest.raises(ProfileSafetyError):
            service.prepare(state['operation_id'])
    assert fingerprint(original) == before


def test_current_webview_preferences_are_preserved_not_taken_from_zip(pair):
    original, _, bundle = pair
    browser = original / 'webview'; browser.mkdir()
    (browser / 'synthetic-preferences').write_text('current TR/light/LITE')
    with ProfileLease(original) as lease:
        service = RestorePreparation(original, lease); state = service.select(bundle)
        state = service.prepare(state['operation_id'])
        candidate = service.directory(state) / 'candidate'
        assert (candidate / 'webview' / 'synthetic-preferences').read_text() == 'current TR/light/LITE'


def test_hydration_failure_never_produces_prepared_or_empty_success(pair, monkeypatch):
    from app.services import macos_migration
    original, _, bundle = pair
    def fail(_):
        raise ProfileSafetyError('synthetic hydration failure')
    monkeypatch.setattr(macos_migration, 'rebuild_duckdb_projection', fail)
    before = fingerprint(original)
    with ProfileLease(original) as lease:
        service = RestorePreparation(original, lease); state = service.select(bundle)
        with pytest.raises(ProfileSafetyError, match='hydration'):
            service.prepare(state['operation_id'])
        assert read_operation(original)['phase'] == 'FAILED'
    assert fingerprint(original) == before
