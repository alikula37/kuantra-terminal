// @vitest-environment jsdom
import React, { act } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ apiFetch: vi.fn() }));
vi.mock("../../lib/backend", () => ({ apiUrl: (path: string) => path, apiFetch: mocks.apiFetch }));

import { TradeEvidencePanel } from "../TradeEvidencePanel";
import { createRoot } from "react-dom/client";

const response = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

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
});

afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
});

it("renders policy provenance, ledger integrity, and unverified market context", async () => {
  mocks.apiFetch.mockResolvedValueOnce(response(basePack));
  await act(async () => root.render(<TradeEvidencePanel tradeId="TRD-1" onClose={vi.fn()} />));
  await flush();

  expect(host.textContent).toContain("Verified chain");
  expect(host.textContent).toContain("default-risk-policy");
  expect(host.textContent).toContain("Playbook: PB-1");
  expect(host.textContent).toContain("Source unverified / descriptive");
});

it("shows a bounded error instead of implying evidence exists", async () => {
  mocks.apiFetch.mockResolvedValueOnce(response({ detail: "trade evidence not found" }, 404));
  await act(async () => root.render(<TradeEvidencePanel tradeId="MISSING" onClose={vi.fn()} />));
  await flush();

  expect(host.textContent).toContain("trade evidence not found");
  expect(host.textContent).not.toContain("Verified chain");
});

