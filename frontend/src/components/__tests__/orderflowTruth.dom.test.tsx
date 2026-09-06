// @vitest-environment jsdom
import React, { act } from "react";
import { createRoot, Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ apiFetch: vi.fn() }));
vi.mock("../../lib/backend", () => ({
  apiBase: () => "",
  apiUrl: (path: string) => path,
  apiFetch: mocks.apiFetch,
}));

import { FootprintChart } from "../orderflow/FootprintChart";
import { FixStatusWidget } from "../orderflow/FixStatusWidget";
import { FIXOrderBookStudio } from "../fix/FIXOrderBookStudio";

const response = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const flush = async () => {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
};

let host: HTMLDivElement;
let root: Root;

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
  vi.useRealTimers();
});

describe("order-flow and FIX truth states", () => {
  it("does not render a fabricated footprint or divergence when no feed exists", async () => {
    mocks.apiFetch
      .mockResolvedValueOnce(response({ status: "NO_DATA", bars: [], caveat: "No feed" }))
      .mockResolvedValueOnce(response({
        status: "NO_DATA",
        series: [],
        divergence: { has_divergence: false, type: "UNAVAILABLE" },
        caveat: "No feed",
      }));

    await act(async () => root.render(<FootprintChart />));
    await flush();

    expect(host.textContent).toContain("NO RECORDED ORDER-FLOW DATA");
    expect(host.textContent).toContain("No footprint bars are rendered");
    expect(host.textContent).not.toContain("INSTITUTIONAL ABSORPTION DETECTED");
  });

  it("keeps FIX dispatch disabled and latency nullable", async () => {
    mocks.apiFetch.mockResolvedValue(response({
      status: "EXPERIMENTAL_DISABLED",
      provenance: "FIX_SERIALIZATION_ONLY",
      caveat: "No certified FIX transport.",
      begin_string: "FIX.4.4",
      sender_comp_id: "—",
      target_comp_id: "—",
      is_logged_on: false,
      outbound_seq_num: null,
      inbound_seq_num: null,
      round_trip_latency_us: null,
      heartbeat_interval_sec: null,
      supported_venues: [],
      transport_connected: false,
    }));

    await act(async () => root.render(<FixStatusWidget />));
    await flush();

    expect(host.textContent).toContain("EXECUTION UNAVAILABLE");
    expect(host.textContent).toContain("—");
    expect(host.textContent).not.toContain("35=A LOGON OK");
    const send = Array.from(host.querySelectorAll("button")).find((button) => button.textContent?.includes("SEND DISABLED"));
    expect(send).toBeDefined();
    expect((send as HTMLButtonElement).disabled).toBe(true);
  });

  it("shows an empty DOM and disables FIX controls", async () => {
    mocks.apiFetch
      .mockResolvedValueOnce(response({ status: "NO_DATA", bids: [], asks: [], book_imbalance_ratio: null }))
      .mockResolvedValueOnce(response({ status: "EXPERIMENTAL_DISABLED", session_state: "DISCONNECTED", message_history: [] }));

    await act(async () => root.render(<FIXOrderBookStudio />));
    await flush();

    expect(host.textContent).toContain("NO VENUE CONNECTION");
    expect(host.textContent).toContain("No recorded L2 feed is connected");
    expect(host.textContent).not.toContain("Sub-10μs Native Matching Engine");
    expect(Array.from(host.querySelectorAll("button")).filter((button) => button.disabled).length).toBeGreaterThanOrEqual(4);
  });
});
