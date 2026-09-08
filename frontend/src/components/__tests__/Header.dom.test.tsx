// @vitest-environment jsdom
import React, { act } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ apiFetch: vi.fn(), t: (key: string) => key }));
vi.mock("../../lib/backend", () => ({ apiUrl: (path: string) => path, apiFetch: mocks.apiFetch }));
vi.mock("../../context/ThemeContext", () => ({
  useTheme: () => ({ theme: "dark", toggleTheme: vi.fn() }),
}));
vi.mock("../../context/I18nContext", () => ({
  SUPPORTED_LOCALES: [{ id: "en" }, { id: "tr" }, { id: "de" }],
  useTranslation: () => ({ locale: "en", setLocale: vi.fn(), t: mocks.t }),
}));
vi.mock("../../context/PluginRegistryContext", () => ({
  usePluginRegistry: () => ({ activePersona: "kuantra_lite", isLiteMode: true, isPluginActive: () => false }),
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

it("does not render unavailable portfolio telemetry as zero values", async () => {
  mocks.apiFetch.mockResolvedValue(response({ detail: "portfolio summary unavailable" }, 503));
  await act(async () => root.render(<Header {...props} />));
  await flush();

  expect(host.querySelector("[data-testid=header-portfolio-unavailable]")?.textContent).toContain("portfolio summary unavailable");
  expect(host.textContent).not.toContain("$0.00");
});

it("aborts the portfolio polling request when the header unmounts", async () => {
  let requestSignal: AbortSignal | undefined;
  const pending = new Promise<Response>(() => {});
  mocks.apiFetch.mockImplementation((_path: string, init?: RequestInit) => {
    requestSignal = init?.signal;
    return pending;
  });

  await act(async () => root.render(<Header {...props} />));
  await flush();
  await act(async () => root.unmount());

  expect(requestSignal?.aborted).toBe(true);
});
