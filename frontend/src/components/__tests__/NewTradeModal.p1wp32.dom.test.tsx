// @vitest-environment jsdom
import React, { act } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  apiFetch: vi.fn(),
  addTrade: vi.fn(),
  symbol: "BTCUSDT",
  t: (key: string, params?: Record<string, string | number>) =>
    params ? `${key}:${Object.values(params).join("|")}` : key,
}));

vi.mock("../../lib/backend", () => ({
  apiUrl: (path: string) => path,
  apiFetch: mocks.apiFetch,
}));
vi.mock("../../context/I18nContext", () => ({
  useTranslation: () => ({ t: mocks.t, locale: "tr" }),
}));
vi.mock("../../stores/marketStore", () => ({
  useMarketStore: () => ({ symbol: mocks.symbol }),
}));
vi.mock("../../stores/tradeStore", () => ({
  useTradeStore: () => ({ addTrade: mocks.addTrade }),
}));

import { NewTradeModal } from "../NewTradeModal";

const response = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

let host: HTMLDivElement;
let root: ReturnType<typeof import("react-dom/client").createRoot>;

const flush = async () => {
  await act(async () => { for (let i = 0; i < 4; i++) await Promise.resolve(); });
};

const setInputValue = (input: HTMLInputElement, value: string) => {
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
  setter?.call(input, value);
  input.dispatchEvent(new Event("input", { bubbles: true }));
  input.dispatchEvent(new Event("change", { bubbles: true }));
};

const capturedPayload = () => {
  const captured: { body?: any } = {};
  mocks.apiFetch.mockImplementation((path: string, init?: RequestInit) => {
    if (path === "/api/v1/trades" && init?.method === "POST") {
      captured.body = JSON.parse(String(init.body));
      return Promise.resolve(response({ id: "TRD-WP32", ...captured.body, status: captured.body.status || "OPEN" }));
    }
    return Promise.resolve(response({}));
  });
  return captured;
};

const fillBase = async (entry = "100", qty = "1") => {
  await act(async () => setInputValue(host.querySelector('input[aria-label="order_ticket.entry_label"]') as HTMLInputElement, entry));
  await act(async () => setInputValue(host.querySelector('input[aria-label="order_ticket.qty_label"]') as HTMLInputElement, qty));
};

beforeEach(async () => {
  (globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
  localStorage.clear();
  host = document.createElement("div");
  document.body.append(host);
  const { createRoot } = await import("react-dom/client");
  root = createRoot(host);
  mocks.apiFetch.mockReset();
  mocks.addTrade.mockReset();
  mocks.symbol = "BTCUSDT";
});

afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
  localStorage.clear();
});

it("sends the Turkey-time trade date as UTC with an explicit open status", async () => {
  const captured = capturedPayload();
  await act(async () => root.render(<NewTradeModal isOpen onClose={vi.fn()} />));
  await fillBase();
  await act(async () => setInputValue(host.querySelector('input[type="datetime-local"]') as HTMLInputElement, "2026-01-15T10:30"));
  await act(async () => (host.querySelector("button[type=submit]") as HTMLButtonElement).click());
  await flush();

  expect(captured.body).toMatchObject({
    status: "OPEN",
    entry_time: "2026-01-15T07:30:00.000Z",
    size_input_mode: "QTY",
    qty: 1,
  });
  expect(host.textContent).toContain("order_ticket.turkey_time");
});

it("hides live tracking and collects user-reported close data for a closed trade", async () => {
  const captured = capturedPayload();
  await act(async () => root.render(<NewTradeModal isOpen onClose={vi.fn()} />));
  await act(async () => (host.querySelector("[data-testid=new-trade-status-closed]") as HTMLButtonElement).click());
  await fillBase("100", "2");
  await act(async () => setInputValue(host.querySelector('input[type="datetime-local"]') as HTMLInputElement, "2026-01-15T10:30"));
  await act(async () => setInputValue(host.querySelector('input[aria-label="order_ticket.exit_price_label"]') as HTMLInputElement, "112"));
  await act(async () => setInputValue(host.querySelector('input[aria-label="order_ticket.exit_time_label"]') as HTMLInputElement, "2026-01-16T09:00"));
  expect(host.querySelector("[data-testid=new-trade-tracking-enabled]")).toBeNull();
  expect(host.textContent).toContain("order_ticket.closed_no_tracking");
  await act(async () => (host.querySelector("button[type=submit]") as HTMLButtonElement).click());
  await flush();

  expect(captured.body).toMatchObject({
    status: "CLOSED",
    exit_price: 112,
    exit_time: "2026-01-16T06:00:00.000Z",
    local_tracking: null,
  });
});

it("equal-split fills exactly 100 percent across three targets", async () => {
  mocks.apiFetch.mockResolvedValue(response({}));
  await act(async () => root.render(<NewTradeModal isOpen onClose={vi.fn()} />));
  for (let i = 1; i <= 3; i++) {
    if (i > 1) {
      await act(async () => (Array.from(host.querySelectorAll("button")).find(b => b.textContent === "tracking.add") as HTMLButtonElement).click());
    }
    await act(async () => setInputValue(host.querySelector(`[aria-label="tracking.price:${i}"]`) as HTMLInputElement, String(100 + i * 10)));
  }
  await act(async () => (host.querySelector("[data-testid=new-trade-equal-split]") as HTMLButtonElement).click());

  const percents = [1, 2, 3].map((i) => (host.querySelector(`[aria-label="tracking.percent:${i}"]`) as HTMLInputElement).value);
  expect(percents).toEqual(["33.33", "33.33", "33.34"]);
  expect(host.textContent).toContain("order_ticket.allocation_total:100.00");
});

