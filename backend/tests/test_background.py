import asyncio
import pytest
from app.core.background import fire_and_forget


async def test_fire_and_forget_runs_coroutine():
    done = asyncio.Event()

    async def job(x):
        await asyncio.sleep(0)
        done.set()
        return x * 2

    fut = fire_and_forget(job, 21)
    assert await asyncio.wait_for(fut, 1) == 42
    assert done.is_set()


async def test_fire_and_forget_runs_sync_function_off_loop():
    import threading
    main = threading.get_ident()

    def job():
        return threading.get_ident()

    fut = fire_and_forget(job)
    assert await asyncio.wait_for(fut, 5) != main


async def test_fire_and_forget_swallows_and_logs_errors(caplog):
    async def boom():
        raise RuntimeError("nope")

    fut = fire_and_forget(boom)
    with pytest.raises(RuntimeError):
        await fut
    assert "nope" in caplog.text
