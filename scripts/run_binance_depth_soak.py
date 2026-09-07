"""Run an explicit offline fixture or Binance Spot testnet depth soak.

The command is intentionally fail-closed: fixture mode is the default, and
testnet mode requires ``--allow-network``.  It never enables private streams,
order submission or ``source_verified=true``.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.market_data.binance_depth_ingestor import BinanceDepthIngestor  # noqa: E402
from app.services.market_data.binance_depth_network import (  # noqa: E402
    BinanceDepthEnvironment,
    BinanceDepthNetworkAdapter,
    BinanceDepthNetworkConfig,
)
from app.services.market_data.binance_depth_session import (  # noqa: E402
    BinanceDepthReconnectPolicy,
    BinanceDepthSession,
)
from app.services.market_data.binance_depth_soak import (  # noqa: E402
    BinanceDepthSoakHarness,
    DepthFixtureCycle,
)
from app.services.market_data.binance_depth_transport import BinanceDepthTransportConfig  # noqa: E402
from app.services.market_data.market_event_segments import MarketEventSegmentSet  # noqa: E402


REPORT_SCHEMA_VERSION = "BINANCE_DEPTH_SOAK_REPORT_V1"
DEFAULT_STORAGE_ROOT = Path(tempfile.gettempdir()) / "kuantra-depth-soak"


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _run_root(storage_root: Path, mode: str) -> Path:
    run_root = storage_root.resolve() / f"{mode}-{int(time.time() * 1000)}"
    run_root.mkdir(parents=True, exist_ok=False)
    return run_root


def _snapshot(symbol: str, last_update_id: int) -> Mapping[str, Any]:
    return {
        "lastUpdateId": last_update_id,
        "bids": [["65000", "2"]],
        "asks": [["65010", "3"]],
    }


def _event(symbol: str, first_update_id: int, final_update_id: int) -> Mapping[str, Any]:
    return {
        "e": "depthUpdate",
        "s": symbol,
        "U": first_update_id,
        "u": final_update_id,
        "b": [["65000", "1"]],
        "a": [],
    }


def _fixture_cycles(symbol: str) -> tuple[DepthFixtureCycle, ...]:
    return (
        DepthFixtureCycle(
            _snapshot(symbol, 101),
            (_event(symbol, 101, 102),),
            failure_reason="fixture disconnect",
        ),
        DepthFixtureCycle(_snapshot(symbol, 102), (_event(symbol, 103, 104),)),
    )


def _report(
    *,
    mode: str,
    environment: str,
    symbol: str,
    started_at: str,
    elapsed_ms: float,
    session_result: Any,
    ingestor: BinanceDepthIngestor,
    sink: MarketEventSegmentSet,
    run_root: Path,
    remaining_fixture_cycles: Optional[int] = None,
) -> dict[str, Any]:
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "mode": mode,
        "environment": environment,
        "symbol": symbol,
        "started_at": started_at,
        "elapsed_ms": round(elapsed_ms, 2),
        "run_root": str(run_root),
        "session": session_result.as_dict(),
        "chain": ingestor.chain.verify(),
        "persistence": sink.recovery_report(),
        "remaining_fixture_cycles": remaining_fixture_cycles,
        "source_verified": False,
        "execution_authority": False,
    }


async def run_fixture_probe(
    *,
    symbol: str,
    storage_root: Path,
    max_reconnects: int,
) -> dict[str, Any]:
    normalized_symbol = str(symbol).strip().upper()
    run_root = _run_root(storage_root, "fixture")
    sink = MarketEventSegmentSet(run_root / "segments", max_events_per_segment=2)
    ingestor = BinanceDepthIngestor(normalized_symbol, event_sink=sink)
    harness = BinanceDepthSoakHarness(
        ingestor,
        BinanceDepthTransportConfig(normalized_symbol, queue_size=2),
        _fixture_cycles(normalized_symbol),
        policy=BinanceDepthReconnectPolicy(max_reconnects=max_reconnects, backoff_initial_seconds=0),
    )
    started_at = _timestamp()
    started = time.perf_counter()
    result = await harness.run()
    return _report(
        mode="fixture",
        environment="offline",
        symbol=normalized_symbol,
        started_at=started_at,
        elapsed_ms=(time.perf_counter() - started) * 1000,
        session_result=result.session,
        ingestor=ingestor,
        sink=sink,
        run_root=run_root,
        remaining_fixture_cycles=result.remaining_fixture_cycles,
    )


async def run_testnet_probe(
    *,
    symbol: str,
    storage_root: Path,
    duration_seconds: float,
    max_reconnects: int,
    retry_recovery: bool = False,
) -> dict[str, Any]:
    normalized_symbol = str(symbol).strip().upper()
    run_root = _run_root(storage_root, "testnet")
    sink = MarketEventSegmentSet(run_root / "segments", max_events_per_segment=100_000)
    ingestor = BinanceDepthIngestor(normalized_symbol, event_sink=sink)
    config = BinanceDepthNetworkConfig(
        normalized_symbol,
        environment=BinanceDepthEnvironment.TESTNET,
    )
    adapter = BinanceDepthNetworkAdapter(ingestor, config)
    session = BinanceDepthSession(
        adapter,
        BinanceDepthReconnectPolicy(
            max_reconnects=max_reconnects,
            backoff_initial_seconds=1,
            retry_recovery=retry_recovery,
        ),
    )
    stop_event = asyncio.Event()
    started_at = _timestamp()
    started = time.perf_counter()
    session_task = asyncio.create_task(session.run(stop_event=stop_event))
    try:
        await asyncio.sleep(duration_seconds)
        stop_event.set()
        result = await asyncio.wait_for(session_task, timeout=10)
    finally:
        if not session_task.done():
            session_task.cancel()
            await asyncio.gather(session_task, return_exceptions=True)
    return _report(
        mode="testnet",
        environment=config.environment.value,
        symbol=normalized_symbol,
        started_at=started_at,
        elapsed_ms=(time.perf_counter() - started) * 1000,
        session_result=result,
        ingestor=ingestor,
        sink=sink,
        run_root=run_root,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Kuantra Binance depth fixture/testnet soak")
    parser.add_argument("--mode", choices=("fixture", "testnet"), default="fixture")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--duration-seconds", type=float, default=30.0)
    parser.add_argument("--max-reconnects", type=int, default=3)
    parser.add_argument(
        "--retry-recovery",
        action="store_true",
        help="retry a sequence-gap cycle with a fresh snapshot within the reconnect budget",
    )
    parser.add_argument("--allow-network", action="store_true")
    parser.add_argument("--output", type=Path, default=None)
    return parser


def _validate_args(args: argparse.Namespace) -> None:
    if args.mode == "testnet" and not args.allow_network:
        raise ValueError("testnet mode requires explicit --allow-network")
    if args.retry_recovery and args.mode != "testnet":
        raise ValueError("retry-recovery is only available in testnet mode")
    if not str(args.symbol).strip():
        raise ValueError("symbol must be non-empty")
    if isinstance(args.duration_seconds, bool) or args.duration_seconds <= 0 or args.duration_seconds > 86_400:
        raise ValueError("duration-seconds must be > 0 and <= 86400")
    if isinstance(args.max_reconnects, bool) or args.max_reconnects < 0 or args.max_reconnects > 100:
        raise ValueError("max-reconnects must be between 0 and 100")


def _write_or_print(report: dict[str, Any], output: Optional[Path]) -> None:
    encoded = json.dumps(report, indent=2, sort_keys=True)
    if output is None:
        print(encoded)
        return
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(encoded + "\n", encoding="utf-8")
    print(f"[binance-depth-soak] report={output}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        _validate_args(args)
        if args.mode == "testnet":
            report = asyncio.run(
                run_testnet_probe(
                    symbol=args.symbol,
                    storage_root=args.storage_root,
                    duration_seconds=args.duration_seconds,
                    max_reconnects=args.max_reconnects,
                    retry_recovery=args.retry_recovery,
                )
            )
        else:
            report = asyncio.run(
                run_fixture_probe(
                    symbol=args.symbol,
                    storage_root=args.storage_root,
                    max_reconnects=args.max_reconnects,
                )
            )
    except (OSError, ValueError, RuntimeError, asyncio.TimeoutError) as exc:
        print(f"[binance-depth-soak] REFUSED/FAIL: {exc}", file=sys.stderr)
        return 2
    _write_or_print(report, args.output)
    decision = report["session"]["decision"]
    return 0 if decision in {"COMPLETED", "STOPPED"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
