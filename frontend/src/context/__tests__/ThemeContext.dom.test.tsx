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
  vi.useRealTimers();
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
  vi.useFakeTimers();
  let resolveSettings!: (value: Response) => void;
  const pendingSettings = new Promise<Response>((resolve) => { resolveSettings = resolve; });
  mocks.apiFetch.mockImplementation((_path: string, init?: RequestInit) => (
    init?.method === "PUT" ? Promise.resolve(response({ active_theme: "light" })) : pendingSettings
  ));

  await act(async () => root.render(<ThemeProvider><ThemeProbe /></ThemeProvider>));
  await act(async () => vi.advanceTimersByTime(1500));
  const toggle = host.querySelector("[data-testid=theme-toggle]") as HTMLButtonElement;
  await act(async () => toggle.click());
  await flush();

  resolveSettings(response({ active_theme: "dark" }));
  await flush();

  expect(toggle.textContent).toBe("light");
  expect(document.documentElement.dataset.theme).toBe("light");
  expect(document.documentElement.classList.contains("light-theme")).toBe(true);
});

it("restores the backend theme before mounting controls when native local storage has no saved theme", async () => {
  let resolve!: (value: Response) => void;
  mocks.apiFetch.mockReturnValue(new Promise<Response>(r => { resolve = r; }));
  const layouts: string[] = [];
  function BackendLayoutProbe() {
    React.useLayoutEffect(() => { layouts.push(document.documentElement.dataset.theme || ""); }, []);
    return <ThemeProbe />;
  }
  await act(async () => root.render(<ThemeProvider><BackendLayoutProbe /></ThemeProvider>));
  expect(host.querySelector("button")).toBeNull();
  await act(async () => resolve(response({ active_theme: "light" })));
  expect(layouts).toEqual(["light"]);
  expect(host.textContent).toBe("light");
});

it("does not leave the app blank when initial settings stall", async () => {
  vi.useFakeTimers();
  mocks.apiFetch.mockReturnValue(new Promise<Response>(() => {}));
  await act(async () => root.render(<ThemeProvider><ThemeProbe /></ThemeProvider>));
  await act(async () => vi.advanceTimersByTime(1500));
  expect(host.textContent).toBe("dark");
});

it.each(["dark", "light"] as const)("applies matching RGB and hex tokens on a cold %s start and roundtrip", async theme => {
  localStorage.setItem("kuantra_theme", theme);
  mocks.apiFetch.mockResolvedValue(response({ active_theme: theme }));
  await act(async () => root.render(<ThemeProvider><ThemeProbe /></ThemeProvider>));
  const check = () => {
    const style = document.documentElement.style;
    for (const [rgb, hex] of [["accent", "accent"], ["gain", "gain"], ["loss", "loss"]]) {
      const value = style.getPropertyValue(`--color-${hex}`);
      const expected = value.slice(1).match(/../g)!.map(v => parseInt(v, 16)).join(", ");
      expect(style.getPropertyValue(`--${rgb}-rgb`)).toBe(expected);
    }
    expect(style.getPropertyValue("--border-rgb")).not.toBe("");
  };
  check();
  const toggle = host.querySelector("button") as HTMLButtonElement;
  await act(async () => toggle.click()); check();
  await act(async () => toggle.click()); check();
  expect(document.documentElement.dataset.theme).toBe(theme);
});

it.each(["dark", "light"] as const)("initializes inherited colors before the first child layout (%s)", async theme => {
  localStorage.setItem("kuantra_theme", theme);
  mocks.apiFetch.mockResolvedValue(response({ active_theme: theme }));
  const firstLayouts: Array<{ theme: string | undefined; accent: string; rgb: string }> = [];
  function LayoutProbe() {
    React.useLayoutEffect(() => {
      const root = document.documentElement;
      firstLayouts.push({ theme: root.dataset.theme, accent: root.style.getPropertyValue("--color-accent"), rgb: root.style.getPropertyValue("--accent-rgb") });
    }, []);
    return <ThemeProbe />;
  }
  await act(async () => root.render(<ThemeProvider><LayoutProbe /></ThemeProvider>));
  expect(firstLayouts).toHaveLength(1);
  expect(firstLayouts[0].theme).toBe(theme);
  expect(firstLayouts[0].accent).not.toBe("");
  expect(firstLayouts[0].rgb).not.toBe("");
});
