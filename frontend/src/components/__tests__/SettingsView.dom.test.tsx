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
