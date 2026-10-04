"""Offline, recoverable two-rename protocol. Never claims global atomicity."""
from __future__ import annotations

import ctypes
from datetime import datetime, timezone
import os
from pathlib import Path
import sys

from app.core.profile_safety import ProfileSafetyError, read_operation, write_operation, sync_directory
from app.services.desktop_restore import RestorePreparation, confirmation_binding, digest_file, fingerprint


def rename_exclusive(source: Path, destination: Path):
    """Native no-clobber directory rename (macOS 10.12+). No unsafe fallback."""
    if sys.platform != 'darwin':
        raise ProfileSafetyError('EXCLUSIVE_RENAME_UNSUPPORTED')
    libc = ctypes.CDLL(None, use_errno=True)
    rename = libc.renameatx_np
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    # SDK sys/stdio.h: RENAME_EXCL=0x4; fcntl.h AT_FDCWD=-2.
    if rename(-2, os.fsencode(source), -2, os.fsencode(destination), 0x4):
        raise OSError(ctypes.get_errno(), 'exclusive rename failed')
    sync_directory(source.parent)
    if source.parent != destination.parent:
        sync_directory(destination.parent)


class RestoreCommit(RestorePreparation):
    def __init__(self, profile, lease, *, checkpoint=None):
        super().__init__(profile, lease)
        self.checkpoint = checkpoint or (lambda _: None)

    def transition(self, state, phase):
        self.checkpoint('before_' + phase)
        state['phase'] = phase
        write_operation(self.profile, state)
        self.checkpoint(phase)
        return state

    def contract(self, state):
        if state.get('confirmation_binding') != confirmation_binding(state):
            raise ProfileSafetyError('RECOVERY_REQUIRED: invalid confirmation binding')
        directory = self.directory(state)
        if state['recovery_location'] != str(directory / 'original'):
            raise ProfileSafetyError('RECOVERY_REQUIRED: invalid recovery location')
        for key in ('original_fingerprint', 'candidate_fingerprint'):
            fp = state[key]
            if not isinstance(fp, dict) or set(fp) != {'device', 'inode', 'bytes', 'sha256'}:
                raise ProfileSafetyError('RECOVERY_REQUIRED: invalid generation identity')
        if digest_file(directory / 'safety.sqlite3') != state['safety_sha256']:
            raise ProfileSafetyError('RECOVERY_REQUIRED: safety snapshot changed')
        return directory

    @staticmethod
    def matches(path, expected):
        if not path.exists():
            return False
        return fingerprint(path) == expected

    def commit(self, operation_id, confirmation):
        state = self.validate_prepared(operation_id, confirmation)
        directory = self.contract(state)
        original = directory / 'original'; candidate = directory / 'candidate'
        state.pop('confirmation', None)  # Consumed durably before moving anything.
        try:
            self.transition(state, 'MOVING_ORIGINAL')
            rename_exclusive(self.profile, original)
            self.checkpoint('original_renamed')
            self.transition(state, 'ORIGINAL_MOVED')
            self.transition(state, 'PROMOTING')
            rename_exclusive(candidate, self.profile)
            self.checkpoint('candidate_renamed')
            self.transition(state, 'VERIFYING')
            if not self.matches(self.profile, state['candidate_fingerprint']) or not self.matches(original, state['original_fingerprint']):
                raise ProfileSafetyError('PROMOTED_GENERATION_MISMATCH')
            state['connectors_fenced'] = True
            return self.transition(state, 'APPLIED_AWAITING_REVIEW')
        except Exception:
            durable = read_operation(self.profile)
            if durable and durable['phase'] == 'PREPARED':
                # Intent consumption was not durable; report the actual failure.
                raise
            return self.recover()

    def recover(self):
        state = read_operation(self.profile)
        if not state:
            raise ProfileSafetyError('RECOVERY_REQUIRED: missing journal')
        if state['phase'] in {'REVIEWED', 'ROLLED_BACK', 'CANCELLED', 'FAILED'}:
            return state
        if state['phase'] in {'INTENT', 'PREPARING', 'PREPARED'}:
            # No destructive step was authorized. Caller can explicitly cancel.
            return state
        try:
            directory = self.contract(state)
            original = directory / 'original'; candidate = directory / 'candidate'
            old = state['original_fingerprint']; new = state['candidate_fingerprint']
            if self.matches(self.profile, old) and not original.exists() and self.matches(candidate, new):
                return self.transition(state, 'ROLLED_BACK')
            if self.matches(self.profile, new) and self.matches(original, old) and not candidate.exists():
                state['connectors_fenced'] = True
                return self.transition(state, 'APPLIED_AWAITING_REVIEW')
            if not self.profile.exists() and self.matches(original, old) and self.matches(candidate, new):
                self.transition(state, 'ROLLING_BACK')
                rename_exclusive(original, self.profile)
                self.checkpoint('original_restored')
                return self.transition(state, 'ROLLED_BACK')
            raise ProfileSafetyError('AMBIGUOUS_GENERATIONS')
        except Exception:
            # Preserve everything. If fsync itself fails, propagate; never PASS.
            return self.transition(state, 'RECOVERY_REQUIRED')

    def review(self, operation_id):
        state = read_operation(self.profile)
        if not state or state['operation_id'] != operation_id or state['phase'] != 'APPLIED_AWAITING_REVIEW':
            raise ProfileSafetyError('STALE_OR_REPLAYED_REVIEW')
        directory = self.contract(state)
        if not self.matches(self.profile, state['candidate_fingerprint']) or not self.matches(directory / 'original', state['original_fingerprint']):
            raise ProfileSafetyError('REVIEW_GENERATION_CHANGED')
        state['resumed_at_utc'] = datetime.now(timezone.utc).isoformat()
        state['connectors_fenced'] = True
        return self.transition(state, 'REVIEWED')
