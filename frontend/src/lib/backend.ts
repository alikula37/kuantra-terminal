/**
 * Single source of truth for the backend base URL.
 *
 * In the packaged Tauri app the Python sidecar is started with `--port 0`
 * and reports the ephemeral port it bound to. The Rust side exposes that port
 * through the `get_backend_port` command. Nothing in the frontend may
 * hardcode `127.0.0.1:8000`: in a packaged build that port belongs to whatever
 * else happens to be listening on the user's machine, not to Kuantra.
 *
 * In plain browser/dev mode (no Tauri runtime) we fall back to the default
 * port used by `python backend/main.py`.
 */

const DEFAULT_PORT = 8000;
const DEFAULT_BASE = `http://127.0.0.1:${DEFAULT_PORT}`;

let resolvedBase: string = DEFAULT_BASE;
let resolved = false;

type TauriInternals = { invoke?: (cmd: string, args?: Record<string, unknown>) => Promise<unknown> };

function tauriInternals(): TauriInternals | null {
  if (typeof window === "undefined") return null;
  const internals = (window as unknown as { __TAURI_INTERNALS__?: TauriInternals }).__TAURI_INTERNALS__;
  return internals && typeof internals.invoke === "function" ? internals : null;
}

/** Current HTTP base, e.g. `http://127.0.0.1:53211`. Never ends with a slash. */
export function apiBase(): string {
  return resolvedBase;
}

/** Build an absolute HTTP URL for a backend path starting with `/`. */
export function apiUrl(path: string): string {
  return `${resolvedBase}${path}`;
}

/** Build an absolute WebSocket URL for a backend path starting with `/`. */
export function wsUrl(path: string): string {
  return `${resolvedBase.replace(/^http/, "ws")}${path}`;
}

export function isBackendResolved(): boolean {
  return resolved;
}

const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

/**
 * Resolve the backend URL from the Tauri runtime. Polls `get_backend_port`
 * until the sidecar has reported its port (0 means "not yet"), then falls back
 * to the default port after `timeoutMs` so the UI still renders if the
 * sidecar failed to start.
 */
export async function resolveBackendUrl(timeoutMs = 120000, pollMs = 250): Promise<string> {
  const internals = tauriInternals();
  if (!internals) {
    resolved = true;
    return resolvedBase;
  }

  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const port = await internals.invoke!("get_backend_port");
      if (typeof port === "number" && port > 0) {
        resolvedBase = `http://127.0.0.1:${port}`;
        console.info(`[backend] resolved sidecar at ${resolvedBase}`);
        // The port is reported before uvicorn binds; wait until it answers.
        await waitForHttp(resolvedBase, Math.max(5000, deadline - Date.now()), pollMs);
        resolved = true;
        return resolvedBase;
      }
    } catch (err) {
      console.warn("[backend] get_backend_port failed, using default port:", err);
      break;
    }
    await sleep(pollMs);
  }

  console.warn(`[backend] sidecar port not reported within ${timeoutMs}ms, falling back to ${DEFAULT_BASE}`);
  resolved = true;
  return resolvedBase;
}

/** Poll `/health` until the backend responds (any HTTP status counts). */
async function waitForHttp(base: string, timeoutMs: number, pollMs: number): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      await fetch(`${base}/health`, { cache: "no-store" });
      return;
    } catch {
      await sleep(pollMs);
    }
  }
  console.warn(`[backend] ${base} did not answer within ${timeoutMs}ms; continuing anyway`);
}
