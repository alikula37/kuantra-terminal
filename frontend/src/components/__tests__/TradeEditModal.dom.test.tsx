// @vitest-environment jsdom
import React, { act } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  apiFetch: vi.fn(),
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

import { TradeEditModal } from "../TradeEditModal";
import { istanbulInputToUtcIso } from "../../lib/tradeTime";

const response = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

const openTrade = {
  id: "T1",
  symbol: "BTCUSDT",
  side: "BUY",
  position_type: "LONG",
  entry_price: 100,
  qty: 2,
  entry_time: "2026-09-13T21:00:00Z",
  status: "OPEN",
  revision: 1,
  leverage: null,
  stop_loss: null,
  take_profit: null,
  notes: "",
  price_source: "binance_public",
  price_source_symbol: "BTCUSDT",
  tracking_started_at: "2026-09-13T21:05:00Z",
};

const planWithClosure = {
  version: 1,
  basis: "LOCAL_ESTIMATE",
  trade_id: "T1",
  symbol: "BTCUSDT",
  side: "BUY",
  entry_price: "100",
  initial_qty: "2",
  remaining_qty: "1",
  gross_pnl: "10",
  targets: [{ id: "TP1", price: "110", percent: "100" }],
  closures: [{
    target_id: "TP1", qty: "1", price: "110", target_price: 110, gross_pnl: "10",
    observed_at: "2026-09-14T06:00:00Z", plan_revision: 1, basis: "LOCAL_ESTIMATE",
  }],
  stop_loss: "95",
  enabled: true,
  source_id: "binance_public",
  source_symbol: "BTCUSDT",
  armed_at: "2026-09-13T21:05:00Z",
  revision: 2,
};

let host: HTMLDivElement;
let root: ReturnType<typeof import("react-dom/client").createRoot>;

const flush = async () => {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
  });
};

const setInputValue = (input: HTMLInputElement | HTMLTextAreaElement, value: string) => {
  const prototype = input.tagName === "TEXTAREA" ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
  const setter = Object.getOwnPropertyDescriptor(prototype, "value")?.set;
  setter?.call(input, value);
  input.dispatchEvent(new Event("input", { bubbles: true }));
  input.dispatchEvent(new Event("change", { bubbles: true }));
};

const respond = (trade: Record<string, unknown>, options: {
  patchStatus?: number;
  plan?: unknown;
} = {}) => {
  const captured: { patch?: any } = {};
  mocks.apiFetch.mockImplementation((path: string, init?: RequestInit) => {
    if (path.endsWith("/tracking")) return Promise.resolve(response({ plan: options.plan ?? null, history: [] }));
    if (path.endsWith("/revisions")) return Promise.resolve(response({ trade_id: "T1", current_revision: 1, revisions: [] }));
    if (path.endsWith("/quotes/refresh")) {
      return Promise.resolve(response({
        checked_at: "2026-09-14T10:00:00Z", requested: 1, identities: 1, skipped_identities: 0,
        quotes: { T1: { quote_status: "LIVE", price: 65000, price_kind: "LAST", source_id: "binance_public", source_symbol: "BTCUSDT", observed_at: "2026-09-14T09:59:59Z", checked_at: "2026-09-14T10:00:00Z", age_seconds: 1, reason: null, last_known: null } },
      }));
    }
    if (init?.method === "PATCH") {
      captured.patch = JSON.parse(String(init.body));
      if (options.patchStatus && options.patchStatus >= 400) {
        return Promise.resolve(response({ detail: { reason: "REVISION_CONFLICT", message: "stale" } }, options.patchStatus));
      }
      return Promise.resolve(response({ trade: { ...trade, ...captured.patch, revision: (trade.revision as number) + 1 }, changed_fields: {}, revision: (trade.revision as number) + 1 }));
    }
    return Promise.resolve(response(trade));
  });
  return captured;
};

const openPlan = {
  version: 1,
  basis: "LOCAL_ESTIMATE",
  trade_id: "T1",
  symbol: "BTCUSDT",
  side: "BUY",
  entry_price: "100",
  initial_qty: "2",
  remaining_qty: "2",
  gross_pnl: "0",
  targets: [{ id: "TP1", price: "110", percent: "100" }],
  closures: [],
  stop_loss: "95",
  enabled: true,
  source_id: "binance_public",
  source_symbol: "BTCUSDT",
  armed_at: "2026-09-13T21:05:00Z",
  revision: 1,
};

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

