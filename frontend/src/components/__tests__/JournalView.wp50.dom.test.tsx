// @vitest-environment jsdom
import React, { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { beforeEach, afterEach, expect, it, vi } from "vitest";
import en from "../../locales/en.json";
import tr from "../../locales/tr.json";
import de from "../../locales/de.json";

const mocks = vi.hoisted(() => ({ apiFetch: vi.fn(), setTrades: vi.fn(), trades: [] as any[], locale: "tr", quote: {} as any }));
vi.mock("../../lib/backend", () => ({ apiUrl: (path: string) => path, apiFetch: mocks.apiFetch }));
vi.mock("../../stores/tradeStore", () => ({ useTradeStore: () => ({
  trades: mocks.trades, setTrades: mocks.setTrades,
  openPositions: [], updatePositionPnl: vi.fn(),
}) }));
vi.mock("../../context/I18nContext", () => {
  const t = (key: string, params?: Record<string, string | number>) => {
    const dictionaries: Record<string, any> = { en, tr, de };
    let value = key.split(".").reduce((part, next) => part?.[next], dictionaries[mocks.locale]);
    if (typeof value !== "string") return key;
    for (const [name, text] of Object.entries(params || {})) value = value.replaceAll(`{${name}}`, String(text));
    return value;
  };
  return { useTranslation: () => ({ locale: mocks.locale, t }) };
});
vi.mock("../../hooks/useOpenQuoteRefresh", () => ({ useOpenQuoteRefresh: () => ({
  quotes: { "TRD-WP50": mocks.quote }, nowMs: Date.parse("2026-10-02T12:00:30Z"),
  refresh: vi.fn(), busy: false, error: null, lastSuccessAt: null, lastAttemptAt: null,
}) }));
vi.mock("../TradeEvidencePanel", () => ({ TradeEvidencePanel: ({ tradeId }: { tradeId: string }) =>
  <div data-testid="evidence-panel">{tradeId}</div>,
}));
import { JournalView } from "../JournalView";

const trade = { id: "TRD-WP50", symbol: "XAUUSD", side: "LONG", position_type: "LONG", status: "OPEN",
  entry_price: 4300, qty: 200, qty_unit: "USD", record_mode: "SIMULATION", revision: 1,
  entry_time: "2026-10-02T10:00:00Z", exit_price: null, pnl: null, r_multiple: null };
const response = (body: unknown) => new Response(JSON.stringify(body), { headers: { "Content-Type": "application/json" } });
let host: HTMLDivElement, root: Root;
const flush = async () => { await act(async () => { for (let i = 0; i < 5; i++) await Promise.resolve(); }); };
const button = (id: string) => host.querySelector(`[data-testid="${id}"]`) as HTMLButtonElement;
beforeEach(() => {
  (globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
  mocks.locale = "tr"; mocks.trades = [trade]; mocks.apiFetch.mockReset();
  mocks.setTrades.mockImplementation((trades: any[]) => { mocks.trades = trades; });
  mocks.quote = { quote_status: "DELAYED", price: 4310, source_id: "biquote_public", source_symbol: "XAUUSD",
    timestamp_basis: "CANDLE_OPEN", candle_interval: "1h", observed_at: "2026-10-02T12:00:00Z" };
  mocks.apiFetch.mockImplementation((path: string) => Promise.resolve(response(path.includes("local-tracking")
    ? [{ trade_id: trade.id, tracking_status: "WAITING_QUOTE", remaining_qty: "200" }] : mocks.trades)));
});
afterEach(async () => { await act(async () => root.unmount()); host.remove(); });

it("keeps primary Edit, seven bounded columns and honest price/status visible without a sticky overlay", async () => {
  const edit = vi.fn();
  await act(async () => root.render(<JournalView onOpenNewTrade={vi.fn()} onEditTrade={edit} onOpenReplay={vi.fn()} />)); await flush();
  expect(host.querySelectorAll("thead th")).toHaveLength(7);
  expect(host.querySelector("th.sticky, td.sticky")).toBeNull();
  expect(host.querySelector("table")?.className).toContain("table-fixed");
  expect(host.querySelector('[data-quote-status="DELAYED"]')).not.toBeNull();
  expect(host.textContent).toContain("Otomatik TP/SL yok");
  expect(host.querySelector('[data-tracking-status="WAITING_QUOTE"]')).not.toBeNull();
  expect(button("journal-details-action")?.getAttribute("aria-expanded")).toBe("false");
  expect(button("journal-replay-action")).toBeNull();
  await act(async () => button("journal-edit-action").click());
  expect(edit).toHaveBeenCalledExactlyOnceWith(trade.id);
});

it.each(["en", "tr", "de"])("discloses full values and preserved secondary actions, with Escape focus return (%s)", async (locale) => {
  mocks.locale = locale;
  const replay = vi.fn();
  await act(async () => root.render(<JournalView onOpenNewTrade={vi.fn()} onOpenReplay={replay} />)); await flush();
  const toggle = button("journal-details-action");
  expect(toggle).not.toBeNull(); expect(toggle.type).toBe("button"); expect(toggle.getAttribute("aria-label")).toContain(trade.symbol);
  await act(async () => toggle.click());
  const details = host.querySelector(`#${toggle.getAttribute("aria-controls")}`);
  expect(details?.textContent).toContain(trade.id);
  expect(details?.textContent).toContain("13:00");
  expect(toggle.getAttribute("aria-expanded")).toBe("true");
  for (const id of ["journal-evidence-action", "journal-replay-action", "journal-cancel-action"]) {
    expect(button(id)?.className).toContain("focus-visible:ring-accent");
  }
  await act(async () => button("journal-replay-action").click());
  expect(replay).toHaveBeenCalledExactlyOnceWith(trade.id);
  await act(async () => button("journal-evidence-action").click());
  expect(host.querySelector('[data-testid="evidence-panel"]')?.textContent).toBe(trade.id);
  // Escape in the inline disclosure collapses it and returns focus to its owner.
  await act(async () => details!.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true })));
  expect(toggle.getAttribute("aria-expanded")).toBe("false"); expect(document.activeElement).toBe(toggle);
  expect(mocks.apiFetch.mock.calls.some(([, init]) => init?.method === "DELETE")).toBe(false);
});

