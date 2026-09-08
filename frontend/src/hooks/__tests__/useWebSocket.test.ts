import { expect, it } from "vitest";
import { normalizeMarketDataStatus } from "../useWebSocket";

it("accepts only explicit market-data truth states", () => {
  expect(normalizeMarketDataStatus("LIVE")).toBe("LIVE");
  expect(normalizeMarketDataStatus("DEGRADED")).toBe("DEGRADED");
  expect(normalizeMarketDataStatus("UNAVAILABLE")).toBe("UNAVAILABLE");
  expect(normalizeMarketDataStatus("NO_DATA")).toBe("UNAVAILABLE");
  expect(normalizeMarketDataStatus(undefined)).toBe("UNAVAILABLE");
});
