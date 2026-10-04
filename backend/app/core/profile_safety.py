"""Dependency-free, pre-DATA_DIR restore guard and POSIX process lease.

The advisory lease coordinates Kuantra writers, not arbitrary external editors.
Never imports paths, databases, runtime, logging, credentials or network code.
"""
from __future__ import annotations

import atexit
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import time
import uuid


class ProfileSafetyError(RuntimeError):
    pass


PHASES = frozenset({'INTENT', 'PREPARING', 'PREPARED', 'MOVING_ORIGINAL',
                    'ORIGINAL_MOVED', 'PROMOTING', 'VERIFYING', 'ROLLING_BACK',
                    'APPLIED_AWAITING_REVIEW', 'REVIEWED', 'ROLLED_BACK',
                    'CANCELLED', 'FAILED', 'RECOVERY_REQUIRED'})
BOOT_PHASES = frozenset({'REVIEWED', 'ROLLED_BACK', 'CANCELLED', 'FAILED'})
MAX_STATE_BYTES = 65536


def profile_path() -> Path:
    override = os.environ.get('KUANTRA_DATA_DIR')
    if override:
        return Path(override).expanduser().absolute()
    if not getattr(sys, 'frozen', False):
        return Path(__file__).resolve().parents[2] / 'data'
    if sys.platform == 'darwin':
        return Path.home() / 'Library' / 'Application Support' / 'Kuantra Terminal'
    if os.name == 'nt':
        return Path(os.environ.get('LOCALAPPDATA', str(Path.home() / 'AppData' / 'Local'))) / 'Kuantra Terminal'
    return Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local' / 'share'))) / 'kuantra-terminal'


def workspace_for(profile: Path) -> Path:
    profile = Path(profile).absolute()
    # Profile itself may legitimately be missing after the first rename.
    if profile.is_symlink():
        raise ProfileSafetyError('UNSAFE_PROFILE_PATH')
    profile = profile.parent.resolve() / profile.name
    digest = hashlib.sha256(str(profile).encode()).hexdigest()[:20]
    return profile.parent / ('.kuantra-restore-' + digest)


def private_workspace(profile: Path) -> Path:
    root = workspace_for(profile)
    if root.is_symlink():
        raise ProfileSafetyError('UNSAFE_WORKSPACE')
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = root.stat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
        raise ProfileSafetyError('UNSAFE_WORKSPACE')
    root.chmod(0o700)
    return root


def sync_directory(path: Path):
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def read_operation(profile: Path) -> dict | None:
    root = workspace_for(profile)
    if root.is_symlink():
        raise ProfileSafetyError('RECOVERY_REQUIRED: unsafe workspace')
    path = root / 'operation.json'
    if not path.exists() and not path.is_symlink():
        # Recovery generations without their journal must never become a blank profile.
        if root.exists() and any(p.name not in {'profile.lock'} for p in root.iterdir()):
            raise ProfileSafetyError('RECOVERY_REQUIRED: missing operation journal')
        return None
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
        with os.fdopen(fd, 'rb') as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_STATE_BYTES:
                raise ValueError('invalid journal file')
            value = json.loads(stream.read(MAX_STATE_BYTES + 1))
        if (not isinstance(value, dict) or value.get('version') != 1
                or value.get('phase') not in PHASES
                or not re.fullmatch('[0-9a-f]{32}', str(value.get('operation_id', '')))):
            raise ValueError('invalid journal contract')
        return value
    except (ValueError, OSError) as exc:
        raise ProfileSafetyError('RECOVERY_REQUIRED: invalid operation journal') from exc


def write_operation(profile: Path, value: dict):
    if (value.get('version') != 1 or value.get('phase') not in PHASES
            or not re.fullmatch('[0-9a-f]{32}', str(value.get('operation_id', '')))):
        raise ProfileSafetyError('INVALID_OPERATION')
    payload = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    if len(payload) > MAX_STATE_BYTES:
        raise ProfileSafetyError('OPERATION_LIMIT')
    root = private_workspace(profile)
    temporary = root / ('.state-' + uuid.uuid4().hex)
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(payload); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, root / 'operation.json')
        sync_directory(root)
    finally:
        temporary.unlink(missing_ok=True)


def assert_boot_allowed(profile: Path):
    operation = read_operation(profile)
    if operation:
        if operation['phase'] not in BOOT_PHASES or not profile.is_dir():
            raise ProfileSafetyError('RECOVERY_REQUIRED: open offline maintenance; profile was not initialized')


class ProfileLease:
    """Exclusive OS lifetime lock outside the directory being replaced."""
    def __init__(self, profile: Path, *, timeout: float = 0):
        self.profile = Path(profile).absolute()
        self.timeout = min(max(float(timeout), 0), 20)
        self.fd = None

    def acquire(self):
        if self.fd is not None:
            return self
        if os.name != 'posix':
            raise ProfileSafetyError('PROFILE_LEASE_UNSUPPORTED: macOS v1 only')
        import fcntl
        root = private_workspace(self.profile)
        fd = os.open(root / 'profile.lock', os.O_RDWR | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid():
            os.close(fd); raise ProfileSafetyError('UNSAFE_PROFILE_LOCK')
        deadline = time.monotonic() + self.timeout
        try:
            while True:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise ProfileSafetyError('PROFILE_BUSY: another Kuantra writer owns the profile')
                    time.sleep(0.05)
            self.fd = fd
            return self
        except BaseException:
            os.close(fd)
            raise

    def close(self):
        if self.fd is not None:
            os.close(self.fd); self.fd = None

    def __enter__(self):
        return self.acquire()

    def __exit__(self, *_):
        self.close()


_process_leases: dict[str, ProfileLease] = {}


def claim_writer(profile: Path | None = None):
    target = Path(profile or profile_path()).absolute()
    key = str(target)
    if key not in _process_leases:
        lease = ProfileLease(target).acquire()
        try:
            assert_boot_allowed(target)
        except BaseException:
            lease.close(); raise
        _process_leases[key] = lease
        atexit.register(lease.close)
    return _process_leases[key]
