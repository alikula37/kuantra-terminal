// @vitest-environment jsdom
import React, { act } from "react";
import { createRoot, Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ refreshPlugins: vi.fn() }));
vi.mock("../../context/PluginRegistryContext", () => ({
  usePluginRegistry: () => ({
    plugins: [],
    activePersona: "kuantra_lite",
    loading: false,
    error: "Installed component registry is unavailable. No plugin capability is asserted.",
    refreshPlugins: mocks.refreshPlugins,
  }),
}));

import { PERSONA_DETAILS } from "../onboarding/PersonaSelectorModal";
import { ModStoreStudio } from "../plugins/ModStoreStudio";

let host: HTMLDivElement;
let root: Root;

beforeEach(() => {
  (globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  mocks.refreshPlugins.mockReset();
});

afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
});

describe("plugin and persona truth surfaces", () => {
  it("removes experimental personas from the selector", () => {
    expect(Object.keys(PERSONA_DETAILS)).toEqual(["kuantra_lite", "kuantra_quant"]);
    expect(PERSONA_DETAILS.kuantra_quant.included.join(" ")).not.toContain("Order Flow");
    expect(PERSONA_DETAILS.kuantra_quant.description).toContain("does not enable order-flow");
  });

  it("shows backend availability only and has no marketplace or download action", async () => {
    await act(async () => root.render(<ModStoreStudio />));

    expect(host.textContent).toContain("Component Registry");
    expect(host.textContent).toContain("Extension downloads, remote registries, and runtime mounting are disabled");
    expect(host.textContent).toContain("No installed component capability is available to display.");
    expect(host.textContent).not.toContain("ModStore Catalog");
    expect(host.textContent).not.toContain("AKTİF ET / İNDİR");
    expect(host.textContent).not.toContain("verified");
  });
});
