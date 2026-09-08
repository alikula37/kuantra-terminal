/** Typed access to window.pywebview.api (the Python DesktopBridge). Null outside the desktop app. */
import type { MarketDataStatus } from "../types";

export interface BridgeFile { field: string; filename: string; content_type: string; data_b64: string; }
export interface BridgeRequest {
  method: string; path: string; query: string; headers: Record<string, string>;
  body: string | null; body_b64?: string | null; files: BridgeFile[]; fields: [string, string][];
}
export interface BridgeResponse { status: number; headers: Record<string, string>; body: string | null; body_b64: string | null; }
export interface StreamSnapshot {
  type: "SNAPSHOT";
  symbol: string;
  last_price: number | null;
  event_age_ms: number | null;
  timestamp: number | null;
  status: MarketDataStatus;
  market_data_enabled?: boolean;
  open_positions: unknown[];
}
export interface AppInfo { version: string; platform: string; gui: string | null; frozen: boolean; data_dir: string; gateway_url: string | null; }
export interface BridgeApi {
  request(req: BridgeRequest): Promise<BridgeResponse>;
  stream_open(): Promise<StreamSnapshot>;
  open_popout(spec: { label: string; title: string; query: string; width: number; height: number }): Promise<{ created: boolean; label: string }>;
  save_file(spec: { filename: string; content: string; encoding: "text" | "base64"; mime?: string }): Promise<{ saved: boolean; path: string | null }>;
  download(spec: { path: string; query?: string; filename?: string }): Promise<{ saved: boolean; path: string | null; status?: number }>;
  copy_text(text: string): Promise<{ ok: boolean }>;
  open_external(url: string): Promise<{ ok: boolean }>;
  get_app_info(): Promise<AppInfo>;
}

function host(): any {
  return typeof window !== "undefined" ? (window as any) : (globalThis as any);
}

export function getBridge(): BridgeApi | null {
  const api = host().pywebview?.api;
  return api && typeof api.request === "function" ? (api as BridgeApi) : null;
}

export function isDesktop(): boolean {
  return getBridge() !== null;
}

/** Expected to run inside pywebview when served from file:// (or when pywebview is already injected). */
export function expectsDesktop(): boolean {
  const loc = host().location;
  return !!getBridge() || (!!loc && loc.protocol === "file:");
}

/** Resolve once pywebview has injected its API (it fires `pywebviewready`), or null after the timeout. */
export function bridgeReady(timeoutMs = expectsDesktop() ? 30000 : 0): Promise<BridgeApi | null> {
  const existing = getBridge();
  if (existing || timeoutMs <= 0) return Promise.resolve(existing);
  return new Promise((resolve) => {
    const timer = setTimeout(() => { cleanup(); resolve(getBridge()); }, timeoutMs);
    const onReady = () => { cleanup(); resolve(getBridge()); };
    const cleanup = () => { clearTimeout(timer); host().removeEventListener?.("pywebviewready", onReady); };
    host().addEventListener?.("pywebviewready", onReady);
  });
}