it("loads the trade and saves changed fields with the expected revision", async () => {
  const trade = { ...openTrade };
  const captured = respond(trade);
  await act(async () => root.render(<TradeEditModal tradeId="T1" onClose={vi.fn()} />));
  await flush();

  expect((host.querySelector("[data-testid=trade-edit-entry]") as HTMLInputElement).value).toBe("100");
  expect((host.querySelector("[data-testid=trade-edit-entry-time]") as HTMLInputElement).value).toBe("2026-09-14T00:00");

  await act(async () => setInputValue(host.querySelector("[data-testid=trade-edit-entry]") as HTMLInputElement, "105"));
  await act(async () => setInputValue(host.querySelector("[data-testid=trade-edit-qty]") as HTMLInputElement, "3"));
  await act(async () => setInputValue(host.querySelector("[data-testid=trade-edit-entry-time]") as HTMLInputElement, "2026-01-16T10:00"));
  await act(async () => (host.querySelector("[data-testid=trade-edit-save]") as HTMLButtonElement).click());
  await flush();

  expect(captured.patch).toMatchObject({
    expected_revision: 1,
    entry_price: 105,
    qty: 3,
    entry_time: "2026-01-16T07:00:00.000Z",
  });
});

it("shows a reload action when the revision is stale", async () => {
  respond({ ...openTrade }, { patchStatus: 409 });
  await act(async () => root.render(<TradeEditModal tradeId="T1" onClose={vi.fn()} />));
  await flush();
  await act(async () => setInputValue(host.querySelector("[data-testid=trade-edit-entry]") as HTMLInputElement, "105"));
  await act(async () => (host.querySelector("[data-testid=trade-edit-save]") as HTMLButtonElement).click());
  await flush();

  expect(host.querySelector("[data-testid=trade-edit-error]")?.textContent).toContain("journal_edit.reason_revision_conflict");
  expect(host.querySelector("[data-testid=trade-edit-reload]")).not.toBeNull();
});

it("locks entry price and quantity after a partial close", async () => {
  respond({ ...openTrade }, { plan: planWithClosure });
  await act(async () => root.render(<TradeEditModal tradeId="T1" onClose={vi.fn()} />));
  await flush();

  expect((host.querySelector("[data-testid=trade-edit-entry]") as HTMLInputElement).disabled).toBe(true);
  expect((host.querySelector("[data-testid=trade-edit-qty]") as HTMLInputElement).disabled).toBe(true);
  expect(host.textContent).toContain("journal_edit.reason_partial_close_locked");
  expect(host.textContent).toContain("journal_edit.tracking_started");
});

it("sends only a note correction for a completed trade", async () => {
  const closed = {
    ...openTrade,
    status: "CLOSED",
    exit_price: 110,
    exit_time: "2026-09-14T06:00:00Z",
    close_source: "USER_REPORTED",
    revision: 2,
  };
  const captured = respond(closed);
  await act(async () => root.render(<TradeEditModal tradeId="T1" onClose={vi.fn()} />));
  await flush();

  expect((host.querySelector("[data-testid=trade-edit-qty]") as HTMLInputElement).disabled).toBe(true);
  await act(async () => {
    const notes = host.querySelector("textarea") as HTMLTextAreaElement;
    const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")?.set;
    setter?.call(notes, "note correction");
    notes.dispatchEvent(new Event("input", { bubbles: true }));
  });
  await act(async () => (host.querySelector("[data-testid=trade-edit-save]") as HTMLButtonElement).click());
  await flush();

  expect(captured.patch).toEqual({ notes: "note correction", expected_revision: 2 });
});

it("refresh price shows the exact provider quote and no liquidity claim", async () => {
  respond({ ...openTrade });
  await act(async () => root.render(<TradeEditModal tradeId="T1" onClose={vi.fn()} />));
  await flush();
  await act(async () => (host.querySelector("[data-testid=trade-edit-refresh-price]") as HTMLButtonElement).click());
  await flush();

  expect(host.textContent).toContain("65000");
  expect(host.textContent).toContain("LIVE");
  expect(host.textContent).toContain("journal_edit.quote_identity_notice");
});

it("edits the local plan from the trade editor with the plan revision", async () => {
  const captured = respond({ ...openTrade }, { plan: openPlan });
  await act(async () => root.render(<TradeEditModal tradeId="T1" onClose={vi.fn()} />));
  await flush();

  // The legacy single stop/target fields are replaced by the plan editor.
  expect(host.querySelector("[data-testid=trade-edit-stop]")).toBeNull();
  expect(host.querySelector("[data-testid=trade-edit-plan]")).not.toBeNull();
  await act(async () => setInputValue(host.querySelector("[data-testid=trade-edit-plan-stop]") as HTMLInputElement, "92"));
  await act(async () => (host.querySelector("[data-testid=trade-edit-save]") as HTMLButtonElement).click());
  await flush();

  expect(captured.patch.local_tracking).toMatchObject({
    expected_revision: 1,
    stop_loss: 92,
    targets: [{ price: 110, percent: 100 }],
  });
  expect(captured.patch.stop_loss).toBeUndefined();
});

