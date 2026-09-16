// @vitest-environment jsdom
import React, { act } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ apiFetch: vi.fn(), fetchEvidencePack: vi.fn(), download: vi.fn() }));
vi.mock("../../lib/backend", () => ({ apiUrl: (path: string) => path, apiFetch: mocks.apiFetch, fetchEvidencePack: mocks.fetchEvidencePack }));
vi.mock("../../lib/desktop", () => ({ downloadFromBackendDetailed: mocks.download }));

import { TradeEvidencePanel } from "../TradeEvidencePanel";
import { I18nProvider } from "../../context/I18nContext";
import { createRoot } from "react-dom/client";

const response = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const mockPanelResponse = (body: unknown, status = 200) => {
  mocks.apiFetch.mockImplementation((path: string) => Promise.resolve(
    path === "/api/v1/settings" ? response({ locale: "en" }) : response(body, status),
  ));
};

const basePack = {
  trade_id: "TRD-1",
  trade: null,
  read_source: "typed_projection",
  coverage: { ready: true },
  ledger_integrity: { valid: true, checked_events: 2, errors: [] },
  event_count: 2,
  events: [
    {
      event_id: "EV-1", event_type: "RiskEvaluated", account_id: "local-risk", venue: "local-risk",
      occurred_at_utc: "2026-09-06T10:00:00Z", chain_date_utc: "2026-09-06", chain_sequence: 1,
      schema_version: "1", adapter_version: "risk-evaluation-v1", correlation_id: "TRD-1",
      idempotency_key: "risk-1", raw_payload_sha256: "a", prev_hash: "0", event_hash: "b",
      normalized_payload: { decision_kind: "PRE_EXECUTION_RISK", decision: { policy_id: "default-risk-policy", policy_version: 3, policy_snapshot_sha256: "c" } },
      provenance: { policy_id: "default-risk-policy", version: 3, snapshot_sha256: "c" },
    },
    {
      event_id: "EV-2", event_type: "JournalReviewAdded", account_id: "local-journal", venue: "local-playbook",
      occurred_at_utc: "2026-09-06T10:01:00Z", chain_date_utc: "2026-09-06", chain_sequence: 2,
      schema_version: "1", adapter_version: "playbook-audit-v1", correlation_id: "TRD-1",
      idempotency_key: "review-1", raw_payload_sha256: "d", prev_hash: "b", event_hash: "e",
      normalized_payload: { review_kind: "PLAYBOOK_AUDIT", playbook_id: "PB-1", playbook_version: 2, playbook_snapshot_sha256: "f" },
      provenance: { playbook_id: "PB-1", version: 2, snapshot_sha256: "f" },
    },
  ],
  market_context: {
    status: "READY", candles: [], provenance: { quality: "BAR_APPROXIMATION", source: "DUCKDB_CANDLES", source_verified: false, timeframe: "1m" },
  },
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
  mocks.fetchEvidencePack.mockReset();
  mocks.download.mockReset();
  mocks.fetchEvidencePack.mockImplementation((tradeId: string, init?: RequestInit) =>
    mocks.apiFetch(`/api/v1/trades/${encodeURIComponent(tradeId)}/evidence`, init),
  );
});

afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
});

it("renders policy provenance, ledger integrity, and unverified market context", async () => {
  mockPanelResponse(basePack);
  await act(async () => root.render(<I18nProvider><TradeEvidencePanel tradeId="TRD-1" onClose={vi.fn()} /></I18nProvider>));
  await flush();

  expect(host.textContent).toContain("Verified chain");
  expect(host.textContent).toContain("default-risk-policy");
  expect(host.textContent).toContain("Playbook: PB-1");
  expect(host.textContent).toContain("Source unverified / descriptive");
});

