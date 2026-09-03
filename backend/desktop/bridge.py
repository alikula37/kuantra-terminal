"""
DesktopBridge is the object pywebview exposes as window.pywebview.api. Every public method is
synchronous (pywebview runs each call on its own thread) and takes/returns JSON-compatible data.
"""
from __future__ import annotations

import base64
import logging
import mimetypes
import re
import sys
import webbrowser
from asyncio import CancelledError
from concurrent.futures import CancelledError as FuturesCancelledError
from pathlib import Path
from typing import Callable, Optional

from app.core.paths import DATA_DIR, is_frozen
from app.version import __version__
from desktop import clipboard
from desktop.push import PushChannel
from desktop.runtime import BackendRuntime

logger = logging.getLogger("desktop.bridge")

TEXT_TYPES = ("application/json", "text/", "application/xml", "application/javascript", "application/problem+json")


def _is_text(content_type: str) -> bool:
    ct = (content_type or "").lower()
    return any(ct.startswith(t) for t in TEXT_TYPES)


class DesktopBridge:
    def __init__(
        self,
        runtime: BackendRuntime,
        push: PushChannel,
        gateway=None,
        index_url: str = "",
        windows_getter: Optional[Callable[[], list]] = None,
        dialog_window_getter: Optional[Callable[[], object]] = None,
    ):
        self.runtime = runtime
        self.push = push
        self.gateway = gateway
        self.index_url = index_url
        self._windows = windows_getter or (lambda: [])
        self._dialog_window = dialog_window_getter
        self._stream_attached = False
        self._popouts: dict[str, object] = {}

    # ---- HTTP-shaped requests, no HTTP ---------------------------------------------------
    def request(self, req: dict) -> dict:
        files = [
            (f["field"], f.get("filename") or "upload", base64.b64decode(f["data_b64"]), f.get("content_type") or "application/octet-stream")
            for f in (req.get("files") or [])
        ]
        fields = [(k, v) for k, v in (req.get("fields") or [])]
        body = req.get("body")
        body_bytes = body.encode("utf-8") if isinstance(body, str) else None
        if req.get("body_b64"):
            body_bytes = base64.b64decode(req["body_b64"])
        try:
            resp = self.runtime.call(
                req.get("method", "GET"), req.get("path", "/"), req.get("query") or "",
                headers=req.get("headers") or {}, body=body_bytes, files=files or None, fields=fields or None,
            )
        except (RuntimeError, CancelledError, FuturesCancelledError) as exc:
            # The backend loop is gone (app is closing). Answer the UI instead of hanging its thread.
            logger.debug("request during shutdown: %s", exc)
            return {"status": 503, "headers": {"content-type": "application/json"},
                    "body": '{"detail":"backend unavailable"}', "body_b64": None}
        content_type = resp.headers.get("content-type", "")
        if _is_text(content_type) or not resp.content:
            return {"status": resp.status, "headers": resp.headers, "body": resp.content.decode("utf-8", errors="replace"), "body_b64": None}
        return {"status": resp.status, "headers": resp.headers, "body": None, "body_b64": base64.b64encode(resp.content).decode("ascii")}

    # ---- live stream -----------------------------------------------------------------------
    def stream_open(self) -> dict:
        from app.websocket.binance_client import binance_client
        from app.websocket.connection_manager import ws_manager

        async def _attach():
            if not self._stream_attached:
                ws_manager.attach(self.push, PushChannel.CHANNELS)
                self._stream_attached = True
            return {
                "type": "SNAPSHOT",
                "symbol": binance_client.symbol,
                "last_price": binance_client.last_price,
                "open_positions": binance_client._recalculate_open_positions(binance_client.last_price),
            }

        return self.runtime.run(_attach())

    # ---- windows ---------------------------------------------------------------------------
    def open_popout(self, spec: dict) -> dict:
        import webview
        label = re.sub(r"[^a-z0-9]", "-", str(spec.get("label", "panel")).lower())
        existing = self._popouts.get(label)
        if existing is not None and existing in webview.windows:
            try:
                existing.restore()
            except Exception:  # noqa: BLE001
                pass
            return {"created": False, "label": label}
        query = str(spec.get("query", "")).lstrip("?")
        url = f"{self.index_url}?{query}" if query else self.index_url
        win = webview.create_window(
            spec.get("title", "Kuantra Terminal"), url=url, js_api=self,
            width=int(spec.get("width", 1024)), height=int(spec.get("height", 700)),
            min_size=(600, 400), text_select=True, background_color="#0b0e14",
        )
        self._popouts[label] = win
        return {"created": True, "label": label}

    # ---- files -----------------------------------------------------------------------------
    def _pick_save_path(self, filename: str) -> Optional[str]:
        import webview
        win = self._dialog_window() if self._dialog_window else (webview.active_window() or (webview.windows[0] if webview.windows else None))
        if win is None:
            return None
        result = win.create_file_dialog(webview.SAVE_DIALOG, save_filename=filename)
        if not result:
            return None
        return result[0] if isinstance(result, (list, tuple)) else str(result)

    def save_file(self, spec: dict) -> dict:
        filename = spec.get("filename") or "download"
        data = spec.get("content") or ""
        raw = base64.b64decode(data) if spec.get("encoding") == "base64" else str(data).encode("utf-8")
        path = self._pick_save_path(filename)
        if not path:
            return {"saved": False, "path": None}
        Path(path).write_bytes(raw)
        return {"saved": True, "path": path}

    def download(self, spec: dict) -> dict:
        resp = self.runtime.call("GET", spec["path"], spec.get("query") or "")
        if resp.status != 200:
            return {"saved": False, "path": None, "status": resp.status}
        filename = spec.get("filename")
        disposition = resp.headers.get("content-disposition", "")
        m = re.search(r'filename="?([^";]+)"?', disposition)
        if m:
            filename = m.group(1)
        if not filename:
            ext = mimetypes.guess_extension(resp.headers.get("content-type", "").split(";")[0]) or ""
            filename = f"kuantra-download{ext}"
        path = self._pick_save_path(filename)
        if not path:
            return {"saved": False, "path": None, "status": 200}
        Path(path).write_bytes(resp.content)
        return {"saved": True, "path": path, "status": 200}

    # ---- misc ------------------------------------------------------------------------------
    def copy_text(self, text: str) -> dict:
        return {"ok": clipboard.copy_text(str(text))}

    def open_external(self, url: str) -> dict:
        if not isinstance(url, str) or not re.match(r"^https?://", url):
            return {"ok": False}
        return {"ok": bool(webbrowser.open(url))}

    def get_app_info(self) -> dict:
        try:
            import webview
            gui = getattr(webview, "guilib", None)
            gui_name = getattr(gui, "renderer", None) or (gui.__name__.split(".")[-1] if gui else None)
        except Exception:  # noqa: BLE001
            gui_name = None
        return {
            "version": __version__,
            "platform": sys.platform,
            "gui": gui_name,
            "frozen": is_frozen(),
            "data_dir": str(DATA_DIR),
            "gateway_url": getattr(self.gateway, "url", None),
        }
