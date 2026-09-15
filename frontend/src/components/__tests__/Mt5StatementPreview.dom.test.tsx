// @vitest-environment jsdom
import React, { act } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  apiFetch: vi.fn(),
  download: vi.fn(),
}));

vi.mock("../../lib/backend", () => ({
  apiUrl: (path: string) => path,
  apiFetch: mocks.apiFetch,
}));
vi.mock("../../lib/desktop", () => ({ downloadFromBackend: mocks.download }));
vi.mock("../../context/I18nContext", () => ({
  useTranslation: () => ({
    t: (key: string, params?: Record<string, string | number>) =>
      params && "count" in params ? `${key}:${params.count}` : key,
  }),
}));
vi.mock("../../hooks/useDialogAccessibility", () => ({
  useDialogAccessibility: vi.fn(),
}));

import { CsvImportModal } from "../modals/CsvImportModal";
import { createRoot } from "react-dom/client";

const response = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

const preview = (overrides: Record<string, unknown> = {}) => ({
  preview_only: true,
  format: "MT5_HTML_REPORT",
  template: "REPORT_HISTORY_EN",
  language: "EN",
  parser_version: "mt5-html-preview/1",
  source_sha256: "a".repeat(64),
  source_size_bytes: 2048,
  account: { masked: "****4321", basis: "SOURCE_DECLARED", verified: false },
  account_currency: "USD",
  time_basis: "SOURCE_LOCAL_TIME_UNVERIFIED",
  quantity_unit: "SOURCE_LOT",
  counts: { orders: 1, deals: 2, rows_total: 3, rows_ok: 3, rows_with_errors: 1 },
  date_range: { start_source: "2026.09.01 10:00:00", end_source: "2026.09.10 11:00:00" },
  orders: [{
    source_identity: "1001",
    source_identity_kind: "SOURCE_ORDER_ID",
    open_time_source: "2026.09.01 10:00:00",
    symbol: "XAUUSD",
    type: "buy",
    volume_source: "0.10",
    volume_unit: "SOURCE_LOT",
    price_source: "2500.00",
  }],
  deals: [{
    source_identity: "5001",
    source_identity_kind: "SOURCE_DEAL_ID",
    related_order_id: "1001",
    time_source: "2026.09.01 10:00:00",
    symbol: "XAUUSD",
    volume_source: "0.10",
    volume_unit: "SOURCE_LOT",
    price_source: "2500.00",
    reported_profit_source: "100.00",
  }],
  row_errors: [{ section: "deal", source_row: 4, reason: "UNPARSED_TIME", fields: ["time"] }],
  unsupported_sections: ["Positions", "Summary"],
  warnings: ["SOURCE_TIME_BASIS_UNVERIFIED", "SOURCE_ACCOUNT_NOT_VERIFIED"],
  ...overrides,
});

let host: HTMLDivElement;
let root: ReturnType<typeof createRoot>;
const flush = async () => { await act(async () => { await Promise.resolve(); await Promise.resolve(); }); };

const selectFile = async (file: File) => {
  const input = host.querySelector("[data-testid=mt5-preview-file-input]") as HTMLInputElement;
  await act(async () => {
    Object.defineProperty(input, "files", { value: [file], configurable: true });
    input.dispatchEvent(new Event("change", { bubbles: true }));
  });
};

const openMt5Tab = async () => {
  await act(async () => root.render(<CsvImportModal isOpen onClose={vi.fn()} />));
  const tab = host.querySelector("[data-testid=mt5-preview-tab]") as HTMLButtonElement;
  await act(async () => tab.dispatchEvent(new MouseEvent("click", { bubbles: true })));
};

beforeEach(() => {
  (globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  mocks.apiFetch.mockReset();
  mocks.download.mockReset();
});

afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
});

it("shows the preview-only notice and no import action in MT5 mode", async () => {
  await openMt5Tab();

  expect(host.querySelector("[data-testid=mt5-preview-only-notice]")?.textContent).toContain("mt5_preview.preview_only_notice");
  expect(host.querySelector("[data-testid=mt5-preview-close]")).not.toBeNull();
  expect(host.textContent).not.toContain("csv_import.import_btn");
  expect(host.textContent).not.toContain("csv_import.download_template");
});

