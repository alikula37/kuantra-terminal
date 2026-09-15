// @vitest-environment jsdom
import React, { act } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  apiFetch: vi.fn(),
  setTrades: vi.fn(),
  trades: [] as any[],
  updatePositionPnl: vi.fn(),
  t: (key: string, params?: Record<string, string | number>) =>
    params ? `${key}:${Object.values(params).join("|")}` : key,
}));

vi.mock("../../lib/backend", () => ({ apiUrl: (path: string) => path, apiFetch: mocks.apiFetch }));
vi.mock("../../context/I18nContext", () => ({
  useTranslation: () => ({ t: mocks.t, locale: "tr" }),
}));
vi.mock("../../stores/tradeStore", () => ({
  useTradeStore: () => ({
    trades: mocks.trades,
    setTrades: mocks.setTrades,
    openPositions: [],
    updatePositionPnl: mocks.updatePositionPnl,
  }),
}));

import { JournalView } from "../JournalView";
import { createRoot } from "react-dom/client";

const response = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

const openTrade = {
  id: "TRD-EDIT-1",
  symbol: "BTCUSDT",
  side: "BUY",
  entry_price: 100,
  qty: 2,
  entry_time: "2026-09-13T21:00:00Z",
  status: "OPEN",
  price_source: "binance_public",
  price_source_symbol: "BTCUSDT",
  revision: 1,
};

