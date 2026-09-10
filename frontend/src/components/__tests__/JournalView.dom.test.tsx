// @vitest-environment jsdom
import React, { act } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  apiFetch: vi.fn(),
  setTrades: vi.fn(),
  trades: [] as any[],
  t: (key: string) => key,
}));
vi.mock("../../lib/backend", () => ({ apiUrl: (path: string) => path, apiFetch: mocks.apiFetch }));
vi.mock("../../context/I18nContext", () => ({
  useTranslation: () => ({ t: mocks.t }),
}));
vi.mock("../../stores/tradeStore", () => ({
  useTradeStore: () => ({ trades: mocks.trades, setTrades: mocks.setTrades }),
}));

import { JournalView } from "../JournalView";
import { createRoot } from "react-dom/client";

const response = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

let host: HTMLDivElement;
let root: ReturnType<typeof createRoot>;
const props = { onOpenNewTrade: vi.fn() };
const flush = async () => { await act(async () => { await Promise.resolve(); await Promise.resolve(); }); };

beforeEach(() => {
  (globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  mocks.apiFetch.mockReset();
  mocks.setTrades.mockReset();
  mocks.trades = [];
  mocks.setTrades.mockImplementation((trades: any[]) => { mocks.trades = trades; });
});

afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
});

it("cancels the trade-list read without showing an empty journal", async () => {
  let resolvePending!: (value: Response) => void;
  const pending = new Promise<Response>((resolve) => { resolvePending = resolve; });
  let requestSignal: AbortSignal | undefined;
  mocks.apiFetch.mockImplementation((_path: string, init?: RequestInit) => {
    requestSignal = init?.signal;
    return pending;
  });

  await act(async () => root.render(<JournalView {...props} />));
  await flush();

  const cancel = host.querySelector("[data-testid=journal-cancel]") as HTMLButtonElement;
  expect(cancel).toBeTruthy();
  await act(async () => cancel.click());
  await flush();

  expect(requestSignal?.aborted).toBe(true);
  expect(host.querySelector("[data-testid=journal-cancelled]")).not.toBeNull();
  expect(host.querySelector("[data-testid=journal-empty]")).toBeNull();

  resolvePending(response([]));
  await flush();
  expect(host.querySelector("[data-testid=journal-empty]")).toBeNull();
  expect(mocks.setTrades).not.toHaveBeenCalled();
});

it("shows an explicit error instead of an empty journal when the trade list fails", async () => {
  mocks.apiFetch.mockResolvedValue(response({ detail: "trade list unavailable" }, 503));
  await act(async () => root.render(<JournalView {...props} />));
  await flush();

  expect(host.querySelector("[data-testid=journal-error]")?.textContent).toContain("trade list unavailable");
  expect(host.querySelector("[data-testid=journal-empty]")).toBeNull();
  expect(mocks.setTrades).not.toHaveBeenCalled();
});

it("rejects a malformed successful trade-list payload", async () => {
  mocks.apiFetch.mockResolvedValue(response({ trades: [] }));
  await act(async () => root.render(<JournalView {...props} />));
  await flush();

  expect(host.querySelector("[data-testid=journal-error]")?.textContent).toContain("Trade list response was malformed");
  expect(host.querySelector("[data-testid=journal-empty]")).toBeNull();
  expect(mocks.setTrades).not.toHaveBeenCalled();
});

it("keeps an unknown closed-trade PnL distinct from zero", async () => {
  const trade = {
    id: "TRD-UNKNOWN",
    symbol: "BTCUSDT",
    side: "BUY",
    entry_price: 100,
    exit_price: 101,
    qty: 1,
    pnl: null,
    entry_time: "2026-09-08T10:00:00Z",
    status: "CLOSED",
  };
  mocks.apiFetch.mockResolvedValue(response([trade]));

  await act(async () => root.render(<JournalView {...props} />));
  await flush();

  expect(host.textContent).toContain("journal.unknown_value");
  expect(host.textContent).not.toContain("$0.00");
});

it("loads older journal pages without silently replacing the first page", async () => {
  const trade = (id: string) => ({
    id,
    symbol: "BTCUSDT",
    side: "BUY",
    entry_price: 100,
    qty: 1,
    entry_time: "2026-09-08T10:00:00Z",
    status: "OPEN",
  });
  const firstPage = Array.from({ length: 201 }, (_, index) => trade(`TRD-${index}`));
  mocks.apiFetch.mockImplementation((path: string) => {
    if (path.includes("offset=0")) return Promise.resolve(response(firstPage));
    return Promise.resolve(response([trade("TRD-201")]));
  });

  await act(async () => root.render(<JournalView {...props} />));
  await flush();

  const loadMore = Array.from(host.querySelectorAll("button")).find((button) => button.textContent === "journal.load_more") as HTMLButtonElement;
  expect(loadMore).toBeTruthy();
  await act(async () => loadMore.click());
  await flush();

  expect(mocks.apiFetch).toHaveBeenCalledWith("/api/v1/trades?limit=201&offset=200", expect.anything());
  expect(mocks.trades).toHaveLength(201);
  expect(host.textContent).toContain("TRD-201");
});
