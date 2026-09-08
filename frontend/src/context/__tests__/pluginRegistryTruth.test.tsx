// @vitest-environment jsdom
import React, { act } from "react";
import { createRoot, Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ apiFetch: vi.fn() }));
vi.mock("../../lib/backend", () => ({
  apiUrl: (path: string) => path,
  apiFetch: mocks.apiFetch,
}));

import {
  PERSONA_PLUGIN_MAP,
  PluginRegistryProvider,
  SAFE_PERSONAS,
  usePluginRegistry,
} from "../PluginRegistryContext";

const Probe = () => {
  const { plugins, error, loading, cancelRefresh } = usePluginRegistry();
  return (
    <div>
      <span>{`${plugins.length}|${error || "NO_ERROR"}`}</span>
      {loading && (
        <button data-testid="plugin-registry-cancel" onClick={cancelRefresh}>
          Cancel
        </button>
      )}
    </div>
  );
};

const response = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const deferred = <T,>() => {
  let resolve!: (value: T) => void;
  return { promise: new Promise<T>((done) => { resolve = done; }), resolve };
};

const validPlugin = {
  plugin_id: "plugin_quant_shield",
  name: "Quant Shield",
  version: "1.0.0",
  category: "Analytics",
  description: "Deterministic analytics",
  author: "Kuantra",
  heavy_dependencies: [],
  router_prefix: null,
  is_active: false,
  ram_footprint_mb: 5,
  persona_tags: ["quant"],
};

const flush = async () => {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
};

let host: HTMLDivElement;
let root: Root;

beforeEach(() => {
  (globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
  localStorage.clear();
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  mocks.apiFetch.mockReset();
});

afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
});

describe("plugin registry truth boundary", () => {
  it("does not invent installed plugins or active capability when the backend is unavailable", async () => {
    mocks.apiFetch.mockRejectedValueOnce(new Error("backend offline"));

    await act(async () => root.render(<PluginRegistryProvider><Probe /></PluginRegistryProvider>));
    await flush();

    expect(host.textContent).toContain("0|Installed component registry is unavailable");
    expect(host.textContent).not.toContain("plugin_ai_swarm");
  });

  it("cancels a pending registry read and ignores a late installed-plugin payload", async () => {
    const pending = deferred<Response>();
    let requestSignal: AbortSignal | undefined;
    mocks.apiFetch.mockImplementation((_path: string, init?: RequestInit) => {
      requestSignal = init?.signal;
      return pending.promise;
    });

    await act(async () => root.render(<PluginRegistryProvider><Probe /></PluginRegistryProvider>));
    await flush();
    await act(async () => (host.querySelector("[data-testid=plugin-registry-cancel]") as HTMLButtonElement).click());
    await flush();

    expect(requestSignal?.aborted).toBe(true);
    expect(host.textContent).toContain("registry request cancelled");
    pending.resolve(response({ plugins: [validPlugin], active_persona: "kuantra_lite" }));
    await flush();
    expect(host.textContent).toContain("0|");
    expect(host.textContent).not.toContain("Quant Shield");
  });

  it("rejects a malformed installed-plugin response without partial capability", async () => {
    mocks.apiFetch.mockResolvedValue(response({ plugins: [{}], active_persona: "kuantra_lite" }));

    await act(async () => root.render(<PluginRegistryProvider><Probe /></PluginRegistryProvider>));
    await flush();

    expect(host.textContent).toContain("0|Installed component registry response was malformed");
  });

  it("exposes only Lite and bounded Quant personas, with no order-flow activation claim", () => {
    expect([...SAFE_PERSONAS]).toEqual(["kuantra_lite", "kuantra_quant"]);
    expect(Object.keys(PERSONA_PLUGIN_MAP).sort()).toEqual([
      "kuantra_lite", "kuantra_quant", "lite", "quant",
    ]);
    expect(PERSONA_PLUGIN_MAP.kuantra_quant).toEqual(["plugin_quant_shield"]);
  });
});
