// @vitest-environment jsdom
import React, { act } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ apiFetch: vi.fn() }));
vi.mock("../../lib/backend", () => ({ apiUrl: (path: string) => path, apiFetch: mocks.apiFetch }));

import { ThemeProvider, useTheme } from "../ThemeContext";
import { createRoot } from "react-dom/client";

const response = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

const ThemeProbe = () => {
  const { theme, toggleTheme } = useTheme();
  return <button type="button" data-testid="theme-toggle" onClick={toggleTheme}>{theme}</button>;
};

let host: HTMLDivElement;
let root: ReturnType<typeof createRoot>;
const flush = async () => { await act(async () => { await Promise.resolve(); await Promise.resolve(); }); };

beforeEach(() => {
  (globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
  localStorage.clear();
  document.documentElement.className = "";
  document.documentElement.dataset.theme = "";
  document.documentElement.style.cssText = "";
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  mocks.apiFetch.mockReset();
  mocks.apiFetch.mockResolvedValue(response({ active_theme: "dark" }));
});

afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
});

it("applies light-mode tokens, classes and native color-scheme state", async () => {
  await act(async () => root.render(<ThemeProvider><ThemeProbe /></ThemeProvider>));
  await flush();

  const toggle = host.querySelector("[data-testid=theme-toggle]") as HTMLButtonElement;
  expect(toggle.textContent).toBe("dark");
  expect(document.documentElement.dataset.theme).toBe("dark");
  expect(document.documentElement.style.colorScheme).toBe("dark");

  await act(async () => toggle.click());
  await flush();

  expect(toggle.textContent).toBe("light");
  expect(document.documentElement.classList.contains("light-theme")).toBe(true);
  expect(document.documentElement.classList.contains("dark-theme")).toBe(false);
  expect(document.documentElement.dataset.theme).toBe("light");
  expect(document.documentElement.style.colorScheme).toBe("light");
  expect(document.documentElement.style.getPropertyValue("--bg-primary")).toBe("#f8fafc");
  expect(document.documentElement.style.getPropertyValue("--text-primary")).toBe("#0f172a");
  expect(mocks.apiFetch).toHaveBeenCalledWith("/api/v1/settings", expect.objectContaining({
    method: "PUT",
    body: JSON.stringify({ active_theme: "light" }),
  }));
});

it("does not let a slower initial settings response undo a user toggle", async () => {
  let resolveSettings!: (value: Response) => void;
  const pendingSettings = new Promise<Response>((resolve) => { resolveSettings = resolve; });
  mocks.apiFetch.mockImplementation((_path: string, init?: RequestInit) => (
    init?.method === "PUT" ? Promise.resolve(response({ active_theme: "light" })) : pendingSettings
  ));

  await act(async () => root.render(<ThemeProvider><ThemeProbe /></ThemeProvider>));
  const toggle = host.querySelector("[data-testid=theme-toggle]") as HTMLButtonElement;
  await act(async () => toggle.click());
  await flush();

  resolveSettings(response({ active_theme: "dark" }));
  await flush();

  expect(toggle.textContent).toBe("light");
  expect(document.documentElement.dataset.theme).toBe("light");
  expect(document.documentElement.classList.contains("light-theme")).toBe(true);
});
