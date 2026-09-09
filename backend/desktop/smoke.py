"""Packaged self-test: proves the app can render the UI and reach Python.

Windows WebView2 uses a visible host because hidden WinForms controllers are not reliable on
all supported Windows builds; the host is closed after the checks complete.
"""
from __future__ import annotations

import json
import threading
import time


def _eval(window, script, timeout=5.0):
    """evaluate_js that also resolves promises via callback."""
    result = {}
    done = threading.Event()

    def cb(value):
        result["value"] = value
        done.set()

    window.evaluate_js(script, callback=cb)
    done.wait(timeout)
    return result.get("value")


SMOKE_PLUGIN_ID = "plugin_orderflow"


def measure_h07_ui(window, fixture, *, size=100_000):
    """Measure the actual Journal/Evidence React path using an isolated fixture.

    Only the read adapter is substituted; HTTP routing, native bridge and React
    rendering remain real. This is synthetic diagnostic evidence, not onboarding
    or import/export end-to-end acceptance.
    """
    from pathlib import Path
    import tempfile
    from desktop.h07_worker import _validate_fixture, _copy_fixture, _fixture_adapter
    from app.api import endpoints

    metadata = _validate_fixture(fixture, size=size, seed="H07-SYNTHETIC-V1")
    previous = endpoints.trade_read_adapter
    with tempfile.TemporaryDirectory(prefix="h07-ui-") as directory:
        copied = Path(directory) / "synthetic.sqlite"
        _copy_fixture(fixture, copied)
        _, ledger, _, adapter = _fixture_adapter(copied)
        endpoints.trade_read_adapter = adapter
        try:
            # Fresh-profile persona prompt is dismissed through its own close handler.
            window.evaluate_js("""(() => {
              const heading = [...document.querySelectorAll('h2')].find(x => x.textContent === 'Select Architectural Persona');
              if (heading) heading.parentElement.parentElement.parentElement.querySelector('button').click();
              const nav = document.querySelector('[data-testid="nav-journal"]');
              if (!nav) throw Error('journal navigation missing'); nav.click();
            })()""")
            samples = []
            for mode in ("cold", "warm"):
                if mode == "cold":
                    ledger.close()
                result = _eval(window, """new Promise((resolve) => {
                  const deadline = performance.now() + 30000;
                  const ready = setInterval(() => {
                    const button = document.querySelector('button[title="Open source-linked Trade Evidence Pack"]');
                    if (!button) { if(performance.now()>deadline) {clearInterval(ready);resolve({status:'FAILED',reason:'journal timeout'});} return; }
                    clearInterval(ready);
                    const start = performance.now(); let last=start, maxGap=0, ticks=0, loading=false;
                    let health=null, read=null, renderedAt=null;
                    button.click();
                    const request = (path) => {const t=performance.now();return window.pywebview.api.request({method:'GET',path,query:'limit=1'}).then(r=>({status:r.status,elapsed_ms:performance.now()-t,completed_before_render:renderedAt===null}));};
                    setTimeout(()=>{request('/health').then(r=>health=r);request('/api/v1/trades').then(r=>read=r);}, 20);
                    const poll=setInterval(()=>{
                      const now=performance.now();maxGap=Math.max(maxGap,now-last);last=now;ticks++;
                      loading ||= !!document.querySelector('[data-testid="trade-evidence-cancel"]');
                      const rendered=document.querySelector('[data-testid="trade-evidence-coverage"]');
                      if(rendered && renderedAt===null) renderedAt=now;
                      if(rendered && health && read) {
                        clearInterval(poll);resolve({status:'MEASURED',elapsed_ms:renderedAt-start,max_timer_gap_ms:maxGap,timer_ticks:ticks,loading_observed:loading,health,read});
                      } else if(now>deadline) {clearInterval(poll);resolve({status:'FAILED',reason:'evidence timeout'});}
                    }, 25);
                  },25);
                })""", timeout=35)
                if not isinstance(result, dict) or result.get("status") != "MEASURED":
                    raise ValueError(f"native Evidence Pack measurement failed: {result}")
                if result["health"]["status"] != 200 or result["read"]["status"] != 200:
                    raise ValueError("concurrent local read failed")
                samples.append({"mode": mode, **result})
                window.evaluate_js("document.querySelector('[aria-label=\"Close Evidence Pack\"]').click()")
                time.sleep(0.1)
            return {"status": "MEASURED", "fixture": metadata, "samples": samples,
                    "adapter": "ISOLATED_SYNTHETIC", "process_cold": False,
                    "percentiles": "UNKNOWN_SINGLE_SAMPLE", "network_isolation": "NOT_VERIFIED"}
        finally:
            endpoints.trade_read_adapter = previous


