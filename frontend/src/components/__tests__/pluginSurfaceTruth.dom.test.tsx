// @vitest-environment jsdom
import React, { act } from "react";
import { createRoot, Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  refreshPlugins: vi.fn(),
  cancelRefresh: vi.fn(),
  state: {
    plugins: [],
    activePersona: "kuantra_lite",
    loading: false,
    error: "Installed component registry is unavailable. No plugin capability is asserted.",
    refreshPlugins: vi.fn(),
    cancelRefresh: vi.fn(),
  },
}));
vi.mock("../../context/PluginRegistryContext", () => ({
  usePluginRegistry: () => mocks.state,
}));

import { PERSONA_DETAILS } from "../onboarding/PersonaSelectorModal";
import { ModStoreStudio } from "../plugins/ModStoreStudio";
import { WorkspacePresetSelector } from "../workspace/WorkspacePresetSelector";

let host: HTMLDivElement;
let root: Root;

beforeEach(() => {
  (globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  mocks.refreshPlugins.mockReset();
  mocks.cancelRefresh.mockReset();
  mocks.state.plugins = [];
  mocks.state.activePersona = "kuantra_lite";
  mocks.state.loading = false;
  mocks.state.error = "Installed component registry is unavailable. No plugin capability is asserted.";
  mocks.state.refreshPlugins = mocks.refreshPlugins;
  mocks.state.cancelRefresh = mocks.cancelRefresh;
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

  it("shows an explicit registry loading state with cancel and retry controls", async () => {
    mocks.state.loading = true;
    mocks.state.error = null;
    await act(async () => root.render(<ModStoreStudio />));

    expect(host.querySelector("[data-testid=plugin-registry-loading]")).not.toBeNull();
    await act(async () => (host.querySelector("[data-testid=plugin-registry-cancel]") as HTMLButtonElement).click());
    expect(mocks.cancelRefresh).toHaveBeenCalledTimes(1);

    mocks.state.loading = false;
    mocks.state.error = "Installed component registry response was malformed";
    await act(async () => root.render(<ModStoreStudio />));
    expect(host.querySelector("[data-testid=plugin-registry-error]")?.getAttribute("role")).toBe("alert");
    await act(async () => (host.querySelector("[data-testid=plugin-registry-retry]") as HTMLButtonElement).click());
    expect(mocks.refreshPlugins).toHaveBeenCalledTimes(1);
  });

  it("keeps the verified Quant workspace on deterministic core presets", async () => {
    await act(async () => root.render(
      <WorkspacePresetSelector
        currentPreset="day_trader"
        onSelectPreset={vi.fn()}
        onPopoutAll={vi.fn()}
        onResetLayout={vi.fn()}
        safeOnly
      />
    ));

    expect(host.textContent).toContain("Day Trader");
    expect(host.textContent).toContain("Quant Analytics");
    expect(host.textContent).not.toContain("Docking Grid");
    expect(host.textContent).not.toContain("AI Auditor Focus");
    expect(host.textContent).not.toContain("POP-OUT MONITORS");
    expect(host.querySelector('button[title="Dashboard, journal and reviewed market context"]')).not.toBeNull();
    expect(host.querySelector('button[title="Deterministic analytics and MAE / MFE review"]')).not.toBeNull();
    expect(host.querySelector('button[title*="Live Positions"]')).toBeNull();
    expect(host.querySelector('button[title*="Prop Shield"]')).toBeNull();
  });
});
