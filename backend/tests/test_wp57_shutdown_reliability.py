"""Disposable, no-network shutdown failure reproductions; never use the user journal."""
import multiprocessing
import sys
import threading
import time
from concurrent.futures import ProcessPoolExecutor
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from contextlib import asynccontextmanager


def test_failed_runtime_start_closes_loop_and_client():
    from desktop.runtime import BackendRuntime

    @asynccontextmanager
    async def lifespan(_app):
        raise ValueError("synthetic startup failure")
        yield

    runtime = BackendRuntime(lambda: FastAPI(lifespan=lifespan))
    with pytest.raises(RuntimeError, match="failed to start"):
        runtime.start()
    runtime._thread.join(timeout=2)
    assert runtime.loop.is_closed()
    assert runtime._client.is_closed
    assert not runtime.is_running
    runtime.stop()


@pytest.mark.parametrize("fail_creation", [False, True])
def test_webview_start_failure_always_closes_owned_context(monkeypatch, fail_creation):
    import desktop_main

    class Event:
        def __iadd__(self, _handler):
            return self

    ctx = object()
    calls = []
    window = SimpleNamespace(events=SimpleNamespace(closed=Event()))
    def fail_start(*_args, **_kwargs):
        raise RuntimeError("synthetic renderer failure")
    monkeypatch.setitem(sys.modules, "webview", SimpleNamespace(
        create_window=fail_start if fail_creation else lambda *_a, **_k: window, start=fail_start,
    ))
    monkeypatch.setattr(desktop_main, "build_app", lambda _args: SimpleNamespace(
        index_url="file:///synthetic/index.html", bridge=ctx, gateway=None,
    ))
    monkeypatch.setattr(desktop_main, "shutdown", lambda context: calls.append(context))
    monkeypatch.setattr(desktop_main, "_configure_logging", lambda *_a: None)
    monkeypatch.setattr(desktop_main, "_preflight_renderer", lambda *_a: None)
    with pytest.raises(RuntimeError, match="synthetic renderer failure"):
        desktop_main.main([])
    assert len(calls) == 1


def test_partial_context_start_failure_cleans_started_resources(monkeypatch):
    import desktop_main
    from app.core.config import settings

    calls = []
    class Runtime:
        def start(self): calls.append("runtime start")
        def stop(self, **_kw): calls.append("runtime stop")
    class Push:
        def attach_windows(self, _getter): pass
        def start(self):
            calls.append("push start")
            raise RuntimeError("synthetic push failure")
        def stop(self): calls.append("push stop")
    monkeypatch.setitem(sys.modules, "webview", SimpleNamespace(windows=[]))
    monkeypatch.setattr("desktop.runtime.BackendRuntime", Runtime)
    monkeypatch.setattr("desktop.push.PushChannel", Push)
    monkeypatch.setattr(settings, "gateway_enabled", False)
    with pytest.raises(RuntimeError, match="synthetic push failure"):
        desktop_main.build_app(desktop_main.parse_args([]))
    assert calls == ["runtime start", "push start", "push stop", "runtime stop"]


def test_concurrent_shell_close_waits_for_cleanup_completion(monkeypatch):
    import desktop_main

    entered, release, second_done = threading.Event(), threading.Event(), threading.Event()
    monkeypatch.setattr(desktop_main, "_shutdown_done", threading.Event())
    monkeypatch.setattr(desktop_main, "_shutdown_lock", threading.Lock(), raising=False)
    def stop(_ctx):
        entered.set()
        assert release.wait(2)
    monkeypatch.setattr(desktop_main, "_stop_resources", stop)
    first = threading.Thread(target=desktop_main.shutdown, args=(object(),))
    second = threading.Thread(target=lambda: (desktop_main.shutdown(object()), second_done.set()))
    first.start()
    assert entered.wait(1)
    second.start()
    try:
        assert not second_done.wait(0.1), "main must not exit while window callback still cleans workers"
    finally:
        release.set()
        first.join(2)
        second.join(2)
    assert second_done.is_set()


def test_close_bounds_real_busy_owned_process_and_is_idempotent(monkeypatch):
    from desktop.bridge import DesktopBridge
    import os

    bridge = DesktopBridge(None, None)
    executor = ProcessPoolExecutor(max_workers=1, mp_context=multiprocessing.get_context("spawn"))
    unrelated = multiprocessing.get_context("spawn").Process(target=time.sleep, args=(30,))
    unrelated.start()
    worker_pid = executor.submit(os.getpid).result(timeout=15)
    processes = tuple(executor._processes.values())
    assert len(processes) == 1 and processes[0].pid == worker_pid
    future = executor.submit(time.sleep, 30)
    deadline = time.monotonic() + 2
    while not future.running() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert future.running(), "failure reproduction requires a running, non-cancellable job"
    bridge._evidence_executor = executor
    bridge._evidence_jobs["synthetic"] = (future, time.monotonic())
    monkeypatch.setattr(bridge, "_EVIDENCE_SHUTDOWN_GRACE_SECONDS", 0.05, raising=False)
    finished = threading.Event()
    def close():
        try:
            bridge._close()
        finally:
            finished.set()
    closer = threading.Thread(target=close, daemon=True)
    closer.start()
    try:
        assert finished.wait(3), "busy Evidence Pack must not indefinitely block GUI shutdown"
        assert not processes[0].is_alive()
        assert unrelated.is_alive(), "unrelated child must not be terminated"
        assert bridge._evidence_jobs_closed
        bridge._close()
        assert bridge.start_evidence_pack({"trade_id": "synthetic"})["status"] == "REJECTED"
    finally:
        # Exact test-owned handle, never a global process-name kill.
        for process in processes:
            if process.is_alive():
                process.terminate()
            process.join(timeout=2)
        closer.join(timeout=2)
        executor.shutdown(wait=True, cancel_futures=True)
        unrelated.terminate()
        unrelated.join(timeout=2)
