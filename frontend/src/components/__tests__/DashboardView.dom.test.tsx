// @vitest-environment jsdom
import React, { act } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ apiFetch: vi.fn(), t: (key: string) => key }));
vi.mock("../../lib/backend", () => ({ apiBase: () => "", apiUrl: (path: string) => path, apiFetch: mocks.apiFetch }));
vi.mock("../../context/I18nContext", () => ({
  useTranslation: () => ({ t: mocks.t }),
}));
vi.mock("../../stores/tradeStore", () => ({
  useTradeStore: () => ({ openPositions: [], updatePositionPnl: vi.fn() }),
}));
vi.mock("../../stores/marketStore", () => ({
  useMarketStore: () => ({ currentPrice: null, marketDataStatus: "UNAVAILABLE" }),
}));
vi.mock("../../context/PluginRegistryContext", () => ({
  usePluginRegistry: () => ({ isLiteMode: true }),
}));
vi.mock("../dashboard/PortfolioKpiGrid", () => ({
  PortfolioKpiGrid: ({ loading }: { loading?: boolean }) => <div data-testid="dashboard-summary">{loading ? "loading" : "summary"}</div>,
}));
vi.mock("../dashboard/MultiAssetBreakdown", () => ({
  MultiAssetBreakdown: ({ loading }: { loading?: boolean }) => <div data-testid="dashboard-breakdown">{loading ? "loading" : "breakdown"}</div>,
}));
vi.mock("../dashboard/EquityCurveChart", () => ({
  EquityCurveChart: ({ loading }: { loading?: boolean }) => <div data-testid="dashboard-equity">{loading ? "loading" : "equity"}</div>,
}));
vi.mock("../dashboard/OpenPositionsTable", () => ({
  OpenPositionsTable: ({ loading }: { loading?: boolean }) => <div data-testid="dashboard-positions">{loading ? "loading" : "positions"}</div>,
}));
vi.mock("../dashboard/PnlCalendarHeatmap", () => ({
  PnlCalendarHeatmap: ({ loading }: { loading?: boolean }) => <div data-testid="dashboard-heatmap">{loading ? "loading" : "heatmap"}</div>,
}));

import { DashboardView } from "../DashboardView";
import { createRoot } from "react-dom/client";

const response = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

let host: HTMLDivElement;
let root: ReturnType<typeof createRoot>;
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

it("cancels all dashboard read requests without showing partial success", async () => {
  let resolvePending!: (value: Response) => void;
  const pending = new Promise<Response>((resolve) => { resolvePending = resolve; });
  const signals: Array<AbortSignal | undefined> = [];
  mocks.apiFetch.mockImplementation((_path: string, init?: RequestInit) => {
    signals.push(init?.signal);
    return pending;
  });

  await act(async () => root.render(<DashboardView />));
  await flush();

  const cancel = host.querySelector("[data-testid=dashboard-cancel]") as HTMLButtonElement;
  expect(cancel).toBeTruthy();
  await act(async () => cancel.click());
  await flush();

  expect(signals).toHaveLength(4);
  expect(signals.every((signal) => signal?.aborted)).toBe(true);
  expect(host.querySelector("[data-testid=dashboard-cancelled]")).not.toBeNull();
  expect(host.querySelector("[data-testid=dashboard-summary]")?.textContent).not.toBe("summary");

  resolvePending(response({}));
  await flush();
  expect(host.querySelector("[data-testid=dashboard-summary]")?.textContent).not.toBe("summary");
});

it("shows an explicit error when any dashboard source is unavailable", async () => {
  mocks.apiFetch.mockImplementation((path: string) => Promise.resolve(
    path === "/api/v1/portfolio/summary"
      ? response({ detail: "portfolio summary unavailable" }, 503)
      : response({}),
  ));

  await act(async () => root.render(<DashboardView />));
  await flush();

  expect(host.querySelector("[data-testid=dashboard-error]")?.textContent).toContain("portfolio summary unavailable");
  expect(host.querySelector("[data-testid=dashboard-summary]")?.textContent).not.toBe("summary");
});

it("rejects a malformed successful response instead of rendering a partial dashboard", async () => {
  mocks.apiFetch.mockImplementation((path: string) => Promise.resolve(
    path === "/api/v1/portfolio/summary" ? response({}) : response([]),
  ));

  await act(async () => root.render(<DashboardView />));
  await flush();

  expect(host.querySelector("[data-testid=dashboard-error]")?.textContent).toContain("Portfolio summary response was incomplete or malformed");
  expect(host.querySelector("[data-testid=dashboard-summary]")?.textContent).not.toBe("summary");
});
