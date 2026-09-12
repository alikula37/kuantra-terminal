import { expect, it } from "vitest";
import { validTargets } from "../localTracking";

it("requires explicit full allocation with no skipped target index", () => {
  expect(validTargets([{ price: "", percent: "" }, { price: "120", percent: "100" }], 100, "BUY", null)).toBe(false);
  expect(validTargets([{ price: "110", percent: "" }], 100, "BUY", null)).toBe(false);
  expect(validTargets([{ price: "110", percent: "50" }], 100, "BUY", null)).toBe(false);
  expect(validTargets([{ price: "110", percent: "100" }], 100, "BUY", 95)).toBe(true);
  expect(validTargets([{ price: "90", percent: "100" }], 100, "SELL", 105)).toBe(true);
  expect(validTargets([{ price: "110", percent: "100" }], 100, "SELL", 105)).toBe(false);
  expect(validTargets([], 100, "SELL", 105)).toBe(true);
});
