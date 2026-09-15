// @vitest-environment jsdom
import React, { act } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  apiFetch: vi.fn(),
  t: (key: string) => key,
  pluginState: {
    activePersona: "kuantra_lite",
    isLiteMode: true,
    isPluginActive: () => false,
  },
}));
vi.mock("../../lib/backend", () => ({ apiUrl: (path: string) => path, apiFetch: mocks.apiFetch }));
vi.mock("../../context/ThemeContext", () => ({
  useTheme: () => ({ theme: "dark", toggleTheme: vi.fn() }),
}));
vi.mock("../../context/I18nContext", () => ({
  SUPPORTED_LOCALES: [{ id: "en" }, { id: "tr" }, { id: "de" }],
  useTranslation: () => ({ locale: "en", setLocale: vi.fn(), t: mocks.t }),
}));
vi.mock("../../context/PluginRegistryContext", () => ({
  usePluginRegistry: () => mocks.pluginState,
}));
vi.mock("../../stores/marketStore", () => ({
  useMarketStore: () => ({ eventAgeMs: null, marketDataStatus: "UNAVAILABLE" }),
}));
vi.mock("../plugins/ExtensionSlot", () => ({ ExtensionSlot: () => null }));

import { Header } from "../Header";
import { createRoot } from "react-dom/client";

const response = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

let host: HTMLDivElement;
let root: ReturnType<typeof createRoot>;
const props = { onOpenNewTrade: vi.fn() };
const flush = async () => { await act(async () => { await Promise.resolve(); await Promise.resolve(); }); };

beforeEach(() => {
  (globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  mocks.apiFetch.mockReset();
});

afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
});

it("renders the slim header without portfolio telemetry boxes", async () => {
  await act(async () => root.render(
    <Header {...props} onOpenApiKeySettings={vi.fn()} onOpenPersonaSelector={vi.fn()} />,
  ));
  await flush();

  // The header no longer fetches or displays portfolio cards.
  expect(mocks.apiFetch).not.toHaveBeenCalled();
  expect(host.textContent).not.toContain("header.total_equity");
  expect(host.textContent).not.toContain("header.open_risk");
  expect(host.textContent).not.toContain("header.today_realized");
  expect(host.querySelector("[data-testid=header-portfolio-unavailable]")).toBeNull();
  // Functional controls remain available.
  expect(host.textContent).toContain("header.new_trade_btn");
  expect(host.textContent).toContain("exchange.header_btn");
  expect(host.textContent).not.toContain("$0.00");
});

it("does not expose Chart Vision from the verified Quant persona", async () => {
  mocks.pluginState.activePersona = "kuantra_quant";
  mocks.pluginState.isLiteMode = false;
  await act(async () => root.render(
    <Header
      {...props}
      onOpenVisionUploader={vi.fn()}
    />
  ));
  await flush();

  expect(host.querySelector('button[title="Upload Chart Screenshot for Vision OCR"]')).toBeNull();
});
