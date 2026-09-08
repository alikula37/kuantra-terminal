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

