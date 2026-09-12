// @vitest-environment jsdom
import React, { act } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { createRoot, type Root } from "react-dom/client";

const mocks = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../lib/backend", () => ({ apiFetch: mocks.request, apiUrl: (s: string) => s }));
vi.mock("../../context/I18nContext", () => ({ useTranslation: () => ({
  t: (key: string, p?: Record<string, number>) => p ? `${key}:${Object.values(p).join("|")}` : key,
}) }));
import { LocalTrackingPanel } from "../LocalTrackingPanel";

const base = {
  version: 1, basis: "LOCAL_ESTIMATE", trade_id: "t1", symbol: "BTCUSDT", side: "BUY", revision: 2,
  enabled: true, source_id: "binance_public", source_symbol: "BTCUSDT", stop_loss: "95",
  entry_price: "100", initial_qty: "2", remaining_qty: "1", gross_pnl: "10", external_status: "OPEN",
  tracking_status: "ACTIVE", last_quote: { price: "125", observed_at: "2026-09-12T12:00:00Z" },
  targets: [{ id: "TP1", price: "110", percent: "50" }, { id: "TP2", price: "120", percent: "50" }],
  closures: [{ target_id: "TP1", qty: "1", price: "110", gross_pnl: "10", observed_at: "2026-09-12T12:00:00Z", plan_revision: 1 }],
};
const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
let host: HTMLDivElement;
let root: Root;
beforeEach(() => {
  (globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
  mocks.request.mockReset();
  mocks.request.mockImplementation((path: string, options?: RequestInit) => Promise.resolve(response(
    options?.method ? { ...base, revision: 3 } : path.endsWith("/local-tracking") ? [base] : { plan: base, history: [{ state: base }] })));
});
afterEach(async () => { await act(async () => root.unmount()); host.remove(); });
const button = (text: string) => Array.from(host.querySelectorAll("button")).find(b => b.textContent === text)!;
const open = async () => {
  await act(async () => root.render(<LocalTrackingPanel editTrade={null} onEditorClose={vi.fn()} />));
  await act(async () => button("tracking.edit").click());
};

it("loads partial history, locks completed targets and saves the exact revision", async () => {
  await open();
  expect((host.querySelector('[aria-label="tracking.price:1"]') as HTMLInputElement).disabled).toBe(true);
  expect(host.textContent).toContain("tracking.remaining: 1 / 2");
  expect(host.textContent).toContain("tracking.already_reached");
  await act(async () => host.querySelector("form")!.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true })));
  const call = mocks.request.mock.calls.find(c => c[1]?.method === "PUT")!;
  expect(JSON.parse(call[1].body)).toMatchObject({ expected_revision: 2, enabled: true,
    targets: [{ price: 110, percent: 50 }, { price: 120, percent: 50 }] });
  expect(host.querySelector("dialog")).toBeNull();
});

it("keeps a conflicting edit open and offers reload instead of silently overwriting", async () => {
  await open();
  mocks.request.mockResolvedValueOnce(response({ detail: "changed" }, 409));
  await act(async () => host.querySelector("form")!.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true })));
  expect(host.querySelector("dialog")).not.toBeNull();
  expect(host.querySelector('[role="alert"]')?.textContent).toContain("tracking.conflict");
});

it("manual close uses only the local endpoint and requires a price", async () => {
  await open();
  await act(async () => button("tracking.manual_close").click());
  expect(mocks.request.mock.calls.some(c => c[1]?.method === "POST")).toBe(false);
  const input = host.querySelector('[aria-label="tracking.manual_price"]') as HTMLInputElement;
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(input, "119");
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
  await act(async () => button("tracking.manual_close").click());
  const call = mocks.request.mock.calls.find(c => c[1]?.method === "POST")!;
  expect(call[0]).toBe("/api/v1/trades/t1/tracking/close");
  expect(JSON.parse(call[1].body)).toEqual({ expected_revision: 2, price: 119 });
});

it("contains keyboard focus and closes on Escape without saving", async () => {
  await open();
  const first = button("tracking.dismiss");
  first.focus();
  await act(async () => first.dispatchEvent(new KeyboardEvent("keydown", { key: "Tab", shiftKey: true, bubbles: true, cancelable: true })));
  expect(document.activeElement?.tagName).toBe("SUMMARY");
  await act(async () => document.activeElement!.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true, cancelable: true })));
  expect(host.querySelector("dialog")).toBeNull();
  expect(mocks.request.mock.calls.some(c => c[1]?.method === "PUT")).toBe(false);
});
