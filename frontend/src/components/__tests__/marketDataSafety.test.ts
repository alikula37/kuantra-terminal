import { expect, it, vi } from "vitest";
import { canClosePositionAtMarketPrice, requestPositionClose } from "../DashboardView";

it("rejects dashboard close actions without a finite positive market price", () => {
  expect(canClosePositionAtMarketPrice(null)).toBe(false);
  expect(canClosePositionAtMarketPrice(0)).toBe(false);
  expect(canClosePositionAtMarketPrice(Number.NaN)).toBe(false);
  expect(canClosePositionAtMarketPrice(65001.25)).toBe(true);
  expect(canClosePositionAtMarketPrice(65001.25, "DEGRADED")).toBe(false);
  expect(canClosePositionAtMarketPrice(65001.25, "UNAVAILABLE")).toBe(false);
});

it("does not send a close request or report success when market price is unavailable", async () => {
  const request = vi.fn();

  const result = await requestPositionClose("OPEN-1", null, request);

  expect(request).not.toHaveBeenCalled();
  expect(result).toEqual({ closed: false, error: "Canlı piyasa fiyatı olmadan pozisyon kapatılamaz." });
});
