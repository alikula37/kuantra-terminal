// @vitest-environment jsdom
import React, { act } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ apiFetch: vi.fn() }));
vi.mock("../../lib/backend", () => ({ apiUrl: (path: string) => path, apiFetch: mocks.apiFetch }));
vi.mock("../../context/I18nContext", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

import { ReconciliationInbox } from "../ReconciliationInbox";
import { createRoot } from "react-dom/client";

const response = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

const unresolved = {
  review_id: "RCN-ABC123",
  status: "UNRESOLVED",
  decision: "UNRESOLVED",
  trade_id: "TRD-1",
  source: {
    event_id: "EV-1",
    event_hash: "a".repeat(64),
    source_file_sha256: "b".repeat(64),
    source_row_number: 3,
  },
  discrepancy: { type: "CSV_ROW_REJECTED", source_row_number: 3 },
  coverage: { status: "PARTIAL", realized_pnl: "UNKNOWN", commission: "COMPLETE" },
  reconciliation: { status: "NOT_PERFORMED" },
};

let host: HTMLDivElement;
let root: ReturnType<typeof createRoot>;
const flush = async () => { await act(async () => { await Promise.resolve(); await Promise.resolve(); }); };

beforeEach(() => {
  (globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  mocks.apiFetch.mockReset();
});

afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
});

it("renders source-linked unresolved coverage and records an acknowledgement", async () => {
  mocks.apiFetch
    .mockResolvedValueOnce(response({ status: "UNRESOLVED", count: 1, items: [unresolved] }))
    .mockResolvedValueOnce(response({
      review_id: unresolved.review_id,
      status: "ACKNOWLEDGED",
      decision: "ACKNOWLEDGED",
      event_id: "EV-DECISION",
    }));

  await act(async () => root.render(<ReconciliationInbox onClose={vi.fn()} />));
  await flush();

  expect(host.querySelector("[data-testid=reconciliation-inbox]")?.textContent).toContain("CSV_ROW_REJECTED");
  expect(host.textContent).toContain("UNKNOWN");
  expect(host.textContent).toContain("NOT_PERFORMED");
  expect(host.textContent).toContain("b".repeat(10));

  const acknowledge = host.querySelector("[data-testid=reconciliation-acknowledge]") as HTMLButtonElement;
  expect(acknowledge).toBeTruthy();
  await act(async () => acknowledge.dispatchEvent(new MouseEvent("click", { bubbles: true })));
  await flush();

  expect(mocks.apiFetch).toHaveBeenLastCalledWith(
    "/api/v1/reconciliation/inbox/RCN-ABC123/decision",
    expect.objectContaining({ method: "POST" }),
  );
  expect(host.textContent).toContain("ACKNOWLEDGED");
  expect(host.querySelector("[data-testid=reconciliation-acknowledge]")).toBeNull();
});

it("does not show no-data as a successful reconciliation", async () => {
  mocks.apiFetch.mockResolvedValueOnce(response({ status: "UNRESOLVED", count: 0, items: [] }));
  await act(async () => root.render(<ReconciliationInbox onClose={vi.fn()} />));
  await flush();

  expect(host.querySelector("[data-testid=reconciliation-inbox-empty]")?.textContent).toContain("reconciliation_inbox.empty");
  expect(host.textContent).not.toContain("PASS");
  expect(host.textContent).not.toContain("COMPLETE");
});