it("renders an explicit import review boundary in the Evidence Pack", async () => {
  mockPanelResponse({
    ...basePack,
    import_review: {
      status: "PARTIAL",
      decision: "USER_REVIEW_REQUIRED",
      reconciliation: { status: "NOT_PERFORMED" },
      coverage: { status: "PARTIAL" },
      source_file_sha256: "a".repeat(64),
    },
  });
  await act(async () => root.render(<I18nProvider><TradeEvidencePanel tradeId="TRD-1" onClose={vi.fn()} /></I18nProvider>));
  await flush();

  expect(host.querySelector("[data-testid=trade-evidence-import-review]")?.textContent).toContain("USER_REVIEW_REQUIRED");
  expect(host.textContent).toContain("NOT_PERFORMED");
});

it("shows a bounded error instead of implying evidence exists", async () => {
  mockPanelResponse({ detail: "trade evidence not found" }, 404);
  await act(async () => root.render(<I18nProvider><TradeEvidencePanel tradeId="MISSING" onClose={vi.fn()} /></I18nProvider>));
  await flush();

  expect(host.textContent).toContain("trade evidence not found");
  expect(host.textContent).not.toContain("Verified chain");
});

it("puts focus in the dialog and closes on Escape", async () => {
  mockPanelResponse(basePack);
  const onClose = vi.fn();
  await act(async () => root.render(<I18nProvider><TradeEvidencePanel tradeId="TRD-1" onClose={onClose} /></I18nProvider>));
  await flush();

  const close = host.querySelector("button[aria-label='Close Evidence Pack']") as HTMLButtonElement;
  expect(document.activeElement).toBe(close);
  await act(async () => document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true })));
  expect(onClose).toHaveBeenCalledTimes(1);
});

it("keeps a failed Evidence Pack request recoverable", async () => {
  let packCalls = 0;
  mocks.apiFetch.mockImplementation((path: string) => {
    if (path === "/api/v1/settings") return Promise.resolve(response({ locale: "en" }));
    packCalls += 1;
    return Promise.resolve(packCalls === 1 ? response({ detail: "temporary evidence failure" }, 503) : response(basePack));
  });
  await act(async () => root.render(<I18nProvider><TradeEvidencePanel tradeId="TRD-1" onClose={vi.fn()} /></I18nProvider>));
  await flush();

  expect(host.textContent).toContain("temporary evidence failure");
  const retry = host.querySelector("[data-testid=trade-evidence-retry]") as HTMLButtonElement;
  expect(retry).toBeTruthy();
  await act(async () => retry.click());
  await flush();
  expect(host.textContent).toContain("Verified chain");
});

it("rejects a malformed successful Evidence Pack response instead of rendering a broken panel", async () => {
  mockPanelResponse({ trade_id: "TRD-1", read_source: "typed_projection" });
  await act(async () => root.render(<I18nProvider><TradeEvidencePanel tradeId="TRD-1" onClose={vi.fn()} /></I18nProvider>));
  await flush();

  expect(host.textContent).toContain("Evidence Pack response was malformed.");
  expect(host.textContent).not.toContain("Verified chain");
});

it("lets the user cancel a pending Evidence Pack load without showing partial success", async () => {
  let resolvePack!: (value: Response) => void;
  let requestSignal: AbortSignal | undefined;
  const pending = new Promise<Response>((resolve) => { resolvePack = resolve; });
  mocks.apiFetch.mockResolvedValue(response({ locale: "en" }));
  mocks.fetchEvidencePack.mockImplementation((_tradeId: string, signal?: AbortSignal) => {
    requestSignal = signal;
    return pending;
  });

  await act(async () => root.render(<I18nProvider><TradeEvidencePanel tradeId="TRD-1" onClose={vi.fn()} /></I18nProvider>));
  await flush();

  const cancel = host.querySelector("[data-testid=trade-evidence-cancel]") as HTMLButtonElement;
  expect(cancel).toBeTruthy();
  await act(async () => cancel.click());
  await flush();

  expect(requestSignal?.aborted).toBe(true);
  expect(host.querySelector("[data-testid=trade-evidence-cancelled]")).not.toBeNull();
  expect(host.textContent).not.toContain("Verified chain");

  resolvePack(response(basePack));
  await flush();
  expect(host.textContent).not.toContain("Verified chain");
});

