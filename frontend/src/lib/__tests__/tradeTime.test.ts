import { describe, expect, it } from "vitest";
import {
  formatIstanbulDateTime,
  isFutureIstanbulInput,
  istanbulDateKey,
  istanbulInputToUtcIso,
  istanbulInputValue,
  relativeAgeLabel,
  utcIsoToIstanbulInput,
} from "../tradeTime";

describe("Turkey-time trade helpers", () => {
  it("stores Istanbul wall time as UTC and round-trips exactly", () => {
    expect(istanbulInputToUtcIso("2026-01-15T10:30")).toBe("2026-01-15T07:30:00.000Z");
    expect(utcIsoToIstanbulInput("2026-01-15T07:30:00Z")).toBe("2026-01-15T10:30");
    expect(istanbulInputToUtcIso("2026-07-15T10:30")).toBe("2026-07-15T07:30:00.000Z");
  });

  it("derives the Istanbul calendar day for filters, not the UTC day", () => {
    expect(istanbulDateKey("2026-01-14T22:30:00Z")).toBe("2026-01-15");
    expect(istanbulDateKey("2026-01-15T20:59:00Z")).toBe("2026-01-15");
    expect(istanbulDateKey("2026-01-15T21:00:00Z")).toBe("2026-01-16");
  });

  it("rejects malformed input and detects a clearly future realized time", () => {
    expect(istanbulInputToUtcIso("not-a-time")).toBeNull();
    expect(isFutureIstanbulInput("2099-01-01T00:00")).toBe(true);
    expect(isFutureIstanbulInput("2020-01-01T00:00")).toBe(false);
  });

  it("formats dates in Istanbul regardless of the machine timezone", () => {
    expect(istanbulInputValue(new Date("2026-09-14T07:30:00Z"))).toBe("2026-09-14T10:30");
    expect(formatIstanbulDateTime("2026-09-14T07:30:00Z", "en")).toContain("10:30");
    expect(formatIstanbulDateTime("2026-09-14T07:30:00Z", "tr")).toContain("10:30");
  });

  it("renders compact age labels", () => {
    expect(relativeAgeLabel(5)).toBe("5s");
    expect(relativeAgeLabel(120)).toBe("2m");
    expect(relativeAgeLabel(7200)).toBe("2h");
    expect(relativeAgeLabel(null)).toBe("");
  });
});
