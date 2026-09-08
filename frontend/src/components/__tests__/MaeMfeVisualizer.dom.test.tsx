// @vitest-environment jsdom
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
const mocks = vi.hoisted(() => ({ apiFetch: vi.fn(), t: (key: string) => key }));
vi.mock("../../lib/backend", () => ({ apiUrl: (path: string) => path, apiFetch: mocks.apiFetch }));
vi.mock("../../context/I18nContext", () => ({
  useTranslation: () => ({ t: mocks.t }),
}));
import { MaeMfeVisualizer } from "../MaeMfeVisualizer";
const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const base = { status: "READY", reason: null, message: null, provenance: null, total_candidates: 2, total_analyzed: 2, total_r_analyzed: 1, excluded_trades: [], average_mae_r: -0.5, average_mfe_r: 1, average_exit_efficiency_pct: 50, trades_left_money_on_table: 0, recommended_target_r: null, stop_loss_sensitivities: [], points: [] as any[] };
let host: HTMLDivElement; let root: ReturnType<typeof createRoot>;
const flush = async () => { await act(async () => { await Promise.resolve(); await Promise.resolve(); }); };
beforeEach(() => { (globalThis as any).IS_REACT_ACT_ENVIRONMENT = true; host = document.createElement("div"); document.body.append(host); root = createRoot(host); mocks.apiFetch.mockReset(); });
afterEach(async () => { await act(async () => root.unmount()); host.remove(); });
it("renders explicit HTTP and no-data states", async () => { mocks.apiFetch.mockResolvedValueOnce(response({ message: "Offline" }, 503)); await act(async () => root.render(<MaeMfeVisualizer key="error" />)); await flush(); expect(host.textContent).toContain("Offline"); mocks.apiFetch.mockResolvedValueOnce(response({ ...base, status: "NO_DATA", message: "No candles" })); await act(async () => root.render(<MaeMfeVisualizer key="nodata" />)); await flush(); expect(host.textContent).toContain("No analyzed trades"); });
it("plots only finite R pairs, shows no target, and colors unknown PnL neutral", async () => { mocks.apiFetch.mockResolvedValue(response({ ...base, points: [{ trade_id: "NULL", symbol: "X", side: "LONG", entry_price: 1, exit_price: 2, risk_unit: null, mae_price: null, mfe_price: null, mae_r: null, mfe_r: null, exit_efficiency: null, pnl: null, r_multiple: null, status: "NO_RISK" }, { trade_id: "FINITE", symbol: "X", side: "SHORT", entry_price: 1, exit_price: 2, risk_unit: 1, mae_price: 1, mfe_price: 2, mae_r: -0.5, mfe_r: 1, exit_efficiency: 0.5, pnl: null, r_multiple: null, status: "READY" }] })); await act(async () => root.render(<MaeMfeVisualizer />)); await flush(); const dots = Array.from(host.querySelectorAll("circle")).filter((dot) => dot.getAttribute("fill")); expect(dots).toHaveLength(1); expect(host.textContent).toContain("Recommended target"); expect(host.textContent).toContain("—"); expect(dots[0].getAttribute("fill")).toBe("#94a3b8"); });
it("cancels the excursion read without rendering a chart from a late response", async () => {
  let resolvePending!: (value: Response) => void;
  const pending = new Promise<Response>((resolve) => { resolvePending = resolve; });
  let requestSignal: AbortSignal | undefined;
  mocks.apiFetch.mockImplementation((_path: string, init?: RequestInit) => {
    requestSignal = init?.signal;
    return pending;
  });

  await act(async () => root.render(<MaeMfeVisualizer />));
  await flush();

  const cancel = host.querySelector("[data-testid=mae-mfe-cancel]") as HTMLButtonElement;
  expect(cancel).toBeTruthy();
  await act(async () => cancel.click());
  await flush();

  expect(requestSignal?.aborted).toBe(true);
  expect(host.querySelector("[data-testid=mae-mfe-cancelled]")).not.toBeNull();
  expect(host.querySelector("svg")).toBeNull();

  resolvePending(response({ ...base, points: [] }));
  await flush();
  expect(host.querySelector("svg")).toBeNull();
});

it("rejects an HTTP failure and malformed successful payload without an empty analytics view", async () => {
  mocks.apiFetch.mockResolvedValueOnce(response({ detail: "excursion store unavailable" }, 503));
  await act(async () => root.render(<MaeMfeVisualizer key="http-error" />));
  await flush();
  expect(host.querySelector("[data-testid=mae-mfe-error]")?.textContent).toContain("excursion store unavailable");
  expect(host.textContent).not.toContain("Candidates:");

  mocks.apiFetch.mockResolvedValueOnce(response({ ...base, total_candidates: "2" }));
  await act(async () => root.render(<MaeMfeVisualizer key="malformed" />));
  await flush();
  expect(host.querySelector("[data-testid=mae-mfe-error]")?.textContent).toContain("MAE/MFE response was malformed");
  expect(host.textContent).not.toContain("Candidates:");
});

it("keeps a valid UNAVAILABLE status explicit and retryable", async () => {
  mocks.apiFetch.mockResolvedValue(response({ ...base, status: "UNAVAILABLE", reason: "CANDLE_STORE_UNAVAILABLE", message: "Candle evidence is unavailable." }));
  await act(async () => root.render(<MaeMfeVisualizer />));
  await flush();

  expect(host.querySelector("[data-testid=mae-mfe-unavailable]")?.getAttribute("role")).toBe("alert");
  expect(host.textContent).toContain("Candle evidence is unavailable.");
  expect(host.querySelector("[data-testid=mae-mfe-retry]")).not.toBeNull();
  expect(host.textContent).not.toContain("Candidates:");
});
