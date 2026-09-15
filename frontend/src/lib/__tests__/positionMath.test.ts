import { describe, expect, it } from "vitest";
import {
  classifyInstrument,
  concentrationWarnings,
  equalPercentages,
  formatPrice,
  positionSizing,
} from "../positionMath";

describe("position sizing rules", () => {
  it("keeps price, position and margin returns separate for leveraged trades", () => {
    const sizing = positionSizing({
      symbol: "BTCUSDT",
      positionType: "LONG",
      side: "BUY",
      entryPrice: 100,
      qty: 10,
      leverage: 10,
      exitPrice: 110,
      qtyUnit: "BASE",
    });
    expect(sizing.notional.value).toBe(1000);
    expect(sizing.marginEstimate.value).toBe(100);
    expect(sizing.marginEstimate.source).toBe("ESTIMATED_FROM_DECLARED_LEVERAGE");
    expect(sizing.priceReturnPct).toBeCloseTo(10);
    expect(sizing.positionReturnPctGross).toBeCloseTo(10);
    expect(sizing.marginReturnPctGross).toBeCloseTo(100);
    expect(sizing.leverage.source).toBe("USER_DECLARED");
  });

  it("treats spot as full payment without leverage", () => {
    const sizing = positionSizing({
      symbol: "LINKUSDT",
      positionType: "SPOT",
      side: "BUY",
      entryPrice: 10,
      qty: 2,
      qtyUnit: "BASE",
    });
    expect(sizing.leverage.value).toBe(1);
    expect(sizing.leverage.source).toBe("SPOT_IMPLIED");
    expect(sizing.marginEstimate.value).toBe(20);
    expect(sizing.marginEstimate.source).toBe("SPOT_FULL_PAYMENT");
    expect(sizing.warnings).not.toContain("LEVERAGE_NOT_DECLARED");
  });

  it("labels an unknown contract size and withholds every monetary figure", () => {
    const sizing = positionSizing({
      symbol: "XAUUSD",
      positionType: "LONG",
      side: "BUY",
      entryPrice: 2000,
      qty: 1,
      leverage: 10,
      exitPrice: 2100,
    });
    expect(classifyInstrument("XAUUSD").contractSize).toBe("UNVERIFIED");
    expect(sizing.warnings).toContain("CONTRACT_SIZE_UNVERIFIED");
    expect(sizing.monetaryCalculation).toEqual({ status: "UNAVAILABLE", reason: "CONTRACT_SIZE_UNVERIFIED" });
    expect(sizing.notional.value).toBeNull();
    expect(sizing.marginEstimate.value).toBeNull();
    expect(sizing.positionReturnPctGross).toBeNull();
    expect(sizing.marginReturnPctGross).toBeNull();
    // The unit-free price move is still shown.
    expect(sizing.priceReturnPct).toBeCloseTo(5);
    expect(JSON.stringify(sizing)).not.toContain("liquidation");
  });

  it.each(["GC=F", "ES=F", "EURUSD=X", "EURUSD", "GBPUSD", "FAKEUSD", "^GSPC", "ARCLK.IS", "AAPL"])(
    "treats %s as an unverified unit and produces no money numbers",
    (symbol) => {
      const sizing = positionSizing({
        symbol,
        positionType: "LONG",
        side: "BUY",
        entryPrice: 100,
        qty: 2,
        leverage: 10,
        exitPrice: 110,
      });
      expect(sizing.monetaryCalculation.status).toBe("UNAVAILABLE");
      expect(sizing.notional.value).toBeNull();
      expect(sizing.marginEstimate.value).toBeNull();
      expect(sizing.positionReturnPctGross).toBeNull();
      expect(sizing.marginReturnPctGross).toBeNull();
    },
  );

  it("does not invent a margin estimate without declared leverage", () => {
    const sizing = positionSizing({
      symbol: "ETHUSDT",
      positionType: "LONG",
      side: "BUY",
      entryPrice: 100,
      qty: 1,
      qtyUnit: "BASE",
    });
    expect(sizing.marginEstimate.value).toBeNull();
    expect(sizing.warnings).toContain("LEVERAGE_NOT_DECLARED");
  });

  it("labels currency only for known quote pairs", () => {
    expect(formatPrice("BTCUSDT", 65000)).toContain("$");
    expect(formatPrice("ARCLK.IS", 120)).not.toContain("$");
  });

  it("accepts only an explicit user declaration as the unit basis", () => {
    const suffixOnly = positionSizing({
      symbol: "EURUSD", positionType: "LONG", side: "BUY",
      entryPrice: 1.1, qty: 1000, leverage: 10, exitPrice: 1.12,
    });
    expect(suffixOnly.instrument.verification).toBe("NONE");
    expect(suffixOnly.instrument.verificationSource).toBe("NONE");
    expect(suffixOnly.monetaryCalculation.status).toBe("UNAVAILABLE");
    expect(suffixOnly.notional.value).toBeNull();

    // A crypto symbol without a declaration is not verified either; only the
    // explicit user contract (labeled as a user declaration) enables math.
    const cryptoUndeclared = positionSizing({
      symbol: "BTCUSDT", positionType: "LONG", side: "BUY",
      entryPrice: 100, qty: 2, leverage: 10, exitPrice: 110,
    });
    expect(cryptoUndeclared.instrument.verification).toBe("NONE");
    expect(cryptoUndeclared.monetaryCalculation.status).toBe("UNAVAILABLE");

    const explicit = positionSizing({
      symbol: "EURUSD", positionType: "LONG", side: "BUY",
      entryPrice: 1.1, qty: 1000, leverage: 10, exitPrice: 1.12, qtyUnit: "BASE",
    });
    expect(explicit.instrument.verification).toBe("EXPLICIT_QTY_UNIT");
    expect(explicit.instrument.verificationSource).toBe("USER_DECLARATION");
    expect(explicit.monetaryCalculation.status).toBe("READY");
    expect(explicit.notional.value).toBeCloseTo(1100);
  });

  it("splits three targets to exactly 100 percent", () => {
    expect(equalPercentages(3)).toEqual(["33.33", "33.33", "33.34"]);
    expect(equalPercentages(2)).toEqual(["50.00", "50.00"]);
    expect(equalPercentages(1)).toEqual(["100.00"]);
    expect(equalPercentages(4)).toEqual([]);
  });

  it("warns on a wrong allocation total and a dominant first target", () => {
    expect(concentrationWarnings([{ percent: "50" }, { percent: "25" }], null, 100)[0]).toContain("ALLOCATION_NOT_TOTAL");
    expect(concentrationWarnings([{ percent: "90" }, { percent: "10" }], null, 100)).toContain("FIRST_TARGET_DOMINANT:90");
  });
});
