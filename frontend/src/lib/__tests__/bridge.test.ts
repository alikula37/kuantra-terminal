import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

declare const globalThis: any;

/** Minimal addEventListener/removeEventListener/dispatchEvent shim standing in for `window`. */
function makeEventHost() {
  const listeners = new Map<string, Set<(ev: any) => void>>();
  return {
    addEventListener: vi.fn((type: string, fn: (ev: any) => void) => {
      if (!listeners.has(type)) listeners.set(type, new Set());
      listeners.get(type)!.add(fn);
    }),
    removeEventListener: vi.fn((type: string, fn: (ev: any) => void) => {
      listeners.get(type)?.delete(fn);
    }),
    dispatchEvent: (type: string) => {
      for (const fn of [...(listeners.get(type) ?? [])]) fn({ type });
    },
    listenerCount: (type: string) => listeners.get(type)?.size ?? 0,
  };
}

let events: ReturnType<typeof makeEventHost>;

beforeEach(() => {
  vi.resetModules();
  vi.useRealTimers();
  events = makeEventHost();
  // `window` is the host object bridge.ts reads: give it the event API and no pywebview yet.
  vi.stubGlobal("window", globalThis);
  vi.stubGlobal("addEventListener", events.addEventListener);
  vi.stubGlobal("removeEventListener", events.removeEventListener);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("bridgeReady", () => {
  it("waits for pywebviewready when loaded over file://", async () => {
    vi.stubGlobal("location", { protocol: "file:", href: "file:///app/index.html" });
    const { bridgeReady, getBridge, isDesktop } = await import("../bridge");
    expect(getBridge()).toBeNull();
    expect(isDesktop()).toBe(false);

    const pending = bridgeReady();
    let settled = false;
    void pending.then(() => (settled = true));
    await Promise.resolve();
    expect(settled).toBe(false);
    expect(events.listenerCount("pywebviewready")).toBe(1);

    const api = { request: vi.fn() };
    vi.stubGlobal("pywebview", { api });
    events.dispatchEvent("pywebviewready");

    await expect(pending).resolves.toBe(api);
    // The listener and its timeout are torn down once resolved.
    expect(events.removeEventListener).toHaveBeenCalledWith("pywebviewready", expect.any(Function));
    expect(events.listenerCount("pywebviewready")).toBe(0);
  });

  it("resolves to null right away in a plain browser (no 30s wait)", async () => {
    vi.stubGlobal("location", { protocol: "http:", href: "http://localhost:5173/" });
    const { bridgeReady, expectsDesktop } = await import("../bridge");
    expect(expectsDesktop()).toBe(false);

    vi.useFakeTimers();
    await expect(bridgeReady()).resolves.toBeNull();
    // Nothing was scheduled and nothing was subscribed: the promise took the synchronous path.
    expect(vi.getTimerCount()).toBe(0);
    expect(events.addEventListener).not.toHaveBeenCalled();
  });

  it("resolves immediately when the api is already injected", async () => {
    vi.stubGlobal("location", { protocol: "file:", href: "file:///app/index.html" });
    const api = { request: vi.fn() };
    vi.stubGlobal("pywebview", { api });
    const { bridgeReady, getBridge, isDesktop, expectsDesktop } = await import("../bridge");

    expect(getBridge()).toBe(api);
    expect(isDesktop()).toBe(true);
    expect(expectsDesktop()).toBe(true);

    vi.useFakeTimers();
    await expect(bridgeReady()).resolves.toBe(api);
    expect(vi.getTimerCount()).toBe(0);
    expect(events.addEventListener).not.toHaveBeenCalled();
  });

  it("ignores a pywebview object without a request() method", async () => {
    vi.stubGlobal("location", { protocol: "http:", href: "http://localhost:5173/" });
    vi.stubGlobal("pywebview", { api: { copy_text: vi.fn() } });
    const { getBridge, isDesktop } = await import("../bridge");
    expect(getBridge()).toBeNull();
    expect(isDesktop()).toBe(false);
  });
});
