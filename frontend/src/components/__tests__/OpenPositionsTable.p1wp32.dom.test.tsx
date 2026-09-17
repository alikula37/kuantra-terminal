// @vitest-environment jsdom
import React, { act } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  apiFetch: vi.fn(),
  t: (key: string, params?: Record<string, string | number>) =>
    params ? `${key}:${Object.values(params).join("|")}` : key,
}));

vi.mock("../../lib/backend", () => ({ apiUrl: (path: string) => path, apiFetch: mocks.apiFetch }));
vi.mock("../../context/I18nContext", () => ({
  useTranslation: () => ({ t: mocks.t, locale: "tr" }),
}));

import { OpenPositionsTable } from "../dashboard/OpenPositionsTable";

const response = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

const positions = [
  {
    id: "TRD-GOLD", symbol: "XAUUSD", side: "BUY", position_type: "LONG",
    entry_price: 2000, qty: 2, entry_time: "2026-09-13T21:00:00Z", status: "OPEN",
  },
  {
    id: "TRD-BTC", symbol: "BTCUSDT", side: "BUY", position_type: "LONG",
    entry_price: 64000, qty: 0.5, entry_time: "2026-09-13T21:00:00Z", status: "OPEN",
    qty_unit: "BASE",
  },
];

let host: HTMLDivElement;
let root: ReturnType<typeof import("react-dom/client").createRoot>;
const flush = async () => { await act(async () => { for (let i = 0; i < 4; i++) await Promise.resolve(); }); };

beforeEach(async () => {
  (globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
  host = document.createElement("div");
  document.body.append(host);
  const { createRoot } = await import("react-dom/client");
  root = createRoot(host);
  mocks.apiFetch.mockReset();
});

afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
});

it("shows local unrealized only for a verified base unit", async () => {
  mocks.apiFetch.mockImplementation((path: string) => {
    if (path.includes("/quotes/refresh")) {
      return Promise.resolve(response({
        checked_at: new Date().toISOString(),
        requested: 2,
        identities: 2,
        skipped_identities: 0,
        quotes: {
          "TRD-GOLD": {
            quote_status: "LIVE", price: 2100, price_kind: "LAST",
            source_id: "biquote_public", source_symbol: "XAUUSD",
            observed_at: new Date().toISOString(), checked_at: new Date().toISOString(),
            age_seconds: 1, reason: null, last_known: null,
          },
          "TRD-BTC": {
            quote_status: "LIVE", price: 65000, price_kind: "LAST",
            source_id: "binance_public", source_symbol: "BTCUSDT",
            observed_at: new Date().toISOString(), checked_at: new Date().toISOString(),
            age_seconds: 1, reason: null, last_known: null,
          },
        },
      }));
    }
    return Promise.resolve(response([]));
  });

  await act(async () => root.render(
    <OpenPositionsTable positions={positions as never} onClosePosition={vi.fn()} />,
  ));
  await flush();

  const rows = Array.from(host.querySelectorAll("tbody tr"));
  expect(rows).toHaveLength(2);
  const goldRow = rows.find((row) => row.textContent?.includes("XAUUSD"))!;
  const btcRow = rows.find((row) => row.textContent?.includes("BTCUSDT"))!;

  // Gold: the price is shown with its status, but no monetary P/L claim.
  expect(goldRow.textContent).toContain("2,100");
  expect(goldRow.textContent).toContain("open_positions.monetary_unavailable");
  expect(goldRow.textContent).not.toContain("open_positions.local_unrealized");

  // Crypto pair: local unrealized appears from the fresh quote.
  expect(btcRow.textContent).toContain("65,000");
  expect(btcRow.textContent).toContain("open_positions.local_unrealized");
  expect(btcRow.textContent).not.toContain("open_positions.monetary_unavailable");
});

