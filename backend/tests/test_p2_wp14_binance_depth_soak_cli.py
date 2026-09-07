"""P2-WP14 opt-in soak CLI contracts; no live network is used."""

import asyncio
import json
from pathlib import Path

import pytest

from app.services.market_data.binance_depth_ingestor import BinanceDepthIngestor
from app.services.market_data.binance_depth_network import BinanceDepthNetworkAdapter, BinanceDepthNetworkConfig
from app.services.market_data.binance_depth_transport import DepthTransportDecision

from scripts.run_binance_depth_soak import (
    REPORT_SCHEMA_VERSION,
    build_parser,
    main,
    run_fixture_probe,
)


def test_cli_defaults_to_offline_fixture_and_refuses_network_without_opt_in(tmp_path):
    args = build_parser().parse_args([])
    assert args.mode == "fixture"
    assert main(["--mode", "testnet", "--storage-root", str(tmp_path)]) == 2


def test_fixture_probe_writes_truth_bound_report(tmp_path):
    report = asyncio.run(
        run_fixture_probe(
            symbol="btcusdt",
            storage_root=tmp_path,
            max_reconnects=1,
        )
    )

    assert report["schema_version"] == REPORT_SCHEMA_VERSION
    assert report["mode"] == "fixture"
    assert report["environment"] == "offline"
    assert report["session"]["decision"] == "COMPLETED"
    assert report["session"]["reconnects"] == 1
    assert report["session"]["continuity"] == {
        "completed_cycle_count": 1,
        "cycle_count": 2,
        "gap_event_count": 0,
        "persistence_failure_cycle_count": 0,
        "processed_event_count": 2,
        "reconnect_count": 1,
        "recovery_required_cycle_count": 0,
        "snapshot_rejected_cycle_count": 0,
        "snapshot_retry_cycle_count": 0,
        "source_failure_cycle_count": 1,
        "stopped_cycle_count": 0,
    }
    assert report["chain"]["valid"] is True
    assert report["persistence"]["valid"] is True
    assert report["source_verified"] is False
    assert report["execution_authority"] is False
    assert Path(report["run_root"]).is_dir()


def test_cli_serializes_fixture_report_without_enabling_network(tmp_path):
    output = tmp_path / "report.json"
    assert (
        main(
            [
                "--mode",
                "fixture",
                "--storage-root",
                str(tmp_path / "storage"),
                "--output",
                str(output),
            ]
        )
        == 0
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == REPORT_SCHEMA_VERSION
    assert payload["source_verified"] is False


def test_cli_rejects_invalid_duration_and_reconnect_bounds(tmp_path):
    assert main(["--duration-seconds", "0", "--storage-root", str(tmp_path)]) == 2
    assert main(["--max-reconnects", "101", "--storage-root", str(tmp_path)]) == 2
    assert main(["--retry-recovery", "--storage-root", str(tmp_path)]) == 2


def test_cli_rejects_stop_during_recovery_backoff(monkeypatch, tmp_path):
    async def fake_testnet_probe(**kwargs):
        report = await run_fixture_probe(
            symbol="BTCUSDT",
            storage_root=tmp_path / "storage",
            max_reconnects=1,
        )
        report["mode"] = "testnet"
        report["environment"] = "testnet"
        report["session"] = {
            "decision": "STOPPED",
            "reason_code": "STOP_EVENT_SET_DURING_BACKOFF",
            "attempts": 1,
            "reconnects": 1,
            "processed_event_count": 2,
            "source_verified": False,
            "cycles": [
                {
                    "decision": "RECOVERY_REQUIRED",
                    "reason_code": "INGESTOR_REQUIRES_RECOVERY",
                    "source_verified": False,
                }
            ],
        }
        return report

    monkeypatch.setattr(
        "scripts.run_binance_depth_soak.run_testnet_probe",
        fake_testnet_probe,
    )

    assert (
        main(
            [
                "--mode",
                "testnet",
                "--allow-network",
                "--storage-root",
                str(tmp_path / "cli-storage"),
            ]
        )
        == 1
    )


def test_cli_exposes_recovery_retry_only_as_an_opt_in_testnet_flag():
    args = build_parser().parse_args(["--mode", "testnet", "--allow-network", "--retry-recovery"])
    assert args.retry_recovery is True


class _BlockingWebsocket:
    def __init__(self):
        self.block = asyncio.Event()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def recv(self):
        await self.block.wait()


@pytest.mark.asyncio
async def test_network_adapter_stop_event_interrupts_quiet_socket():
    config = BinanceDepthNetworkConfig("BTCUSDT", recv_timeout_seconds=60)
    blocking_socket = _BlockingWebsocket()

    def websocket_connect(url, **kwargs):
        return blocking_socket

    adapter = BinanceDepthNetworkAdapter(
        BinanceDepthIngestor("BTCUSDT"),
        config,
        websocket_connect=websocket_connect,
    )
    stop_event = asyncio.Event()

    async def stop_soon():
        await asyncio.sleep(0.01)
        stop_event.set()

    stopper = asyncio.create_task(stop_soon())
    try:
        result = await asyncio.wait_for(
            adapter.transport.run_once(
                event_source=adapter.event_source(stop_event=stop_event),
                snapshot_fetcher=lambda: {"lastUpdateId": 101, "bids": [], "asks": []},
                stop_event=stop_event,
            ),
            timeout=1,
        )
    finally:
        await stopper
    assert result.decision is DepthTransportDecision.STOPPED
