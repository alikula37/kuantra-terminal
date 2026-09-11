// @vitest-environment jsdom
import React, { act } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  apiFetch: vi.fn(),
  addTrade: vi.fn(),
  t: (key: string, params?: Record<string, string | number>) =>
    params ? `${key}:${Object.values(params).join("|")}` : key,
}));

vi.mock("../../lib/backend", () => ({
  apiUrl: (path: string) => path,
  apiFetch: mocks.apiFetch,
}));
vi.mock("../../context/I18nContext", () => ({
  useTranslation: () => ({ t: mocks.t }),
}));
vi.mock("../../stores/marketStore", () => ({
  useMarketStore: () => ({ symbol: "BTCUSDT" }),
}));
vi.mock("../../stores/tradeStore", () => ({
  useTradeStore: () => ({ addTrade: mocks.addTrade }),
}));

import { NewTradeModal } from "../NewTradeModal";
import { Trade } from "../../types";

const response = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

const savedTrade: Trade = {
  id: "TRD-EXTERNAL-1",
  symbol: "BTCUSDT",
  side: "BUY",
  entry_price: 123.45,
  qty: 1,
  entry_time: "2026-09-11T10:00:00Z",
  status: "OPEN",
  record_mode: "EXTERNAL",
  price_source: "binance_public",
  price_status: "LIVE",
  price_origin: "PUBLIC_QUOTE",
};

let host: HTMLDivElement;
let root: ReturnType<typeof import("react-dom/client").createRoot>;

const flush = async () => {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
};

const setInputValue = (input: HTMLInputElement, value: string) => {
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
  setter?.call(input, value);
  input.dispatchEvent(new Event("input", { bubbles: true }));
  input.dispatchEvent(new Event("change", { bubbles: true }));
};

const renderModal = () => {
  const onClose = vi.fn();
  return { onClose };
};

beforeEach(async () => {
  (globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
  host = document.createElement("div");
  document.body.append(host);
  const { createRoot } = await import("react-dom/client");
  root = createRoot(host);
  mocks.apiFetch.mockReset();
  mocks.addTrade.mockReset();
});

afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
});

it("uses a free quote only when the exact quote is available and records the returned trade", async () => {
  let submittedBody: any;
  mocks.apiFetch.mockImplementation((path: string, init?: RequestInit) => {
    if (path.startsWith("/api/v1/market-data/quote")) {
      return Promise.resolve(response({
        requested_symbol: "BTCUSDT",
        source_id: "binance_public",
        source_symbol: "BTCUSDT",
        price: 123.45,
        status: "LIVE",
        price_kind: "LAST",
        observed_at: "2026-09-11T10:00:00Z",
        reason: null,
        free_source: true,
        credentials_required: false,
      }));
    }
    if (path === "/api/v1/trades") {
      submittedBody = JSON.parse(String(init?.body));
      return Promise.resolve(response(savedTrade));
    }
    return Promise.resolve(response({}));
  });

  const { onClose } = renderModal();
  await act(async () => root.render(<NewTradeModal isOpen onClose={onClose} />));
  const fetchButton = host.querySelector('button[title="order_ticket.fetch_price_btn"]') as HTMLButtonElement;
  await act(async () => fetchButton.click());
  await flush();

  expect((host.querySelectorAll("input[type=number]")[0] as HTMLInputElement).value).toBe("123.45");
  expect(host.querySelector("[data-testid=trade-quote-status]")?.textContent).toContain("order_ticket.quote_status:LIVE");

  await act(async () => (host.querySelector("button[type=submit]") as HTMLButtonElement).click());
  await flush();

  expect(submittedBody).toMatchObject({
    symbol: "BTCUSDT",
    record_mode: "EXTERNAL",
    price_source: "binance_public",
    price_source_symbol: "BTCUSDT",
    price_status: "LIVE",
    price_origin: "PUBLIC_QUOTE",
  });
  expect(mocks.addTrade).toHaveBeenCalledWith(savedTrade);
  expect(onClose).toHaveBeenCalledTimes(1);
  expect(mocks.apiFetch.mock.calls.some(([path]) => path === "/api/v1/execution/order")).toBe(false);
});

it("keeps the external journal default and requests manual price when the free source is unavailable", async () => {
  mocks.apiFetch.mockResolvedValue(response({
    requested_symbol: "XAUUSD",
    source_id: null,
    source_symbol: null,
    price: null,
    status: "UNAVAILABLE",
    price_kind: null,
    observed_at: null,
    reason: "NO_FREE_EXACT_QUOTE",
    free_source: true,
    credentials_required: false,
  }));

  await act(async () => root.render(<NewTradeModal isOpen onClose={vi.fn()} />));
  expect(host.querySelector("[data-testid=trade-record-mode-note]")?.textContent).toContain("order_ticket.external_record_notice");
  await act(async () => (host.querySelector('button[title="order_ticket.fetch_price_btn"]') as HTMLButtonElement).click());
  await flush();

  expect(host.textContent).toContain("order_ticket.price_unavailable_manual");
  expect(host.querySelector("[data-testid=trade-record-mode-note]")?.textContent).not.toContain("order_ticket.simulation_notice");
});

it("treats a malformed successful quote response as unavailable", async () => {
  mocks.apiFetch.mockResolvedValue(response({ status: "LIVE", price: 123.45 }));

  await act(async () => root.render(<NewTradeModal isOpen onClose={vi.fn()} />));
  await act(async () => (host.querySelector('button[title="order_ticket.fetch_price_btn"]') as HTMLButtonElement).click());
  await flush();

  expect(host.textContent).toContain("order_ticket.price_unavailable_manual");
  expect(host.querySelector("[data-testid=trade-quote-status]")).toBeNull();
});

it("requires an explicit simulation choice and still posts only to the journal endpoint", async () => {
  let submittedBody: any;
  mocks.apiFetch.mockImplementation((path: string, init?: RequestInit) => {
    if (path === "/api/v1/trades") {
      submittedBody = JSON.parse(String(init?.body));
      return Promise.resolve(response({ ...savedTrade, id: "TRD-SIM-1", record_mode: "SIMULATION", price_origin: "MANUAL" }));
    }
    return Promise.resolve(response({}));
  });

  await act(async () => root.render(<NewTradeModal isOpen onClose={vi.fn()} />));
  const modeButtons = Array.from(host.querySelectorAll("button"));
  const simulationButton = modeButtons.find((button) => button.textContent === "order_ticket.mode_simulation") as HTMLButtonElement;
  await act(async () => simulationButton.click());

  const numberInputs = host.querySelectorAll("input[type=number]");
  await act(async () => setInputValue(numberInputs[0] as HTMLInputElement, "100"));
  await act(async () => (host.querySelector("button[type=submit]") as HTMLButtonElement).click());
  await flush();

  expect(submittedBody).toMatchObject({
    record_mode: "SIMULATION",
    price_source: "manual",
    price_status: "UNAVAILABLE",
    price_origin: "MANUAL",
  });
  expect(mocks.apiFetch.mock.calls.some(([path]) => path === "/api/v1/execution/order")).toBe(false);
});
