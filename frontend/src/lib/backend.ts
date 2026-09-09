/**
 * Single source of truth for how the UI reaches the backend.
 *
 * Desktop (pywebview): no HTTP at all. apiFetch() serialises the request and calls
 * window.pywebview.api.request(); the reply is rebuilt into a real Response.
 * Browser dev (vite + `python backend/main.py`): plain fetch against DEFAULT_BASE.
 */
import { getBridge, type BridgeFile, type BridgeResponse } from "./bridge";

export const DEFAULT_BASE = "http://127.0.0.1:8000";

export function apiBase(): string {
  return getBridge() ? "" : DEFAULT_BASE;
}

export function apiUrl(path: string): string {
  return `${apiBase()}${path}`;
}

export function wsUrl(path: string): string {
  return `${DEFAULT_BASE.replace(/^http/, "ws")}${path}`;
}

/** True for our own backend: a relative URL, or an absolute one under DEFAULT_BASE. */
function isBackendUrl(input: string): boolean {
  if (!/^[a-z][a-z0-9+.-]*:/i.test(input) && !input.startsWith("//")) return true;
  return input === DEFAULT_BASE || input.startsWith(`${DEFAULT_BASE}/`) || input.startsWith(`${DEFAULT_BASE}?`);
}

function splitUrl(input: string): { path: string; query: string } {
  let s = input;
  if (s.startsWith(DEFAULT_BASE)) s = s.slice(DEFAULT_BASE.length) || "/";
  const q = s.indexOf("?");
  return q === -1 ? { path: s, query: "" } : { path: s.slice(0, q), query: s.slice(q + 1) };
}

function normalizeHeaders(h: HeadersInit | undefined): Record<string, string> {
  const out: Record<string, string> = {};
  if (!h) return out;
  if (typeof Headers !== "undefined" && h instanceof Headers) h.forEach((v, k) => (out[k] = v));
  else if (Array.isArray(h)) h.forEach(([k, v]) => (out[k] = v));
  else Object.entries(h).forEach(([k, v]) => (out[k] = String(v)));
  return out;
}

async function blobToBase64(blob: Blob): Promise<string> {
  const bytes = new Uint8Array(await blob.arrayBuffer());
  let bin = "";
  for (let i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(bin);
}

function base64ToBytes(b64: string): Uint8Array<ArrayBuffer> {
  const bin = atob(b64);
  // Backed by a plain ArrayBuffer (not ArrayBufferLike) so it satisfies BodyInit under TS 5.7 libs.
  const out = new Uint8Array(new ArrayBuffer(bin.length));
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

function abortError(): Error {
  const e = new Error("The operation was aborted.");
  e.name = "AbortError";
  return e;
}

function raceAbort<T>(p: Promise<T>, signal: AbortSignal): Promise<T> {
  if (signal.aborted) return Promise.reject(abortError());
  return new Promise<T>((resolve, reject) => {
    const onAbort = () => reject(abortError());
    signal.addEventListener("abort", onAbort, { once: true });
    p.then((v) => { signal.removeEventListener("abort", onAbort); resolve(v); },
           (e) => { signal.removeEventListener("abort", onAbort); reject(e); });
  });
}

// 101 is intentionally absent: the clamp below already rewrites anything under 200 to 500.
const NULL_BODY_STATUS = new Set([204, 205, 304]);

function bridgeResponseToResponse(result: BridgeResponse): Response {
  const status = result.status >= 200 && result.status <= 599 ? result.status : 500;
  const payload: BodyInit | null = NULL_BODY_STATUS.has(status) ? null : result.body_b64 != null ? base64ToBytes(result.body_b64) : result.body ?? "";
  return new Response(payload, { status, headers: result.headers });
}

export async function apiFetch(input: string, init: RequestInit = {}): Promise<Response> {
  const api = getBridge();
  // A third-party absolute URL (an exchange API, a CDN) is not ours to route through the bridge:
  // the backend would try to serve it as one of its own paths. Only our own backend is bridged.
  if (!api || !isBackendUrl(input)) return fetch(input, init);

  const { path, query } = splitUrl(input);
  const method = (init.method || "GET").toUpperCase();
  const headers = normalizeHeaders(init.headers);
  let body: string | null = null;
  let bodyB64: string | null = null;
  const files: BridgeFile[] = [];
  const fields: [string, string][] = [];

  if (typeof FormData !== "undefined" && init.body instanceof FormData) {
    for (const [k, v] of (init.body as any).entries() as Iterable<[string, FormDataEntryValue]>) {
      if (typeof v === "string") fields.push([k, v]);
      else files.push({ field: k, filename: (v as File).name || "upload", content_type: v.type || "application/octet-stream", data_b64: await blobToBase64(v) });
    }
  } else if (typeof init.body === "string") {
    body = init.body;
  } else if (init.body instanceof Blob) {
    // fetch() would send a bare Blob as the raw request body, so the bridge does the same:
    // wrapping it in a multipart part named "file" would silently change the request shape.
    bodyB64 = await blobToBase64(init.body);
    if (!Object.keys(headers).some((k) => k.toLowerCase() === "content-type") && init.body.type) headers["Content-Type"] = init.body.type;
  } else if (init.body != null) {
    body = String(init.body);
  }

  const call = api.request({ method, path, query, headers, body, body_b64: bodyB64, files, fields });
  const result = init.signal ? await raceAbort(call, init.signal) : await call;

  return bridgeResponseToResponse(result);
}

const EVIDENCE_PACK_JOB_TIMEOUT_MS = 120_000;
const EVIDENCE_PACK_JOB_POLL_MS = 25;

function localErrorResponse(status: number, detail: string): Response {
  return new Response(JSON.stringify({ detail }), {
    status,
    headers: { "content-type": "application/json" },
  });
}

/**
 * Load an Evidence Pack without synchronously occupying the native pywebview bridge thread.
 * Browser development keeps the ordinary fetch path; only the desktop bridge uses the job API.
 */
export async function fetchEvidencePack(tradeId: string, signal?: AbortSignal): Promise<Response> {
  const path = `/api/v1/trades/${encodeURIComponent(tradeId)}/evidence`;
  const api = getBridge();
  if (!api || typeof api.start_evidence_pack !== "function" || typeof api.get_evidence_pack_job !== "function") {
    return apiFetch(apiUrl(path), { signal });
  }

  const start = signal
    ? await raceAbort(api.start_evidence_pack({ trade_id: tradeId }), signal)
    : await api.start_evidence_pack({ trade_id: tradeId });
  if (start.status !== "PENDING") {
    return start.response ? bridgeResponseToResponse(start.response) : localErrorResponse(503, "Evidence Pack job was not accepted.");
  }

  const deadline = Date.now() + EVIDENCE_PACK_JOB_TIMEOUT_MS;
  while (Date.now() < deadline) {
    const job = signal
      ? await raceAbort(api.get_evidence_pack_job({ job_id: start.job_id }), signal)
      : await api.get_evidence_pack_job({ job_id: start.job_id });
    if (job.status !== "PENDING") {
      return job.response ? bridgeResponseToResponse(job.response) : localErrorResponse(502, "Evidence Pack job returned no response.");
    }
    const pause = new Promise<void>((resolve) => window.setTimeout(resolve, EVIDENCE_PACK_JOB_POLL_MS));
    if (signal) await raceAbort(pause, signal);
    else await pause;
  }
  return localErrorResponse(504, "Evidence Pack job timed out.");
}
