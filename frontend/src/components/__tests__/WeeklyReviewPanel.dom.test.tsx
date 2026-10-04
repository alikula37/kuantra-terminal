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
  malformed_event_count: 0,
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
  localStorage.clear();
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
  localStorage.clear();
});

it("localizes coverage and warnings while folding unknown diagnostics", async () => {
  mocks.apiFetch.mockImplementation((path: string) => Promise.resolve(response(path === "/api/v1/settings" ? { locale: "en" } : {
    ...review, warnings: ["FEES_UNKNOWN", "FUTURE_SERVER_CODE"],
  })));
  await act(async () => root.render(<I18nProvider><WeeklyReviewPanel onClose={vi.fn()} /></I18nProvider>));
  await flush();
  expect(host.querySelector('[data-testid="weekly-review-status"]')?.textContent).toBe("Limited evidence");
  expect(host.querySelector('[data-testid="weekly-review-warnings"]')?.textContent).toContain("Fees: Unknown");
  expect(host.querySelector('[data-testid="weekly-review-warnings"]')?.textContent).not.toContain("FUTURE_SERVER_CODE");
  expect(host.querySelector('details[data-testid="weekly-review-diagnostics"]')?.hasAttribute("open")).toBe(false);
  expect(host.querySelector('details[data-testid="weekly-review-diagnostics"]')?.textContent).toContain("FUTURE_SERVER_CODE");
});

it("explains Istanbul cutoff and exclusive period end using the returned snapshot", async () => {
  await act(async () => root.render(<I18nProvider><WeeklyReviewPanel onClose={vi.fn()} /></I18nProvider>));
  await flush();
  expect(host.querySelector('[data-testid="weekly-review-period"]')?.textContent).toContain("07:00");
  expect(host.querySelector('[data-testid="weekly-review-cutoff"]')?.textContent).toContain("15:00");
  expect(host.textContent).toContain("The end date is excluded");
  expect(host.querySelector('[data-testid="weekly-review-cutoff"]')?.textContent).toContain("Europe/Istanbul");
});

it.each(["NOT_READY", "STALE_REVIEW", "FUTURE_STATUS"])("does not allow a manual completion for %s even if flagged", async (status) => {
  mocks.apiFetch.mockImplementation((path: string) => Promise.resolve(response(path === "/api/v1/settings" ? { locale: "en" } : {
    ...review, review_status: status, completion_allowed: true, event_count: status === "NOT_READY" ? 0 : 1,
  })));
  await act(async () => root.render(<I18nProvider><WeeklyReviewPanel onClose={vi.fn()} /></I18nProvider>));
  await flush();
  expect((host.querySelector('[data-testid="weekly-review-complete"]') as HTMLButtonElement)?.disabled).toBe(true);
  expect(host.textContent).not.toContain("PASS");
});

it("keeps completed review distinct from complete coverage and renders genuine zero", async () => {
  mocks.apiFetch.mockImplementation((path: string) => Promise.resolve(response(path === "/api/v1/settings" ? { locale: "en" } : {
    ...review, review_status: "COMPLETED", completion: { decision: "COMPLETED", note: "Synthetic review" },
  })));
  await act(async () => root.render(<I18nProvider><WeeklyReviewPanel onClose={vi.fn()} /></I18nProvider>));
  await flush();
  expect(host.querySelector('[data-testid="weekly-review-status"]')?.textContent).toBe("Your review is completed");
  expect(host.querySelector('[data-testid="weekly-review-summary"]')?.textContent).toContain("0");
  expect(host.querySelector('[data-testid="weekly-review-coverage"]')?.textContent).toContain("Unknown");
  expect(host.textContent).toContain("Synthetic review");
});

