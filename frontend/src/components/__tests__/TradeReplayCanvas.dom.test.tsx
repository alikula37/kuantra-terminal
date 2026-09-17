// @vitest-environment jsdom
import React, { act } from "react";
import { createRoot, Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => {
  const apiFetch = vi.fn();
  const setData = vi.fn();
  const setMarkers = vi.fn();
  const remove = vi.fn();
  const removePriceLine = vi.fn();
  const createPriceLine = vi.fn((options: unknown) => ({ options, remove: removePriceLine }));
  const addCandlestickSeries = vi.fn(() => ({ setData, setMarkers, createPriceLine, removePriceLine }));
  const applyOptions = vi.fn();
  const createChart = vi.fn(() => ({ addCandlestickSeries, applyOptions, remove }));
  return { apiFetch, setData, setMarkers, remove, removePriceLine, createPriceLine, addCandlestickSeries, applyOptions, createChart, theme: "dark" as "dark" | "light" };
});
const { apiFetch, setData, setMarkers, removePriceLine, createPriceLine, createChart } = mocks;

vi.mock("../../lib/backend", () => ({ apiBase: () => "", apiFetch: mocks.apiFetch }));
vi.mock("lightweight-charts", () => ({
  createChart: mocks.createChart,
  LineStyle: { Solid: 0, Dotted: 1, Dashed: 2, LargeDashed: 3, SparseDotted: 4 },
}));
vi.mock("../../context/I18nContext", () => ({ useTranslation: () => ({ t: (key: string) => key, locale: "tr" }) }));
vi.mock("../../context/ThemeContext", () => ({
  useTheme: () => ({
    theme: mocks.theme,
    colors: {},
    setTheme: vi.fn(),
    toggleTheme: vi.fn(),
    getChartTheme: () => ({
      layout: { background: { color: mocks.theme === "light" ? "#f8fafc" : "#0b0e14" }, textColor: "#000" },
      grid: { vertLines: { color: "#eee" }, horzLines: { color: "#eee" } },
      candlestick: {
        upColor: "#059669", downColor: "#e11d48", borderUpColor: "#059669",
        borderDownColor: "#e11d48", wickUpColor: "#059669", wickDownColor: "#e11d48",
      },
    }),
  }),
}));

import { productCheckText, TradeReplayCanvas } from "../TradeReplayCanvas";

const candles = [
  { time: 1, open: 100, high: 101, low: 99, close: 100.5 },
  { time: 2, open: 100.5, high: 103, low: 100, close: 102 },
  { time: 3, open: 102, high: 104, low: 101, close: 103 },
];
const plan = {
  kind: "LOCAL_PLAN", reference: true, reference_code: "CURRENT_PLAN_REFERENCE",
  plan_revision: 3, plan_reset_count: 0, created_after_entry: false, plan_mismatch: false,
  levels: [
    { kind: "ENTRY", price: 100 },
    { kind: "SL", price: 96 },
    { kind: "TP1", price: 105, weight_pct: 50 },
    { kind: "TP2", price: 110, weight_pct: 50 },
  ],
};
const tradeState = {
  trade_id: "T1", symbol: "BTCUSDT", side: "BUY", entry_price: 100, current_price: 102,
  qty: 1, stop_loss: 96, take_profit: 110, phase: "ACTIVE", is_active: true, is_past_exit: false,
  unrealized_pnl: 2, realized_pnl: null, r_multiple: 0.5, mae_r: -0.2, mfe_r: 0.6,
  risk_unit: 4, entry_index: 0, exit_index: 2,
};
const ready = (symbol = "BTCUSDT", extra: Record<string, unknown> = {}) => ({
  status: "READY", reason: null, message: null,
  provenance: { quality: "BAR_APPROXIMATION", source: "DUCKDB_CANDLES", source_verified: false, timeframe: "1m" },
  session_id: `S-${symbol}`, symbol, total_bars: 3, current_index: 0, entry_index: 0, exit_index: 2,
  speed_multiplier: 1, is_playing: false, current_candle: candles[0], visible_candles: candles,
  trade: { ...tradeState, symbol }, plan, origin_class: "JOURNAL", close_evidence: null,
  market_context: {
    symbol, venue: "BINANCE", feed: "PUBLIC_REST", timeframe: "1m", bar_count: 3, trade_bar_count: 3,
    sequence_gap_count: 0, complete_trade_window: true,
  },
  ...extra,
});
const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const deferred = <T,>() => { let resolve!: (value: T) => void; return { promise: new Promise<T>((done) => { resolve = done; }), resolve }; };
const rejected = <T,>() => { let reject!: (reason?: unknown) => void; return { promise: new Promise<T>((_done, fail) => { reject = fail; }), reject }; };