let host: HTMLDivElement;
let root: ReturnType<typeof createRoot>;
const flush = async () => {
  await act(async () => {
    for (let i = 0; i < 4; i++) await Promise.resolve();
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
};

beforeEach(async () => {
  (globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
  host = document.createElement("div");
  document.body.append(host);
  const { createRoot: create } = await import("react-dom/client");
  root = create(host);
  mocks.apiFetch.mockReset();
  mocks.setTrades.mockReset();
  mocks.updatePositionPnl.mockReset();
  mocks.trades = [];
  mocks.setTrades.mockImplementation((trades: any[]) => { mocks.trades = trades; });
});

afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
});

it("opens the trade editor instead of replay from the journal row", async () => {
  mocks.apiFetch.mockResolvedValue(response([openTrade]));
  const onEditTrade = vi.fn();
  await act(async () => root.render(<JournalView onOpenNewTrade={vi.fn()} onEditTrade={onEditTrade} />));
  await flush();

  const editButton = host.querySelector("[data-testid=journal-edit-action]") as HTMLButtonElement;
  expect(editButton).not.toBeNull();
  expect(editButton.dataset.tradeId).toBe("TRD-EDIT-1");
  await act(async () => editButton.click());
  expect(onEditTrade).toHaveBeenCalledWith("TRD-EDIT-1");
  expect(host.querySelector("svg.lucide-play-circle")).toBeNull();
});

it("refreshes all open prices and shows status with age", async () => {
  mocks.apiFetch.mockImplementation((path: string, init?: RequestInit) => {
    if (path.includes("/quotes/refresh")) {
      expect(init?.method).toBe("POST");
      return Promise.resolve(response({
        checked_at: "2026-09-14T10:00:00Z",
        requested: 1,
        identities: 1,
        skipped_identities: 0,
        quotes: {
          "TRD-EDIT-1": {
            quote_status: "LIVE", price: 65000, price_kind: "LAST",
            source_id: "binance_public", source_symbol: "BTCUSDT",
            observed_at: "2026-09-14T09:59:59Z", checked_at: "2026-09-14T10:00:00Z",
            age_seconds: 1, reason: null, last_known: null,
          },
        },
      }));
    }
    return Promise.resolve(response([openTrade]));
  });

  await act(async () => root.render(<JournalView onOpenNewTrade={vi.fn()} onEditTrade={vi.fn()} />));
  await flush();

  const refresh = host.querySelector("[data-testid=journal-refresh-all]") as HTMLButtonElement;
  expect(refresh.disabled).toBe(false);
  await act(async () => refresh.click());
  await flush();

  expect(host.textContent).toContain("65,000");
  expect(host.textContent).toContain("LIVE");
  expect(host.textContent).toContain("journal.refresh_checked");
});

it("shows the last known price as stale when the refresh fails", async () => {
  mocks.apiFetch.mockImplementation((path: string) => {
    if (path.includes("/quotes/refresh")) {
      return Promise.resolve(response({
        checked_at: "2026-09-14T10:00:00Z",
        requested: 1,
        identities: 1,
        skipped_identities: 0,
        quotes: {
          "TRD-EDIT-1": {
            quote_status: "UNAVAILABLE", price: null, price_kind: null,
            source_id: "binance_public", source_symbol: "BTCUSDT",
            observed_at: null, checked_at: "2026-09-14T10:00:00Z",
            age_seconds: null, reason: "PROVIDER_UNAVAILABLE",
            last_known: { price: 64000, observed_at: "2026-09-14T09:55:00Z", quote_status: "LIVE", stale: true },
          },
        },
      }));
    }
    return Promise.resolve(response([openTrade]));
  });

  await act(async () => root.render(<JournalView onOpenNewTrade={vi.fn()} onEditTrade={vi.fn()} />));
  await flush();

  expect(host.textContent).toContain("journal.quote_unavailable");
  expect(host.textContent).toContain("journal.quote_last_known");
  expect(host.textContent).toContain("64,000");
});

it("demotes a previously live quote after a transport failure and recovers", async () => {
  let failing = false;
  const observedAt = new Date(Date.now() - 3000).toISOString();
  mocks.apiFetch.mockImplementation((path: string) => {
    if (path.includes("/quotes/refresh")) {
      if (failing) return Promise.reject(new Error("network down"));
      return Promise.resolve(response({
        checked_at: new Date().toISOString(),
        requested: 1,
        identities: 1,
        skipped_identities: 0,
        quotes: {
          "TRD-EDIT-1": {
            quote_status: "LIVE", price: 65000, price_kind: "LAST",
            source_id: "binance_public", source_symbol: "BTCUSDT",
            observed_at: observedAt, checked_at: new Date().toISOString(),
            age_seconds: 3, reason: null, last_known: null,
          },
        },
      }));
    }
    return Promise.resolve(response([openTrade]));
  });

  await act(async () => root.render(<JournalView onOpenNewTrade={vi.fn()} onEditTrade={vi.fn()} />));
  await flush();
  expect(host.textContent).toContain("LIVE");
  expect(host.textContent).toContain("65,000");

  failing = true;
  await act(async () => (host.querySelector("[data-testid=journal-refresh-all]") as HTMLButtonElement).click());
  await flush();

  // The old price is never presented as live; it is demoted to stale data and
  // the attempt/success times stay distinct.
  expect(host.textContent).not.toContain("LIVE");
  expect(host.textContent).toContain("journal.quote_unavailable");
  expect(host.textContent).toContain("journal.quote_last_known");
  expect(host.textContent).toContain("journal.refresh_failed");
  expect(host.textContent).toContain("journal.refresh_attempt");
  expect(host.textContent).toContain("journal.refresh_last_success");

  failing = false;
  await act(async () => (host.querySelector("[data-testid=journal-refresh-all]") as HTMLButtonElement).click());
  await flush();
  expect(host.textContent).toContain("LIVE");
  expect(host.textContent).not.toContain("journal.quote_last_known");
});

it("advances the displayed quote age between refreshes", async () => {
  // Fake only the interval/clock so the hook's age ticker is controllable
  // while real timers keep act() flushing deterministic.
  vi.useFakeTimers({ toFake: ["setInterval", "clearInterval", "Date"] });
  try {
    const observedAt = new Date(Date.now() - 5000).toISOString();
    mocks.apiFetch.mockImplementation((path: string) => {
      if (path.includes("/quotes/refresh")) {
        return Promise.resolve(response({
          checked_at: new Date().toISOString(),
          requested: 1,
          identities: 1,
          skipped_identities: 0,
          quotes: {
            "TRD-EDIT-1": {
              quote_status: "LIVE", price: 65000, price_kind: "LAST",
              source_id: "binance_public", source_symbol: "BTCUSDT",
              observed_at: observedAt, checked_at: new Date().toISOString(),
              age_seconds: 5, reason: null, last_known: null,
            },
          },
        }));
      }
      return Promise.resolve(response([openTrade]));
    });

    await act(async () => root.render(<JournalView onOpenNewTrade={vi.fn()} onEditTrade={vi.fn()} />));
    await flush();
    expect(host.textContent).toContain("5s");

    await act(async () => { vi.advanceTimersByTime(5000); });
    expect(host.textContent).toContain("10s");
  } finally {
    vi.useRealTimers();
  }
});

it("filters by several symbols and statuses at once", async () => {
  const trade = (id: string, symbol: string, status: string) => ({
    id, symbol, side: "BUY", status, position_type: "LONG",
    entry_price: 100, qty: 1, entry_time: "2026-09-15T10:00:00Z",
    exit_price: null, exit_time: null, pnl: null, notes: "", qty_unit: "BASE",
    created_at: "2026-09-15T10:00:00Z", updated_at: "2026-09-15T10:00:00Z", revision: 1,
  });
  mocks.apiFetch.mockImplementation((path: string) => {
    if (path.includes("/api/v1/trades?")) {
      return Promise.resolve(response([
        trade("T-ETH", "ETHUSDT", "OPEN"),
        trade("T-XAU", "XAUUSD", "OPEN"),
        trade("T-BTC", "BTCUSDT", "CLOSED"),
      ]));
    }
    if (path.includes("/quotes/refresh")) {
      return Promise.resolve(response({
        checked_at: new Date().toISOString(), requested: 2, identities: 2, skipped_identities: 0, quotes: {},
      }));
    }
    return Promise.resolve(response([]));
  });

  await act(async () => root.render(<JournalView onOpenNewTrade={vi.fn()} />));
  await flush();
  const rowsText = () => Array.from(host.querySelectorAll("tbody tr")).map((row) => row.textContent).join(" | ");
  expect(rowsText()).toContain("ETHUSDT");
  expect(rowsText()).toContain("XAUUSD");
  expect(rowsText()).toContain("BTCUSDT");

  await act(async () => (host.querySelector("[data-testid=journal-filter-symbols]") as HTMLButtonElement).click());
  await act(async () => (host.querySelector("[data-testid=journal-filter-symbols-option-ETHUSDT]") as HTMLInputElement).click());
  await act(async () => (host.querySelector("[data-testid=journal-filter-symbols-option-XAUUSD]") as HTMLInputElement).click());
  await flush();

  expect(rowsText()).toContain("ETHUSDT");
  expect(rowsText()).toContain("XAUUSD");
  expect(rowsText()).not.toContain("BTCUSDT");

  await act(async () => (host.querySelector("[data-testid=journal-filter-symbols-clear]") as HTMLButtonElement).click());
  await flush();
  expect(rowsText()).toContain("BTCUSDT");

  await act(async () => (host.querySelector("[data-testid=journal-filter-statuses]") as HTMLButtonElement).click());
  await act(async () => (host.querySelector("[data-testid=journal-filter-statuses-option-CLOSED]") as HTMLInputElement).click());
  await flush();

  expect(rowsText()).not.toContain("ETHUSDT");
  expect(rowsText()).not.toContain("XAUUSD");
  expect(rowsText()).toContain("BTCUSDT");

  await act(async () => (host.querySelector("[data-testid=journal-filter-statuses-clear]") as HTMLButtonElement).click());
  await flush();
  expect(rowsText()).toContain("ETHUSDT");
});
