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
  useTranslation: () => ({ t: mocks.t }),
}));
vi.mock("../../stores/marketStore", () => ({
  useMarketStore: () => ({ symbol: mocks.symbol }),
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

const waitForSearch = async () => {
  await act(async () => {
    await new Promise((resolve) => window.setTimeout(resolve, 350));
  });
  await flush();
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
  mocks.symbol = "BTCUSDT";
});

it("creates a three-target local plan with explicit allocations and enabled default", async () => {
  mocks.apiFetch.mockResolvedValue(response(savedTrade));
  await act(async () => root.render(<NewTradeModal isOpen onClose={vi.fn()} />));
  await act(async () => setInputValue(host.querySelector('input[type=number]') as HTMLInputElement, "100"));
  await act(async () => setInputValue(host.querySelectorAll('input[type=number]')[1] as HTMLInputElement, "1"));
  await act(async () => (host.querySelector("[data-testid=new-trade-qty-unit-base]") as HTMLInputElement).click());
  for (let i = 1; i <= 3; i++) {
    if (i > 1) await act(async () => (Array.from(host.querySelectorAll("button")).find(b => b.textContent === "tracking.add") as HTMLButtonElement).click());
    await act(async () => {
      setInputValue(host.querySelector(`[aria-label="tracking.price:${i}"]`) as HTMLInputElement, String(100 + i * 10));
      setInputValue(host.querySelector(`[aria-label="tracking.percent:${i}"]`) as HTMLInputElement, String(i === 1 ? 50 : 25));
    });
  }
  await act(async () => host.querySelector("form")!.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true })));
  const payload = JSON.parse(String(mocks.apiFetch.mock.calls.at(-1)?.[1]?.body));
  expect(payload.local_tracking.enabled).toBe(true);
  expect(payload.local_tracking.targets).toEqual([{ price: 110, percent: 50 }, { price: 120, percent: 25 }, { price: 130, percent: 25 }]);
});

it("keeps a chart-selected non-catalog instrument and searches the same ticker explicitly", async () => {
  mocks.symbol = "ARCLK.IS";
  mocks.apiFetch.mockImplementation(() => Promise.resolve(response({ status: "READY", results: [
    { symbol: "ARCLK.IS", name: "Arcelik", exchange: "Istanbul", asset_type: "EQUITY", source_id: "yahoo_public", source_symbol: "ARCLK.IS" },
  ] })));
  await act(async () => root.render(<NewTradeModal isOpen onClose={vi.fn()} />));
  const search = host.querySelectorAll('input[type="text"]')[1] as HTMLInputElement;
  expect(search.value).toBe("");
  expect(host.querySelector("[data-testid=new-trade-selected-symbol]")?.textContent).toContain("ARCLK.IS");
  await act(async () => setInputValue(search, "ARCLK.IS"));
  await waitForSearch();
  expect(host.querySelector('[data-testid="new-trade-symbol-search-result-ARCLK.IS"]')).not.toBeNull();
  expect((host.querySelector('button[title="order_ticket.fetch_price_btn"]') as HTMLButtonElement).disabled).toBe(true);
});

it("ignores an old quote after switching instruments and clears the previous price", async () => {
  let resolveQuote!: (value: Response) => void;
  mocks.apiFetch.mockImplementation((path: string) => path.includes("/quote?")
    ? new Promise<Response>((resolve) => { resolveQuote = resolve; })
    : Promise.resolve(response({ status: "READY", results: [
      { symbol: "LINKUSDT", name: "Chainlink", exchange: "Binance Spot", asset_type: "CRYPTO", source_id: "binance_public", source_symbol: "LINKUSDT" },
    ] })));
  await act(async () => root.render(<NewTradeModal isOpen onClose={vi.fn()} />));
  await act(async () => setInputValue(host.querySelector('input[type="number"]') as HTMLInputElement, "100"));
  await act(async () => (host.querySelector('button[title="order_ticket.fetch_price_btn"]') as HTMLButtonElement).click());
  await act(async () => setInputValue(host.querySelectorAll('input[type="text"]')[1] as HTMLInputElement, "LINK"));
  await waitForSearch();
  await act(async () => (host.querySelector("[data-testid=new-trade-symbol-search-result-LINKUSDT]") as HTMLButtonElement).click());
  await act(async () => (host.querySelector("[data-testid=new-trade-confirm-symbol]") as HTMLButtonElement).click());
  resolveQuote(response({ requested_symbol: "BTCUSDT", source_id: "binance_public", source_symbol: "BTCUSDT", price: 999,
    status: "LIVE", price_kind: "LAST", observed_at: "2026-09-11T10:00:00Z", free_source: true, credentials_required: false }));
  await flush();
  expect((host.querySelector('input[type="number"]') as HTMLInputElement).value).toBe("");
  expect(host.querySelector("[data-testid=trade-quote-status]")).toBeNull();
});

