// @vitest-environment jsdom
import React, { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { beforeEach, afterEach, expect, it, vi } from "vitest";
import { QuoteQuality } from "../QuoteQuality";

vi.mock("../../context/I18nContext", () => ({ useTranslation: () => ({
  locale: "tr", t: (key: string, args?: Record<string, unknown>) => `${key}:${args ? Object.values(args).join("|") : ""}`,
}) }));
let host: HTMLDivElement, root: Root;
const quote = { price: 100, status: "LIVE" as const, observed_at: "2026-10-02T12:00:00Z",
  timestamp_basis: "PROVIDER_EVENT" as const, source_id: "binance_public", source_symbol: "BTCUSDT" };
beforeEach(() => {
  (globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
  vi.useFakeTimers(); vi.setSystemTime(new Date("2026-10-02T12:00:59Z"));
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
});
afterEach(async () => { await act(async () => root.unmount()); host.remove(); vi.useRealTimers(); });

it("ages out LIVE without a network refresh or replacing the price", async () => {
  await act(async () => root.render(<QuoteQuality quote={quote} />));
  expect(host.querySelector("[data-quote-status]")?.getAttribute("data-quote-status")).toBe("LIVE");
  await act(async () => vi.advanceTimersByTime(2000));
  expect(host.querySelector("[data-quote-status]")?.getAttribute("data-quote-status")).toBe("DELAYED");
  expect(host.textContent).toContain("quote_quality.stale");
});

it("labels candle-open time and display-only tracking in Istanbul time", async () => {
  await act(async () => root.render(<QuoteQuality quote={{ ...quote, source_id: "biquote_public", source_symbol: "XAUUSD",
    timestamp_basis: "CANDLE_OPEN", candle_interval: "1h" }} />));
  expect(host.querySelector("[data-quote-status]")?.getAttribute("data-quote-status")).toBe("DELAYED");
  expect(host.textContent).toContain("quote_quality.candle_open");
  expect(host.textContent).toContain("15:00");
  expect(host.textContent).toContain("quote_quality.display_only");
});

it("unknown or naive timestamps never become live", async () => {
  await act(async () => root.render(<QuoteQuality quote={{ ...quote, observed_at: "2026-10-02T12:00:00" }} />));
  expect(host.querySelector("[data-quote-status]")?.getAttribute("data-quote-status")).toBe("DELAYED");
  expect(host.textContent).toContain("quote_quality.unknown_time");
});

it("a future event and legacy LIVE payload have no freshness claim", async () => {
  await act(async () => root.render(<QuoteQuality quote={{ ...quote, observed_at: "2026-10-02T12:05:00Z" }} />));
  expect(host.querySelector("[data-quote-status]")?.getAttribute("data-quote-status")).toBe("DELAYED");
  await act(async () => root.render(<QuoteQuality quote={{ ...quote, timestamp_basis: undefined }} />));
  expect(host.textContent).toContain("quote_quality.unknown_time");
});

it("compact disclosure never conceals delayed or unknown quality and retains the exact source time", async () => {
  await act(async () => root.render(<QuoteQuality compact quote={{ ...quote,
    timestamp_basis: "CANDLE_OPEN", candle_interval: "1h" }} />));
  expect(host.querySelector("details")?.open).toBe(false);
  expect(host.querySelector("[data-quote-status]")?.getAttribute("data-quote-status")).toBe("DELAYED");
  expect(host.querySelector("details")?.textContent).toContain("15:00");
  expect(host.querySelector("details")?.previousElementSibling?.textContent).toContain("quote_quality.display_only_short");
  await act(async () => root.render(<QuoteQuality compact quote={{ ...quote, timestamp_basis: undefined }} />));
  expect(host.querySelector("details")?.previousElementSibling?.textContent).toContain("quote_quality.unknown_time_short");
  expect(host.querySelector("details")?.textContent).toContain("quote_quality.unknown_time");
});
