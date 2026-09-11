// @vitest-environment jsdom
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => {
  const apiFetch = vi.fn();
  const setData = vi.fn();
  const updateTick = vi.fn();
  const setSymbol = vi.fn();
  const remove = vi.fn();
  const createChart = vi.fn(() => ({
    addCandlestickSeries: () => ({ setData, applyOptions: vi.fn() }),
    addHistogramSeries: () => ({ setData, applyOptions: vi.fn() }),
    applyOptions: vi.fn(),
    priceScale: () => ({ applyOptions: vi.fn() }),
    timeScale: () => ({ fitContent: vi.fn() }),
    subscribeCrosshairMove: vi.fn(),
    remove,
  }));
  return { apiFetch, createChart, remove, setData, setSymbol, updateTick, t: (key: string) => key };
});

vi.mock("../../lib/backend", () => ({ apiBase: () => "", apiFetch: mocks.apiFetch }));
vi.mock("../../context/I18nContext", () => ({
  useTranslation: () => ({ t: mocks.t }),
}));
vi.mock("../../context/ThemeContext", () => ({
  useTheme: () => ({ theme: "dark" }),
  getChartTheme: () => ({
    layout: { background: { color: "#0b0e14" }, textColor: "#f8fafc" },
    grid: { vertLines: { color: "#1e293b" }, horzLines: { color: "#1e293b" } },
    candlestick: {
      upColor: "#10b981",
      downColor: "#f43f5e",
      borderUpColor: "#10b981",
      borderDownColor: "#f43f5e",
      wickUpColor: "#10b981",
      wickDownColor: "#f43f5e",
    },
    palette: { accent: "#38bdf8", surfaceBorder: "#1e293b" },
  }),
}));
vi.mock("../../stores/marketStore", () => ({
  useMarketStore: () => ({ symbol: "BTCUSDT", setSymbol: mocks.setSymbol, updateTick: mocks.updateTick }),
}));
vi.mock("lightweight-charts", () => ({ createChart: mocks.createChart }));

import { TradingViewChart } from "../TradingViewChart";

const response = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const candles = {
  symbol: "BTCUSDT",
  timeframe: "15m",
  count: 1,
  candles: [{ timestamp: 1_700_000_000_000, open: 100, high: 110, low: 90, close: 105, volume: 12 }],
};
const deferred = <T,>() => {
  let resolve!: (value: T) => void;
  return { promise: new Promise<T>((done) => { resolve = done; }), resolve };
};

let host: HTMLDivElement;
let root: ReturnType<typeof createRoot>;
const flush = async () => { await act(async () => { await Promise.resolve(); await Promise.resolve(); }); };
const setInputValue = (input: HTMLInputElement, value: string) => {
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
  setter?.call(input, value);
  input.dispatchEvent(new Event("input", { bubbles: true }));
  input.dispatchEvent(new Event("change", { bubbles: true }));
};

beforeEach(() => {
  (globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
  window.localStorage.clear();
  (globalThis as any).ResizeObserver = class {
    observe() {}
    disconnect() {}
  };
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  mocks.apiFetch.mockReset();
  mocks.createChart.mockClear();
  mocks.remove.mockClear();
  mocks.setData.mockClear();
  mocks.setSymbol.mockClear();
  mocks.updateTick.mockClear();
});

afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
  vi.useRealTimers();
});

it("cancels a pending candle read and ignores a late response", async () => {
  const pending = deferred<Response>();
  let requestSignal: AbortSignal | undefined;
  mocks.apiFetch.mockImplementation((_url: string, init?: RequestInit) => {
    requestSignal = init?.signal;
    return pending.promise;
  });

  await act(async () => root.render(<TradingViewChart />));
  await flush();
  const cancel = host.querySelector("[data-testid=market-chart-cancel]") as HTMLButtonElement;
  expect(cancel).toBeTruthy();

  await act(async () => cancel.click());
  await flush();
  expect(requestSignal?.aborted).toBe(true);
  expect(host.querySelector("[data-testid=market-chart-cancelled]")).not.toBeNull();

  pending.resolve(response(candles));
  await flush();
  expect(mocks.setData).not.toHaveBeenCalled();
  expect(mocks.updateTick).not.toHaveBeenCalled();
});

it("rejects malformed candle payloads instead of rendering or marking them live", async () => {
  mocks.apiFetch.mockResolvedValue(response({ candles: [{ ...candles.candles[0], close: "not-a-price" }] }));

  await act(async () => root.render(<TradingViewChart />));
  await flush();

  expect(host.querySelector("[data-testid=market-chart-error]")?.textContent).toContain("market_chart.malformed");
  expect(mocks.setData.mock.calls.every(([value]) => Array.isArray(value) && value.length === 0)).toBe(true);
  expect(mocks.updateTick).not.toHaveBeenCalled();
});

