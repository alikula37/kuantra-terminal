"""
Parent Process Watcher for Kuantra Terminal.
Monitors parent Tauri process lifecycle to guarantee zero zombie backend processes.
"""

import os
import sys
import time
import threading
import logging
from typing import Optional

logger = logging.getLogger("parent_watcher")

def is_process_alive(pid: int) -> bool:
    """Cross-platform check to determine if a process ID is currently active."""
    if pid <= 0:
        return False

    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return False

        try:
            exit_code = wintypes.DWORD()
            if kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return exit_code.value == STILL_ACTIVE
            return False
        finally:
            kernel32.CloseHandle(handle)
    else:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

class ParentProcessWatcher:
    """Daemon thread that polls parent PID and terminates sidecar if parent dies."""

    def __init__(self, parent_pid: int, poll_interval: float = 1.5):
        self.parent_pid = parent_pid
        self.poll_interval = poll_interval
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> threading.Thread:
        self._thread = threading.Thread(
            target=self._watch_loop,
            name="ParentProcessWatcherThread",
            daemon=True
        )
        self._thread.start()
        print(f"[+] Parent process watcher armed for PID: {self.parent_pid}", flush=True)
        return self._thread

    def stop(self):
        self._stop_event.set()

    def _watch_loop(self):
        while not self._stop_event.is_set():
            if not is_process_alive(self.parent_pid):
                print(f"\n[!] Parent process (PID: {self.parent_pid}) terminated or died. Triggering clean sidecar shutdown...", flush=True)
                # Flush stdout and terminate process immediately
                sys.stdout.flush()
                sys.stderr.flush()
                os._exit(0)
            time.sleep(self.poll_interval)

def start_parent_watcher(parent_pid: int, poll_interval: float = 1.5) -> ParentProcessWatcher:
    """Helper function to instantiate and start parent process watcher."""
    watcher = ParentProcessWatcher(parent_pid=parent_pid, poll_interval=poll_interval)
    watcher.start()
    return watcher