// @vitest-environment jsdom
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ apiFetch: vi.fn(), t: (key: string) => key }));
vi.mock("../../lib/backend", () => ({ apiUrl: (path: string) => path, apiFetch: mocks.apiFetch }));
vi.mock("../../context/I18nContext", () => ({
  useTranslation: () => ({ t: mocks.t }),
}));
vi.mock("../settings/SystemHealthSettings", () => ({ SystemHealthSettings: () => null }));
vi.mock("../updater/UpdateNotifier", () => ({ UpdateNotifier: () => null }));

import { SettingsView } from "../SettingsView";

const response = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

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

it("cancels the initial-balance read without applying a late portfolio response", async () => {
  let resolvePending!: (value: Response) => void;
  const pending = new Promise<Response>((resolve) => { resolvePending = resolve; });
  let requestSignal: AbortSignal | undefined;
  mocks.apiFetch.mockImplementation((_path: string, init?: RequestInit) => {
    requestSignal = init?.signal;
    return pending;
  });

  await act(async () => root.render(<SettingsView />));
  await flush();

  const cancel = host.querySelector("[data-testid=settings-capital-cancel]") as HTMLButtonElement;
  expect(cancel).toBeTruthy();
  await act(async () => cancel.click());
  await flush();

  expect(requestSignal?.aborted).toBe(true);
  expect(host.querySelector("[data-testid=settings-capital-cancelled]")).not.toBeNull();
  expect((host.querySelector("input[type=number]") as HTMLInputElement).value).toBe("");

  resolvePending(response({ initial_balance: 1000 }));
  await flush();
  expect((host.querySelector("input[type=number]") as HTMLInputElement).value).toBe("");
});

it("shows an explicit error instead of a zero initial-balance fallback", async () => {
  mocks.apiFetch.mockResolvedValue(response({ detail: "portfolio summary unavailable" }, 503));
  await act(async () => root.render(<SettingsView />));
  await flush();

  expect(host.querySelector("[data-testid=settings-capital-error]")?.textContent).toContain("portfolio summary unavailable");
  expect((host.querySelector("input[type=number]") as HTMLInputElement).value).toBe("");
});

it("rejects a malformed portfolio summary response", async () => {
  mocks.apiFetch.mockResolvedValue(response({}));
  await act(async () => root.render(<SettingsView />));
  await flush();

  expect(host.querySelector("[data-testid=settings-capital-error]")?.textContent).toContain("Portfolio summary response was malformed");
  expect((host.querySelector("input[type=number]") as HTMLInputElement).value).toBe("");
});

it("runs a real full dual-db sync and reports the honest outcome", async () => {
  mocks.apiFetch.mockImplementation((path: string) => {
    if (path === "/api/v1/system/sync/full") {
      return Promise.resolve(response({ available: true, coverage_ready: true, synced: 5, reason: null }));
    }
    return Promise.resolve(response({ initial_balance: 1000 }));
  });

  await act(async () => root.render(<SettingsView />));
  await flush();

  const syncButton = host.querySelector("[data-testid=settings-sync]") as HTMLButtonElement;
  expect(syncButton).toBeTruthy();
  await act(async () => syncButton.click());
  await flush();

  const call = mocks.apiFetch.mock.calls.find(([path]) => path === "/api/v1/system/sync/full");
  expect(call?.[1]?.method).toBe("POST");
  expect(host.querySelector("[data-testid=settings-sync-status]")?.textContent).toContain("settings.sync_success");
  expect(host.querySelector("[data-testid=settings-sync-error]")).toBeNull();
});

it("shows an honest notice instead of a fake success when DuckDB is unavailable", async () => {
  mocks.apiFetch.mockImplementation((path: string) => {
    if (path === "/api/v1/system/sync/full") {
      return Promise.resolve(response({ available: false, coverage_ready: false, synced: 0, reason: "DUCKDB_UNAVAILABLE" }));
    }
    return Promise.resolve(response({ initial_balance: 1000 }));
  });

  await act(async () => root.render(<SettingsView />));
  await flush();
  await act(async () => (host.querySelector("[data-testid=settings-sync]") as HTMLButtonElement).click());
  await flush();

  expect(host.querySelector("[data-testid=settings-sync-status]")?.textContent).toContain("settings.sync_unavailable");
  expect(host.querySelector("[data-testid=settings-sync-error]")).toBeNull();
});

it("surfaces a blocked coverage gate and a transport failure distinctly", async () => {
  mocks.apiFetch.mockImplementation((path: string) => {
    if (path === "/api/v1/system/sync/full") {
      return Promise.resolve(response({ available: true, coverage_ready: false, synced: 0, reason: "COVERAGE_INCOMPLETE" }));
    }
    return Promise.resolve(response({ initial_balance: 1000 }));
  });
  await act(async () => root.render(<SettingsView />));
  await flush();
  await act(async () => (host.querySelector("[data-testid=settings-sync]") as HTMLButtonElement).click());
  await flush();
  expect(host.querySelector("[data-testid=settings-sync-error]")?.textContent).toContain("settings.sync_blocked");

  mocks.apiFetch.mockImplementation((path: string) => {
    if (path === "/api/v1/system/sync/full") return Promise.resolve(response({ detail: "boom" }, 500));
    return Promise.resolve(response({ initial_balance: 1000 }));
  });
  await act(async () => (host.querySelector("[data-testid=settings-sync]") as HTMLButtonElement).click());
  await flush();
  expect(host.querySelector("[data-testid=settings-sync-error]")?.textContent).toContain("settings.sync_failed");
});
