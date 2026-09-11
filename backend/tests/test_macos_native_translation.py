"""Apple's ENOENT native-process case must not reject genuine Intel hosts."""

import ctypes
import errno
from types import SimpleNamespace

import pytest

from scripts import macos_architecture as arch


@pytest.mark.parametrize("result,error,value,expected", [
    (0, 0, 0, False),
    (0, 0, 1, True),
    (-1, errno.ENOENT, 0, False),
    (-1, errno.EPERM, 0, None),
    (-1, errno.EIO, 0, None),
    (0, 0, 7, None),
])
def test_translation_probe_distinguishes_native_missing_key_from_errors(monkeypatch, result, error, value, expected):
    monkeypatch.setattr(arch.platform, "system", lambda: "Darwin")

    def sysctl(name, output, size, new_value, new_size):
        assert name == b"sysctl.proc_translated"
        assert new_value is None and new_size == 0
        output._obj.value = value
        ctypes.set_errno(error)
        return result

    monkeypatch.setattr(ctypes, "CDLL", lambda *args, **kwargs: SimpleNamespace(sysctlbyname=sysctl))
    assert arch.rosetta_translation_status() is expected
    monkeypatch.setattr(arch.platform, "machine", lambda: "x86_64")
    assert arch.native_host_matches("x86_64")[0] is (expected is False)


def test_unavailable_sysctl_library_is_not_native_evidence(monkeypatch):
    monkeypatch.setattr(arch.platform, "system", lambda: "Darwin")

    def fail(*args, **kwargs):
        raise OSError("library unavailable")

    monkeypatch.setattr(ctypes, "CDLL", fail)
    assert arch.rosetta_translation_status() is None
