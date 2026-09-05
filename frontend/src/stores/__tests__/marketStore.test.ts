import { beforeEach, expect, it } from "vitest";
import { useMarketStore } from "../marketStore";

beforeEach(() => {
  useMarketStore.setState({
    currentPrice: null,
    prevPrice: null,
    eventAgeMs: null,
    lastTickTime: null,
    recentTicks: [],
  });
});

it("starts with an explicit no-data market state", () => {
  const state = useMarketStore.getState();

  expect(state.currentPrice).toBeNull();
  expect(state.prevPrice).toBeNull();
  expect(state.eventAgeMs).toBeNull();
  expect(state.lastTickTime).toBeNull();
  expect(state.recentTicks).toEqual([]);
});

it("records only a real tick with its supplied volume, timestamp, event age, and aggressor side", () => {
  useMarketStore.getState().updateTick(65001.25, 10, 1_700_000_000_000, 0.42, "SELL");
  const state = useMarketStore.getState();

  expect(state.currentPrice).toBe(65001.25);
  expect(state.eventAgeMs).toBe(10);
  expect(state.lastTickTime).toBe(1_700_000_000_000);
  expect(state.recentTicks).toEqual([{ price: 65001.25, volume: 0.42, time: 1_700_000_000_000, side: "SELL" }]);
});

it("preserves BUY, SELL, and UNKNOWN sides supplied by the market-data contract", () => {
  const store = useMarketStore.getState();
  store.updateTick(65001.25, 10, 1, 0.42, "BUY");
  store.updateTick(65000.25, 11, 2, 0.43, "SELL");
  store.updateTick(65001.25, 12, 3, 0.44, "UNKNOWN");
  store.updateTick(65002.25, 13, 4, 0.45, "MALFORMED");

  expect(useMarketStore.getState().recentTicks.map((tick) => tick.side)).toEqual(["UNKNOWN", "UNKNOWN", "SELL", "BUY"]);
});

it("keeps tick history while a no-data snapshot clears only market values", () => {
  useMarketStore.getState().updateTick(65001.25, 10, 1_700_000_000_000, 0.42, "BUY");
  useMarketStore.getState().setMarketSnapshot(null, null, null);
  const state = useMarketStore.getState();

  expect(state.currentPrice).toBeNull();
  expect(state.eventAgeMs).toBeNull();
  expect(state.recentTicks).toHaveLength(1);
});