it("enables money math once the server verifies the symbol", async () => {
  const solPosition = {
    id: "TRD-SOL", symbol: "SOLUSDT", side: "BUY", position_type: "LONG",
    entry_price: 150, qty: 10, entry_time: "2026-09-15T10:00:00Z", status: "OPEN",
  };
  mocks.apiFetch.mockImplementation((path: string) => {
    if (path.includes("/market-data/instrument")) {
      return Promise.resolve(response({
        status: "VERIFIED", provider: "binance_spot", base_asset: "SOL", quote_asset: "USDT",
      }));
    }
    if (path.includes("/quotes/refresh")) {
      return Promise.resolve(response({
        checked_at: new Date().toISOString(), requested: 1, identities: 1, skipped_identities: 0,
        quotes: {
          "TRD-SOL": {
            quote_status: "LIVE", price: 160, price_kind: "LAST",
            source_id: "binance_public", source_symbol: "SOLUSDT",
            observed_at: new Date().toISOString(), checked_at: new Date().toISOString(),
            age_seconds: 1, reason: null, last_known: null,
          },
        },
      }));
    }
    return Promise.resolve(response([]));
  });

  await act(async () => root.render(
    <OpenPositionsTable positions={[solPosition] as never} onClosePosition={vi.fn()} />,
  ));
  await flush();

  const row = host.querySelector("tbody tr")!;
  expect(row.textContent).toContain("160");
  expect(row.textContent).toContain("open_positions.local_unrealized");
  expect(row.textContent).not.toContain("open_positions.monetary_unavailable");
});

it("refreshes quotes when the parent bumps the refresh nonce", async () => {
  const position = {
    id: "TRD-NONCE", symbol: "ETHUSDT", side: "BUY", position_type: "LONG",
    entry_price: 2500, qty: 1, entry_time: "2026-09-15T10:00:00Z", status: "OPEN",
  };
  const refreshCalls: string[] = [];
  mocks.apiFetch.mockImplementation((path: string, init?: RequestInit) => {
    if (path.includes("/market-data/instrument")) {
      return Promise.resolve(response({ status: "VERIFIED", provider: "binance_spot", base_asset: "ETH", quote_asset: "USDT" }));
    }
    if (path.includes("/quotes/refresh")) {
      refreshCalls.push(String(init?.method || "GET"));
      return Promise.resolve(response({
        checked_at: new Date().toISOString(), requested: 1, identities: 1, skipped_identities: 0,
        quotes: {
          "TRD-NONCE": {
            quote_status: "LIVE", price: 2510, price_kind: "LAST",
            source_id: "binance_public", source_symbol: "ETHUSDT",
            observed_at: new Date().toISOString(), checked_at: new Date().toISOString(),
            age_seconds: 1, reason: null, last_known: null,
          },
        },
      }));
    }
    return Promise.resolve(response([]));
  });

  await act(async () => root.render(
    <OpenPositionsTable positions={[position] as never} onClosePosition={vi.fn()} refreshNonce={0} />,
  ));
  await flush();
  const initialCalls = refreshCalls.length;
  expect(initialCalls).toBeGreaterThan(0);

  await act(async () => root.render(
    <OpenPositionsTable positions={[position] as never} onClosePosition={vi.fn()} refreshNonce={1} />,
  ));
  await flush();

  expect(refreshCalls.length).toBe(initialCalls + 1);
});

it("offers a one-click unit declaration for positions that cannot be priced", async () => {
  const position = {
    id: "TRD-DECLARE", symbol: "XAUUSD", side: "SELL", position_type: "SHORT",
    entry_price: 4294.732, qty: 1000, entry_time: "2026-09-15T10:00:00Z", status: "OPEN",
    qty_unit: "UNKNOWN",
  };
  const onEditPosition = vi.fn();
  mocks.apiFetch.mockImplementation((path: string) => {
    if (path.includes("/market-data/instrument")) {
      return Promise.resolve(response({ status: "UNVERIFIED" }));
    }
    if (path.includes("/quotes/refresh")) {
      return Promise.resolve(response({
        checked_at: new Date().toISOString(), requested: 1, identities: 1, skipped_identities: 0,
        quotes: {
          "TRD-DECLARE": {
            quote_status: "LIVE", price: 4286.05, price_kind: "LAST",
            source_id: "biquote_public", source_symbol: "XAUUSD",
            observed_at: new Date().toISOString(), checked_at: new Date().toISOString(),
            age_seconds: 1, reason: null, last_known: null,
          },
        },
      }));
    }
    return Promise.resolve(response([]));
  });

  await act(async () => root.render(
    <OpenPositionsTable positions={[position] as never} onClosePosition={vi.fn()} onEditPosition={onEditPosition} />,
  ));
  await flush();

  const declare = host.querySelector("[data-testid=declare-unit-TRD-DECLARE]") as HTMLButtonElement;
  expect(declare).toBeTruthy();
  await act(async () => declare.click());
  expect(onEditPosition).toHaveBeenCalledWith(expect.objectContaining({ id: "TRD-DECLARE" }));
});

