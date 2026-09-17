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

const fillBase = async (entry = "100", value = "1000") => {
  await act(async () => setInputValue(host.querySelector('input[aria-label="order_ticket.entry_label"]') as HTMLInputElement, entry));
  await act(async () => setInputValue(host.querySelector('input[aria-label="order_ticket.position_value_label"]') as HTMLInputElement, value));
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
    size_input_mode: "NOTIONAL",
    notional_size: 1000,
    qty_unit: "USD",
  });
  expect(captured.body.qty).toBeUndefined();
  expect(host.textContent).toContain("order_ticket.turkey_time");
});

it("hides live tracking and collects user-reported close data for a closed trade", async () => {
  const captured = capturedPayload();
  await act(async () => root.render(<NewTradeModal isOpen onClose={vi.fn()} />));
  await act(async () => (host.querySelector("[data-testid=new-trade-status-closed]") as HTMLButtonElement).click());
  await fillBase("100", "2000");
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

it("submits the USD position value as the only sizing input", async () => {
  const captured = capturedPayload();
  await act(async () => root.render(<NewTradeModal isOpen onClose={vi.fn()} />));
  await act(async () => setInputValue(host.querySelector('input[aria-label="order_ticket.entry_label"]') as HTMLInputElement, "100"));
  await act(async () => setInputValue(host.querySelector('input[aria-label="order_ticket.position_value_label"]') as HTMLInputElement, "500"));
  await act(async () => (host.querySelector("button[type=submit]") as HTMLButtonElement).click());
  await flush();

  expect(captured.body).toMatchObject({ size_input_mode: "NOTIONAL", notional_size: 500, qty_unit: "USD" });
  expect(captured.body.qty).toBeUndefined();
  expect(host.querySelector("[data-testid=new-trade-summary-value]")?.textContent).toContain("$500.00");
});

it("prices a manual symbol from the USD value without contract verification", async () => {
  mocks.symbol = "XAUUSD";
  const captured = capturedPayload();
  await act(async () => root.render(<NewTradeModal isOpen onClose={vi.fn()} />));

  await fillBase("2000", "1000");
  expect(host.querySelector("[data-testid=new-trade-usd-value-declared]")).not.toBeNull();
  expect(host.textContent).toContain("order_ticket.verification_EXPLICIT_USD_VALUE");
  expect(host.querySelector("[data-testid=new-trade-monetary-unavailable]")).toBeNull();
  expect(host.querySelector("[data-testid=new-trade-tracking-enabled]")).not.toBeNull();
  await act(async () => (host.querySelector("button[type=submit]") as HTMLButtonElement).click());
  await flush();

  expect(captured.body.qty_unit).toBe("USD");
  expect(captured.body.local_tracking).toMatchObject({ enabled: true });
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

it("declares the USD position value for a manual symbol end to end", async () => {
  const captured = capturedPayload();
  await act(async () => root.render(<NewTradeModal isOpen onClose={vi.fn()} />));
  await fillBase();
  expect((host.textContent || "")).toContain("order_ticket.verification_EXPLICIT_USD_VALUE");
  await act(async () => (host.querySelector("button[type=submit]") as HTMLButtonElement).click());
  await flush();

  expect(captured.body.qty_unit).toBe("USD");
  expect(captured.body.notional_size).toBe(1000);
  expect(captured.body.local_tracking).toMatchObject({ enabled: true });
});

it("keeps the USD value declaration and still shows the provider verification", async () => {
  const quote = {
    requested_symbol: "BTCUSDT", source_id: "binance_public", source_symbol: "BTCUSDT",
    price: 65000, status: "LIVE", price_kind: "LAST",
    observed_at: "2026-09-15T10:00:00Z", reason: null, free_source: true, credentials_required: false,
  };
  mocks.apiFetch.mockImplementation((path: string) => {
    if (path.startsWith("/api/v1/market-data/instrument")) {
      return Promise.resolve(response({ status: "VERIFIED", provider: "binance_spot", base_asset: "BTC", quote_asset: "USDT" }));
    }
    if (path.startsWith("/api/v1/market-data/quote")) return Promise.resolve(response(quote));
    return Promise.resolve(response({}));
  });

  await act(async () => root.render(<NewTradeModal isOpen onClose={vi.fn()} />));
  await act(async () => (host.querySelector('button[title="order_ticket.fetch_price_btn"]') as HTMLButtonElement).click());
  await flush();

  expect(host.querySelector("[data-testid=new-trade-usd-value-declared]")).not.toBeNull();
  expect(host.textContent).toContain("order_ticket.verification_EXPLICIT_USD_VALUE");
});
