// @vitest-environment jsdom
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  fetch: vi.fn(),
  download: vi.fn(),
  t: vi.fn((key: string, params?: Record<string, unknown>) =>
    params ? `${key}|${JSON.stringify(params)}` : key),
}));

vi.mock("../../lib/backend", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../lib/backend")>()),
  apiFetch: (...args: unknown[]) => mocks.fetch(...args),
}));
vi.mock("../../lib/desktop", () => ({
  downloadFromBackendDetailed: (...args: unknown[]) => mocks.download(...args),
}));
vi.mock("../../context/I18nContext", () => ({
  useTranslation: () => ({ t: mocks.t, locale: "tr", setLocale: vi.fn() }),
}));

import { JournalExportModal } from "../modals/JournalExportModal";

const preview = {
  record_count: 5,
  counts: { total: 5, open: 1, closed: 3, canceled: 1 },
  warnings: ["unknown_pnl:1", "local_estimates:2", "unverified_currency:2", "canceled_records:1"],
  exceeds_limit: false,
  max_records: 2000,
  money_totals_available: true,
  unknown_pnl_closed: 1,
  unverified_currency_records: 1,
  estimated_trades: 2,
  realized_total_by_quote: { USDT: { user_reported_net: 12.5, source_declared: 0, count: 3 } },
  snapshot_sha256: "ab".repeat(32),
};

let host: HTMLDivElement;
let root: ReturnType<typeof createRoot>;

beforeEach(() => {
  (globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
  mocks.fetch.mockReset().mockResolvedValue({ ok: true, json: async () => preview });
  mocks.download.mockReset().mockResolvedValue({ saved: true, status: 200 });
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
});

afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
});

const render = async (filters = { symbols: ["BTCUSDT"], statuses: ["CLOSED"], dateFrom: "2026-08-01", dateTo: "2026-08-31" }) => {
  await act(async () => root.render(
    <JournalExportModal onClose={() => {}} filters={filters} />
  ));
  await act(async () => { await Promise.resolve(); await Promise.resolve(); });
};

it("labels the filtered scope as all matching records, not the loaded page", async () => {
  await render();
  const text = host.textContent || "";
  expect(text).toContain("journal_export.scope_filtered_hint");
  expect(text).toContain("journal_export.scope_all_hint");
  expect(text).toContain("journal_export.date_basis_entry");
  expect(text).toContain("journal_export.date_basis_close");
});

it("previews the exact snapshot with counts and data-quality warnings", async () => {
  await render();
  const text = host.textContent || "";
  expect(text).toContain("journal_export.preview_counts");
  const warnings = Array.from(host.querySelectorAll("[data-warning]")).map((el) => el.getAttribute("data-warning"));
  expect(warnings).toEqual(expect.arrayContaining(["unknown_pnl:1", "local_estimates:2", "unverified_currency:2"]));
  expect(text).toContain("journal_export.warn_unknown_pnl");
  expect(text).toContain("journal_export.warn_local_estimates");
  expect(text).toContain("journal_export.warn_unverified_currency");
  expect((host.querySelector('[data-testid="journal-export-submit"]') as HTMLButtonElement).disabled).toBe(false);
  const called = String(mocks.fetch.mock.calls[0][0]);
  expect(called).toContain("/api/v1/journal/export/preview");
  expect(called).toContain("scope=filtered");
});

it("disables export and explains the limit instead of truncating", async () => {
  mocks.fetch.mockResolvedValue({
    ok: true,
    json: async () => ({ ...preview, record_count: 2500, exceeds_limit: true, counts: { total: 2500, open: 0, closed: 2500, canceled: 0 } }),
  });
  await render();
  expect((host.querySelector('[data-testid="journal-export-submit"]') as HTMLButtonElement).disabled).toBe(true);
  expect(host.textContent).toContain("journal_export.limit_exceeded");
});

it("month preset fills both date bounds", async () => {
  await render();
  const month = host.querySelector('[data-testid="journal-export-month"]') as HTMLInputElement;
  mocks.fetch.mockClear();
  await act(async () => {
    month.value = "2026-08";
    month.dispatchEvent(new Event("input", { bubbles: true }));
    month.dispatchEvent(new Event("change", { bubbles: true }));
  });
  const from = host.querySelector('[data-testid="journal-export-date-from"]') as HTMLInputElement;
  const to = host.querySelector('[data-testid="journal-export-date-to"]') as HTMLInputElement;
  expect(from.value).toBe("2026-08-01");
  expect(to.value).toBe("2026-08-31");
});

it("switching to all records drops the filters from the export query", async () => {
  await render();
  const allScope = host.querySelector('[data-testid="journal-export-scope-all"]') as HTMLInputElement;
  await act(async () => { allScope.click(); });
  await act(async () => { await Promise.resolve(); });
  const called = String(mocks.fetch.mock.calls.at(-1)?.[0]);
  expect(called).toContain("scope=all");
  expect(called).not.toContain("symbols=");
  await act(async () => {
    (host.querySelector('[data-testid="journal-export-submit"]') as HTMLButtonElement).click();
  });
  const downloadQuery = String(mocks.download.mock.calls[0][2]);
  expect(downloadQuery).toContain("scope=all");
  expect(downloadQuery).toContain("format=csv");
  expect(downloadQuery).toContain("lang=tr");
  expect(downloadQuery).toContain("date_basis=entry");
});

it("reports a successful save", async () => {
  await render();
  await act(async () => {
    (host.querySelector('[data-testid="journal-export-submit"]') as HTMLButtonElement).click();
  });
  expect(host.textContent).toContain("journal_export.saved");
});

it("reports a cancelled save honestly and never as success", async () => {
  mocks.download.mockResolvedValue({ saved: false, status: 200 });
  await render();
  await act(async () => {
    (host.querySelector('[data-testid="journal-export-submit"]') as HTMLButtonElement).click();
  });
  expect(host.textContent).toContain("journal_export.cancelled");
  expect(host.textContent).not.toContain("journal_export.saved");
});

it("maps a 413 export failure to the limit message", async () => {
  mocks.download.mockResolvedValue({ saved: false, status: 413 });
  await render();
  await act(async () => {
    (host.querySelector('[data-testid="journal-export-submit"]') as HTMLButtonElement).click();
  });
  expect(host.textContent).toContain("journal_export.limit_exceeded");
  expect(host.textContent).not.toContain("journal_export.saved");
});

it("maps other failures to a generic export error", async () => {
  mocks.download.mockResolvedValue({ saved: false, status: 500 });
  await render();
  await act(async () => {
    (host.querySelector('[data-testid="journal-export-submit"]') as HTMLButtonElement).click();
  });
  expect(host.textContent).toContain("journal_export.failed");
  expect(host.textContent).not.toContain("journal_export.saved");
});

it("shows an honest preview error and keeps export disabled", async () => {
  mocks.fetch.mockRejectedValue(new Error("offline"));
  await render();
  expect(host.textContent).toContain("journal_export.preview_failed");
  expect((host.querySelector('[data-testid="journal-export-submit"]') as HTMLButtonElement).disabled).toBe(true);
  expect(host.textContent).not.toContain("journal_export.saved");
});
