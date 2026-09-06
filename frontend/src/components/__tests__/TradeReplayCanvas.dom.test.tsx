// @vitest-environment jsdom
import React, { act } from "react";
import { createRoot, Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => {
  const apiFetch = vi.fn();
  const setData = vi.fn();
  const remove = vi.fn();
  const createChart = vi.fn(() => ({ addCandlestickSeries: () => ({ setData }), applyOptions: vi.fn(), remove }));
  return { apiFetch, setData, remove, createChart };
});
const { apiFetch, setData, remove, createChart } = mocks;
vi.mock("../../lib/backend", () => ({ apiBase: () => "", apiFetch: mocks.apiFetch }));
vi.mock("lightweight-charts", () => ({ createChart: mocks.createChart }));

import { TradeReplayCanvas } from "../TradeReplayCanvas";

const ready = (symbol = "BTCUSDT") => ({ status: "READY", reason: null, message: null, provenance: { quality: "BAR_APPROXIMATION", source: "DUCKDB_CANDLES", source_verified: false, timeframe: "1m" }, session_id: `S-${symbol}`, symbol, total_bars: 2, current_index: 0, entry_index: 0, exit_index: 1, speed_multiplier: 1, is_playing: false, current_candle: { time: 1, open: 1, high: 2, low: 1, close: 2 }, trade: null, visible_candles: [{ time: 1, open: 1, high: 2, low: 1, close: 2 }] });
const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const deferred = <T,>() => { let resolve!: (value: T) => void; return { promise: new Promise<T>((done) => { resolve = done; }), resolve }; };
const rejected = <T,>() => { let reject!: (reason?: unknown) => void; return { promise: new Promise<T>((_done, fail) => { reject = fail; }), reject }; };

let host: HTMLDivElement; let root: Root;
const flush = async () => { await act(async () => { await Promise.resolve(); await Promise.resolve(); }); };

beforeEach(() => { (globalThis as any).IS_REACT_ACT_ENVIRONMENT = true; host = document.createElement("div"); document.body.append(host); root = createRoot(host); apiFetch.mockReset(); createChart.mockClear(); setData.mockClear(); remove.mockClear(); });
afterEach(async () => { await act(async () => root.unmount()); host.remove(); vi.useRealTimers(); });

describe("TradeReplayCanvas lifecycle", () => {
  it("waits for the async READY response before chart initialization and cleans up", async () => {
    apiFetch.mockResolvedValue(response(ready()));
    await act(async () => root.render(<TradeReplayCanvas tradeId="T1" />)); await flush();
    expect(createChart).toHaveBeenCalledTimes(1); expect(setData).toHaveBeenCalledWith(expect.any(Array));
    await act(async () => root.unmount()); expect(remove).toHaveBeenCalledTimes(1);
  });
  it("renders explicit no-data and HTTP error states without creating a chart", async () => {
    apiFetch.mockResolvedValueOnce(response({ ...ready(), status: "NO_DATA", session_id: null, total_bars: 0, current_index: null, current_candle: null, visible_candles: [], message: "Candle range is missing." }));
    await act(async () => root.render(<TradeReplayCanvas tradeId="missing" />)); await flush();
    expect(host.textContent).toContain("No replay data"); expect(createChart).not.toHaveBeenCalled();
    apiFetch.mockResolvedValueOnce(response({ message: "Backend unavailable" }, 503));
    await act(async () => root.render(<TradeReplayCanvas tradeId="broken" />)); await flush();
    expect(host.textContent).toContain("Replay unavailable"); expect(host.textContent).toContain("Backend unavailable");
  });
  it("ignores a stale trade response after tradeId changes", async () => {
    const oldRequest = deferred<Response>(), newRequest = deferred<Response>(); apiFetch.mockReturnValueOnce(oldRequest.promise).mockReturnValueOnce(newRequest.promise);
    await act(async () => root.render(<TradeReplayCanvas tradeId="old" />)); await act(async () => root.render(<TradeReplayCanvas tradeId="new" />));
    newRequest.resolve(response(ready("NEW"))); await flush(); expect(host.textContent).toContain("NEW");
    oldRequest.resolve(response(ready("OLD"))); await flush(); expect(host.textContent).not.toContain("OLD"); expect(host.textContent).toContain("NEW");
  });
  it("does not overlap playback step requests while a prior step is in flight", async () => {
    vi.useFakeTimers(); const step = deferred<Response>(); apiFetch.mockResolvedValueOnce(response(ready())).mockReturnValueOnce(step.promise);
    await act(async () => root.render(<TradeReplayCanvas tradeId="T1" />)); await flush();
    const play = Array.from(host.querySelectorAll("button")).find((button) => button.textContent?.includes("PLAY"))!;
    await act(async () => play.dispatchEvent(new MouseEvent("click", { bubbles: true }))); await act(async () => { await vi.advanceTimersByTimeAsync(1000); });
    expect(apiFetch).toHaveBeenCalledTimes(2); await act(async () => { await vi.advanceTimersByTimeAsync(5000); }); expect(apiFetch).toHaveBeenCalledTimes(2);
    step.resolve(response({ ...ready(), current_index: 1 })); await flush();
  });
  it("does not let an old in-flight step error clear a newer trade session", async () => {
    const oldStep = rejected<Response>();
    apiFetch.mockResolvedValueOnce(response(ready("OLD"))).mockReturnValueOnce(oldStep.promise).mockResolvedValueOnce(response(ready("NEW")));
    await act(async () => root.render(<TradeReplayCanvas tradeId="old" />)); await flush();
    const forward = host.querySelector('button[aria-label="Step forward"]')!;
    await act(async () => forward.dispatchEvent(new MouseEvent("click", { bubbles: true })));
    await act(async () => root.render(<TradeReplayCanvas tradeId="new" />)); await flush(); expect(host.textContent).toContain("NEW");
    oldStep.reject(new Error("old step failed")); await flush();
    expect(host.textContent).toContain("NEW"); expect(host.textContent).not.toContain("Replay unavailable");
  });
  it("ignores an old step success and lets the new trade step before it resolves", async () => {
    const oldStep = deferred<Response>();
    apiFetch.mockResolvedValueOnce(response(ready("OLD"))).mockReturnValueOnce(oldStep.promise).mockResolvedValueOnce(response(ready("NEW"))).mockResolvedValueOnce(response({ ...ready("NEW"), current_index: 1 }));
    await act(async () => root.render(<TradeReplayCanvas tradeId="old" />)); await flush();
    await act(async () => host.querySelector('button[aria-label="Step forward"]')!.dispatchEvent(new MouseEvent("click", { bubbles: true })));
    await act(async () => root.render(<TradeReplayCanvas tradeId="new" />)); await flush();
    await act(async () => host.querySelector('button[aria-label="Step forward"]')!.dispatchEvent(new MouseEvent("click", { bubbles: true }))); await flush();
    expect(apiFetch).toHaveBeenCalledTimes(4); expect(host.textContent).toContain("Bar 2 of 2");
    oldStep.resolve(response({ ...ready("OLD"), current_index: 1 })); await flush(); expect(host.textContent).toContain("NEW");
  });
});