it("keeps a completed plan target locked while editing the stop", async () => {
  const captured = respond({ ...openTrade }, { plan: planWithClosure });
  await act(async () => root.render(<TradeEditModal tradeId="T1" onClose={vi.fn()} />));
  await flush();

  expect((host.querySelector('[aria-label="tracking.price:1"]') as HTMLInputElement).disabled).toBe(true);
  await act(async () => setInputValue(host.querySelector("[data-testid=trade-edit-plan-stop]") as HTMLInputElement, "92"));
  await act(async () => (host.querySelector("[data-testid=trade-edit-save]") as HTMLButtonElement).click());
  await flush();

  expect(captured.patch.local_tracking).toMatchObject({
    expected_revision: 2,
    stop_loss: 92,
    targets: [{ price: 110, percent: 100 }],
  });
  expect(captured.patch.entry_price).toBeUndefined();
  expect(captured.patch.qty).toBeUndefined();
});

it("saves a plan-only target change with its plan revision", async () => {
  const captured = respond({ ...openTrade }, { plan: openPlan });
  await act(async () => root.render(<TradeEditModal tradeId="T1" onClose={vi.fn()} />));
  await flush();

  await act(async () => setInputValue(
    host.querySelector('[aria-label="tracking.price:1"]') as HTMLInputElement,
    "118",
  ));
  await act(async () => (host.querySelector("[data-testid=trade-edit-save]") as HTMLButtonElement).click());
  await flush();

  expect(captured.patch.local_tracking).toMatchObject({
    expected_revision: 1,
    stop_loss: 95,
    targets: [{ price: 118, percent: 100 }],
  });
  expect(captured.patch.take_profit).toBeUndefined();
  expect(captured.patch.stop_loss).toBeUndefined();
});

it("restores a canceled trade to open from the status control", async () => {
  const canceledTrade = { ...openTrade, status: "CANCELED", revision: 2 };
  const captured = respond(canceledTrade);
  await act(async () => root.render(<TradeEditModal tradeId="T1" onClose={vi.fn()} />));
  await flush();

  expect((host.querySelector("[data-testid=trade-edit-status-canceled]") as HTMLButtonElement).getAttribute("aria-pressed")).toBe("true");
  await act(async () => (host.querySelector("[data-testid=trade-edit-status-open]") as HTMLButtonElement).click());
  await act(async () => (host.querySelector("[data-testid=trade-edit-save]") as HTMLButtonElement).click());
  await flush();

  expect(captured.patch).toMatchObject({ status: "OPEN", expected_revision: 2 });
});

it("requires user-reported exit data when closing from the editor", async () => {
  const captured = respond({ ...openTrade });
  await act(async () => root.render(<TradeEditModal tradeId="T1" onClose={vi.fn()} />));
  await flush();

  await act(async () => (host.querySelector("[data-testid=trade-edit-status-closed]") as HTMLButtonElement).click());
  expect(host.querySelector("[data-testid=trade-edit-exit-price]")).not.toBeNull();
  await act(async () => (host.querySelector("[data-testid=trade-edit-save]") as HTMLButtonElement).click());
  await flush();
  expect(host.querySelector("[data-testid=trade-edit-error]")?.textContent).toContain("journal_edit.reason_exit_required");
  expect(captured.patch).toBeUndefined();

  await act(async () => setInputValue(host.querySelector("[data-testid=trade-edit-exit-price]") as HTMLInputElement, "110"));
  await act(async () => setInputValue(host.querySelector("[data-testid=trade-edit-exit-time]") as HTMLInputElement, "2026-01-16T10:00"));
  await act(async () => (host.querySelector("[data-testid=trade-edit-save]") as HTMLButtonElement).click());
  await flush();

  expect(captured.patch).toMatchObject({ status: "CLOSED", exit_price: 110 });
  expect(captured.patch.exit_time).toBe("2026-01-16T07:00:00.000Z");
});

it("unlocks a completed trade when the editor selects Open", async () => {
  const closedTrade = {
    ...openTrade,
    status: "CLOSED",
    exit_price: 110,
    exit_time: "2026-09-14T06:00:00Z",
    revision: 3,
  };
  respond(closedTrade);
  await act(async () => root.render(<TradeEditModal tradeId="T1" onClose={vi.fn()} />));
  await flush();

  expect(host.querySelector("[data-testid=trade-edit-completed-notice]")).not.toBeNull();
  expect((host.querySelector("[data-testid=trade-edit-qty]") as HTMLInputElement).disabled).toBe(true);
  await act(async () => (host.querySelector("[data-testid=trade-edit-status-open]") as HTMLButtonElement).click());
  expect(host.querySelector("[data-testid=trade-edit-reopen-notice]")).not.toBeNull();
  expect((host.querySelector("[data-testid=trade-edit-qty]") as HTMLInputElement).disabled).toBe(false);
});

