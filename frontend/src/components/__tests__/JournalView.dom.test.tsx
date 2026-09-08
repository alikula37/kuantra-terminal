// @vitest-environment jsdom
import React, { act } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  apiFetch: vi.fn(),
  setTrades: vi.fn(),
  t: (key: string) => key,
}));
vi.mock("../../lib/backend", () => ({ apiUrl: (path: string) => path, apiFetch: mocks.apiFetch }));
vi.mock("../../context/I18nContext", () => ({
  useTranslation: () => ({ t: mocks.t }),
}));
vi.mock("../../stores/tradeStore", () => ({
  useTradeStore: () => ({ trades: [], setTrades: mocks.setTrades }),
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
