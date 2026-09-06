import { describe, expect, it } from "vitest";
import { canRenderReplayChart, shouldApplyReplayResponse } from "../TradeReplayCanvas";
import { finite, matchesSide, plotEligible } from "../MaeMfeVisualizer";
import type { MaeMfePoint, ReplaySessionResponse } from "../../types";

const noData: ReplaySessionResponse = {
  status: "NO_DATA", reason: "MISSING_CANDLES", message: "No recorded candles.", provenance: null,
  session_id: null, symbol: null, total_bars: 0, current_index: null, entry_index: null, exit_index: null,
  speed_multiplier: 1, is_playing: false, current_candle: null, trade: null, visible_candles: [],
};

describe("replay truth UI guards", () => {
  it("does not initialize a chart until an async READY session has visible candles", () => {
    expect(canRenderReplayChart(noData)).toBe(false);
    expect(canRenderReplayChart({ ...noData, status: "READY", session_id: "S-1", visible_candles: [{ time: 1, open: 1, high: 2, low: 1, close: 2 }] })).toBe(true);
  });
  it("rejects a late response belonging to a previous trade", () => {
    expect(shouldApplyReplayResponse(1, 2)).toBe(false);
    expect(shouldApplyReplayResponse(2, 2)).toBe(true);
  });
});

describe("excursion truth UI guards", () => {
  const point = { trade_id: "T1", symbol: "BTCUSDT", side: "BUY", entry_price: 1, exit_price: 2, risk_unit: null, mae_price: null, mfe_price: null, mae_r: null, mfe_r: null, exit_efficiency: null, pnl: null, r_multiple: null, status: "NO_RISK", provenance: null, risk_reason: "MISSING_STOP" } as MaeMfePoint;
  it("uses an em-dash-compatible finite guard for null and non-finite values", () => {
    expect(finite(null)).toBe(false); expect(finite(Number.NaN)).toBe(false); expect(finite(Infinity)).toBe(false); expect(finite(1.25)).toBe(true);
  });
  it("does not draw null-risk points, but draws finite MAE/MFE pairs", () => {
    expect(plotEligible(point)).toBe(false);
    expect(plotEligible({ ...point, mae_r: -0.5, mfe_r: 1.25 })).toBe(true);
  });
  it("treats LONG/SHORT as their BUY/SELL filter equivalents", () => {
    expect(matchesSide("LONG", "BUY")).toBe(true);
    expect(matchesSide("SHORT", "SELL")).toBe(true);
  });
});