it("lets a completed trade declare its unit and correct the exit", async () => {
  const closedTrade = {
    ...openTrade,
    status: "CLOSED",
    exit_price: 110,
    exit_time: "2026-09-14T06:00:00Z",
    qty_unit: "UNKNOWN",
    revision: 3,
  };
  const captured = respond(closedTrade);
  await act(async () => root.render(<TradeEditModal tradeId="T1" onClose={vi.fn()} />));
  await flush();

  expect(host.querySelector("[data-testid=trade-edit-completed-notice]")).not.toBeNull();
  expect((host.querySelector("[data-testid=trade-edit-exit-price]") as HTMLInputElement).value).toBe("110");
  expect((host.querySelector("[data-testid=trade-edit-qty-unit]") as HTMLInputElement).disabled).toBe(false);
  expect((host.querySelector("[data-testid=trade-edit-qty]") as HTMLInputElement).disabled).toBe(true);

  await act(async () => (host.querySelector("[data-testid=trade-edit-qty-unit]") as HTMLInputElement).click());
  await act(async () => setInputValue(host.querySelector("[data-testid=trade-edit-exit-price]") as HTMLInputElement, "112"));
  await act(async () => (host.querySelector("[data-testid=trade-edit-save]") as HTMLButtonElement).click());
  await flush();

  expect(captured.patch).toMatchObject({ qty_unit: "BASE", exit_price: 112, expected_revision: 3 });
  expect(captured.patch.status).toBeUndefined();
  expect(captured.patch.qty).toBeUndefined();
});

it("keeps the stored entry seconds when an unrelated field is saved", async () => {
  const trade = { ...openTrade, entry_time: "2026-09-13T21:00:15Z" };
  const captured = respond(trade);
  await act(async () => root.render(<TradeEditModal tradeId="T1" onClose={vi.fn()} />));
  await flush();

  const notes = host.querySelector("textarea") as HTMLTextAreaElement;
  setInputValue(notes, "sadece not");
  await act(async () => (host.querySelector('[data-testid="trade-edit-save"]') as HTMLButtonElement).click());
  await flush();

  expect(captured.patch.notes).toBe("sadece not");
  expect(captured.patch.entry_time).toBeUndefined();
});

it("sends an explicitly changed entry time at minute precision", async () => {
  const trade = { ...openTrade, entry_time: "2026-09-13T21:00:15Z" };
  const captured = respond(trade);
  await act(async () => root.render(<TradeEditModal tradeId="T1" onClose={vi.fn()} />));
  await flush();

  const entryTime = host.querySelector('[data-testid="trade-edit-entry-time"]') as HTMLInputElement;
  setInputValue(entryTime, "2026-09-14T00:30");
  await act(async () => (host.querySelector('[data-testid="trade-edit-save"]') as HTMLButtonElement).click());
  await flush();

  expect(captured.patch.entry_time).toBe(istanbulInputToUtcIso("2026-09-14T00:30"));
});

it("rejects a cleared entry time instead of silently skipping the save", async () => {
  const trade = { ...openTrade, entry_time: "2026-09-13T21:00:15Z" };
  const captured = respond(trade);
  await act(async () => root.render(<TradeEditModal tradeId="T1" onClose={vi.fn()} />));
  await flush();

  const entryTime = host.querySelector('[data-testid="trade-edit-entry-time"]') as HTMLInputElement;
  setInputValue(entryTime, "");
  const notes = host.querySelector("textarea") as HTMLTextAreaElement;
  setInputValue(notes, "saat yok");
  await act(async () => (host.querySelector('[data-testid="trade-edit-save"]') as HTMLButtonElement).click());
  await flush();

  expect((host.querySelector('[data-testid="trade-edit-error"]') as HTMLElement).textContent).toContain("journal_edit.reason_time_invalid");
  expect(captured.patch).toBeUndefined();
});

it("allows fixing the entry time after a partial close while price and quantity stay locked", async () => {
  respond({ ...openTrade }, { plan: planWithClosure });
  await act(async () => root.render(<TradeEditModal tradeId="T1" onClose={vi.fn()} />));
  await flush();

  expect((host.querySelector('[data-testid="trade-edit-entry"]') as HTMLInputElement).disabled).toBe(true);
  expect((host.querySelector('[data-testid="trade-edit-qty"]') as HTMLInputElement).disabled).toBe(true);
  expect((host.querySelector('[data-testid="trade-edit-entry-time"]') as HTMLInputElement).disabled).toBe(false);
});
