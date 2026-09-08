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