it("uses standard theme-aware readable controls instead of fixed dark surfaces", async () => {
  await act(async () => root.render(<I18nProvider><WeeklyReviewPanel onClose={vi.fn()} /></I18nProvider>));
  await flush();
  expect(host.innerHTML).not.toMatch(/bg-\[#|text-white|text-\[10px\]|text-amber-300/);
  expect(host.querySelector('input[name="period_start"]')?.classList.contains("k-input")).toBe(true);
});

it.each([['tr', 'Sınırlı kanıt', 'Komisyonlar: Bilinmiyor'], ['de', 'Begrenzte Belege', 'Gebühren: Unbekannt'], ['en', 'Limited evidence', 'Fees: Unknown']])("localizes primary states and warnings in %s", async (locale, status, warning) => {
  localStorage.setItem('kuantra_locale', locale);
  mocks.apiFetch.mockImplementation((path: string) => Promise.resolve(response(path === '/api/v1/settings' ? { active_locale: locale } : { ...review, warnings: ['FEES_UNKNOWN'] })));
  await act(async () => root.render(<I18nProvider><WeeklyReviewPanel onClose={vi.fn()} /></I18nProvider>)); await flush();
  expect(host.querySelector('[data-testid="weekly-review-status"]')?.textContent).toBe(status);
  expect(host.querySelector('[data-testid="weekly-review-warnings"]')?.textContent).toContain(warning);
});

it.each(['timezone', 'as_of_utc'])("requires reload after %s changes and sends no decision", async (name) => {
  await act(async () => root.render(<I18nProvider><WeeklyReviewPanel onClose={vi.fn()} /></I18nProvider>)); await flush();
  const input = host.querySelector(`input[name=${name}]`) as HTMLInputElement;
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set?.call(input, name === 'timezone' ? 'UTC' : '2026-09-09T12:00:00Z');
  await act(async () => input.dispatchEvent(new Event('input', { bubbles: true })));
  const complete = host.querySelector('[data-testid="weekly-review-complete"]') as HTMLButtonElement;
  expect(complete.disabled).toBe(true);
  await act(async () => complete.click());
  expect(mocks.apiFetch.mock.calls.some(([path]) => path.includes('/decision'))).toBe(false);
});

it("records only an explicit synthetic decision with the unchanged UTC boundary and bounded note", async () => {
  await act(async () => root.render(<I18nProvider><WeeklyReviewPanel onClose={vi.fn()} /></I18nProvider>)); await flush();
  expect(mocks.apiFetch.mock.calls.some(([path]) => path.includes('/decision'))).toBe(false);
  const note = host.querySelector('textarea') as HTMLTextAreaElement;
  expect(note.maxLength).toBe(500);
  Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value')?.set?.call(note, '  Synthetic review only  ');
  await act(async () => note.dispatchEvent(new Event('input', { bubbles: true })));
  const cutoff = (host.querySelector('input[name=as_of_utc]') as HTMLInputElement).value;
  await act(async () => (host.querySelector('[data-testid="weekly-review-complete"]') as HTMLButtonElement).click()); await flush();
  const decision = mocks.apiFetch.mock.calls.find(([path]) => path.includes('/decision'));
  expect(JSON.parse(decision?.[1].body)).toMatchObject({ decision: 'COMPLETE', timezone: 'Europe/Istanbul', as_of_utc: cutoff, note: 'Synthetic review only' });
});

it("retains the synthetic note and retry after a failed decision without claiming completion", async () => {
  mocks.apiFetch.mockImplementation((path: string) => Promise.resolve(response(path === '/api/v1/settings' ? { locale: 'en' } : review, path.includes('/decision') ? 409 : 200)));
  await act(async () => root.render(<I18nProvider><WeeklyReviewPanel onClose={vi.fn()} /></I18nProvider>)); await flush();
  await act(async () => (host.querySelector('[data-testid="weekly-review-complete"]') as HTMLButtonElement).click()); await flush();
  expect(host.querySelector('[role="alert"]')).not.toBeNull();
  expect(host.textContent).not.toContain('Review decision recorded.');
  expect(host.querySelector('[data-testid="weekly-review-retry"]')).not.toBeNull();
});

it("lets the user advance cutoff explicitly without automatically recording or loading a decision", async () => {
  await act(async () => root.render(<I18nProvider><WeeklyReviewPanel onClose={vi.fn()} /></I18nProvider>)); await flush();
  const calls = mocks.apiFetch.mock.calls.length;
  await act(async () => (host.querySelector('[data-testid="weekly-review-now"]') as HTMLButtonElement).click()); await flush();
  expect(host.querySelector('[data-testid="weekly-review-inputs-changed"]')).not.toBeNull();
  expect(mocks.apiFetch.mock.calls.length).toBe(calls);
  expect((host.querySelector('[data-testid="weekly-review-complete"]') as HTMLButtonElement).disabled).toBe(true);
});

it("rejects an old response for completion after inputs change during its load", async () => {
  let resolve!: (value: Response) => void;
  mocks.apiFetch.mockImplementation((path: string) => path === '/api/v1/settings' ? Promise.resolve(response({ locale: 'en' })) : new Promise<Response>(r => { resolve = r; }));
  await act(async () => root.render(<I18nProvider><WeeklyReviewPanel onClose={vi.fn()} /></I18nProvider>)); await flush();
  const input = host.querySelector('input[name=timezone]') as HTMLInputElement;
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set?.call(input, 'UTC');
  await act(async () => input.dispatchEvent(new Event('input', { bubbles: true })));
  await act(async () => resolve(response(review))); await flush();
  expect(host.querySelector('[data-testid="weekly-review-inputs-changed"]')).not.toBeNull();
  expect((host.querySelector('[data-testid="weekly-review-complete"]') as HTMLButtonElement).disabled).toBe(true);
});

it("reopens only by explicit choice and keeps unknown coverage visible", async () => {
  mocks.apiFetch.mockImplementation((path: string) => Promise.resolve(response(path === '/api/v1/settings' ? { locale: 'en' } : { ...review, review_status: 'COMPLETED', completion: { decision: 'COMPLETED' } })));
  await act(async () => root.render(<I18nProvider><WeeklyReviewPanel onClose={vi.fn()} /></I18nProvider>)); await flush();
  expect(mocks.apiFetch.mock.calls.some(([path]) => path.includes('/decision'))).toBe(false);
  await act(async () => (host.querySelector('[data-testid="weekly-review-reopen"]') as HTMLButtonElement).click()); await flush();
  const call = mocks.apiFetch.mock.calls.find(([path]) => path.includes('/decision'));
  expect(JSON.parse(call?.[1].body).decision).toBe('REOPEN');
  expect(host.querySelector('[data-testid="weekly-review-coverage"]')?.textContent).toContain('Unknown');
});

it("handles prototype-like unknown codes without treating them as supported states", async () => {
  mocks.apiFetch.mockImplementation((path: string) => Promise.resolve(response(path === '/api/v1/settings' ? { locale: 'en' } : {
    ...review, review_status: 'constructor', warnings: ['constructor'], coverage: { overall: 'constructor', constructor: 'toString' },
  })));
  await act(async () => root.render(<I18nProvider><WeeklyReviewPanel onClose={vi.fn()} /></I18nProvider>)); await flush();
  expect(host.querySelector('[data-testid="weekly-review-status"]')?.textContent).toBe('Review status could not be interpreted');
  expect(host.querySelector('[data-testid="weekly-review-warnings"]')?.textContent).toContain('unrecognized evidence condition');
  expect((host.querySelector('[data-testid="weekly-review-complete"]') as HTMLButtonElement).disabled).toBe(true);
});

it("keeps note focus during parent quote updates and uses the latest Escape callback", async () => {
  const oldClose = vi.fn(), newClose = vi.fn();
  await act(async () => root.render(<I18nProvider><WeeklyReviewPanel onClose={oldClose} /></I18nProvider>)); await flush();
  const note = host.querySelector('textarea') as HTMLTextAreaElement; note.focus();
  await act(async () => root.render(<I18nProvider><WeeklyReviewPanel onClose={newClose} /></I18nProvider>)); await flush();
  expect(document.activeElement).toBe(note);
  await act(async () => document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true })));
  expect(newClose).toHaveBeenCalledTimes(1); expect(oldClose).not.toHaveBeenCalled();
});

