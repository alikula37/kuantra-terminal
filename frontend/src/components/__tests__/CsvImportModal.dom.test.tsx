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
      key === "csv_import.import_btn" ? `Import ${params?.count || 0} Trades` : key,
  }),
}));

import { CsvImportModal } from "../modals/CsvImportModal";
import { createRoot } from "react-dom/client";

const response = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

const review = {
  status: "PARTIAL",
  decision: "USER_REVIEW_REQUIRED",
  reconciliation: { status: "NOT_PERFORMED", discrepancy_count: 1 },
  coverage: { status: "PARTIAL", normalized_rows: 1, rejected_rows: 1 },
  discrepancies: [{ type: "CSV_ROW_REJECTED", source_row_number: 3 }],
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
  mocks.download.mockReset();
});

afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
});

it("shows partial import as review-required instead of a success-only state", async () => {
  mocks.apiFetch.mockResolvedValueOnce(response({
    detected_format: "GENERIC_KUANTRA",
    total_rows_parsed: 1,
    preview_trades: [{ symbol: "BTCUSDT", side: "BUY", entry_price: 100, qty: 1, pnl: 1, entry_time: "2026-09-08T10:00:00Z" }],
    import_review: review,
  }));

  await act(async () => root.render(<CsvImportModal isOpen onClose={vi.fn()} />));
  const input = host.querySelector("input[type=file]") as HTMLInputElement;
  const file = new File(["symbol,side\nBTCUSDT,BUY\n"], "partial.csv", { type: "text/csv" });
  await act(async () => {
    Object.defineProperty(input, "files", { value: [file], configurable: true });
    input.dispatchEvent(new Event("change", { bubbles: true }));
  });
  await flush();

  expect(host.querySelector("[data-testid=csv-import-preview-review]")?.textContent).toContain("USER_REVIEW_REQUIRED");

  mocks.apiFetch.mockResolvedValueOnce(response({
    success: true,
    imported: 1,
    duplicates_skipped: 0,
    errors: ["Row 3: invalid"],
    message: "stored",
    import_review: review,
  }));
  const importButton = Array.from(host.querySelectorAll("button")).find((button) => button.textContent?.includes("Import 1 Trades"));
  expect(importButton).toBeTruthy();
  await act(async () => importButton?.dispatchEvent(new MouseEvent("click", { bubbles: true })));
  await flush();

  expect(host.querySelector("[data-testid=csv-import-result-review]")?.textContent).toContain("USER_REVIEW_REQUIRED");
  expect(host.textContent).toContain("csv_import.result_review_title");
  expect(host.textContent).not.toContain("csv_import.result_success_msg");
});

it("aborts a pending preview when the modal cancel action is used", async () => {
  let resolvePreview!: (value: Response) => void;
  let requestSignal: AbortSignal | undefined;
  const pending = new Promise<Response>((resolve) => { resolvePreview = resolve; });
  const onClose = vi.fn();
  mocks.apiFetch.mockImplementation((_path: string, init?: RequestInit) => {
    requestSignal = init?.signal;
    return pending;
  });

  await act(async () => root.render(<CsvImportModal isOpen onClose={onClose} />));
  const input = host.querySelector("input[type=file]") as HTMLInputElement;
  const file = new File(["symbol,side\nBTCUSDT,BUY\n"], "pending.csv", { type: "text/csv" });
  await act(async () => {
    Object.defineProperty(input, "files", { value: [file], configurable: true });
    input.dispatchEvent(new Event("change", { bubbles: true }));
  });
  await flush();

  const cancel = host.querySelector("[data-testid=csv-import-cancel]") as HTMLButtonElement;
  expect(cancel).toBeTruthy();
  await act(async () => cancel.click());
  await flush();

  expect(requestSignal?.aborted).toBe(true);
  expect(onClose).toHaveBeenCalledTimes(1);
  resolvePreview(response({ detected_format: "GENERIC_KUANTRA", total_rows_parsed: 1, preview_trades: [] }));
  await flush();
  expect(host.textContent).not.toContain("csv_import.result_success_msg");
});

it("keeps the modal close action disabled while an import mutation is pending", async () => {
  let resolveImport!: (value: Response) => void;
  const pendingImport = new Promise<Response>((resolve) => { resolveImport = resolve; });
  const onClose = vi.fn();
  mocks.apiFetch.mockImplementation((path: string) => {
    if (path === "/api/v1/journal/preview-csv") {
      return Promise.resolve(response({
        detected_format: "GENERIC_KUANTRA",
        total_rows_parsed: 1,
        preview_trades: [{ symbol: "BTCUSDT", side: "BUY", entry_price: 100, qty: 1, pnl: 1, entry_time: "2026-09-08T10:00:00Z" }],
        import_review: { status: "READY", decision: "READY", coverage: { status: "COMPLETE" } },
      }));
    }
    if (path === "/api/v1/journal/import-csv") return pendingImport;
    return Promise.resolve(response([]));
  });

  await act(async () => root.render(<CsvImportModal isOpen onClose={onClose} />));
  const input = host.querySelector("input[type=file]") as HTMLInputElement;
  const file = new File(["symbol,side\nBTCUSDT,BUY\n"], "pending-import.csv", { type: "text/csv" });
  await act(async () => {
    Object.defineProperty(input, "files", { value: [file], configurable: true });
    input.dispatchEvent(new Event("change", { bubbles: true }));
  });
  await flush();

  const importButton = Array.from(host.querySelectorAll("button")).find((button) => button.textContent?.includes("Import 1 Trades"));
  expect(importButton).toBeTruthy();
  await act(async () => importButton?.dispatchEvent(new MouseEvent("click", { bubbles: true })));
  await flush();

  const cancel = host.querySelector("[data-testid=csv-import-cancel]") as HTMLButtonElement;
  expect(cancel.disabled).toBe(true);
  expect(onClose).not.toHaveBeenCalled();

  resolveImport(response({ success: true, imported: 1, duplicates_skipped: 0, errors: [], message: "stored" }));
  await flush();
});

