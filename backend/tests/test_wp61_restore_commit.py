"""Only disposable synthetic generations; actual subprocess interruption."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from backend.tests.test_wp61_restore_preparation import pair
from app.core.profile_safety import ProfileLease, ProfileSafetyError, read_operation, assert_boot_allowed
from app.services.desktop_restore import RestorePreparation, fingerprint
from app.services.desktop_restore_commit import RestoreCommit


def prepared(pair):
    original, _, bundle = pair
    with ProfileLease(original) as lease:
        service = RestorePreparation(original, lease)
        state = service.select(bundle)
        return original, service.prepare(state['operation_id'])


def test_commit_retains_original_and_requires_review(pair):
    profile, state = prepared(pair)
    with ProfileLease(profile) as lease:
        service = RestoreCommit(profile, lease)
        result = service.commit(state['operation_id'], state['confirmation'])
        assert result['phase'] == 'APPLIED_AWAITING_REVIEW'
        assert fingerprint(profile) == state['candidate_fingerprint']
        assert fingerprint(Path(state['recovery_location'])) == state['original_fingerprint']
        with pytest.raises(ProfileSafetyError):
            assert_boot_allowed(profile)
        with pytest.raises(ProfileSafetyError):
            service.commit(state['operation_id'], state['confirmation'])
        result = service.review(state['operation_id'])
        assert result['phase'] == 'REVIEWED' and result['connectors_fenced'] is True
        assert result['resumed_at_utc']
        assert_boot_allowed(profile)


@pytest.mark.parametrize('point', ['before_MOVING_ORIGINAL', 'MOVING_ORIGINAL', 'original_renamed',
                                   'before_ORIGINAL_MOVED', 'ORIGINAL_MOVED', 'before_PROMOTING',
                                   'PROMOTING', 'candidate_renamed', 'before_VERIFYING', 'VERIFYING',
                                   'before_APPLIED_AWAITING_REVIEW', 'APPLIED_AWAITING_REVIEW'])
def test_process_crash_and_repeat_recovery_never_mix_generations(pair, point):
    profile, state = prepared(pair)
    code = '''import os,sys
from pathlib import Path
from app.core.profile_safety import ProfileLease
from app.services.desktop_restore_commit import RestoreCommit
with ProfileLease(Path(sys.argv[1])) as lease:
    service=RestoreCommit(Path(sys.argv[1]),lease,checkpoint=lambda p: os._exit(73) if p==sys.argv[4] else None)
    service.commit(sys.argv[2],sys.argv[3])
'''
    result = subprocess.run([sys.executable, '-c', code, str(profile), state['operation_id'],
                             state['confirmation'], point],
                            env=dict(os.environ, PYTHONPATH=str(Path(__file__).parents[1])), timeout=30)
    assert result.returncode == 73
    with ProfileLease(profile) as lease:
        service = RestoreCommit(profile, lease)
        result = service.recover()
        assert result['phase'] in {'PREPARED', 'ROLLED_BACK', 'APPLIED_AWAITING_REVIEW'}
        assert fingerprint(profile) in [state['original_fingerprint'], state['candidate_fingerprint']]
        assert service.recover()['phase'] == result['phase']


def test_promotion_failure_rolls_back_and_preserves_candidate(pair, monkeypatch):
    profile, state = prepared(pair)
    import app.services.desktop_restore_commit as module
    rename = module.rename_exclusive
    def fail_candidate(source, destination):
        if source.name == 'candidate':
            raise OSError('synthetic disk full')
        rename(source, destination)
    monkeypatch.setattr(module, 'rename_exclusive', fail_candidate)
    with ProfileLease(profile) as lease:
        result = RestoreCommit(profile, lease).commit(state['operation_id'], state['confirmation'])
    assert result['phase'] == 'ROLLED_BACK'
    assert fingerprint(profile) == state['original_fingerprint']


@pytest.mark.parametrize('point', ['before_ROLLING_BACK', 'ROLLING_BACK', 'original_restored',
                                  'before_ROLLED_BACK', 'ROLLED_BACK'])
def test_process_crash_during_rollback_is_recoverable(pair, point):
    profile, state = prepared(pair)
    code = '''import os,sys
from pathlib import Path
from app.core.profile_safety import ProfileLease
import app.services.desktop_restore_commit as module
rename=module.rename_exclusive
def fail(source,destination):
    if source.name=='candidate': raise OSError('synthetic promotion failure')
    rename(source,destination)
module.rename_exclusive=fail
with ProfileLease(Path(sys.argv[1])) as lease:
    service=module.RestoreCommit(Path(sys.argv[1]),lease,checkpoint=lambda p: os._exit(73) if p==sys.argv[4] else None)
    service.commit(sys.argv[2],sys.argv[3])
'''
    result = subprocess.run([sys.executable, '-c', code, str(profile), state['operation_id'], state['confirmation'], point],
                            env=dict(os.environ, PYTHONPATH=str(Path(__file__).parents[1])), timeout=30)
    assert result.returncode == 73
    with ProfileLease(profile) as lease:
        assert RestoreCommit(profile, lease).recover()['phase'] == 'ROLLED_BACK'
    assert fingerprint(profile) == state['original_fingerprint']
    assert (Path(state['recovery_location']).parent / 'candidate').is_dir()


def test_failed_rollback_retains_both_and_blocks_blank_start(pair, monkeypatch):
    profile, state = prepared(pair)
    import app.services.desktop_restore_commit as module
    rename = module.rename_exclusive
    def fail_after_original(source, destination):
        if source == profile:
            return rename(source, destination)
        raise PermissionError('synthetic read-only disk')
    monkeypatch.setattr(module, 'rename_exclusive', fail_after_original)
    with ProfileLease(profile) as lease:
        result = RestoreCommit(profile, lease).commit(state['operation_id'], state['confirmation'])
    assert result['phase'] == 'RECOVERY_REQUIRED' and not profile.exists()
    assert Path(state['recovery_location']).is_dir()
    with pytest.raises(ProfileSafetyError):
        assert_boot_allowed(profile)
    monkeypatch.setattr(module, 'rename_exclusive', rename)
    with ProfileLease(profile) as lease:
        assert RestoreCommit(profile, lease).recover()['phase'] == 'ROLLED_BACK'


def test_metadata_tampering_and_unknown_generation_fail_closed(pair):
    profile, state = prepared(pair)
    from app.core.profile_safety import write_operation
    state['after_counts']['trades'] += 1
    write_operation(profile, state)
    with ProfileLease(profile) as lease:
        with pytest.raises(ProfileSafetyError, match='BINDING'):
            RestoreCommit(profile, lease).commit(state['operation_id'], state['confirmation'])
    assert profile.is_dir()


def test_exclusive_rename_does_not_overwrite_existing_generation(tmp_path):
    from app.services.desktop_restore_commit import rename_exclusive
    source = tmp_path / 'source'; source.mkdir()
    target = tmp_path / 'target'; target.mkdir()
    with pytest.raises(OSError):
        rename_exclusive(source, target)
    assert source.is_dir() and target.is_dir()


@pytest.mark.parametrize('kind', ['corrupt', 'missing', 'interference'])
def test_interrupted_unknown_state_never_initializes_blank_profile(pair, kind):
    from app.core.profile_safety import workspace_for
    profile, state = prepared(pair)
    with ProfileLease(profile) as lease:
        service = RestoreCommit(profile, lease)
        def stop(point):
            if point == 'ORIGINAL_MOVED':
                raise KeyboardInterrupt()
        service.checkpoint = stop
        with pytest.raises(KeyboardInterrupt):
            service.commit(state['operation_id'], state['confirmation'])
        if kind == 'corrupt':
            (workspace_for(profile) / 'operation.json').write_text('{broken')
        elif kind == 'missing':
            (workspace_for(profile) / 'operation.json').unlink()
        else:
            profile.mkdir(); (profile / 'foreign').write_text('unexplained generation')
        if kind == 'interference':
            assert service.recover()['phase'] == 'RECOVERY_REQUIRED'
            assert (profile / 'foreign').read_text() == 'unexplained generation'
        else:
            with pytest.raises(ProfileSafetyError):
                service.recover()
        with pytest.raises(ProfileSafetyError):
            assert_boot_allowed(profile)
        assert Path(state['recovery_location']).is_dir()


def test_persistent_fsync_failure_never_claims_success(pair, monkeypatch):
    profile, state = prepared(pair)
    import app.core.profile_safety as module
    def fail(*_):
        raise OSError('synthetic fsync disk failure')
    monkeypatch.setattr(module.os, 'fsync', fail)
    with ProfileLease(profile) as lease:
        with pytest.raises(OSError):
            RestoreCommit(profile, lease).commit(state['operation_id'], state['confirmation'])
    assert fingerprint(profile) == state['original_fingerprint']
