"""Synthetic process boundaries; never the installed profile."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.core.profile_safety import (
    ProfileLease, ProfileSafetyError, assert_boot_allowed, workspace_for,
    read_operation, write_operation,
)


def child(code, profile):
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).parents[1]),
               KUANTRA_DATA_DIR=str(profile))
    return subprocess.run([sys.executable, '-c', code], env=env,
                          capture_output=True, text=True, timeout=10)


def test_lease_is_os_owned_outside_profile_and_released(tmp_path):
    profile = tmp_path / 'synthetic'
    with ProfileLease(profile):
        assert not profile.exists()
        result = child('from app.core.profile_safety import ProfileLease; '
                       'import os; ProfileLease(os.environ["KUANTRA_DATA_DIR"]).acquire()', profile)
        assert result.returncode != 0 and 'PROFILE_BUSY' in result.stderr
        assert workspace_for(profile).parent == profile.parent.resolve()
    assert child('from app.core.profile_safety import ProfileLease; '
                 'import os; ProfileLease(os.environ["KUANTRA_DATA_DIR"]).acquire()', profile).returncode == 0


@pytest.mark.parametrize('state', ['PREPARING', 'PREPARED', 'MOVING_ORIGINAL', 'PROMOTING', 'RECOVERY_REQUIRED'])
def test_pending_state_blocks_import_before_empty_data_dir(tmp_path, state):
    profile = tmp_path / 'synthetic'
    write_operation(profile, {'version': 1, 'operation_id': 'a'*32, 'phase': state})
    result = child('import app.core.paths', profile)
    assert result.returncode != 0 and 'RECOVERY_REQUIRED' in result.stderr
    assert not profile.exists()


def test_corrupt_operation_blocks_boot_without_repair_or_profile_creation(tmp_path):
    profile = tmp_path / 'synthetic'
    root = workspace_for(profile); root.mkdir(mode=0o700)
    path = root / 'operation.json'; path.write_text('{broken')
    with pytest.raises(ProfileSafetyError, match='RECOVERY_REQUIRED'):
        assert_boot_allowed(profile)
    assert path.read_text() == '{broken' and not profile.exists()


def test_unrecognized_or_oversized_state_and_symlink_are_rejected(tmp_path):
    profile = tmp_path / 'synthetic'
    root = workspace_for(profile); root.mkdir(mode=0o700)
    path = root / 'operation.json'
    for value in [json.dumps({'version': 999, 'phase': 'APPLIED_AWAITING_REVIEW', 'operation_id': 'a'*32}), ' '*65537]:
        path.write_text(value)
        with pytest.raises(ProfileSafetyError):
            read_operation(profile)
    path.unlink(); path.symlink_to(tmp_path / 'outside')
    with pytest.raises(ProfileSafetyError):
        read_operation(profile)


def test_applied_requires_explicit_review_even_with_existing_target(tmp_path):
    profile = tmp_path / 'synthetic'
    write_operation(profile, {'version': 1, 'operation_id': 'b'*32, 'phase': 'APPLIED_AWAITING_REVIEW'})
    with pytest.raises(ProfileSafetyError):
        assert_boot_allowed(profile)
    profile.mkdir()
    with pytest.raises(ProfileSafetyError):
        assert_boot_allowed(profile)
    write_operation(profile, {'version': 1, 'operation_id': 'b'*32, 'phase': 'REVIEWED'})
    assert_boot_allowed(profile)
    assert (workspace_for(profile).stat().st_mode & 0o077) == 0


def test_maintenance_dispatch_never_imports_runtime_or_creates_profile(tmp_path):
    profile = tmp_path / 'synthetic'
    env = dict(os.environ, KUANTRA_DATA_DIR=str(profile))
    result = subprocess.run([sys.executable, str(Path(__file__).parents[1] / 'desktop_main.py'),
                             '--restore-maintenance', '--restore-status'], env=env,
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['phase'] == 'NONE'
    assert not profile.exists()


def test_spawned_owned_worker_retains_lease_after_parent_releases(tmp_path):
    from concurrent.futures import ProcessPoolExecutor
    import multiprocessing
    from multiprocessing.reduction import DupFd
    from desktop.bridge import _extend_profile_lease
    profile = tmp_path / 'synthetic-worker'
    lease = ProfileLease(profile).acquire()
    try:
        with ProcessPoolExecutor(max_workers=1, mp_context=multiprocessing.get_context('spawn'),
                                 initializer=_extend_profile_lease, initargs=(DupFd(lease.fd),)) as pool:
            assert pool.submit(os.getpid).result(timeout=10) != os.getpid()
            lease.close()
            with pytest.raises(ProfileSafetyError, match='PROFILE_BUSY'):
                ProfileLease(profile).acquire()
        with ProfileLease(profile):
            pass
    finally:
        lease.close()


def test_state_fsync_failure_keeps_previous_journal(tmp_path, monkeypatch):
    from app.core import profile_safety
    profile = tmp_path / 'synthetic'
    state = {'version': 1, 'operation_id': 'b'*32, 'phase': 'CANCELLED'}
    write_operation(profile, state)
    def fail(_):
        raise OSError('synthetic fsync failure')
    monkeypatch.setattr(profile_safety.os, 'fsync', fail)
    with pytest.raises(OSError):
        write_operation(profile, dict(state, phase='PREPARING'))
    assert read_operation(profile) == state
    assert not list(workspace_for(profile).glob('.state-*'))


@pytest.mark.parametrize('module', ['main', 'app.cli'])
def test_console_and_asgi_imports_claim_before_db_singletons(tmp_path, module):
    profile = tmp_path / 'synthetic-console'
    with ProfileLease(profile):
        result = child('import '+module, profile)
        assert result.returncode != 0 and 'PROFILE_BUSY' in result.stderr
        assert not profile.exists()
