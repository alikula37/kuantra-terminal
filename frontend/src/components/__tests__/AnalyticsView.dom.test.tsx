// @vitest-environment jsdom
import React, { act } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ apiFetch: vi.fn(), t: (key: string) => key }));
vi.mock("../../lib/backend", () => ({ apiUrl: (path: string) => path, apiFetch: mocks.apiFetch }));
vi.mock("../../context/I18nContext", () => ({
  useTranslation: () => ({ t: mocks.t }),
}));

import { AnalyticsView } from "../AnalyticsView";
import { createRoot } from "react-dom/client";

const response = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

const scorecard = {
  total_trades: 1,
  win_rate: 100,
  loss_rate: 0,
  total_pnl: 12,
  avg_win: 12,
  avg_loss: 0,
  profit_factor: 999,
  expectancy: 12,
  sqn: 1,
  sharpe_ratio: 1,
  sortino_ratio: 1,
  max_drawdown_amount: 0,
  max_drawdown_pct: 0,
  half_kelly_pct: 10,
};

const symbolRow = (overrides: Record<string, unknown> = {}) => ({
  symbol: "BTCUSDT",
  count: 4,
  known_pnl_count: 3,
  unknown_pnl_count: 1,
  total_pnl: 2,
  avg_pnl: 0.67,
  win_rate: 33.33,
  ...overrides,
});

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

it("cancels analytics reads without converting a late response into a scorecard", async () => {
  let resolveQuant!: (value: Response) => void;
  let resolveSymbols!: (value: Response) => void;
  const quantPending = new Promise<Response>((resolve) => { resolveQuant = resolve; });
  const symbolsPending = new Promise<Response>((resolve) => { resolveSymbols = resolve; });
  const signals: AbortSignal[] = [];
  mocks.apiFetch.mockImplementation((path: string, init?: RequestInit) => {
    if (init?.signal) signals.push(init.signal);
    return path.includes("/quant") ? quantPending : symbolsPending;
  });

  await act(async () => root.render(<AnalyticsView />));
  await flush();

  const cancel = host.querySelector("[data-testid=analytics-cancel]") as HTMLButtonElement;
  expect(cancel).toBeTruthy();
  await act(async () => cancel.click());
  await flush();

  expect(signals).toHaveLength(2);
  expect(signals.every((signal) => signal.aborted)).toBe(true);
  expect(host.querySelector("[data-testid=analytics-cancelled]")).not.toBeNull();
  expect(host.textContent).not.toContain("SYSTEM QUALITY NUMBER");

  resolveQuant(response(scorecard));
  resolveSymbols(response([]));
  await flush();
  expect(host.textContent).not.toContain("SYSTEM QUALITY NUMBER");
});

it("keeps an unavailable analytics response as an explicit error, not a zero scorecard", async () => {
  mocks.apiFetch.mockImplementation((path: string) => Promise.resolve(
    path.includes("/quant")
      ? response({ detail: "analytics unavailable" }, 503)
      : response([]),
  ));

  await act(async () => root.render(<AnalyticsView />));
  await flush();

  expect(host.querySelector("[data-testid=analytics-error]")?.textContent).toContain("analytics unavailable");
  expect(host.textContent).not.toContain("SYSTEM QUALITY NUMBER");
  expect(host.textContent).not.toContain("TOTAL CLOSED TRADES: 0");
});

it("keeps a valid zero-trade response as an explicit empty state", async () => {
  mocks.apiFetch.mockImplementation((path: string) => Promise.resolve(
    path.includes("/quant") ? response({ ...scorecard, total_trades: 0 }) : response([]),
  ));

  await act(async () => root.render(<AnalyticsView />));
  await flush();

  expect(host.textContent).toContain("analytics.waiting_title");
  expect(host.textContent).not.toContain("SYSTEM QUALITY NUMBER");
});

it("shows the unknown-result count when known and unknown results are mixed", async () => {
  mocks.apiFetch.mockImplementation((path: string) => Promise.resolve(
    path.includes("/quant")
      ? response({ ...scorecard, total_trades: 3, win_rate: 33.33, total_pnl: 2 })
      : response([symbolRow()]),
  ));

  await act(async () => root.render(<AnalyticsView />));
  await flush();

  expect(host.textContent).toContain("analytics.unknown_pnl_note");
  expect(host.textContent).toContain("analytics.symbol_unknown_count");
  expect(host.textContent).toContain("SYSTEM QUALITY NUMBER");
});

it("labels an all-unknown book instead of claiming there are no trades", async () => {
  mocks.apiFetch.mockImplementation((path: string) => Promise.resolve(
    path.includes("/quant")
      ? response({ ...scorecard, total_trades: 0, total_pnl: 0 })
      : response([symbolRow({
          count: 2,
          known_pnl_count: 0,
          unknown_pnl_count: 2,
          total_pnl: 0,
          avg_pnl: 0,
          win_rate: 0,
        })]),
  ));

  await act(async () => root.render(<AnalyticsView />));
  await flush();

  expect(host.textContent).toContain("analytics.unknown_all_title");
  expect(host.textContent).not.toContain("analytics.waiting_title");
  expect(host.textContent).not.toContain("SYSTEM QUALITY NUMBER");
});

it("keeps a fully known book free of unknown-result notes", async () => {
  mocks.apiFetch.mockImplementation((path: string) => Promise.resolve(
    path.includes("/quant")
      ? response({ ...scorecard, total_trades: 2, win_rate: 50, total_pnl: -1 })
      : response([symbolRow({
          count: 2,
          known_pnl_count: 2,
          unknown_pnl_count: 0,
          total_pnl: -1,
          avg_pnl: -0.5,
          win_rate: 50,
        })]),
  ));

  await act(async () => root.render(<AnalyticsView />));
  await flush();

  expect(host.textContent).not.toContain("analytics.unknown_pnl_note");
  expect(host.textContent).not.toContain("analytics.unknown_all_title");
  expect(host.textContent).toContain("SYSTEM QUALITY NUMBER");
});

it("states that simulations are excluded when the counter is non-zero", async () => {
  mocks.apiFetch.mockImplementation((path: string) => {
    if (path.includes("/analytics/quant")) {
      return Promise.resolve(response({ ...scorecard, simulation_trades: 3 }));
    }
    return Promise.resolve(response(path.includes("/analytics/pivot")
      ? { dimensions: ["symbol"], total_buckets: 0, rows: [], basis: "NO_CLOSED_TRADES" }
      : [symbolRow()]));
  });
  await act(async () => root.render(<AnalyticsView />));
  await flush();

  const note = host.querySelector('[data-testid="analytics-simulation-excluded"]');
  expect(note?.textContent).toContain("analytics.simulation_excluded");
});
