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
