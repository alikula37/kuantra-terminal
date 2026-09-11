// @vitest-environment jsdom
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
const mocks = vi.hoisted(() => ({ desktop: true, bridge: true, open: vi.fn() }));
vi.mock("../../lib/bridge", () => ({
  expectsDesktop: () => mocks.desktop,
  getBridge: () => mocks.bridge ? { open_external: mocks.open } : null,
}));
vi.mock("../../context/I18nContext", () => ({ useTranslation: () => ({ t: (key: string) => key }) }));
import { UpdateNotifier } from "../updater/UpdateNotifier";
const url = "https://github.com/alikula37/kuantra-terminal/releases/tag/pilot-v1.0.0-arm64";
let host: HTMLDivElement;
let root: ReturnType<typeof createRoot>;
beforeEach(async () => {
  (globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
  vi.useFakeTimers();
  mocks.desktop = true; mocks.bridge = true; mocks.open.mockReset();
  host = document.createElement("div"); document.body.append(host);
  root = createRoot(host);
});
afterEach(async () => { await act(async () => root.unmount()); host.remove(); vi.useRealTimers(); });
const render = async () => { await act(async () => root.render(<UpdateNotifier />)); };
const click = async () => { await act(async () => host.querySelector("button")!.click()); };
it("opens the fixed pilot URL only on click and never claims a version check", async () => {
  mocks.open.mockResolvedValue({ ok: true });
  await render();
  await act(async () => vi.advanceTimersByTime(6000));
  expect(mocks.open).not.toHaveBeenCalled();
  await click();
  expect(mocks.open).toHaveBeenCalledExactlyOnceWith(url);
  expect(host.querySelector('[role="alert"]')).toBeNull();
  expect(host.textContent).not.toMatch(/up to date|CHECK UPDATES|UPDATE & RESTART/i);
});
it.each([false, undefined])("rejects unsuccessful or malformed responses: %s", async (ok) => {
  mocks.open.mockResolvedValue({ ok });
  await render(); await click();
  expect(host.querySelector('[role="alert"]')).not.toBeNull();
  mocks.open.mockResolvedValue({ ok: true }); await click();
  expect(host.querySelector('[role="alert"]')).toBeNull();
});
it("handles rejection", async () => {
  mocks.open.mockRejectedValue(new Error("browser"));
  await render(); await click();
  expect(host.querySelector('[role="alert"]')).not.toBeNull();
});
it("times out and ignores a late result from the previous attempt", async () => {
  let resolve!: (v: {ok: boolean}) => void;
  mocks.open.mockImplementationOnce(() => new Promise(r => { resolve = r; }));
  await render(); await click();
  expect(host.querySelector("button")!.disabled).toBe(true);
  await act(async () => vi.advanceTimersByTime(5000));
  expect(host.querySelector('[role="alert"]')).not.toBeNull();
  mocks.open.mockResolvedValue({ ok: false }); await click();
  await act(async () => resolve({ ok: true }));
  expect(host.querySelector('[role="alert"]')).not.toBeNull();
});
it("does not navigate the WebView when the desktop bridge is missing", async () => {
  mocks.bridge = false;
  await render(); await click();
  expect(host.querySelector("a")).toBeNull();
  expect(host.querySelector('[role="alert"]')).not.toBeNull();
});
it("uses a safe browser link in web development mode", async () => {
  mocks.desktop = false;
  await render();
  const link = host.querySelector("a")!;
  expect(link.href).toBe(url);
  expect(link.target).toBe("_blank");
  expect(link.rel).toBe("noopener noreferrer");
  expect(host.querySelector("button")).toBeNull();
});