it("clears the previous preview when a new file is selected", async () => {
  let resolveSecondPreview!: (value: Response) => void;
  const secondPreview = new Promise<Response>((resolve) => { resolveSecondPreview = resolve; });
  let previewCalls = 0;
  mocks.apiFetch.mockImplementation((path: string) => {
    if (path !== "/api/v1/journal/preview-csv") return Promise.resolve(response([]));
    previewCalls += 1;
    if (previewCalls === 1) {
      return Promise.resolve(response({
        detected_format: "GENERIC_KUANTRA",
        total_rows_parsed: 1,
        preview_trades: [{ symbol: "BTCUSDT", side: "BUY", entry_price: 100, qty: 1, pnl: 1, entry_time: "2026-09-08T10:00:00Z" }],
        import_review: review,
      }));
    }
    return secondPreview;
  });

  await act(async () => root.render(<CsvImportModal isOpen onClose={vi.fn()} />));
  const input = host.querySelector("input[type=file]") as HTMLInputElement;
  const first = new File(["first"], "first.csv", { type: "text/csv" });
  await act(async () => {
    Object.defineProperty(input, "files", { value: [first], configurable: true });
    input.dispatchEvent(new Event("change", { bubbles: true }));
  });
  await flush();
  expect(host.querySelector("[data-testid=csv-import-preview-review]")).not.toBeNull();

  const second = new File(["second"], "SECOND.CSV", { type: "text/csv" });
  await act(async () => {
    Object.defineProperty(input, "files", { value: [second], configurable: true });
    input.dispatchEvent(new Event("change", { bubbles: true }));
  });

  expect(host.textContent).toContain("SECOND.CSV");
  expect(host.querySelector("[data-testid=csv-import-preview-review]")).toBeNull();
  const importButton = Array.from(host.querySelectorAll("button")).find((button) => button.textContent?.includes("Import")) as HTMLButtonElement;
  expect(importButton.disabled).toBe(true);

  resolveSecondPreview(response({ detected_format: "GENERIC_KUANTRA", total_rows_parsed: 1, preview_trades: [] }));
  await flush();
});

it("makes the CSV dropzone keyboard accessible", async () => {
  await act(async () => root.render(<CsvImportModal isOpen onClose={vi.fn()} />));
  const dropzone = host.querySelector('[role="button"]') as HTMLDivElement;
  expect(dropzone).toBeTruthy();
  expect(dropzone.tabIndex).toBe(0);
  expect(dropzone.getAttribute("aria-label")).toBe("csv_import.select_file");
});

it("rejects a malformed successful preview response", async () => {
  mocks.apiFetch.mockResolvedValue(response({
    detected_format: "GENERIC_KUANTRA",
    total_rows_parsed: 1,
    preview_trades: [{}],
  }));

  await act(async () => root.render(<CsvImportModal isOpen onClose={vi.fn()} />));
  const input = host.querySelector("input[type=file]") as HTMLInputElement;
  const file = new File(["invalid"], "invalid.csv", { type: "text/csv" });
  await act(async () => {
    Object.defineProperty(input, "files", { value: [file], configurable: true });
    input.dispatchEvent(new Event("change", { bubbles: true }));
  });
  await flush();

  expect(host.querySelector('[role="alert"]')?.textContent).toContain("csv_import.error_malformed_preview");
  expect(host.textContent).not.toContain("csv_import.preview_title");
});

it("rejects a malformed successful import response instead of rendering a result", async () => {
  mocks.apiFetch.mockImplementation((path: string) => {
    if (path === "/api/v1/journal/preview-csv") {
      return Promise.resolve(response({
        detected_format: "GENERIC_KUANTRA",
        total_rows_parsed: 1,
        preview_trades: [{ symbol: "BTCUSDT", side: "BUY", entry_price: 100, qty: 1, pnl: null, entry_time: "2026-09-08T10:00:00Z" }],
      }));
    }
    return Promise.resolve(response({ success: true, imported: 1, duplicates_skipped: 0, errors: [] }));
  });

  await act(async () => root.render(<CsvImportModal isOpen onClose={vi.fn()} />));
  const input = host.querySelector("input[type=file]") as HTMLInputElement;
  const file = new File(["valid"], "valid.csv", { type: "text/csv" });
  await act(async () => {
    Object.defineProperty(input, "files", { value: [file], configurable: true });
    input.dispatchEvent(new Event("change", { bubbles: true }));
  });
  await flush();

  const importButton = Array.from(host.querySelectorAll("button")).find((button) => button.textContent?.includes("Import 1 Trades")) as HTMLButtonElement;
  expect(importButton).toBeTruthy();
  await act(async () => importButton.click());
  await flush();

  expect(host.querySelector('[role="alert"]')?.textContent).toContain("csv_import.error_malformed_result");
  expect(host.textContent).not.toContain("csv_import.result_title");
});
