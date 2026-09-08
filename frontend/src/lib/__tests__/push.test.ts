import { beforeEach, expect, it, vi } from "vitest";
declare const globalThis: any;
beforeEach(() => { vi.resetModules(); globalThis.window = globalThis; delete globalThis.__kuantraPush; delete globalThis.pywebview; });

it("dispatches batched messages (objects or JSON strings) to subscribers", async () => {
  const { installPushSink, subscribePush } = await import("../push");
  installPushSink();
  const got: any[] = [];
  const off = subscribePush((m) => got.push(m));
  globalThis.__kuantraPush([{ type: "TICK", price: 1 }, JSON.stringify({ type: "CANDLE_UPDATE" }), "not json"]);
  expect(got.map((m) => m.type)).toEqual(["TICK", "CANDLE_UPDATE"]);
  off();
  globalThis.__kuantraPush([{ type: "TICK" }]);
  expect(got).toHaveLength(2);
});

it("openStream returns the snapshot from the bridge and null in the browser", async () => {
  const { openStream } = await import("../push");
  expect(await openStream()).toBeNull();
  globalThis.pywebview = { api: { request: async () => ({}), stream_open: async () => ({ type: "SNAPSHOT", symbol: "BTCUSDT", last_price: 1, event_age_ms: 10, timestamp: 1700000000000, status: "LIVE", open_positions: [] }) } };
  expect((await openStream())?.symbol).toBe("BTCUSDT");
});

it("preserves an explicit degraded snapshot status from the desktop bridge", async () => {
  const { openStream } = await import("../push");
  globalThis.pywebview = { api: { request: async () => ({}), stream_open: async () => ({ type: "SNAPSHOT", symbol: "BTCUSDT", last_price: 65001.25, event_age_ms: 2500, timestamp: 1700000000000, status: "DEGRADED", open_positions: [] }) } };
  expect((await openStream())?.status).toBe("DEGRADED");
});
