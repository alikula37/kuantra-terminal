"""
DesktopBridge is the object pywebview exposes as window.pywebview.api. Every public method is
synchronous (pywebview runs each call on its own thread) and takes/returns JSON-compatible data.
"""
from __future__ import annotations

import base64
import binascii
from functools import lru_cache
import json
import logging
import mimetypes
import re
import sys
import threading
import time
import uuid
import webbrowser
from asyncio import CancelledError
from concurrent.futures import CancelledError as FuturesCancelledError
from concurrent.futures import Future, ProcessPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import quote, unquote, urlsplit

from app.core.input_limits import MAX_BRIDGE_BODY_BYTES, MAX_BRIDGE_FILES, MAX_BRIDGE_TEXT_BYTES
from app.core.paths import DATA_DIR, is_frozen
from app.version import __version__
from desktop import clipboard
from desktop.push import PushChannel
from desktop.runtime import BackendRuntime, BridgeResponse, RuntimeStopped

logger = logging.getLogger("desktop.bridge")

TEXT_TYPES = ("application/json", "text/", "application/xml", "application/javascript", "application/problem+json")

# Hop-by-hop and framing headers describe the transport we do not have. Passing them to fetch()
# in the UI makes it disagree with the body we actually hand over (notably content-length, which
# counts bytes, not the decoded string).
HOP_BY_HOP_HEADERS = {
    "content-length", "content-encoding", "transfer-encoding", "connection", "keep-alive", "upgrade",
}


def _is_text(content_type: str) -> bool:
    ct = (content_type or "").lower()
    return any(ct.startswith(t) for t in TEXT_TYPES)


def _passthrough_headers(headers) -> dict:
    return {k: v for k, v in headers.items() if k.lower() not in HOP_BY_HOP_HEADERS}


def _bridge_response(resp) -> dict:
    headers = _passthrough_headers(resp.headers)
    content_type = resp.headers.get("content-type", "")
    if _is_text(content_type) or not resp.content:
        return {
            "status": resp.status,
            "headers": headers,
            "body": resp.content.decode("utf-8", errors="replace"),
            "body_b64": None,
        }
    return {
        "status": resp.status,
        "headers": headers,
        "body": None,
        "body_b64": base64.b64encode(resp.content).decode("ascii"),
    }


def _bridge_error(detail: str, status: int = 400) -> dict:
    safe_detail = json.dumps(str(detail), ensure_ascii=True)
    return {
        "status": status,
        "headers": {"content-type": "application/json"},
        "body": '{"detail":' + safe_detail + '}',
        "body_b64": None,
    }


def _decode_base64(value, *, label: str, limit: int = MAX_BRIDGE_BODY_BYTES) -> bytes:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a base64 string")
    try:
        decoded = base64.b64decode(value.encode("ascii"), validate=True)
    except (UnicodeEncodeError, ValueError, binascii.Error) as exc:
        raise ValueError(f"{label} is not valid base64") from exc
    if len(decoded) > limit:
        raise ValueError(f"{label} exceeds the safety size limit of {limit} bytes")
    return decoded


def _bounded_text(value, *, label: str, limit: int = MAX_BRIDGE_TEXT_BYTES) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be text")
    if any(ord(character) < 32 and character not in "\t\n\r" for character in value):
        raise ValueError(f"{label} contains a control character")
    if len(value.encode("utf-8")) > limit:
        raise ValueError(f"{label} exceeds the safety size limit of {limit} bytes")
    return value


def _safe_backend_path(value: str) -> str:
    path = _bounded_text(value, label="path")
    if not path.startswith("/") or path.startswith("//"):
        raise ValueError("path must be an internal absolute route")
    decoded = unquote(path)
    if any(part == ".." for part in decoded.split("/")) or any(part == ".." for part in path.split("/")):
        raise ValueError("path traversal is not allowed")
    if path == "/health" or path == "/api/v1" or path.startswith("/api/v1/"):
        return path
    if path == "/plugins" or path.startswith("/plugins/"):
        return path
    raise ValueError("path is outside the desktop API allowlist")


def _safe_filename(value: str, *, default: str = "download") -> str:
    filename = _bounded_text(value, label="filename", limit=160).strip()
    if not filename or filename in {".", ".."} or Path(filename).name != filename:
        return default
    return filename