it("renders explicit coverage, applicable rule provenance, snapshot identity, and CSV export", async () => {
  mockPanelResponse({
    ...basePack,
    snapshot_sha256: "a".repeat(64),
    coverage_summary: {
      overall: "PARTIAL",
      fees: "UNKNOWN",
      funding_transfer: "NOT_AVAILABLE",
      market_context: "PARTIAL",
    },
    applicable_rules: [{
      kind: "risk",
      rule_id: "risk-policy",
      version: "3",
      snapshot_sha256: "b".repeat(64),
    }],
  });
  await act(async () => root.render(<I18nProvider><TradeEvidencePanel tradeId="TRD-1" onClose={vi.fn()} /></I18nProvider>));
  await flush();

  expect(host.textContent).toContain("Fee coverage");
  expect(host.textContent).toContain("UNKNOWN");
  expect(host.textContent).toContain("risk-policy");
  expect(host.textContent).toContain("a".repeat(10));
  expect(Array.from(host.querySelectorAll("button")).some((button) => button.textContent?.includes("CSV"))).toBe(true);
});

it("uses the native download bridge and reports only an actual save as ready", async () => {
  mockPanelResponse(basePack);
  mocks.download.mockResolvedValue({ saved: true, status: 200 });
  await act(async () => root.render(<I18nProvider><TradeEvidencePanel tradeId="TRD-1" onClose={vi.fn()} /></I18nProvider>));
  await flush();

  const csvButton = Array.from(host.querySelectorAll("button")).find((button) => button.textContent?.includes("CSV")) as HTMLButtonElement;
  await act(async () => csvButton.click());
  await flush();

  expect(mocks.download).toHaveBeenCalledWith(
    "/api/v1/trades/TRD-1/evidence/export",
    "kuantra-evidence-TRD-1.csv",
    "format=csv",
  );
  expect(host.textContent).toContain("CSV export ready.");
});

it("offers a direct PDF export of the evidence pack", async () => {
  mockPanelResponse(basePack);
  mocks.download.mockResolvedValue({ saved: true, status: 200 });
  await act(async () => root.render(<I18nProvider><TradeEvidencePanel tradeId="TRD-1" onClose={vi.fn()} /></I18nProvider>));
  await flush();

  const pdfButton = Array.from(host.querySelectorAll("button")).find((button) => button.textContent?.includes("PDF")) as HTMLButtonElement;
  await act(async () => pdfButton.click());
  await flush();

  expect(mocks.download).toHaveBeenCalledWith(
    "/api/v1/trades/TRD-1/evidence/export",
    "kuantra-evidence-TRD-1.pdf",
    "format=pdf",
  );
  expect(host.textContent).toContain("PDF export ready.");
});

it("reports an export limit without claiming a save", async () => {
  mockPanelResponse(basePack);
  mocks.download.mockResolvedValue({ saved: false, status: 413 });
  await act(async () => root.render(<I18nProvider><TradeEvidencePanel tradeId="TRD-1" onClose={vi.fn()} /></I18nProvider>));
  await flush();

  const pdfButton = Array.from(host.querySelectorAll("button")).find((button) => button.textContent?.includes("PDF")) as HTMLButtonElement;
  await act(async () => pdfButton.click());
  await flush();

  expect(host.textContent).toContain("Export limit exceeded; nothing was saved.");
  expect(host.textContent).not.toContain("PDF export ready.");
});

it("does not report a cancelled native export as ready", async () => {
  mockPanelResponse(basePack);
  mocks.download.mockResolvedValue({ saved: false, status: 200 });
  await act(async () => root.render(<I18nProvider><TradeEvidencePanel tradeId="TRD-1" onClose={vi.fn()} /></I18nProvider>));
  await flush();

  const jsonButton = Array.from(host.querySelectorAll("button")).find((button) => button.textContent?.includes("JSON")) as HTMLButtonElement;
  await act(async () => jsonButton.click());
  await flush();

  expect(host.textContent).toContain("Export cancelled or was not saved.");
  expect(host.textContent).not.toContain("JSON export ready.");
});