it("does not reinterpret an already-selected LINK ticker as a crypto alias", async () => {
  mocks.symbol = "LINK";
  await act(async () => root.render(<NewTradeModal isOpen onClose={vi.fn()} />));
  expect(host.querySelector("[data-testid=new-trade-selected-symbol]")?.textContent).toBe("order_ticket.selected_symbol:LINK");
  expect(mocks.apiFetch).not.toHaveBeenCalled();
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

  await act(async () => setInputValue(host.querySelectorAll("input[type=number]")[1] as HTMLInputElement, "1"));
  await act(async () => (host.querySelector("button[type=submit]") as HTMLButtonElement).click());
  await flush();

  expect(submittedBody).toMatchObject({
    symbol: "BTCUSDT",
    position_type: "SPOT",
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

it("does not invent equity percentages, stop losses or targets from a quote", async () => {
  mocks.apiFetch.mockResolvedValue(response({ requested_symbol: "BTCUSDT", source_id: "binance_public", source_symbol: "BTCUSDT",
    price: 100, status: "LIVE", price_kind: "LAST", observed_at: "2026-09-12T00:00:00Z", free_source: true, credentials_required: false }));
  await act(async () => root.render(<NewTradeModal isOpen onClose={vi.fn()} />));
  await act(async () => (host.querySelector('button[title="order_ticket.fetch_price_btn"]') as HTMLButtonElement).click());
  await flush();
  const numbers = host.querySelectorAll('input[type="number"]');
  expect((numbers[2] as HTMLInputElement).value).toBe("");
  expect((numbers[3] as HTMLInputElement).value).toBe("");
  expect(host.textContent).toContain("order_ticket.estimate_unavailable");
  expect(host.textContent).not.toContain("% of equity");
});

it.each([['order_ticket.side_spot', 'SPOT', 'BUY'], ['order_ticket.side_buy', 'LONG', 'BUY'], ['order_ticket.side_sell', 'SHORT', 'SELL']])(
  "records the explicitly selected %s position kind", async (label, positionType, side) => {
    let payload: any;
    mocks.apiFetch.mockImplementation((_path: string, init?: RequestInit) => {
      payload = JSON.parse(String(init?.body));
      return Promise.resolve(response({ ...savedTrade, ...payload }));
    });
    await act(async () => root.render(<NewTradeModal isOpen onClose={vi.fn()} />));
    const button = Array.from(host.querySelectorAll("button")).find((element) => element.textContent === label)!;
    await act(async () => button.click());
    await act(async () => setInputValue(host.querySelector('input[type="number"]') as HTMLInputElement, "100"));
    await act(async () => setInputValue(host.querySelectorAll('input[type="number"]')[1] as HTMLInputElement, "1"));
    await act(async () => (host.querySelector('button[type="submit"]') as HTMLButtonElement).click());
    await flush();
    expect(payload).toMatchObject({ position_type: positionType, side, record_mode: "EXTERNAL" });
  },
);

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

it("requires selecting and confirming LINKUSDT before fetching its quote", async () => {
  const requestedQuoteUrls: string[] = [];
  mocks.apiFetch.mockImplementation((path: string) => {
    if (path.startsWith("/api/v1/market-data/search")) {
      return Promise.resolve(response({
        status: "READY",
        results: [{ symbol: "LINKUSDT", name: "Chainlink / Tether", exchange: "Binance Spot", asset_type: "CRYPTO", source_id: "binance_public", source_symbol: "LINKUSDT" }],
      }));
    }
    if (path.startsWith("/api/v1/market-data/quote")) {
      requestedQuoteUrls.push(path);
      return Promise.resolve(response({
        requested_symbol: "LINKUSDT",
        source_id: "binance_public",
        source_symbol: "LINKUSDT",
        price: 12.34,
        status: "LIVE",
        price_kind: "LAST",
        observed_at: "2026-09-11T10:00:00Z",
        reason: null,
        free_source: true,
        credentials_required: false,
      }));
    }
    return Promise.resolve(response({}));
  });

  await act(async () => root.render(<NewTradeModal isOpen onClose={vi.fn()} />));
  const symbolInput = host.querySelectorAll('input[type="text"]')[1] as HTMLInputElement;
  const fetchButton = host.querySelector('button[title="order_ticket.fetch_price_btn"]') as HTMLButtonElement;

  await act(async () => setInputValue(symbolInput, "LINK"));
  await act(async () => symbolInput.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true })));
  await waitForSearch();

  expect(requestedQuoteUrls).toHaveLength(0);
  expect(host.querySelector("[data-testid=new-trade-symbol-search-error]")?.textContent).toContain("order_ticket.select_result_to_confirm");
  expect(host.querySelector("[data-testid=new-trade-symbol-search-result-LINKUSDT]")).not.toBeNull();
  expect(fetchButton.disabled).toBe(true);

  await act(async () => (host.querySelector("[data-testid=new-trade-symbol-search-result-LINKUSDT]") as HTMLButtonElement).click());
  await flush();
  expect(host.querySelector("[data-testid=new-trade-symbol-confirmation]")).not.toBeNull();
  expect(requestedQuoteUrls).toHaveLength(0);

  await act(async () => (host.querySelector("[data-testid=new-trade-confirm-symbol]") as HTMLButtonElement).click());
  await flush();
  expect(fetchButton.disabled).toBe(false);

  await act(async () => fetchButton.click());
  await flush();
  expect(requestedQuoteUrls).toHaveLength(1);
  expect(requestedQuoteUrls[0]).toContain("symbol=LINKUSDT");
  expect(host.querySelector("[data-testid=trade-quote-status]")).not.toBeNull();
});

it("allows an explicit manual symbol confirmation when providers return no match", async () => {
  const requestedQuoteUrls: string[] = [];
  mocks.apiFetch.mockImplementation((path: string) => {
    if (path.startsWith("/api/v1/market-data/search")) {
      return Promise.resolve(response({
        status: "NO_MATCH",
        results: [],
        sources: ["binance_public", "yahoo_public"],
      }));
    }
    if (path.startsWith("/api/v1/market-data/quote")) {
      requestedQuoteUrls.push(path);
      return Promise.resolve(response({
        requested_symbol: "OTC:KUANTRA",
        source_id: null,
        source_symbol: null,
        price: null,
        status: "UNAVAILABLE",
        price_kind: null,
        observed_at: null,
        reason: "NO_FREE_QUOTE_SOURCE",
        free_source: true,
        credentials_required: false,
      }));
    }
    return Promise.resolve(response({}));
  });

  await act(async () => root.render(<NewTradeModal isOpen onClose={vi.fn()} />));
  const symbolInput = host.querySelectorAll('input[type="text"]')[1] as HTMLInputElement;
  await act(async () => setInputValue(symbolInput, "OTC:KUANTRA"));
  await waitForSearch();

  const manual = host.querySelector("[data-testid=new-trade-manual-symbol-result]") as HTMLButtonElement;
  expect(manual).not.toBeNull();
  await act(async () => manual.click());
  await flush();
  expect(host.querySelector("[data-testid=new-trade-symbol-confirmation]")?.textContent).toContain("OTC:KUANTRA");
  await act(async () => (host.querySelector("[data-testid=new-trade-confirm-symbol]") as HTMLButtonElement).click());
  await flush();

  const fetchButton = host.querySelector('button[title="order_ticket.fetch_price_btn"]') as HTMLButtonElement;
  expect(fetchButton.disabled).toBe(false);
  await act(async () => fetchButton.click());
  await flush();
  expect(requestedQuoteUrls).toHaveLength(1);
  expect(requestedQuoteUrls[0]).toContain("symbol=OTC%3AKUANTRA");
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
  await act(async () => setInputValue(numberInputs[1] as HTMLInputElement, "1"));
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

it("keeps the confirmed provider identity when the entry price is typed manually", async () => {
  let submittedBody: any;
  mocks.apiFetch.mockImplementation((path: string, init?: RequestInit) => {
    if (path.startsWith("/api/v1/market-data/quote")) {
      return Promise.resolve(response({
        requested_symbol: "BTCUSDT",
        source_id: "binance_public",
        source_symbol: "BTCUSDT",
        price: 61234.5,
        status: "LIVE",
        price_kind: "LAST",
        observed_at: "2026-09-17T09:00:00Z",
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
  const simulation = Array.from(host.querySelectorAll("button"))
    .find((element) => element.textContent === "order_ticket.mode_simulation") as HTMLButtonElement;
  await act(async () => simulation.click());
  const longSide = Array.from(host.querySelectorAll("button"))
    .find((element) => element.textContent === "order_ticket.side_buy") as HTMLButtonElement;
  await act(async () => longSide.click());
  await act(async () => (host.querySelector('button[title="order_ticket.fetch_price_btn"]') as HTMLButtonElement).click());
  await flush();
  // The reported flow: replace the quoted price with the real entry fill.
  await act(async () => setInputValue(host.querySelectorAll("input[type=number]")[0] as HTMLInputElement, "76000"));
  await act(async () => setInputValue(host.querySelectorAll("input[type=number]")[1] as HTMLInputElement, "0.001"));
  const baseUnit = host.querySelector("[data-testid=new-trade-qty-unit-base]") as HTMLInputElement | null;
  if (baseUnit) await act(async () => baseUnit.click());
  await act(async () => (host.querySelector("button[type=submit]") as HTMLButtonElement).click());
  await flush();

  expect(submittedBody).toMatchObject({
    entry_price: 76000,
    record_mode: "SIMULATION",
    price_source: "binance_public",
    price_source_symbol: "BTCUSDT",
    price_status: "UNAVAILABLE",
    price_observed_at: null,
    price_origin: "MANUAL",
  });
  expect(submittedBody.local_tracking?.source_id).toBe("binance_public");
  expect(submittedBody.local_tracking?.source_symbol).toBe("BTCUSDT");
});