@lru_cache(maxsize=4)
def _evidence_pack_adapter(
    db_path: str,
    account_id: str,
    venue: str,
    projection_venues: tuple[str, ...],
):
    """Create a bounded, process-local read adapter for repeated pack reads."""
    from app.db.repositories.evidence_ledger_repo import EvidenceLedgerRepository
    from app.db.repositories.evidence_projection_repo import EvidenceTradeProjectionRepository
    from app.db.sqlite_driver import SQLiteDriver
    from app.services.trade_read_adapter import TradeReadAdapter

    driver = SQLiteDriver(db_path)
    ledger = EvidenceLedgerRepository(db_path)
    projection = EvidenceTradeProjectionRepository(db_path)
    return TradeReadAdapter(
        legacy_driver=driver,
        projection_repo=projection,
        ledger_repo=ledger,
        account_id=account_id,
        venue=venue,
        projection_venues=projection_venues,
    )


def _evidence_pack_worker(
    db_path: str,
    account_id: str,
    venue: str,
    projection_venues: tuple[str, ...],
    trade_id: str,
) -> BridgeResponse:
    """Build one read-only Evidence Pack outside the desktop process.

    The worker reconstructs only the existing local read adapter from the supplied SQLite path.
    It does not start the app, market-data connector, gateway, or a second web server. Keeping
    this function at module scope also makes its process-pool contract explicit and picklable on
    macOS spawn.
    """
    adapter = _evidence_pack_adapter(db_path, account_id, venue, projection_venues)
    pack = adapter.get_evidence_pack(trade_id)
    if pack["trade"] is None and pack["event_count"] == 0:
        return BridgeResponse(
            status=404,
            headers={"content-type": "application/json"},
            content=b'{"detail":"Trade evidence not found"}',
        )
    return BridgeResponse(
        status=200,
        headers={"content-type": "application/json"},
        content=json.dumps(pack, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8"),
    )


class DesktopBridge:
    _MAX_EVIDENCE_PACK_JOBS = 4
    _EVIDENCE_PACK_JOB_TTL_SECONDS = 300.0
    _EVIDENCE_PACK_JOB_ID = re.compile(r"^[0-9a-f]{32}$")

    def __init__(
        self,
        runtime: BackendRuntime,
        push: PushChannel,
        gateway=None,
        index_url: str = "",
        windows_getter: Optional[Callable[[], list]] = None,
        dialog_window_getter: Optional[Callable[[], object]] = None,
    ):
        # Leading underscore is load-bearing: pywebview walks the js_api object's public
        # attributes and recursively exposes non-callable ones to JavaScript.
        self._runtime = runtime
        self._push = push
        self._gateway = gateway
        self._index_url = index_url
        self._windows = windows_getter or (lambda: [])
        self._dialog_window = dialog_window_getter
        self._stream_attached = False
        self._popouts: dict[str, object] = {}
        # Evidence Pack generation can verify a large append-only chain. Keep that work off the
        # pywebview bridge thread, but bound retained jobs so an aborted UI cannot grow memory.
        self._evidence_jobs: dict[str, tuple[Future, float]] = {}
        self._evidence_jobs_lock = threading.Lock()
        self._evidence_executor: Optional[ProcessPoolExecutor] = None
        self._evidence_jobs_closed = False

    # ---- HTTP-shaped requests, no HTTP ---------------------------------------------------
    def request(self, req: dict) -> dict:
        try:
            if not isinstance(req, dict):
                raise ValueError("bridge request must be an object")
            method = _bounded_text(str(req.get("method", "GET")).upper(), label="method", limit=16)
            if method not in {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"}:
                raise ValueError("method is not allowed")
            path = _safe_backend_path(req.get("path", "/"))
            query = _bounded_text(str(req.get("query", "")), label="query")

            files_spec = req.get("files") or []
            if not isinstance(files_spec, list) or len(files_spec) > MAX_BRIDGE_FILES:
                raise ValueError("files must be a bounded list")
            files = []
            total_file_bytes = 0
            for file_spec in files_spec:
                if not isinstance(file_spec, dict):
                    raise ValueError("file parts must be objects")
                field = _bounded_text(file_spec.get("field"), label="file field", limit=160)
                filename = _safe_filename(file_spec.get("filename") or "upload", default="upload")
                raw = _decode_base64(file_spec.get("data_b64"), label="file data")
                content_type = _bounded_text(
                    file_spec.get("content_type") or "application/octet-stream",
                    label="file content type",
                    limit=160,
                )
                total_file_bytes += len(raw)
                files.append((field, filename, raw, content_type))
            if total_file_bytes > MAX_BRIDGE_BODY_BYTES:
                raise ValueError(f"file payload exceeds the safety size limit of {MAX_BRIDGE_BODY_BYTES} bytes")

            fields_spec = req.get("fields") or []
            if not isinstance(fields_spec, list) or len(fields_spec) > 64:
                raise ValueError("fields must be a bounded list")
            fields = []
            for pair in fields_spec:
                if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                    raise ValueError("field entries must be two-item pairs")
                fields.append((
                    _bounded_text(pair[0], label="field name", limit=160),
                    _bounded_text(pair[1], label="field value"),
                ))

            body = req.get("body")
            body_bytes = _bounded_text(body, label="body").encode("utf-8") if body is not None else None
            if req.get("body_b64") is not None:
                if body is not None:
                    raise ValueError("body and body_b64 are mutually exclusive")
                body_bytes = _decode_base64(req["body_b64"], label="body data")
            if body_bytes is not None and len(body_bytes) > MAX_BRIDGE_BODY_BYTES:
                raise ValueError(f"body exceeds the safety size limit of {MAX_BRIDGE_BODY_BYTES} bytes")
            if files and body_bytes is not None:
                raise ValueError("multipart files cannot be combined with a raw body")

            headers_spec = req.get("headers") or {}
            if not isinstance(headers_spec, dict) or len(headers_spec) > 64:
                raise ValueError("headers must be a bounded object")
            headers = {}
            forbidden_request_headers = {
                "connection", "content-length", "host", "keep-alive", "origin",
                "transfer-encoding", "upgrade", "forwarded", "x-forwarded-host",
                "x-forwarded-proto",
            }
            for key, value in headers_spec.items():
                normalized_key = _bounded_text(key, label="header name", limit=160)
                if normalized_key.lower() in forbidden_request_headers:
                    raise ValueError(f"request header is not allowed: {normalized_key}")
                headers[normalized_key] = _bounded_text(value, label="header value")
        except (KeyError, TypeError, ValueError) as exc:
            return _bridge_error(str(exc))
        try:
            resp = self._runtime.call(
                method, path, query,
                headers=headers, body=body_bytes, files=files or None, fields=fields or None,
            )
        except (RuntimeStopped, CancelledError, FuturesCancelledError) as exc:
            # The backend loop is gone (app is closing). Answer the UI instead of hanging its thread.
            logger.debug("request during shutdown: %s", exc)
            return {"status": 503, "headers": {"content-type": "application/json"},
                    "body": '{"detail":"backend unavailable"}', "body_b64": None}
        except FuturesTimeoutError:
            logger.warning("request timed out: %s %s", req.get("method", "GET"), req.get("path", "/"))
            return {"status": 504, "headers": {"content-type": "application/json"},
                    "body": '{"detail":"backend timed out"}', "body_b64": None}
        return _bridge_response(resp)

    # ---- asynchronous Evidence Pack reads ------------------------------------------------
    def start_evidence_pack(self, spec: dict) -> dict:
        """Queue one bounded read without holding the pywebview bridge thread.

        This is deliberately a read-only, internal route. It does not add a ledger event type,
        connector, or execution capability; it only changes how the existing Evidence Pack read
        is scheduled in the desktop shell.
        """
        try:
            if not isinstance(spec, dict):
                raise ValueError("evidence job spec must be an object")
            if set(spec) - {"trade_id"}:
                raise ValueError("evidence job fields are not allowed")
            trade_id = _bounded_text(spec.get("trade_id"), label="trade_id", limit=256).strip()
            if not trade_id:
                raise ValueError("trade_id must not be empty")
            path = _safe_backend_path(f"/api/v1/trades/{quote(trade_id, safe='')}/evidence")
        except (TypeError, ValueError) as exc:
            return {"job_id": "", "status": "REJECTED", "response": _bridge_error(str(exc))}

        now = time.monotonic()
        with self._evidence_jobs_lock:
            if self._evidence_jobs_closed:
                return {"job_id": "", "status": "REJECTED", "response": _bridge_error("backend unavailable", 503)}
            for job_id, (future, created_at) in list(self._evidence_jobs.items()):
                if future.done() and now - created_at > self._EVIDENCE_PACK_JOB_TTL_SECONDS:
                    self._evidence_jobs.pop(job_id, None)
            if len(self._evidence_jobs) >= self._MAX_EVIDENCE_PACK_JOBS:
                return {"job_id": "", "status": "REJECTED", "response": _bridge_error("evidence job queue is full", 429)}
            from app.api import endpoints
            adapter = endpoints.trade_read_adapter
            ledger = getattr(adapter, "ledger_repo", None)
            db_path = getattr(ledger, "db_path", None)
            account_id = getattr(adapter, "account_id", None)
            venue = getattr(adapter, "venue", None)
            projection_venues = getattr(adapter, "projection_venues", None)
            if not isinstance(db_path, str) or not db_path:
                return {"job_id": "", "status": "REJECTED", "response": _bridge_error("backend unavailable", 503)}
            if not isinstance(account_id, str) or not account_id or not isinstance(venue, str) or not venue:
                return {"job_id": "", "status": "REJECTED", "response": _bridge_error("backend unavailable", 503)}
            if not isinstance(projection_venues, tuple) or not all(isinstance(item, str) and item for item in projection_venues):
                return {"job_id": "", "status": "REJECTED", "response": _bridge_error("backend unavailable", 503)}
            job_id = uuid.uuid4().hex
            try:
                if self._evidence_executor is None:
                    self._evidence_executor = ProcessPoolExecutor(max_workers=1)
                future = self._evidence_executor.submit(
                    _evidence_pack_worker,
                    db_path,
                    account_id,
                    venue,
                    projection_venues,
                    trade_id,
                )
            except RuntimeError:
                return {"job_id": "", "status": "REJECTED", "response": _bridge_error("backend unavailable", 503)}
            self._evidence_jobs[job_id] = (future, now)
        return {"job_id": job_id, "status": "PENDING"}

    def get_evidence_pack_job(self, spec: dict) -> dict:
        try:
            if not isinstance(spec, dict):
                raise ValueError("evidence job poll must be an object")
            if set(spec) - {"job_id"}:
                raise ValueError("evidence job poll fields are not allowed")
            job_id = _bounded_text(spec.get("job_id"), label="job_id", limit=64)
            if not self._EVIDENCE_PACK_JOB_ID.fullmatch(job_id):
                raise ValueError("job_id is invalid")
        except (TypeError, ValueError) as exc:
            return {"job_id": "", "status": "FAILED", "response": _bridge_error(str(exc))}

        with self._evidence_jobs_lock:
            entry = self._evidence_jobs.get(job_id)
        if entry is None:
            return {"job_id": job_id, "status": "FAILED", "response": _bridge_error("evidence job not found", 404)}
        future, _created_at = entry
        if not future.done():
            return {"job_id": job_id, "status": "PENDING"}

        try:
            response = _bridge_response(future.result())
            status = "COMPLETED"
        except (RuntimeStopped, CancelledError, FuturesCancelledError):
            response = _bridge_error("backend unavailable", 503)
            status = "FAILED"
        except Exception:  # noqa: BLE001 - do not expose worker internals to the UI
            logger.exception("Evidence Pack job failed")
            response = _bridge_error("evidence job failed", 500)
            status = "FAILED"
        with self._evidence_jobs_lock:
            self._evidence_jobs.pop(job_id, None)
        return {"job_id": job_id, "status": status, "response": response}

    def _close(self) -> None:
        with self._evidence_jobs_lock:
            if self._evidence_jobs_closed:
                return
            self._evidence_jobs_closed = True
            executor = self._evidence_executor
            self._evidence_executor = None
        if executor is not None:
            executor.shutdown(wait=True, cancel_futures=True)

    # ---- live stream -----------------------------------------------------------------------
    def stream_open(self) -> dict:
        from app.websocket.binance_client import binance_client
        from app.websocket.connection_manager import ws_manager

        async def _attach():
            if not self._stream_attached:
                ws_manager.attach(self._push, PushChannel.CHANNELS)
                self._stream_attached = True
            return {
                "type": "SNAPSHOT",
                "symbol": binance_client.symbol,
                "last_price": binance_client.last_price,
                "event_age_ms": binance_client.event_age_ms,
                "timestamp": int(binance_client.last_tick_time * 1000) if binance_client.last_tick_time is not None else None,
                "status": binance_client.market_data_status,
                "market_data_enabled": binance_client.market_data_enabled,
                "open_positions": binance_client._recalculate_open_positions(binance_client.last_price),
            }

        return self._runtime.run(_attach())

    # ---- windows ---------------------------------------------------------------------------
    def open_popout(self, spec: dict) -> dict:
        import webview
        try:
            if not isinstance(spec, dict):
                raise ValueError("popout spec must be an object")
            label = re.sub(
                r"[^a-z0-9]",
                "-",
                _safe_filename(spec.get("label", "panel"), default="panel").lower(),
            )
            query = _bounded_text(str(spec.get("query", "")).lstrip("?"), label="query")
            title = _bounded_text(str(spec.get("title", "Kuantra Terminal")), label="title", limit=160)
            width = max(600, min(2400, int(spec.get("width", 1024))))
            height = max(400, min(1600, int(spec.get("height", 700))))
        except (TypeError, ValueError):
            return {"created": False, "label": "", "reason": "invalid popout payload"}
        existing = self._popouts.get(label)
        if existing is not None and existing in webview.windows:
            try:
                existing.restore()
            except Exception:  # noqa: BLE001
                pass
            return {"created": False, "label": label}
        url = f"{self._index_url}?{query}" if query else self._index_url
        win = webview.create_window(
            title, url=url, js_api=self,
            width=width, height=height,
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
        try:
            if not isinstance(spec, dict):
                raise ValueError("file spec must be an object")
            filename = _safe_filename(spec.get("filename") or "download")
            data = spec.get("content") or ""
            if spec.get("encoding") == "base64":
                raw = _decode_base64(data, label="file content")
            elif spec.get("encoding") in {None, "text"}:
                raw = _bounded_text(data, label="file content", limit=MAX_BRIDGE_BODY_BYTES).encode("utf-8")
            else:
                raise ValueError("file encoding is not allowed")
        except (TypeError, ValueError) as exc:
            logger.warning("save_file rejected: %s", exc)
            return {"saved": False, "path": None, "reason": "invalid file payload"}
        path = self._pick_save_path(filename)
        if not path:
            return {"saved": False, "path": None}
        try:
            Path(path).write_bytes(raw)
        except OSError:
            return {"saved": False, "path": None}
        return {"saved": True, "path": path}

    def download(self, spec: dict) -> dict:
        try:
            path = _safe_backend_path(spec["path"])
            query = _bounded_text(str(spec.get("query", "")), label="query")
        except (KeyError, TypeError, ValueError):
            return {"saved": False, "path": None, "status": 400}
        resp = self._runtime.call("GET", path, query)
        if resp.status != 200:
            return {"saved": False, "path": None, "status": resp.status}
        if len(resp.content) > MAX_BRIDGE_BODY_BYTES:
            return {"saved": False, "path": None, "status": 413}
        filename = spec.get("filename")
        disposition = resp.headers.get("content-disposition", "")
        m = re.search(r'filename="?([^";]+)"?', disposition)
        if m:
            filename = m.group(1)
        if not filename:
            ext = mimetypes.guess_extension(resp.headers.get("content-type", "").split(";")[0]) or ""
            filename = f"kuantra-download{ext}"
        try:
            filename = _safe_filename(filename)
        except (TypeError, ValueError):
            filename = "kuantra-download"
        path = self._pick_save_path(filename)
        if not path:
            return {"saved": False, "path": None, "status": 200}
        try:
            Path(path).write_bytes(resp.content)
        except OSError:
            return {"saved": False, "path": None, "status": 500}
        return {"saved": True, "path": path, "status": 200}

    # ---- misc ------------------------------------------------------------------------------
    def copy_text(self, text: str) -> dict:
        try:
            bounded = _bounded_text(text, label="clipboard text", limit=MAX_BRIDGE_BODY_BYTES)
        except (TypeError, ValueError):
            return {"ok": False}
        return {"ok": clipboard.copy_text(bounded)}

    def open_external(self, url: str) -> dict:
        if not isinstance(url, str) or len(url) > 2048:
            return {"ok": False}
        try:
            parsed = urlsplit(url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                return {"ok": False}
            if parsed.username or parsed.password or parsed.hostname is None:
                return {"ok": False}
            if parsed.port is not None and not (1 <= parsed.port <= 65535):
                return {"ok": False}
            if any(ord(character) < 32 for character in url):
                return {"ok": False}
        except ValueError:
            return {"ok": False}
        return {"ok": bool(webbrowser.open(parsed.geturl()))}

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
            "gateway_url": getattr(self._gateway, "url", None),
        }