it("aborts an in-flight candle read when the chart unmounts", async () => {
  const pending = deferred<Response>();
  let requestSignal: AbortSignal | undefined;
  mocks.apiFetch.mockImplementation((_url: string, init?: RequestInit) => {
    requestSignal = init?.signal;
    return pending.promise;
  });

  await act(async () => root.render(<TradingViewChart />));
  await flush();
  await act(async () => root.unmount());
  expect(requestSignal?.aborted).toBe(true);

  pending.resolve(response(candles));
  await flush();
  expect(mocks.setData).not.toHaveBeenCalled();
});

it("renders valid historical candles without promoting them to live ticks", async () => {
  mocks.apiFetch.mockResolvedValue(response(candles));

  await act(async () => root.render(<TradingViewChart />));
  await flush();

  expect(mocks.setData).toHaveBeenCalledWith(expect.arrayContaining([
    expect.objectContaining({ open: 100, high: 110, low: 90, close: 105 }),
  ]));
  expect(mocks.updateTick).not.toHaveBeenCalled();
});

it("requires selecting and confirming a catalog result before re-adding gold", async () => {
  mocks.apiFetch.mockResolvedValue(response(candles));

  await act(async () => root.render(<TradingViewChart />));
  await flush();

  const removeGold = host.querySelector("[data-testid=market-chart-remove-XAUUSD]") as HTMLButtonElement;
  await act(async () => removeGold.click());
  await flush();
  expect(host.querySelector("[data-testid=market-chart-symbol-XAUUSD]")).toBeNull();

  const input = host.querySelector("[data-testid=market-chart-symbol-search]") as HTMLInputElement;
  await act(async () => setInputValue(input, "gold"));
  await flush();

  const result = host.querySelector("[data-testid=market-chart-search-result-XAUUSD]") as HTMLButtonElement;
  expect(result).toBeTruthy();
  await act(async () => result.click());
  await flush();
  expect(host.querySelector("[data-testid=market-chart-symbol-confirmation]")).not.toBeNull();
  expect(host.querySelector("[data-testid=market-chart-symbol-XAUUSD]")).toBeNull();
  await act(async () => (host.querySelector("[data-testid=market-chart-confirm-symbol]") as HTMLButtonElement).click());
  await flush();
  expect(host.querySelector("[data-testid=market-chart-symbol-XAUUSD]")).not.toBeNull();
});

it("does not auto-add LINK on Enter and requires explicit Chainlink confirmation", async () => {
  mocks.apiFetch.mockResolvedValue(response(candles));

  await act(async () => root.render(<TradingViewChart />));
  await flush();

  const removeLink = host.querySelector("[data-testid=market-chart-remove-LINKUSDT]") as HTMLButtonElement;
  await act(async () => removeLink.click());
  await flush();
  expect(host.querySelector("[data-testid=market-chart-symbol-LINKUSDT]")).toBeNull();

  const input = host.querySelector("[data-testid=market-chart-symbol-search]") as HTMLInputElement;
  const callsBeforeEnter = mocks.apiFetch.mock.calls.length;
  await act(async () => setInputValue(input, "LINK"));
  await flush();

  await act(async () => (host.querySelector('form button[type="submit"]') as HTMLButtonElement).click());
  await flush();
  expect(mocks.apiFetch.mock.calls.length).toBe(callsBeforeEnter);
  expect(host.querySelector("[data-testid=market-chart-search-result-LINKUSDT]")).not.toBeNull();
  expect(host.querySelector("[data-testid=market-chart-symbol-LINKUSDT]")).toBeNull();

  await act(async () => (host.querySelector("[data-testid=market-chart-search-result-LINKUSDT]") as HTMLButtonElement).click());
  await flush();
  expect(host.querySelector("[data-testid=market-chart-symbol-confirmation]")).not.toBeNull();
  expect(host.querySelector("[data-testid=market-chart-symbol-LINKUSDT]")).toBeNull();

  await act(async () => (host.querySelector("[data-testid=market-chart-confirm-symbol]") as HTMLButtonElement).click());
  await flush();
  expect(host.querySelector("[data-testid=market-chart-symbol-LINKUSDT]")).not.toBeNull();
  expect(mocks.apiFetch.mock.calls.length).toBeGreaterThan(callsBeforeEnter);
});
