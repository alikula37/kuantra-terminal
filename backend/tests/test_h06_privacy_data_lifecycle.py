"""H06 privacy, data-lifecycle and credential-availability boundary tests."""

from __future__ import annotations

import json
import os
import stat
import zipfile

import pytest

from app.core import logging_config
from app.core import paths
from app.core.telemetry import PrivacyTelemetryManager


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission contract")
def test_data_directory_is_tightened_to_owner_only(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir(mode=0o755)

    paths.ensure_private_directory(data_dir)

    assert stat.S_IMODE(data_dir.stat().st_mode) == 0o700


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission contract")
def test_read_only_data_directory_fails_closed(tmp_path):
    data_dir = tmp_path / "readonly-data"
    data_dir.mkdir(mode=0o500)
    try:
        with pytest.raises(paths.DataDirectoryError, match="owner-writable"):
            paths.ensure_private_directory(data_dir)
    finally:
        data_dir.chmod(0o700)


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission contract")
def test_generated_private_file_is_owner_only(tmp_path):
    path = tmp_path / "private.json"
    paths.ensure_private_file(path)

    assert stat.S_IMODE(path.stat().st_mode) == 0o600

    path.chmod(0o644)
    paths.ensure_private_file(path)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_telemetry_does_not_claim_success_or_clear_queue_without_transport(tmp_path):
    queue_file = tmp_path / "telemetry" / "queue.json"
    manager = PrivacyTelemetryManager(queue_file=queue_file)
    manager.is_opted_in = lambda: True

    manager.spool_crash(
        "SyntheticFailure",
        "api_key=secret-value-123456",
        "File /Users/alice/private/journal.sqlite",
    )

    result = manager.flush_queue()

    assert result == {"status": "NO_TRANSPORT", "flushed_count": 0}
    assert manager.get_queued_crashes_count() == 1
    payload = json.loads(queue_file.read_text(encoding="utf-8"))
    assert "secret-value-123456" not in json.dumps(payload)
    assert "/Users/alice/private/journal.sqlite" not in json.dumps(payload)


def test_telemetry_clears_queue_only_after_injected_transport_ack(tmp_path):
    queue_file = tmp_path / "telemetry" / "queue.json"
    accepted = []
    manager = PrivacyTelemetryManager(
        queue_file=queue_file,
        flush_transport=lambda records: accepted.append(records) or False,
    )
    manager.is_opted_in = lambda: True
    manager.spool_crash("SyntheticFailure", "safe", "trace")

    rejected = manager.flush_queue()
    assert rejected["status"] == "TRANSPORT_REJECTED"
    assert manager.get_queued_crashes_count() == 1
    assert len(accepted) == 1

    manager.flush_transport = lambda records: True
    delivered = manager.flush_queue()
    assert delivered == {"status": "SUCCESS", "flushed_count": 1}
    assert manager.get_queued_crashes_count() == 0


def test_telemetry_queue_is_bounded_and_redacted(tmp_path):
    queue_file = tmp_path / "telemetry" / "queue.json"
    manager = PrivacyTelemetryManager(queue_file=queue_file, max_queue_records=2)
    for index in range(3):
        manager.spool_crash("SyntheticFailure", f"token=secret-value-{index:06d}", "trace")

    payload = json.loads(queue_file.read_text(encoding="utf-8"))
    assert len(payload) == 2
    assert "secret-value-000000" not in json.dumps(payload)
    assert "secret-value-000001" not in json.dumps(payload)
    assert stat.S_IMODE(queue_file.stat().st_mode) == 0o600


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission contract")
def test_support_archive_is_private_and_redacted(tmp_path, monkeypatch):
    log_dir = tmp_path / "logs"
    log_dir.mkdir(mode=0o700)
    (log_dir / "synthetic.log").write_text(
        "api_key=secret-value-123456 path=/Users/alice/private/journal.sqlite\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(logging_config, "LOGS_DIR", log_dir)
    output = tmp_path / "support.zip"

    archive_path = logging_config.export_logs_zip(str(output))

    assert stat.S_IMODE(os.stat(archive_path).st_mode) == 0o600
    with zipfile.ZipFile(archive_path) as archive:
        content = archive.read("synthetic.log").decode("utf-8")
    assert "secret-value-123456" not in content
    assert "/Users/alice/private/journal.sqlite" not in content
