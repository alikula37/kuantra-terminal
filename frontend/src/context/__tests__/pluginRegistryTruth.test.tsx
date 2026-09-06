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
  const { plugins, error } = usePluginRegistry();
  return <div>{`${plugins.length}|${error || "NO_ERROR"}`}</div>;
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

  it("exposes only Lite and bounded Quant personas, with no order-flow activation claim", () => {
    expect([...SAFE_PERSONAS]).toEqual(["kuantra_lite", "kuantra_quant"]);
    expect(Object.keys(PERSONA_PLUGIN_MAP).sort()).toEqual([
      "kuantra_lite", "kuantra_quant", "lite", "quant",
    ]);
    expect(PERSONA_PLUGIN_MAP.kuantra_quant).toEqual(["plugin_quant_shield"]);
  });
});
