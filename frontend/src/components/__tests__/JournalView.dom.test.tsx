// @vitest-environment jsdom
import React, { act } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  apiFetch: vi.fn(),
  setTrades: vi.fn(),
  trades: [] as any[],
  openPositions: [] as any[],
  updatePositionPnl: vi.fn(),
  t: (key: string) => key,
}));
vi.mock("../../lib/backend", () => ({ apiUrl: (path: string) => path, apiFetch: mocks.apiFetch }));
vi.mock("../../context/I18nContext", () => ({
  useTranslation: () => ({ t: mocks.t }),
}));
vi.mock("../../stores/tradeStore", () => ({
  useTradeStore: () => ({
    trades: mocks.trades,
    setTrades: mocks.setTrades,
    openPositions: mocks.openPositions,
    updatePositionPnl: mocks.updatePositionPnl,
  }),
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
  mocks.updatePositionPnl.mockReset();
  mocks.trades = [];
  mocks.openPositions = [];
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

it("offers a confirmed audit-safe cancellation instead of physically deleting a trade", async () => {
  const trade = {
    id: "TRD-CANCEL",
    symbol: "XAUUSD",
    side: "BUY",
    entry_price: 2400,
    qty: 1,
    entry_time: "2026-09-08T10:00:00Z",
    status: "OPEN",
  };
  const canceledTrade = { ...trade, status: "CANCELED" };
  mocks.openPositions = [trade];
  mocks.apiFetch.mockImplementation((_path: string, init?: RequestInit) => (
    init?.method === "DELETE"
      ? Promise.resolve(response({ status: "canceled", id: trade.id, trade: canceledTrade }))
      : Promise.resolve(response([trade]))
  ));

  await act(async () => root.render(<JournalView {...props} />));
  await flush();

  const action = host.querySelector("[data-testid=journal-cancel-action]") as HTMLButtonElement;
  expect(action).toBeTruthy();
  expect(action.dataset.tradeId).toBe(trade.id);
  await act(async () => action.click());
  expect(host.querySelector("[data-testid=journal-cancel-dialog]")).not.toBeNull();
  expect(host.textContent).toContain("journal.cancel_audit_note");

  const confirm = host.querySelector("[data-testid=journal-cancel-confirm]") as HTMLButtonElement;
  await act(async () => confirm.click());
  await flush();

  expect(mocks.apiFetch).toHaveBeenCalledWith(`/api/v1/trades/${trade.id}`, { method: "DELETE" });
  expect(mocks.setTrades).toHaveBeenCalledWith([canceledTrade]);
  expect(mocks.updatePositionPnl).toHaveBeenCalledWith([]);
  expect(host.querySelector("[data-testid=journal-cancel-dialog]")).toBeNull();
  expect(host.querySelector("[data-testid=journal-cancel-success]")?.textContent).toContain("journal.cancel_success");
});

it("keeps the cancellation confirmation open when the server response is unsafe", async () => {
  const trade = {
    id: "TRD-CANCEL-ERROR",
    symbol: "BTCUSDT",
    side: "SELL",
    entry_price: 100,
    qty: 1,
    entry_time: "2026-09-08T10:00:00Z",
    status: "CLOSED",
  };
  mocks.apiFetch.mockImplementation((_path: string, init?: RequestInit) => (
    init?.method === "DELETE"
      ? Promise.resolve(response({ status: "canceled", id: trade.id }))
      : Promise.resolve(response([trade]))
  ));

  await act(async () => root.render(<JournalView {...props} />));
  await flush();
  mocks.setTrades.mockClear();
  await act(async () => (host.querySelector("[data-testid=journal-cancel-action]") as HTMLButtonElement).click());
  await act(async () => (host.querySelector("[data-testid=journal-cancel-confirm]") as HTMLButtonElement).click());
  await flush();

  expect(host.querySelector("[data-testid=journal-cancel-dialog]")).not.toBeNull();
  expect(host.querySelector("[data-testid=journal-cancel-error]")?.textContent).toContain("Trade cancellation response was malformed");
  expect(mocks.setTrades).not.toHaveBeenCalled();
});

it("does not offer a second cancellation action for a retained tombstone", async () => {
  const trade = {
    id: "TRD-CANCELED",
    symbol: "ETHUSDT",
    side: "BUY",
    entry_price: 100,
    qty: 1,
    entry_time: "2026-09-08T10:00:00Z",
    status: "CANCELED",
  };
  mocks.apiFetch.mockResolvedValue(response([trade]));

  await act(async () => root.render(<JournalView {...props} />));
  await flush();

  expect(host.querySelector("[data-testid=journal-cancel-action]")).toBeNull();
  expect(host.textContent).toContain("CANCELED");
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

it("opens the export modal with the current filters from the toolbar", async () => {
  const previewFixture = {
    record_count: 2, counts: { total: 2, open: 1, closed: 1, canceled: 0 }, warnings: [],
    exceeds_limit: false, max_records: 2000, unknown_pnl_closed: 0, unverified_currency_records: 0,
    estimated_trades: 0, snapshot_sha256: "ab".repeat(32),
  };
  mocks.apiFetch.mockImplementation((path: string) =>
    Promise.resolve(path.includes("/journal/export/preview") ? response(previewFixture) : response([])));
  await act(async () => root.render(<JournalView {...props} onOpenCsvImport={vi.fn()} />));
  await flush();

  const open = host.querySelector('[data-testid="journal-export-open"]') as HTMLButtonElement;
  expect(open).not.toBeNull();
  await act(async () => open.click());
  await flush();

  expect(host.textContent).toContain("journal_export.scope_filtered_hint");
  expect(host.textContent).toContain("journal_export.scope_all_hint");
  const previewCall = String(mocks.apiFetch.mock.calls.find((call) => String(call[0]).includes("/journal/export/preview"))?.[0]);
  expect(previewCall).toContain("scope=filtered");
  expect(previewCall).toContain("date_basis=entry");
});

it("offers a read-only chart inspection action per trade and routes it to the replay tab", async () => {
  const closedTrade = {
    id: "TRD-REPLAY", symbol: "BTCUSDT", side: "BUY", position_type: "LONG", status: "CLOSED",
    entry_price: 100, exit_price: 110, qty: 1, stop_loss: 95, take_profit: 110,
    entry_time: "2026-09-01T10:00:00.000000Z", exit_time: "2026-09-01T12:00:00.000000Z",
    pnl: 9.5, commission: 0.5, revision: 1,
  };
  const canceledTrade = { ...closedTrade, id: "TRD-CANCELED", status: "CANCELED", pnl: null, exit_price: null, exit_time: null };
  mocks.apiFetch.mockImplementation(() => Promise.resolve(response([closedTrade, canceledTrade])));
  const onOpenReplay = vi.fn();
  await act(async () => root.render(<JournalView {...props} onOpenCsvImport={vi.fn()} onOpenReplay={onOpenReplay} />));
  await flush();

  const action = host.querySelector('[data-testid="journal-replay-action"][data-trade-id="TRD-REPLAY"]') as HTMLButtonElement;
  expect(action).not.toBeNull();
  await act(async () => action.dispatchEvent(new MouseEvent("click", { bubbles: true })));
  expect(onOpenReplay).toHaveBeenCalledExactlyOnceWith("TRD-REPLAY");
  expect(host.querySelector('[data-testid="journal-replay-action"][data-trade-id="TRD-CANCELED"]')).toBeNull();
});

it("labels a simulation row and shows the local plan separately from the external status", async () => {
  const simTrade = {
    id: "TRD-SIM", symbol: "BTCUSDT", side: "BUY", position_type: "LONG", status: "OPEN",
    entry_price: 76000, exit_price: null, qty: 0.001, stop_loss: 70000, take_profit: 90000,
    entry_time: "2026-09-17T09:00:00.000000Z", exit_time: null, pnl: null, commission: 0,
    revision: 1, record_mode: "SIMULATION", price_source: "binance_public",
  };
  mocks.apiFetch.mockImplementation((path: string) => {
    if (path.includes("/local-tracking")) {
      return Promise.resolve(response([{
        trade_id: "TRD-SIM", tracking_status: "COMPLETED", remaining_qty: "0", initial_qty: "0.001",
      }]));
    }
    if (path.includes("/quotes/refresh")) {
      return Promise.resolve(response({ checked_at: new Date().toISOString(), requested: 1, identities: 1, skipped_identities: 0, quotes: {} }));
    }
    return Promise.resolve(response([simTrade]));
  });
  mocks.trades = [simTrade];
  await act(async () => root.render(<JournalView {...props} />));
  await flush();

  const badge = host.querySelector('[data-testid="journal-sim-badge-TRD-SIM"]');
  expect(badge?.textContent).toContain("journal.simulation_badge");
  const tracking = host.querySelector('[data-testid="journal-local-tracking-TRD-SIM"]');
  expect(tracking?.getAttribute("data-tracking-status")).toBe("COMPLETED");
  expect(tracking?.textContent).toContain("journal.local_status_completed");
  expect(host.querySelector('[data-testid="journal-local-completed-note-TRD-SIM"]')?.textContent)
    .toContain("journal.local_completed_external_open");
  // The external lifecycle status is never rewritten by the local estimate.
  expect(tracking?.parentElement?.textContent).toContain("OPEN");
});

it("keeps the row actions in a sticky column with keyboard focus styling", async () => {
  const openTrade = {
    id: "TRD-ACTIONS", symbol: "BTCUSDT", side: "BUY", position_type: "LONG", status: "OPEN",
    entry_price: 76000, exit_price: null, qty: 0.001, stop_loss: 70000, take_profit: 90000,
    entry_time: "2026-09-17T09:00:00.000000Z", exit_time: null, pnl: null, commission: 0,
    revision: 1,
  };
  mocks.apiFetch.mockImplementation((path: string) => {
    if (path.includes("/local-tracking")) return Promise.resolve(response([]));
    if (path.includes("/quotes/refresh")) {
      return Promise.resolve(response({ checked_at: new Date().toISOString(), requested: 1, identities: 1, skipped_identities: 0, quotes: {} }));
    }
    return Promise.resolve(response([openTrade]));
  });
  mocks.trades = [openTrade];
  await act(async () => root.render(<JournalView {...props} onEditTrade={vi.fn()} onOpenReplay={vi.fn()} />));
  await flush();

  const actionsHeader = Array.from(host.querySelectorAll("th"))
    .find((cell) => cell.textContent === "journal.col_actions");
  expect(actionsHeader?.className).toContain("sticky");
  expect(actionsHeader?.className).toContain("right-0");
  const editCell = host.querySelector('[data-testid="journal-edit-action"]')?.closest("td");
  expect(editCell?.className).toContain("sticky");
  expect(editCell?.className).toContain("right-0");
  for (const testId of ["journal-edit-action", "journal-evidence-action", "journal-replay-action", "journal-cancel-action"]) {
    const button = host.querySelector(`[data-testid="${testId}"]`) as HTMLButtonElement | null;
    expect(button).not.toBeNull();
    expect(button?.type).toBe("button");
    expect(button?.className).toContain("focus-visible:ring-accent");
  }
});

it("shows a USD position value as currency and keeps legacy quantities raw", async () => {
  const usdTrade = {
    id: "TRD-USD", symbol: "XAUUSD", side: "BUY", position_type: "LONG", status: "OPEN",
    entry_price: 4300, exit_price: null, qty: 1000, qty_unit: "USD", stop_loss: 4270,
    take_profit: 4360, entry_time: "2026-09-17T09:00:00.000000Z", exit_time: null,
    pnl: null, commission: 0, revision: 1,
  };
  const legacyTrade = { ...usdTrade, id: "TRD-LEGACY", qty: 2, qty_unit: "UNKNOWN" };
  mocks.apiFetch.mockImplementation((path: string) => {
    if (path.includes("/local-tracking")) return Promise.resolve(response([]));
    if (path.includes("/quotes/refresh")) {
      return Promise.resolve(response({ checked_at: new Date().toISOString(), requested: 2, identities: 2, skipped_identities: 0, quotes: {} }));
    }
    return Promise.resolve(response([usdTrade, legacyTrade]));
  });
  mocks.trades = [usdTrade, legacyTrade];
  await act(async () => root.render(<JournalView {...props} />));
  await flush();

  const row = (id: string) => Array.from(host.querySelectorAll("tbody tr"))
    .find((tr) => tr.textContent?.includes(id));
  expect(row("TRD-USD")?.textContent).toContain("$1,000.00");
  expect(row("TRD-LEGACY")?.textContent).toContain("2");
});
