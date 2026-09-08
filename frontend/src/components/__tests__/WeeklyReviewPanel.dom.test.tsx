// @vitest-environment jsdom
import React, { act } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ apiFetch: vi.fn() }));
vi.mock("../../lib/backend", () => ({ apiUrl: (path: string) => path, apiFetch: mocks.apiFetch }));

import { I18nProvider } from "../../context/I18nContext";
import { WeeklyReviewPanel } from "../WeeklyReviewPanel";
import { createRoot } from "react-dom/client";

const response = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

const review = {
  review_id: "WR-1",
  review_status: "LIMITED",
  completion_allowed: true,
  is_pass: false,
  period: {
    start_local: "2026-09-01T00:00:00-04:00",
    end_local: "2026-09-08T00:00:00-04:00",
    start_utc: "2026-09-01T04:00:00Z",
    end_utc: "2026-09-08T04:00:00Z",
    timezone: "America/New_York",
  },
  as_of_utc: "2026-09-08T12:00:00Z",
  coverage: { overall: "PARTIAL", fees: "UNKNOWN", funding_transfer: "NOT_AVAILABLE" },
  trade_count: 1,
  event_count: 1234,
  late_event_count: 0,
  excluded_future_rule_count: 0,
  applicable_rules: [],
  completion: null,
  warnings: ["Fees remain UNKNOWN; review is limited."],
  snapshot_sha256: "a".repeat(64),
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
  mocks.apiFetch.mockImplementation((path: string) => Promise.resolve(
    path === "/api/v1/settings" ? response({ locale: "en" }) : response(review),
  ));
});

afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
});

it("shows limited coverage and never presents it as PASS", async () => {
  await act(async () => root.render(<I18nProvider><WeeklyReviewPanel onClose={vi.fn()} /></I18nProvider>));
  await flush();

  expect(host.textContent).toContain("LIMITED");
  expect(host.textContent).toContain("UNKNOWN");
  expect(host.textContent).not.toContain("PASS");
  expect(host.textContent).toContain("Fees remain UNKNOWN");
});

it("requires explicit review inputs and exposes the as-of boundary", async () => {
  await act(async () => root.render(<I18nProvider><WeeklyReviewPanel onClose={vi.fn()} /></I18nProvider>));
  await flush();

  expect(host.querySelector("input[name=period_start]")).not.toBeNull();
  expect(host.querySelector("input[name=period_end]")).not.toBeNull();
  expect(host.querySelector("input[name=as_of_utc]")).not.toBeNull();
  expect(host.textContent).toContain("as-of");
});

it("puts focus in the dialog and closes on Escape", async () => {
  const onClose = vi.fn();
  mocks.apiFetch.mockImplementation((path: string) => Promise.resolve(
    path === "/api/v1/settings" ? response({ locale: "en" }) : response(review),
  ));
  await act(async () => root.render(<I18nProvider><WeeklyReviewPanel onClose={onClose} /></I18nProvider>));
  await flush();

  const close = host.querySelector("button[aria-label='Close weekly review']") as HTMLButtonElement;
  expect(document.activeElement).toBe(close);
  await act(async () => document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true })));
  expect(onClose).toHaveBeenCalledTimes(1);
});

it("offers a bounded retry after a review request failure", async () => {
  let reviewCalls = 0;
  mocks.apiFetch.mockImplementation((path: string) => {
    if (path === "/api/v1/settings") return Promise.resolve(response({ locale: "en" }));
    reviewCalls += 1;
    return Promise.resolve(reviewCalls === 1 ? response({ detail: "temporary review failure" }, 503) : response(review));
  });
  await act(async () => root.render(<I18nProvider><WeeklyReviewPanel onClose={vi.fn()} /></I18nProvider>));
  await flush();

  expect(host.textContent).toContain("temporary review failure");
  const retry = host.querySelector("[data-testid=weekly-review-retry]") as HTMLButtonElement;
  expect(retry).toBeTruthy();
  await act(async () => retry.click());
  await flush();
  expect(host.textContent).toContain("LIMITED");
});

it("formats numeric counts and keeps long snapshot identifiers bounded", async () => {
  mocks.apiFetch.mockImplementation((path: string) => Promise.resolve(
    path === "/api/v1/settings" ? response({ locale: "en" }) : response(review),
  ));
  await act(async () => root.render(<I18nProvider><WeeklyReviewPanel onClose={vi.fn()} /></I18nProvider>));
  await flush();

  expect(host.textContent).toContain("1,234");
  const snapshot = host.textContent?.match(/a{10}…a{6}/)?.[0];
  expect(snapshot).toBe("aaaaaaaaaa…aaaaaa");
  expect(host.textContent).not.toContain("a".repeat(64));
});