it("requires confirmation from the disclosed cancellation action and retains a canceled tombstone", async () => {
  mocks.apiFetch.mockImplementation((path: string, init?: RequestInit) => Promise.resolve(response(init?.method === "DELETE"
    ? { trade: { ...trade, status: "CANCELED" } }
    : path.includes("local-tracking") ? [] : mocks.trades)));
  await act(async () => root.render(<JournalView onOpenNewTrade={vi.fn()} onOpenReplay={vi.fn()} />)); await flush();
  await act(async () => button("journal-details-action").click());
  await act(async () => button("journal-cancel-action").click());
  expect(host.querySelector('[data-testid="journal-cancel-dialog"]')).not.toBeNull();
  expect(mocks.apiFetch.mock.calls.some(([, init]) => init?.method === "DELETE")).toBe(false);
  await act(async () => button("journal-cancel-confirm").click()); await flush();
  await act(async () => root.render(<JournalView onOpenNewTrade={vi.fn()} onOpenReplay={vi.fn()} />));
  expect(button("journal-cancel-action")).toBeNull(); expect(button("journal-replay-action")).toBeNull();
  expect(host.textContent).toContain("İptal edildi");
});

it.each([null, 0])("retains unknown versus actual zero closed results, exit and R in full details (%s)", async (pnl) => {
  mocks.trades = [{ ...trade, status: "CLOSED", exit_price: 4310, pnl, r_multiple: 0.25 }];
  await act(async () => root.render(<JournalView onOpenNewTrade={vi.fn()} />)); await flush();
  // The result remains visible even before opening the details.
  expect(host.textContent).toContain(pnl === null ? "Bilinmiyor" : "0.00");
  await act(async () => button("journal-details-action").click());
  const details = host.querySelector('[data-testid="journal-row-details"]');
  expect(details?.textContent).toContain(pnl === null ? "Bilinmiyor" : "0.00");
  expect(details?.textContent).toContain("4,310"); expect(details?.textContent).toContain("+0.25R");
});
