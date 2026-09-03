/**
 * Single source of truth for how the UI reaches the backend.
 *
 * Desktop (pywebview): no HTTP at all. apiFetch() serialises the request and calls
 * window.pywebview.api.request(); the reply is rebuilt into a real Response.
 * Browser dev (vite + `python backend/main.py`): plain fetch against DEFAULT_BASE.
 */
import { getBridge, type BridgeFile } from "./bridge";

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

function splitUrl(input: string): { path: string; query: string } {
  let s = input;
  if (s.startsWith(DEFAULT_BASE)) s = s.slice(DEFAULT_BASE.length);
  const m = /^https?:\/\/[^/]+(\/.*)?$/.exec(s);
  if (m) s = m[1] || "/";
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

const NULL_BODY_STATUS = new Set([101, 204, 205, 304]);

export async function apiFetch(input: string, init: RequestInit = {}): Promise<Response> {
  const api = getBridge();
  if (!api) return fetch(input, init);

  const { path, query } = splitUrl(input);
  const method = (init.method || "GET").toUpperCase();
  const headers = normalizeHeaders(init.headers);
  let body: string | null = null;
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
    files.push({ field: "file", filename: "upload", content_type: init.body.type || "application/octet-stream", data_b64: await blobToBase64(init.body) });
  } else if (init.body != null) {
    body = String(init.body);
  }

  const call = api.request({ method, path, query, headers, body, files, fields });
  const result = init.signal ? await raceAbort(call, init.signal) : await call;

  const status = result.status >= 200 && result.status <= 599 ? result.status : 500;
  const payload: BodyInit | null = NULL_BODY_STATUS.has(status) ? null : result.body_b64 != null ? base64ToBytes(result.body_b64) : result.body ?? "";
  return new Response(payload, { status, headers: result.headers });
}
