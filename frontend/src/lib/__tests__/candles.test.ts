import { describe, expect, it } from "vitest";
import {
  CHART_OLDER_CHUNK,
  hasMoreHistory,
  mergeCandleHistory,
  olderStartMs,
  timeframeMs,
  type CandlePoint,
} from "../candles";

const candle = (timestamp: number, close = 100): CandlePoint => ({
  timestamp,
  open: close,
  high: close,
  low: close,
  close,
  volume: 1,
});

describe("market chart history helpers", () => {
  it("merges older bars by timestamp in ascending order", () => {
    const recent = [candle(300, 3), candle(400, 4)];
    const older = [candle(100, 1), candle(200, 2)];
    const merged = mergeCandleHistory(recent, older);
    expect(merged.map((item) => item.timestamp)).toEqual([100, 200, 300, 400]);
  });

  it("keeps the newest record for a duplicate timestamp", () => {
    const merged = mergeCandleHistory([candle(100, 1)], [candle(100, 9)]);
    expect(merged).toHaveLength(1);
    expect(merged[0].close).toBe(9);
  });

  it("computes the older request window in milliseconds", () => {
    const oldestSeconds = 1_700_000_000;
    const startMs = olderStartMs(oldestSeconds, "1h");
    expect(startMs).toBe(oldestSeconds * 1000 - CHART_OLDER_CHUNK * 3_600_000);
    expect(timeframeMs("1d")).toBe(86_400_000);
    expect(timeframeMs("unknown")).toBe(3_600_000);
  });

  it("only reports more history for a full page", () => {
    expect(hasMoreHistory(1000, 1000)).toBe(true);
    expect(hasMoreHistory(1000, 180)).toBe(false);
    expect(hasMoreHistory(1000, 0)).toBe(false);
  });
});