it("tabs through visible buttons and summaries, never folded advanced inputs", async () => {
  await act(async () => root.render(<I18nProvider><WeeklyReviewPanel onClose={vi.fn()} /></I18nProvider>)); await flush();
  const now = host.querySelector('[data-testid="weekly-review-now"]') as HTMLButtonElement; now.focus();
  await act(async () => document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', bubbles: true })));
  expect(document.activeElement?.tagName).toBe('SUMMARY');
  await act(async () => document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', bubbles: true })));
  expect((document.activeElement as HTMLButtonElement).type).toBe('submit');
});

it("shows limited coverage and never presents it as PASS", async () => {
  await act(async () => root.render(<I18nProvider><WeeklyReviewPanel onClose={vi.fn()} /></I18nProvider>));
  await flush();

  expect(host.textContent).toContain("LIMITED");
  expect(host.textContent).toContain("UNKNOWN");
  expect(host.textContent).not.toContain("PASS");
  expect(host.textContent).toContain("Fees remain UNKNOWN");
});

it("rejects a malformed successful review response instead of crashing the panel", async () => {
  mocks.apiFetch.mockImplementation((path: string) => Promise.resolve(
    path === "/api/v1/settings" ? response({ locale: "en" }) : response({ review_id: "WR-1" }),
  ));
  await act(async () => root.render(<I18nProvider><WeeklyReviewPanel onClose={vi.fn()} /></I18nProvider>));
  await flush();

  expect(host.querySelector('[role="alert"]')?.textContent).toContain("Weekly review response was malformed.");
  expect(host.querySelector('[data-testid="weekly-review-panel"]')).not.toBeNull();
});

it("requires explicit review inputs and exposes the as-of boundary", async () => {
  await act(async () => root.render(<I18nProvider><WeeklyReviewPanel onClose={vi.fn()} /></I18nProvider>));
  await flush();

  expect(host.querySelector("input[name=period_start]")).not.toBeNull();
  expect(host.querySelector("input[name=period_end]")).not.toBeNull();
  expect(host.querySelector("input[name=as_of_utc]")).not.toBeNull();
  expect(host.textContent).toContain("as-of");
});

it("disables a completion decision when review inputs no longer match the loaded snapshot", async () => {
  await act(async () => root.render(<I18nProvider><WeeklyReviewPanel onClose={vi.fn()} /></I18nProvider>));
  await flush();

  const periodStart = host.querySelector("input[name=period_start]") as HTMLInputElement;
  const setInputValue = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
  setInputValue?.call(periodStart, "2026-09-02");
  await act(async () => periodStart.dispatchEvent(new Event("input", { bubbles: true })));
  await act(async () => periodStart.dispatchEvent(new Event("change", { bubbles: true })));
  await flush();

  expect(host.querySelector("[data-testid=weekly-review-inputs-changed]")).not.toBeNull();
  const complete = Array.from(host.querySelectorAll("button")).find((button) => button.textContent?.includes("Record review completion")) as HTMLButtonElement;
  expect(complete?.disabled).toBe(true);
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

it("cancels a pending review load without showing stale or successful review data", async () => {
  let resolveReview!: (value: Response) => void;
  let requestSignal: AbortSignal | undefined;
  const pending = new Promise<Response>((resolve) => { resolveReview = resolve; });
  mocks.apiFetch.mockImplementation((path: string, init?: RequestInit) => {
    if (path === "/api/v1/settings") return Promise.resolve(response({ locale: "en" }));
    requestSignal = init?.signal;
    return pending;
  });

  await act(async () => root.render(<I18nProvider><WeeklyReviewPanel onClose={vi.fn()} /></I18nProvider>));
  await flush();

  const cancel = host.querySelector("[data-testid=weekly-review-cancel]") as HTMLButtonElement;
  expect(cancel).toBeTruthy();
  await act(async () => cancel.click());
  await flush();

  expect(requestSignal?.aborted).toBe(true);
  expect(host.querySelector("[data-testid=weekly-review-cancelled]")).not.toBeNull();
  expect(host.textContent).not.toContain("LIMITED");

  resolveReview(response(review));
  await flush();
  expect(host.textContent).not.toContain("LIMITED");
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
