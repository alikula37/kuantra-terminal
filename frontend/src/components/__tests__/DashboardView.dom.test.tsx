// @vitest-environment jsdom
import React, { act } from "react";
vi.mock("../LocalTrackingPanel", () => ({ LocalTrackingPanel: () => null }));
import { afterEach, beforeEach, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ apiFetch: vi.fn(), setOpenPositions: vi.fn(), t: (key: string) => key }));
vi.mock("../../lib/backend", () => ({ apiBase: () => "", apiUrl: (path: string) => path, apiFetch: mocks.apiFetch }));
vi.mock("../../context/I18nContext", () => ({
  useTranslation: () => ({ t: mocks.t }),
}));
vi.mock("../../stores/tradeStore", () => ({
  useTradeStore: () => ({ openPositions: [], setOpenPositions: mocks.setOpenPositions, updatePositionPnl: vi.fn() }),
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
  OpenPositionsTable: ({ loading, refreshNonce }: { loading?: boolean; refreshNonce?: number }) => (
    <div data-testid="dashboard-positions" data-nonce={refreshNonce ?? 0}>{loading ? "loading" : "positions"}</div>
  ),
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
  vi.useRealTimers();
  host.remove();
});

const validSummary = Object.fromEntries([
  "initial_balance", "total_equity", "net_pnl", "net_pnl_pct", "today_pnl", "today_pnl_pct",
  "open_risk_usd", "open_risk_r", "active_positions_count", "total_closed_trades", "win_rate",
  "profit_factor", "avg_r_multiple", "max_drawdown_usd", "max_drawdown_pct",
].map((key) => [key, 0]));

function readyDashboard() {
  mocks.apiFetch.mockImplementation((path: string) => Promise.resolve(response(
    path.endsWith("/summary")
      ? { ...validSummary, today_trades_count: { wins: 0, losses: 0, total: 0 } }
      : [],
  )));
}

it("keeps displayed cards mounted during background refresh and does not abort slow reads", async () => {
  vi.useFakeTimers();
  readyDashboard();
  await act(async () => root.render(<DashboardView />));
  await flush();
  const card = host.querySelector("[data-testid=dashboard-equity]");
  expect(card?.textContent).toBe("equity");
  const signals: AbortSignal[] = [];
  mocks.apiFetch.mockImplementation((_path: string, init: RequestInit) => {
    signals.push(init.signal as AbortSignal);
    return new Promise(() => {});
  });
  await act(async () => vi.advanceTimersByTime(4000));
  expect(host.querySelector("[data-testid=dashboard-equity]")).toBe(card);
  expect(card?.textContent).toBe("equity");
  expect(host.querySelector("[data-testid=dashboard-loading]")).toBeNull();
  await act(async () => vi.advanceTimersByTime(12000));
  expect(signals).toHaveLength(5);
  expect(signals.every((signal) => !signal.aborted)).toBe(true);
});

it("keeps the last valid snapshot with an explicit refresh error until recovery", async () => {
  vi.useFakeTimers();
  readyDashboard();
  await act(async () => root.render(<DashboardView />));
  await flush();
  const card = host.querySelector("[data-testid=dashboard-equity]");
  mocks.apiFetch.mockImplementation(() => Promise.resolve(response({ detail: "refresh unavailable" }, 503)));
  await act(async () => vi.advanceTimersByTime(4000));
  await flush();
  expect(host.querySelector("[data-testid=dashboard-error]")?.textContent).toContain("refresh unavailable");
  expect(host.querySelector("[data-testid=dashboard-equity]")).toBe(card);
  expect(card?.textContent).toBe("equity");
  readyDashboard();
  await act(async () => vi.advanceTimersByTime(4000));
  await flush();
  expect(host.querySelector("[data-testid=dashboard-error]")).toBeNull();
  expect(host.querySelector("[data-testid=dashboard-equity]")).toBe(card);
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

  expect(signals).toHaveLength(5);
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

it("cascades the dashboard refresh into the open-position quotes", async () => {
  readyDashboard();
  await act(async () => root.render(<DashboardView />));
  await flush();
  expect(host.querySelector("[data-testid=dashboard-positions]")?.getAttribute("data-nonce")).toBe("0");

  await act(async () => (host.querySelector('button[title="dashboard.refresh_title"]') as HTMLButtonElement).click());
  await flush();

  expect(host.querySelector("[data-testid=dashboard-positions]")?.getAttribute("data-nonce")).toBe("1");
});

it("uses the localized dashboard title instead of a hardcoded bilingual string", async () => {
  readyDashboard();
  await act(async () => root.render(<DashboardView />));
  await flush();

  expect(host.textContent).toContain("dashboard.title_lite");
  expect(host.textContent).not.toContain("LITE PORTFÖY");
});

it("loads open positions from the server so earlier trades appear on the dashboard", async () => {
  const openTrade = {
    id: "TRD-SERVER", symbol: "BTCUSDT", side: "BUY", position_type: "LONG", status: "OPEN",
    entry_price: 76601, qty: 500, qty_unit: "USD", record_mode: "SIMULATION",
    entry_time: "2026-09-17T13:23:56Z",
  };
  mocks.apiFetch.mockImplementation((path: string) => Promise.resolve(response(
    path.endsWith("/trades/open") ? [openTrade] : path.endsWith("/summary") ? { ...validSummary, today_trades_count: { wins: 0, losses: 0, total: 0 } } : [],
  )));
  await act(async () => root.render(<DashboardView />));
  await flush();

  expect(mocks.setOpenPositions).toHaveBeenCalledWith([openTrade]);
});