it("offers the previous leverage only as an explicit suggestion", async () => {
  localStorage.setItem("kuantra_trade_prefs_v1", JSON.stringify({ recordMode: "EXTERNAL", positionType: "LONG", leverage: 7 }));
  mocks.apiFetch.mockResolvedValue(response({}));
  await act(async () => root.render(<NewTradeModal isOpen onClose={vi.fn()} />));

  const leverage = host.querySelector('input[aria-label="order_ticket.leverage_label"]') as HTMLInputElement;
  expect(leverage.value).toBe("");
  const suggestion = host.querySelector("[data-testid=new-trade-leverage-suggestion]") as HTMLButtonElement;
  expect(suggestion.textContent).toContain("order_ticket.leverage_suggested:7");
  await act(async () => suggestion.click());
  expect(leverage.value).toBe("7");
});

it("derives quantity from a position-size input without conflicting fields", async () => {
  const captured = capturedPayload();
  await act(async () => root.render(<NewTradeModal isOpen onClose={vi.fn()} />));
  await act(async () => setInputValue(host.querySelector('input[aria-label="order_ticket.entry_label"]') as HTMLInputElement, "100"));
  await act(async () => (host.querySelector("[data-testid=new-trade-qty-unit-base]") as HTMLInputElement).click());
  await act(async () => (host.querySelector("[data-testid=new-trade-size-notional]") as HTMLButtonElement).click());
  await act(async () => setInputValue(host.querySelector('input[aria-label="order_ticket.position_size_label"]') as HTMLInputElement, "500"));
  expect(host.querySelector('input[aria-label="order_ticket.qty_label"]')).toBeNull();
  await act(async () => (host.querySelector("button[type=submit]") as HTMLButtonElement).click());
  await flush();

  expect(captured.body).toMatchObject({ size_input_mode: "NOTIONAL", notional_size: 500 });
  expect(captured.body.qty).toBeUndefined();
  expect(host.textContent).toContain("order_ticket.summary_quantity_notional");
});

it("hides live tracking and monetary math for an unverified contract size", async () => {
  mocks.symbol = "XAUUSD";
  const captured = capturedPayload();
  await act(async () => root.render(<NewTradeModal isOpen onClose={vi.fn()} />));

  expect(host.querySelector("[data-testid=new-trade-tracking-enabled]")).toBeNull();
  expect(host.textContent).toContain("order_ticket.tracking_requires_verified_unit");
  expect(host.querySelector("[data-testid=new-trade-monetary-unavailable]")).not.toBeNull();
  await fillBase("2000", "2");
  await act(async () => (host.querySelector("button[type=submit]") as HTMLButtonElement).click());
  await flush();

  expect(captured.body.local_tracking).toBeNull();
  expect(host.textContent).toContain("order_ticket.estimate_unavailable");
});

it("blocks a future realized trade before calling the backend", async () => {
  const captured = capturedPayload();
  await act(async () => root.render(<NewTradeModal isOpen onClose={vi.fn()} />));
  await fillBase();
  await act(async () => setInputValue(host.querySelector('input[type="datetime-local"]') as HTMLInputElement, "2099-01-01T00:00"));
  await act(async () => (host.querySelector("button[type=submit]") as HTMLButtonElement).click());
  await flush();

  expect(host.querySelector("[data-testid=new-trade-error-time]")?.textContent).toContain("order_ticket.errors.time_future");
  expect(captured.body).toBeUndefined();
});

it("requires an explicit unit declaration before money math and tracking for a manual symbol", async () => {
  const captured = capturedPayload();
  await act(async () => root.render(<NewTradeModal isOpen onClose={vi.fn()} />));

  // Manual BTCUSDT without provider identity or declaration: no tracking,
  // no monetary derivation.
  expect(host.querySelector("[data-testid=new-trade-tracking-enabled]")).toBeNull();
  expect(host.querySelector("[data-testid=new-trade-tracking-unverified]")).not.toBeNull();
  expect((host.textContent || "")).toContain("order_ticket.verification_NONE");
  expect(host.querySelector("[data-testid=new-trade-monetary-unavailable]")).not.toBeNull();

  await act(async () => (host.querySelector("[data-testid=new-trade-qty-unit-base]") as HTMLInputElement).click());
  await fillBase();
  expect(host.querySelector("[data-testid=new-trade-tracking-enabled]")).not.toBeNull();
  expect((host.textContent || "")).toContain("order_ticket.verification_EXPLICIT_QTY_UNIT");
  expect(host.querySelector("[data-testid=new-trade-monetary-unavailable]")).toBeNull();
  await act(async () => (host.querySelector("button[type=submit]") as HTMLButtonElement).click());
  await flush();

  expect(captured.body.qty_unit).toBe("BASE");
  expect(captured.body.local_tracking).toMatchObject({ enabled: true });
});