let host: HTMLDivElement; let root: Root;
const flush = async () => { await act(async () => { await Promise.resolve(); await Promise.resolve(); }); };
const byTestId = (id: string) => host.querySelector(`[data-testid="${id}"]`) as HTMLElement | null;

beforeEach(() => {
  (globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
  mocks.theme = "dark";
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
  apiFetch.mockReset(); createChart.mockClear(); setData.mockClear(); setMarkers.mockClear();
  removePriceLine.mockClear(); createPriceLine.mockClear(); mocks.remove.mockClear(); mocks.addCandlestickSeries.mockClear();
});
afterEach(async () => { await act(async () => root.unmount()); host.remove(); vi.useRealTimers(); });

describe("TradeReplayCanvas read-only chart review (P1)", () => {
  it("waits for READY before chart initialization and cleans up", async () => {
    apiFetch.mockResolvedValue(response(ready()));
    await act(async () => root.render(<TradeReplayCanvas tradeId="T1" />)); await flush();
    expect(createChart).toHaveBeenCalledTimes(1);
    expect(setData).toHaveBeenCalledWith(expect.any(Array));
    await act(async () => root.unmount());
    expect(mocks.remove).toHaveBeenCalledTimes(1);
  });

  it("always shows the current-plan reference disclaimer and the plan kind", async () => {
    apiFetch.mockResolvedValue(response(ready()));
    await act(async () => root.render(<TradeReplayCanvas tradeId="T1" />)); await flush();
    expect(byTestId("replay-reference-banner")?.textContent).toContain("replay.reference_banner");
    expect(byTestId("replay-plan-kind")?.textContent).toContain("replay.plan_kind.local");
  });

  it("flags a plan that was created after the trade entry", async () => {
    apiFetch.mockResolvedValue(response(ready("BTCUSDT", { plan: { ...plan, revision: 1, created_after_entry: true } })));
    await act(async () => root.render(<TradeReplayCanvas tradeId="T1" />)); await flush();
    expect(byTestId("replay-plan-created-after")?.textContent).toContain("replay.plan_after_entry");
  });

  it("draws the recorded entry solid and plan levels as dashed reference lines with price and weight", async () => {
    apiFetch.mockResolvedValue(response(ready()));
    await act(async () => root.render(<TradeReplayCanvas tradeId="T1" />)); await flush();
    const calls = createPriceLine.mock.calls.map(([options]) => options as Record<string, unknown>);
    expect(calls).toHaveLength(4);
    const byTitle = Object.fromEntries(calls.map((line) => [String(line.title).split(" ")[0], line]));
    expect(byTitle.ENTRY.lineStyle).toBe(0);
    expect(byTitle.SL.lineStyle).toBe(2);
    expect(byTitle.TP1.lineStyle).toBe(2);
    expect(String(byTitle.TP1.title)).toContain("105");
    expect(String(byTitle.TP1.title)).toContain("50%");
    expect(String(byTitle.ENTRY.title)).toContain("100.00");
  });

  it("falls back to the trade row levels without inventing a weight", async () => {
    const tradeRowPlan = {
      ...plan, kind: "TRADE_ROW", plan_revision: null,
      levels: [{ kind: "ENTRY", price: 100 }, { kind: "SL", price: 95 }, { kind: "TP1", price: 108, weight_pct: null }],
    };
    apiFetch.mockResolvedValue(response(ready("BTCUSDT", { plan: tradeRowPlan })));
    await act(async () => root.render(<TradeReplayCanvas tradeId="T1" />)); await flush();
    expect(byTestId("replay-plan-kind")?.textContent).toContain("replay.plan_kind.trade_row");
    const tp1 = byTestId("replay-level-TP1");
    expect(tp1?.textContent).toContain("108.00");
    expect(tp1?.textContent).not.toContain("%");
  });

  it("destroys the previous chart and rebuilds fresh price lines when the trade changes", async () => {
    apiFetch.mockResolvedValue(response(ready("OLD")));
    await act(async () => root.render(<TradeReplayCanvas tradeId="old" />)); await flush();
    expect(createPriceLine).toHaveBeenCalledTimes(4);
    const oldLines = createPriceLine.mock.calls.map(([options]) => options as Record<string, unknown>);
    apiFetch.mockResolvedValue(response(ready("NEW")));
    await act(async () => root.render(<TradeReplayCanvas tradeId="new" />)); await flush();
    // The previous chart (owner of the old lines) is removed and exactly four
    // fresh lines are built for the new trade; no stale level line survives.
    expect(mocks.remove).toHaveBeenCalledTimes(1);
    expect(createPriceLine).toHaveBeenCalledTimes(8);
    const newLines = createPriceLine.mock.calls.slice(4).map(([options]) => options as Record<string, unknown>);
    expect(newLines).toHaveLength(4);
    for (const line of newLines) expect(oldLines).not.toContain(line);
    expect(host.textContent).toContain("NEW");
  });

  it("does not leak the close before the exit bar and marks it with its recorded source after", async () => {
    apiFetch.mockResolvedValue(response(ready()));
    await act(async () => root.render(<TradeReplayCanvas tradeId="T1" />)); await flush();
    const leaked = setMarkers.mock.calls.flatMap(([markers]) => (markers ?? []) as unknown[]);
    expect(leaked).toHaveLength(0);

    const closed = ready("BTCUSDT", {
      current_index: 2, trade: { ...tradeState, phase: "CLOSED", is_active: false, is_past_exit: true, realized_pnl: 3 },
      close_evidence: { price: 103, time_utc: "2026-09-01T10:02:35Z", source: "IMPORTED_FILE", broker_verified: false, close_source_raw: null },
    });
    apiFetch.mockResolvedValueOnce(response(closed));
    await act(async () => byTestId("replay-forward")!.dispatchEvent(new MouseEvent("click", { bubbles: true }))); await flush();
    const markers = setMarkers.mock.calls.flatMap(([value]) => (value ?? []) as Array<{ text?: string }>);
    expect(markers.length).toBeGreaterThan(0);
    expect(String(markers.at(-1)?.text)).toContain("replay.close_source.imported");
    expect(byTestId("replay-close-source")?.textContent).toContain("replay.close_source.imported");
  });

  it("uses the light chart theme when the app is in light mode", async () => {
    mocks.theme = "light";
    apiFetch.mockResolvedValue(response(ready()));
    await act(async () => root.render(<TradeReplayCanvas tradeId="T1" />)); await flush();
    const options = createChart.mock.calls[0][1] as { layout: { background: { color: string } } };
    expect(options.layout.background.color).toBe("#f8fafc");
  });

  it("shows provider, timeframe and the explicit gap note", async () => {
    apiFetch.mockResolvedValue(response(ready("BTCUSDT", {
      market_context: { symbol: "BTCUSDT", venue: "BINANCE", feed: "PUBLIC_REST", timeframe: "1m", bar_count: 3, trade_bar_count: 3, sequence_gap_count: 2, complete_trade_window: true },
    })));
    await act(async () => root.render(<TradeReplayCanvas tradeId="T1" />)); await flush();
    const strip = byTestId("replay-source-strip");
    expect(strip?.textContent).toContain("BINANCE");
    expect(strip?.textContent).toContain("PUBLIC_REST");
    expect(strip?.textContent).toContain("1m");
    expect(byTestId("replay-gap-note")?.textContent).toContain("replay.source_strip.gap_note");
    expect(byTestId("replay-disclaimer")?.textContent).toContain("replay.disclaimer");
  });

  it("renders an honest localized state for open trades instead of hiding the limit", async () => {
    apiFetch.mockResolvedValueOnce(response({
      ...ready(), status: "NO_DATA", session_id: null, total_bars: 0, current_index: null,
      current_candle: null, visible_candles: [], trade: null, plan: null, close_evidence: null,
      reason: "TRADE_NOT_CLOSED", message: "Historical evidence currently supports closed trades only.",
    }));
    await act(async () => root.render(<TradeReplayCanvas tradeId="open" />)); await flush();
    expect(createChart).not.toHaveBeenCalled();
    expect(byTestId("replay-state")?.getAttribute("data-reason")).toBe("TRADE_NOT_CLOSED");
    expect(host.textContent).toContain("replay.reason.TRADE_NOT_CLOSED");
    expect(host.textContent).toContain("replay.closed_only_note");
    expect(host.textContent).not.toContain("replay.disclaimer");
  });

  it("localizes a missing candle history without leaking the raw English message", async () => {
    apiFetch.mockResolvedValueOnce(response({
      ...ready(), status: "NO_DATA", session_id: null, total_bars: 0, current_index: null,
      current_candle: null, visible_candles: [], trade: null, plan: null, close_evidence: null,
      reason: "NO_CANDLE_HISTORY", message: "No recorded one-minute history covers this trade.",
    }));
    await act(async () => root.render(<TradeReplayCanvas tradeId="gold" />)); await flush();
    expect(host.textContent).toContain("replay.reason.NO_CANDLE_HISTORY");
    expect(host.textContent).not.toContain("replay.reason.unknown");
    expect(host.textContent).not.toContain("No recorded one-minute history covers this trade.");
  });

  it("shows the raw reason when a state is not localized yet", async () => {
    apiFetch.mockResolvedValueOnce(response({ ...ready(), status: "NO_DATA", reason: "SOMETHING_NEW", message: "New server reason." }));
    await act(async () => root.render(<TradeReplayCanvas tradeId="T1" />)); await flush();
    expect(host.textContent).toContain("SOMETHING_NEW");
    expect(host.textContent).toContain("New server reason.");
  });

  it("ignores a stale trade response after tradeId changes", async () => {
    const oldRequest = deferred<Response>(), newRequest = deferred<Response>();
    apiFetch.mockReturnValueOnce(oldRequest.promise).mockReturnValueOnce(newRequest.promise);
    await act(async () => root.render(<TradeReplayCanvas tradeId="old" />));
    await act(async () => root.render(<TradeReplayCanvas tradeId="new" />));
    newRequest.resolve(response(ready("NEW"))); await flush();
    expect(host.textContent).toContain("NEW");
    oldRequest.resolve(response(ready("OLD"))); await flush();
    expect(host.textContent).not.toContain("OLD");
    expect(host.textContent).toContain("NEW");
  });

  it("does not overlap playback step requests while a prior step is in flight", async () => {
    vi.useFakeTimers();
    const step = deferred<Response>();
    apiFetch.mockResolvedValueOnce(response(ready())).mockReturnValueOnce(step.promise);
    await act(async () => root.render(<TradeReplayCanvas tradeId="T1" />)); await flush();
    await act(async () => byTestId("replay-play")!.dispatchEvent(new MouseEvent("click", { bubbles: true })));
    await act(async () => { await vi.advanceTimersByTimeAsync(1000); });
    expect(apiFetch).toHaveBeenCalledTimes(2);
    await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
    expect(apiFetch).toHaveBeenCalledTimes(2);
    step.resolve(response({ ...ready(), current_index: 1 }));
    await flush();
  });

  it("does not let an old in-flight step error clear a newer trade session", async () => {
    const oldStep = rejected<Response>();
    apiFetch.mockResolvedValueOnce(response(ready("OLD"))).mockReturnValueOnce(oldStep.promise).mockResolvedValueOnce(response(ready("NEW")));
    await act(async () => root.render(<TradeReplayCanvas tradeId="old" />)); await flush();
    await act(async () => byTestId("replay-forward")!.dispatchEvent(new MouseEvent("click", { bubbles: true })));
    await act(async () => root.render(<TradeReplayCanvas tradeId="new" />)); await flush();
    expect(host.textContent).toContain("NEW");
    oldStep.reject(new Error("old step failed")); await flush();
    expect(host.textContent).toContain("NEW");
    expect(byTestId("replay-state")).toBeNull();
  });

  it("ignores an old step success and lets the new trade step before it resolves", async () => {
    const oldStep = deferred<Response>();
    apiFetch
      .mockResolvedValueOnce(response(ready("OLD")))
      .mockReturnValueOnce(oldStep.promise)
      .mockResolvedValueOnce(response(ready("NEW")))
      .mockResolvedValueOnce(response({ ...ready("NEW"), current_index: 1 }));
    await act(async () => root.render(<TradeReplayCanvas tradeId="old" />)); await flush();
    await act(async () => byTestId("replay-forward")!.dispatchEvent(new MouseEvent("click", { bubbles: true })));
    await act(async () => root.render(<TradeReplayCanvas tradeId="new" />)); await flush();
    await act(async () => byTestId("replay-forward")!.dispatchEvent(new MouseEvent("click", { bubbles: true }))); await flush();
    expect(apiFetch).toHaveBeenCalledTimes(4);
    expect(host.textContent).toContain("NEW");
    oldStep.resolve(response({ ...ready("OLD"), current_index: 1 })); await flush();
    expect(host.textContent).toContain("NEW");
  });
});

const openBlock = {
  history_status: "FULL_SINCE_ENTRY", timeframe: "1m", entry_bar_present: true,
  bars: 3, coverage_start_utc: "2026-09-01T10:00:00Z", coverage_end_utc: "2026-09-01T10:02:00Z",
  missing_before_entry_minutes: 0, gap_count: 0, gap_ranges: [], gap_note: "RANGE_NOT_ASSESSABLE",
  bars_truncated: false, last_candle_time_utc: "2026-09-01T10:02:00Z", last_candle_age_seconds: 4200,
  last_candle_state: "CLOSED", delay_indicator: "DELAYED", provider_latency: "UNKNOWN",
  last_download_at: null, refresh_result: "NOT_REQUESTED", provider: null, provider_symbol: null,
  identity_verified: false, identity_note: "SYMBOL_TEXT_NOT_PROVIDER_PROOF",
  instrument: "XAUUSD", cache_symbol: "XAUUSD", store: "SQLITE_CHART_CACHE",
};

const openReady = (extra: Record<string, unknown> = {}) => {
  const block = { ...openBlock, ...extra };
  return {
    ...ready("XAUUSD"),
    review_mode: "OPEN",
    exit_index: null,
    close_evidence: null,
    open_review: block,
    trade: { ...tradeState, symbol: "XAUUSD", exit_index: null, phase: "ACTIVE" },
    market_context: { ...(ready("XAUUSD").market_context as Record<string, unknown>), sequence_gap_count: block.gap_count },
  };
};

describe("open position review (OP-01)", () => {
  it("shows the open badge, levels and no close marker or performance numbers", async () => {
    apiFetch.mockResolvedValue(response(openReady()));
    await act(async () => root.render(<TradeReplayCanvas tradeId="open" />)); await flush();
    const text = host.textContent || "";
    expect(text).toContain("replay.open_review.badge");
    expect(byTestId("replay-reference-banner")?.textContent).toContain("replay.reference_banner");
    expect(byTestId("replay-level-TP1")).not.toBeNull();
    expect(text).toContain("replay.open_review.no_performance");
    expect(text).not.toContain("replay.summary.unrealized");
    expect(text).not.toContain("replay.close_marker");
    const markers = setMarkers.mock.calls.flatMap(([value]) => (value ?? []) as unknown[]);
    expect(markers).toHaveLength(0);
  });

  it("reports delayed data only as a delay indicator, never as live", async () => {
    apiFetch.mockResolvedValue(response(openReady()));
    await act(async () => root.render(<TradeReplayCanvas tradeId="open" />)); await flush();
    const banner = byTestId("replay-freshness");
    expect(banner?.textContent).toContain("replay.open_review.freshness_delayed");
    expect(banner?.textContent).toContain("replay.open_review.last_candle");
    expect(banner?.textContent).not.toMatch(/canlı veri|LIVE DATA/i);
    expect(byTestId("replay-provider")?.textContent).toContain("replay.open_review.provider_unknown");
    expect(byTestId("replay-identity")?.textContent).toContain("replay.open_review.identity_note");
  });

  it("renders the product check with the independent source, never a bare verified claim", async () => {
    apiFetch.mockResolvedValue(response(openReady({
      instrument_product: {
        status: "CONSISTENT", reason: null, product_key: "SPOT_METAL:XAU:USD", asset_class: "SPOT_METAL",
        declared_provider: "biquote_public", declared_symbol: "XAUUSD",
        independent_provider: "yahoo_public", independent_symbol: "XAUUSD=X",
        alignment: "EXACT_BAR", overlap_bars: 42, median_deviation_pct: 0.034, max_deviation_pct: 0.09,
        tolerance_pct: 0.5, checked_at: "2026-09-17T09:20:00Z", note: "NOT_BROKER_EXECUTION_EVIDENCE",
      },
    })));
    await act(async () => root.render(<TradeReplayCanvas tradeId="open" />)); await flush();
    const line = byTestId("replay-product-check");
    expect(line?.getAttribute("data-product-status")).toBe("CONSISTENT");
    expect(line?.getAttribute("data-product-provider")).toBe("yahoo_public");
    expect(line?.getAttribute("data-product-key")).toBe("SPOT_METAL:XAU:USD");
    expect(line?.textContent).toContain("replay.open_review.product_consistent");
    expect(host.textContent).not.toMatch(/ürün doğrulandı|product verified/i);
  });

  it("shows divergent and unverifiable product states honestly", async () => {
    apiFetch.mockResolvedValue(response(openReady({
      instrument_product: {
        status: "DIVERGENT", reason: null, product_key: "SPOT_METAL:XAU:USD", asset_class: "SPOT_METAL",
        declared_provider: "biquote_public", declared_symbol: "XAUUSD",
        independent_provider: "yahoo_public", independent_symbol: "XAUUSD=X",
        alignment: "EXACT_BAR", overlap_bars: 30, median_deviation_pct: 2.4, max_deviation_pct: 3.1,
        tolerance_pct: 0.5, checked_at: "2026-09-17T09:20:00Z", note: "NOT_BROKER_EXECUTION_EVIDENCE",
      },
    })));
    await act(async () => root.render(<TradeReplayCanvas tradeId="open" />)); await flush();
    expect(byTestId("replay-product-check")?.getAttribute("data-product-status")).toBe("DIVERGENT");
    expect(byTestId("replay-product-check")?.textContent).toContain("replay.open_review.product_divergent");

    apiFetch.mockResolvedValue(response(openReady({
      instrument_product: {
        status: "UNVERIFIABLE", reason: "INSUFFICIENT_OVERLAP", product_key: "SPOT_METAL:XAU:USD",
        asset_class: "SPOT_METAL", declared_provider: "biquote_public", declared_symbol: "XAUUSD",
        independent_provider: "stooq_public", independent_symbol: "xauusd",
        alignment: "UTC_DAY", overlap_bars: 3, median_deviation_pct: null, max_deviation_pct: null,
        tolerance_pct: 0.5, checked_at: "2026-09-17T09:20:00Z", note: "NOT_BROKER_EXECUTION_EVIDENCE",
      },
    })));
    await act(async () => root.render(<TradeReplayCanvas tradeId="open-unverifiable" />)); await flush();
    expect(byTestId("replay-product-check")?.getAttribute("data-product-status")).toBe("UNVERIFIABLE");
    expect(byTestId("replay-product-check")?.textContent).toContain("replay.open_review.product_unverifiable");
  });

  it("never renders an unrecognized product-check reason raw", () => {
    const calls: Array<[string, Record<string, string> | undefined]> = [];
    const t = (key: string, params?: Record<string, string>) => { calls.push([key, params]); return key; };
    const text = productCheckText({
      status: "UNVERIFIABLE", reason: "SOMETHING_NEW", product_key: null, asset_class: null,
      declared_provider: "biquote_public", declared_symbol: "XAUUSD",
      independent_provider: null, independent_symbol: null, alignment: null, overlap_bars: 0,
      median_deviation_pct: null, max_deviation_pct: null, tolerance_pct: null,
      checked_at: null, note: "NOT_BROKER_EXECUTION_EVIDENCE",
    }, t);
    expect(text).toBe("replay.open_review.product_unverifiable");
    expect(calls.map(([key]) => key)).toEqual([
      "replay.product_reason.UNKNOWN", "replay.open_review.product_unverifiable",
    ]);
  });

  it("shows partial history with the covered range and gap note", async () => {
    apiFetch.mockResolvedValue(response(openReady({
      history_status: "PARTIAL_SINCE_ENTRY", entry_bar_present: false,
      missing_before_entry_minutes: 12, coverage_start_utc: "2026-09-01T10:12:00Z",
      coverage_end_utc: "2026-09-01T11:00:00Z", gap_count: 2, delay_indicator: "FRESH_DELAY",
    })));
    await act(async () => root.render(<TradeReplayCanvas tradeId="open" />)); await flush();
    expect(byTestId("replay-partial-history")?.textContent).toContain("replay.open_review.partial_history");
    expect(host.textContent).toContain("replay.open_review.freshness_fresh");
    expect(byTestId("replay-gap-note")?.textContent).toContain("replay.source_strip.gap_note");
  });

  it("refreshes manually only, keeps the chart on failure and retries", async () => {
    vi.useFakeTimers();
    apiFetch.mockResolvedValueOnce(response(openReady()));
    await act(async () => root.render(<TradeReplayCanvas tradeId="open" />)); await flush();
    expect(apiFetch).toHaveBeenCalledTimes(1);
    await act(async () => { await vi.advanceTimersByTimeAsync(120000); });
    expect(apiFetch).toHaveBeenCalledTimes(1);  // no automatic refresh

    const failed = deferred<Response>();
    apiFetch.mockReturnValueOnce(failed.promise);
    await act(async () => byTestId("replay-refresh")!.dispatchEvent(new MouseEvent("click", { bubbles: true })));
    expect(String(apiFetch.mock.calls[1][0])).toContain("refresh=true");
    failed.resolve(response({ ...openReady(), status: "UNAVAILABLE", reason: "REFRESH_FAILED", message: "no candles" }));
    await flush();
    expect(byTestId("replay-refresh-error")?.textContent).toContain("replay.refresh.error");
    expect(byTestId("replay-chart")).not.toBeNull();  // chart retained
    expect(host.textContent).toContain("replay.open_review.badge");

    apiFetch.mockResolvedValueOnce(response(openReady({ last_download_at: "2026-09-01T11:05:00Z", provider: "BIQUOTE" })));
    await act(async () => byTestId("replay-refresh")!.dispatchEvent(new MouseEvent("click", { bubbles: true })));
    await flush();
    expect(byTestId("replay-refresh-error")).toBeNull();
    expect(byTestId("replay-provider")?.getAttribute("data-provider")).toBe("BIQUOTE");
    expect(byTestId("replay-provider")?.textContent).toContain("replay.open_review.provider");
    expect(byTestId("replay-freshness")?.textContent).toContain("replay.open_review.last_download");
    vi.useRealTimers();
  });

  it("ignores a late refresh response after the trade changed", async () => {
    const stale = deferred<Response>();
    apiFetch.mockResolvedValueOnce(response(openReady())).mockReturnValueOnce(stale.promise).mockResolvedValueOnce(response(openReady({ instrument: "XAUUSD" })));
    await act(async () => root.render(<TradeReplayCanvas tradeId="open" />)); await flush();
    await act(async () => byTestId("replay-refresh")!.dispatchEvent(new MouseEvent("click", { bubbles: true })));
    await act(async () => root.render(<TradeReplayCanvas tradeId="other" />)); await flush();
    stale.resolve(response(openReady({ instrument: "STALE" })));
    await flush();
    expect(host.textContent).toContain("replay.open_review.badge");
    expect(host.textContent).not.toContain("STALE");
  });
});

describe("close source labels cannot be forged (P1 label contract)", () => {
  it("shows a declared-but-unverified raw close source without any verified label", async () => {
    const forged = ready("BTCUSDT", {
      current_index: 2,
      trade: { ...tradeState, phase: "CLOSED", is_active: false, is_past_exit: true, realized_pnl: 3 },
      close_evidence: { price: 103, time_utc: "2026-09-01T10:02:35Z", source: "SOURCE_DECLARED", broker_verified: false, close_source_raw: "BROKER_VERIFIED" },
    });
    apiFetch.mockResolvedValueOnce(response(ready())).mockResolvedValueOnce(response(forged));
    await act(async () => root.render(<TradeReplayCanvas tradeId="T1" />)); await flush();
    await act(async () => byTestId("replay-forward")!.dispatchEvent(new MouseEvent("click", { bubbles: true }))); await flush();
    const text = host.textContent || "";
    expect(byTestId("replay-close-source")?.textContent).toContain("replay.close_source.source_declared");
    expect(text).toContain("BROKER_VERIFIED");  // raw declaration stays visible
    expect(text).not.toContain("replay.close_source.broker_verified");
    const markers = setMarkers.mock.calls.flatMap(([value]) => (value ?? []) as Array<{ text?: string }>);
    expect(String(markers.at(-1)?.text)).toContain("replay.close_source.source_declared");
    expect(String(markers.at(-1)?.text)).not.toContain("replay.close_source.broker_verified");
  });
});

describe("open review provider match (OP-01 hard-fail rules)", () => {
  const unmatched = (reason: string, extra: Record<string, unknown> = {}) => ({
    ...ready("XAUUSD"), status: "NO_DATA", review_mode: "OPEN", reason, message: null,
    session_id: null, total_bars: 0, current_index: null, entry_index: null, exit_index: null,
    current_candle: null, visible_candles: [], trade: null, plan: null, close_evidence: null,
    open_review: null, provider: "biquote_public", provider_symbol: "XAUUSD",
    ...extra,
  });

  it("asks for a manual refresh without ever drawing cached rows", async () => {
    apiFetch.mockResolvedValueOnce(response(unmatched("PROVIDER_MATCH_REQUIRED")))
      .mockResolvedValueOnce(response(openReady({ provider: "biquote_public", provider_symbol: "XAUUSD" })));
    await act(async () => root.render(<TradeReplayCanvas tradeId="open" />)); await flush();
    expect(createChart).not.toHaveBeenCalled();
    expect(host.textContent).toContain("replay.reason.PROVIDER_MATCH_REQUIRED");
    expect(byTestId("replay-declared-identity")?.getAttribute("data-provider")).toBe("biquote_public");
    expect(byTestId("replay-declared-identity")?.getAttribute("data-provider-symbol")).toBe("XAUUSD");

    await act(async () => byTestId("replay-refresh")!.dispatchEvent(new MouseEvent("click", { bubbles: true })));
    await flush();
    expect(String(apiFetch.mock.calls[1][0])).toContain("refresh=true");
    expect(host.textContent).toContain("replay.open_review.badge");
    expect(byTestId("replay-provider")?.getAttribute("data-provider")).toBe("biquote_public");
  });

  it("reports a declared-provider failure honestly and keeps the retry available", async () => {
    apiFetch.mockResolvedValueOnce(response(unmatched("PROVIDER_MATCH_REQUIRED")))
      .mockResolvedValueOnce(response(unmatched("PROVIDER_FETCH_FAILED", { provider_symbol: "XAUUSD" })));
    await act(async () => root.render(<TradeReplayCanvas tradeId="open" />)); await flush();
    await act(async () => byTestId("replay-refresh")!.dispatchEvent(new MouseEvent("click", { bubbles: true })));
    await flush();
    // The failed refresh keeps the previous state and shows a retry error.
    expect(host.textContent).toContain("replay.refresh.error");
    expect(host.textContent).toContain("replay.reason.PROVIDER_MATCH_REQUIRED");
    expect(byTestId("replay-refresh")).not.toBeNull();
  });

  it("shows guidance instead of a refresh button when no provider is declared", async () => {
    apiFetch.mockResolvedValueOnce(response(unmatched("PROVIDER_NOT_DECLARED", {
      provider: null, provider_symbol: null,
    })));
    await act(async () => root.render(<TradeReplayCanvas tradeId="open" />)); await flush();
    expect(host.textContent).toContain("replay.reason.PROVIDER_NOT_DECLARED");
    expect(byTestId("replay-refresh")).toBeNull();
  });
});