it("previews a supported report with counts, masked account and reported-result labels", async () => {
  mocks.apiFetch.mockResolvedValueOnce(response(preview()));
  await openMt5Tab();
  await selectFile(new File(["<html></html>"], "xm-report.html", { type: "text/html" }));
  await flush();

  expect(mocks.apiFetch).toHaveBeenCalledWith("/api/v1/broker/statement/preview-html", expect.objectContaining({ method: "POST" }));
  expect(host.querySelector("[data-testid=mt5-preview-account]")?.textContent).toContain("****4321");
  expect(host.querySelector("[data-testid=mt5-preview-account]")?.textContent).toContain("mt5_preview.account_basis");
  expect(host.querySelector("[data-testid=mt5-preview-counts]")?.textContent).toContain("mt5_preview.counts_deals");
  expect(host.querySelector("[data-testid=mt5-preview-orders]")?.textContent).toContain("1001");
  expect(host.querySelector("[data-testid=mt5-preview-deals]")?.textContent).toContain("5001");
  expect(host.querySelector("[data-testid=mt5-preview-deals]")?.textContent).toContain("mt5_preview.reported_profit_label");
  expect(host.querySelector("[data-testid=mt5-preview-time-basis]")?.textContent).toContain("mt5_preview.time_basis_warning");
  expect(host.querySelector("[data-testid=mt5-preview-errors]")?.textContent).toContain("UNPARSED_TIME");
  expect(host.querySelector("[data-testid=mt5-preview-unsupported]")?.textContent).toContain("Positions");
});

it("rejects a non-html file before calling the API", async () => {
  await openMt5Tab();
  await selectFile(new File(["a,b"], "statement.csv", { type: "text/csv" }));
  await flush();

  expect(mocks.apiFetch).not.toHaveBeenCalled();
  expect(host.querySelector("[data-testid=mt5-preview-error]")?.textContent).toContain("mt5_preview.error_invalid_format");
});

it("keeps a late response from overwriting the newer file preview", async () => {
  let resolveFirst!: (value: Response) => void;
  let resolveSecond!: (value: Response) => void;
  const first = new Promise<Response>((resolve) => { resolveFirst = resolve; });
  const second = new Promise<Response>((resolve) => { resolveSecond = resolve; });
  mocks.apiFetch.mockReturnValueOnce(first).mockReturnValueOnce(second);

  await openMt5Tab();
  await selectFile(new File(["<html>one</html>"], "first.html", { type: "text/html" }));
  await selectFile(new File(["<html>two</html>"], "second.html", { type: "text/html" }));

  await act(async () => {
    resolveSecond(response(preview({ account: { masked: "****2222", basis: "SOURCE_DECLARED", verified: false } })));
  });
  await flush();
  expect(host.querySelector("[data-testid=mt5-preview-account]")?.textContent).toContain("****2222");

  await act(async () => {
    resolveFirst(response(preview({ account: { masked: "****1111", basis: "SOURCE_DECLARED", verified: false } })));
  });
  await flush();
  expect(host.querySelector("[data-testid=mt5-preview-account]")?.textContent).toContain("****2222");
  expect(host.querySelector("[data-testid=mt5-preview-account]")?.textContent).not.toContain("****1111");
});

it("clears the previous preview when a new file is selected", async () => {
  let resolveSecond!: (value: Response) => void;
  mocks.apiFetch.mockResolvedValueOnce(response(preview()));
  await openMt5Tab();
  await selectFile(new File(["<html>one</html>"], "first.html", { type: "text/html" }));
  await flush();
  expect(host.querySelector("[data-testid=mt5-preview-account]")?.textContent).toContain("****4321");

  mocks.apiFetch.mockReturnValueOnce(new Promise<Response>((resolve) => { resolveSecond = resolve; }));
  await selectFile(new File(["<html>two</html>"], "second.html", { type: "text/html" }));
  expect(host.querySelector("[data-testid=mt5-preview-account]")).toBeNull();

  await act(async () => { resolveSecond(response(preview())); });
  await flush();
  expect(host.querySelector("[data-testid=mt5-preview-account]")).not.toBeNull();
});

it("shows a safe error and still allows another file selection", async () => {
  mocks.apiFetch.mockResolvedValueOnce(response({ detail: { code: "UNSUPPORTED_TEMPLATE", message: "safe" } }, 400));
  await openMt5Tab();
  await selectFile(new File(["<html></html>"], "broken.html", { type: "text/html" }));
  await flush();
  expect(host.querySelector("[data-testid=mt5-preview-error]")).not.toBeNull();

  mocks.apiFetch.mockResolvedValueOnce(response(preview()));
  await selectFile(new File(["<html></html>"], "again.html", { type: "text/html" }));
  await flush();
  expect(host.querySelector("[data-testid=mt5-preview-error]")).toBeNull();
  expect(host.querySelector("[data-testid=mt5-preview-account]")).not.toBeNull();
});

it("renders injected markup from the report as plain text", async () => {
  mocks.apiFetch.mockResolvedValueOnce(response(preview({
    orders: [{
      source_identity: "1001",
      source_identity_kind: "SOURCE_ORDER_ID",
      open_time_source: "2026.09.01 10:00:00",
      symbol: '<img src=x onerror="window.__pwned=1">',
      type: "buy",
      volume_source: "0.10",
      volume_unit: "SOURCE_LOT",
      price_source: "2500.00",
    }],
  })));
  await openMt5Tab();
  await selectFile(new File(["<html></html>"], "injected.html", { type: "text/html" }));
  await flush();

  expect(host.querySelector("img")).toBeNull();
  expect(host.textContent).toContain("<img src=x");
  expect((globalThis as any).__pwned).toBeUndefined();
});
