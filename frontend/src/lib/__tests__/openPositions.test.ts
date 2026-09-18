import { describe, expect, it } from "vitest";
import { mergePositionUpdates } from "../openPositions";

describe("mergePositionUpdates", () => {
  it("applies live prices without dropping unit/label metadata", () => {
    const existing = [{
      id: "TRD-1", symbol: "BTCUSDT", side: "BUY", status: "OPEN", entry_price: 76000,
      qty: 100, qty_unit: "USD", record_mode: "SIMULATION", unrealized_pnl: 0,
    }] as never[];
    const live = [{
      id: "TRD-1", symbol: "BTCUSDT", side: "BUY", entry_price: 76000,
      current_price: 76787.7, qty: 100, unrealized_pnl: 1.04,
    }] as never[];
    const merged = mergePositionUpdates(existing, live);
    expect(merged).toHaveLength(1);
    expect((merged[0] as Record<string, unknown>).record_mode).toBe("SIMULATION");
    expect((merged[0] as Record<string, unknown>).qty_unit).toBe("USD");
    expect((merged[0] as Record<string, unknown>).unrealized_pnl).toBe(1.04);
  });

  it("keeps server rows when a live update omits fields or the feed is empty", () => {
    const existing = [{ id: "TRD-1", status: "OPEN", qty_unit: "USD", record_mode: "SIMULATION" }] as never[];
    expect(mergePositionUpdates(existing, [] as never[])[0]).toMatchObject({ qty_unit: "USD" });
    const partial = mergePositionUpdates(existing, [{ id: "TRD-1", current_price: 1 }] as never[]);
    expect(partial[0]).toMatchObject({ qty_unit: "USD", record_mode: "SIMULATION", current_price: 1 });
  });
});