it("does not offer the declaration once the unit is verified", async () => {
  const position = {
    id: "TRD-VERIFIED", symbol: "ETHUSDT", side: "BUY", position_type: "LONG",
    entry_price: 2500, qty: 1, entry_time: "2026-09-15T10:00:00Z", status: "OPEN",
    qty_unit: "BASE",
  };
  mocks.apiFetch.mockImplementation((path: string) => {
    if (path.includes("/quotes/refresh")) {
      return Promise.resolve(response({
        checked_at: new Date().toISOString(), requested: 1, identities: 1, skipped_identities: 0,
        quotes: {},
      }));
    }
    return Promise.resolve(response([]));
  });

  await act(async () => root.render(
    <OpenPositionsTable positions={[position] as never} onClosePosition={vi.fn()} onEditPosition={vi.fn()} />,
  ));
  await flush();

  expect(host.querySelector("[data-testid=declare-unit-TRD-VERIFIED]")).toBeNull();
});

it("labels a simulation position explicitly without touching real rows", async () => {
  mocks.apiFetch.mockImplementation((path: string) => {
    if (path.includes("/quotes/refresh")) {
      return Promise.resolve(response({
        checked_at: new Date().toISOString(), requested: 2, identities: 2, skipped_identities: 0,
        quotes: {},
      }));
    }
    if (path.includes("/market-data/instrument")) {
      return Promise.resolve(response({ status: "UNVERIFIED" }));
    }
    return Promise.resolve(response([]));
  });
  const simPosition = { ...positions[1], id: "TRD-SIM", record_mode: "SIMULATION" };
  await act(async () => root.render(
    <OpenPositionsTable positions={[positions[0], simPosition] as never} onClosePosition={vi.fn()} />,
  ));
  await flush();

  const badge = host.querySelector('[data-testid="open-sim-badge-TRD-SIM"]');
  expect(badge?.textContent).toContain("journal.simulation_badge");
  expect(host.querySelector('[data-testid="open-sim-badge-TRD-GOLD"]')).toBeNull();
});

it("shows a USD position value and computes unrealized from the value", async () => {
  mocks.apiFetch.mockImplementation((path: string) => {
    if (path.includes("/quotes/refresh")) {
      return Promise.resolve(response({
        checked_at: new Date().toISOString(), requested: 1, identities: 1, skipped_identities: 0,
        quotes: {
          "TRD-XAU-USD": {
            quote_status: "LIVE", price: 4343, price_kind: "LAST",
            source_id: "biquote_public", source_symbol: "XAUUSD",
            observed_at: new Date().toISOString(), checked_at: new Date().toISOString(),
            age_seconds: 1, reason: null, last_known: null,
          },
        },
      }));
    }
    if (path.includes("/market-data/instrument")) return Promise.resolve(response({ status: "UNVERIFIED" }));
    return Promise.resolve(response([]));
  });
  const usdPosition = {
    id: "TRD-XAU-USD", symbol: "XAUUSD", side: "BUY", position_type: "LONG",
    entry_price: 4300, qty: 1000, qty_unit: "USD", entry_time: "2026-09-17T09:00:00Z",
    status: "OPEN",
  };
  await act(async () => root.render(
    <OpenPositionsTable positions={[usdPosition] as never} onClosePosition={vi.fn()} />,
  ));
  await flush();

  const row = host.querySelector("tbody tr");
  expect(row?.textContent).toContain("$1,000.00");
  expect(row?.textContent).toContain("open_positions.local_unrealized:+10.00");
  // The open PnL column is the mark-to-market value, never the stored zero.
  expect(host.querySelector('[data-testid="open-pnl-TRD-XAU-USD"]')?.textContent).toBe("+10.00");
});