def _toggle_plugin(ctx, enable: bool):
    return ctx.runtime.call(
        "POST", "/api/v1/plugins/toggle",
        headers={"Content-Type": "application/json"},
        body=json.dumps({"plugin_id": SMOKE_PLUGIN_ID, "enable": enable}).encode("utf-8"),
    )


def _check_plugin_boundary(ctx) -> bool:
    """Prove the packaged app rejects unsigned experimental runtime activation.

    The old smoke check activated ``plugin_orderflow`` and therefore encoded a
    prototype capability as a required production success path.  WP08 makes
    that route fail closed; the smoke test must verify the typed 503 boundary
    instead of trying to undo it after activation.
    """
    resp = _toggle_plugin(ctx, True)
    if resp.status != 503:
        return False
    try:
        payload = json.loads(resp.content)
        detail = payload.get("detail", payload)
    except (TypeError, ValueError):
        return False
    return (
        detail.get("status") == "EXPERIMENTAL_DISABLED"
        and detail.get("capability") == "plugin_runtime"
        and detail.get("execution_authority") is False
        and detail.get("data_connected") is False
        and detail.get("transport_connected") is False
    )


def run_smoke(window, ctx, timeout: float = 90.0) -> dict:
    checks = {"react_mounted": False, "bridge_roundtrip": False, "health": False, "push_sink": False,
              "plugin_boundary": False}
    # pywebview's evaluate_js waits 20 seconds per call when the native controller never became
    # ready. Check the readiness event once so a renderer failure produces a bounded diagnostic
    # instead of multiplying that wait across every smoke assertion.
    ready_event = getattr(getattr(window, "events", None), "_pywebviewready", None)
    if ready_event is not None and not ready_event.wait(timeout):
        return {"ok": False, "reason": "renderer controller did not become ready", "checks": checks}
    deadline = time.time() + timeout
    reason = "timeout"
    while time.time() < deadline:
        try:
            n = window.evaluate_js("(function(){var r=document.getElementById('root');return r?r.children.length:0})()")
            text = window.evaluate_js("(function(){var r=document.getElementById('root');return r?r.innerText.slice(0,60):''})()") or ""
            checks["react_mounted"] = bool(n) and "LOADING KUANTRA" not in text.upper()
            if checks["react_mounted"]:
                info = _eval(window, "window.pywebview.api.get_app_info()")
                checks["bridge_roundtrip"] = isinstance(info, dict) and "version" in info
                checks["push_sink"] = bool(window.evaluate_js("typeof window.__kuantraPush === 'function'"))
                resp = ctx.runtime.call("GET", "/health")
                checks["health"] = resp.status == 200 and json.loads(resp.content).get("status") == "online"
                if checks["health"] and not checks["plugin_boundary"]:
                    checks["plugin_boundary"] = _check_plugin_boundary(ctx)
            if all(checks.values()):
                return {"ok": True, "reason": "", "checks": checks}
        except Exception as exc:  # noqa: BLE001
            reason = f"{type(exc).__name__}: {exc}"
        time.sleep(0.5)
    return {"ok": False, "reason": reason, "checks": checks}
