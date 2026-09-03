"""Run work after responding without Starlette BackgroundTasks.

Under the desktop shell every request is awaited in-process, so BackgroundTasks would delay
the response until the task finishes. fire_and_forget schedules the work on the running loop
(coroutines) or the default executor (sync callables) and returns a Future.
"""
import asyncio
import functools
import inspect
import logging

logger = logging.getLogger(__name__)


def fire_and_forget(func, *args, **kwargs) -> "asyncio.Future":
    loop = asyncio.get_running_loop()
    if inspect.iscoroutinefunction(func):
        fut = loop.create_task(func(*args, **kwargs))
    else:
        fut = loop.run_in_executor(None, functools.partial(func, *args, **kwargs))

    def _log(f):
        if not f.cancelled() and f.exception() is not None:
            logger.error("background task %s failed: %s", getattr(func, "__name__", func), f.exception())

    fut.add_done_callback(_log)
    return fut
