import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

declare const globalThis: any;

function installBridge(impl: Partial<Record<string, any>>) {
  vi.stubGlobal("pywebview", { api: impl });
}

beforeEach(() => {
  vi.resetModules();
  vi.stubGlobal("window", globalThis);
  vi.stubGlobal("location", { protocol: "http:", href: "http://localhost:5173/" });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("apiFetch in desktop mode", () => {
  it("serialises a JSON POST and rebuilds a Response", async () => {
    const request = vi.fn(async (req: any) => ({ status: 200, headers: { "content-type": "application/json" }, body: JSON.stringify({ echo: req }), body_b64: null }));
    installBridge({ request });
    const { apiFetch, apiUrl } = await import("../backend");
    const res = await apiFetch(apiUrl("/api/v1/x?a=1"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ k: 1 }) });
    expect(res.ok).toBe(true);
    const data = await res.json();
    expect(data.echo.method).toBe("POST");
    expect(data.echo.path).toBe("/api/v1/x");
    expect(data.echo.query).toBe("a=1");
    expect(data.echo.body).toBe(JSON.stringify({ k: 1 }));
    expect(request).toHaveBeenCalledTimes(1);
  });

  it("encodes FormData files as base64", async () => {
    const request = vi.fn(async (req: any) => ({ status: 200, headers: {}, body: JSON.stringify(req.files), body_b64: null }));
    installBridge({ request });
    const { apiFetch, apiUrl } = await import("../backend");
    const fd = new FormData();
    fd.append("file", new File(["a,b\n1,2"], "t.csv", { type: "text/csv" }));
    fd.append("note", "hello");
    const res = await apiFetch(apiUrl("/api/v1/journal/preview-csv"), { method: "POST", body: fd });
    const files = await res.json();
    expect(files[0].field).toBe("file");
    expect(files[0].filename).toBe("t.csv");
    expect(atob(files[0].data_b64)).toBe("a,b\n1,2");
    expect(request.mock.calls[0][0].fields).toEqual([["note", "hello"]]);
  });

  it("sends a raw Blob body as body_b64 with the caller's content type", async () => {
    const request = vi.fn(async () => ({ status: 200, headers: {}, body: "{}", body_b64: null }));
    installBridge({ request });
    const { apiFetch } = await import("../backend");
    await apiFetch("/api/v1/upload", { method: "POST", headers: { "Content-Type": "application/pdf" }, body: new Blob(["%PDF-1.4"]) });
    const req = request.mock.calls[0][0] as any;
    expect(req.files).toEqual([]);
    expect(req.body).toBe(null);
    expect(atob(req.body_b64)).toBe("%PDF-1.4");
    expect(req.headers["Content-Type"]).toBe("application/pdf");
  });

  it("passes a third-party absolute URL through to real fetch", async () => {
    const request = vi.fn(async () => ({ status: 200, headers: {}, body: "{}", body_b64: null }));
    const fetchMock = vi.fn(async () => new Response("[]", { status: 200 }));
    installBridge({ request });
    vi.stubGlobal("fetch", fetchMock);
    const { apiFetch } = await import("../backend");
    const init: RequestInit = { method: "GET" };
    await apiFetch("https://api.binance.com/api/v3/time", init);
    expect(request).not.toHaveBeenCalled();
    expect(fetchMock).toHaveBeenCalledWith("https://api.binance.com/api/v3/time", init);
    // ...while our own backend still goes through the bridge, absolute or not.
    await apiFetch("http://127.0.0.1:8000/api/v1/x");
    await apiFetch("/api/v1/y");
    expect(request).toHaveBeenCalledTimes(2);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("maps non-2xx to ok=false and decodes base64 bodies", async () => {
    installBridge({ request: async () => ({ status: 404, headers: {}, body: null, body_b64: btoa("nope") }) });
    const { apiFetch } = await import("../backend");
    const res = await apiFetch("/api/v1/missing");
    expect(res.ok).toBe(false);
    expect(res.status).toBe(404);
    expect(await res.text()).toBe("nope");
  });

  it("clamps an out-of-range status to 500 and keeps the body", async () => {
    installBridge({ request: async () => ({ status: 101, headers: {}, body: "switching", body_b64: null }) });
    const { apiFetch } = await import("../backend");
    const res = await apiFetch("/api/v1/upgrade");
    expect(res.status).toBe(500);
    expect(await res.text()).toBe("switching");
  });

  it("rejects with AbortError when the signal fires", async () => {
    installBridge({ request: () => new Promise(() => {}) });
    const { apiFetch } = await import("../backend");
    const c = new AbortController();
    const p = apiFetch("/slow", { signal: c.signal });
    c.abort();
    await expect(p).rejects.toMatchObject({ name: "AbortError" });
  });

  it("apiUrl/apiBase are path-only in desktop mode", async () => {
    installBridge({ request: async () => ({ status: 200, headers: {}, body: "{}", body_b64: null }) });
    const { apiUrl, apiBase } = await import("../backend");
    expect(apiUrl("/api/v1/x")).toBe("/api/v1/x");
    expect(apiBase()).toBe("");
  });

  it("uses a bounded background job for desktop Evidence Pack reads", async () => {
    const start_evidence_pack = vi.fn(async (spec: any) => ({ job_id: "a".repeat(32), status: "PENDING", spec }));
    let polls = 0;
    const get_evidence_pack_job = vi.fn(async () => {
      polls += 1;
      return polls === 1
        ? { job_id: "a".repeat(32), status: "PENDING" }
        : { job_id: "a".repeat(32), status: "COMPLETED", response: { status: 200, headers: { "content-type": "application/json" }, body: JSON.stringify({ event_count: 2 }), body_b64: null } };
    });
    installBridge({ request: vi.fn(), start_evidence_pack, get_evidence_pack_job });
    const { fetchEvidencePack } = await import("../backend");

    const result = await fetchEvidencePack("TRD/1");
    expect(result.status).toBe(200);
    expect(await result.json()).toEqual({ event_count: 2 });
    expect(start_evidence_pack).toHaveBeenCalledWith({ trade_id: "TRD/1" });
    expect(get_evidence_pack_job).toHaveBeenCalledWith({ job_id: "a".repeat(32) });
  });

  it("aborts a pending desktop Evidence Pack job", async () => {
    const controller = new AbortController();
    installBridge({
      request: vi.fn(),
      start_evidence_pack: vi.fn(async () => ({ job_id: "b".repeat(32), status: "PENDING" })),
      get_evidence_pack_job: vi.fn(() => new Promise(() => {})),
    });
    const { fetchEvidencePack } = await import("../backend");
    const pending = fetchEvidencePack("TRD-1", controller.signal);
    await Promise.resolve();
    controller.abort();
    await expect(pending).rejects.toMatchObject({ name: "AbortError" });
  });
});

describe("apiFetch in browser dev mode", () => {
  it("delegates to window.fetch with the default base and forwards init untouched", async () => {
    const fetchMock = vi.fn(async (_input: any, _init?: any) => new Response("{}", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const { apiFetch, apiUrl, apiBase, wsUrl } = await import("../backend");
    expect(apiBase()).toBe("http://127.0.0.1:8000");
    expect(wsUrl("/api/v1/ws/stream")).toBe("ws://127.0.0.1:8000/api/v1/ws/stream");
    const init: RequestInit = { method: "POST", headers: { "X-Test": "1" }, body: "payload" };
    await apiFetch(apiUrl("/api/v1/x"), init);
    expect(fetchMock).toHaveBeenCalledWith("http://127.0.0.1:8000/api/v1/x", init);
    // The very same object, not a copy: no serialisation happens outside the desktop app.
    expect(fetchMock.mock.calls[0][1]).toBe(init);
  });
});
