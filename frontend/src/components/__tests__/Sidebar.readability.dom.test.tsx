// @vitest-environment jsdom
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
vi.mock("../../lib/backend", () => ({ apiUrl: (p: string) => p, apiFetch: vi.fn().mockRejectedValue(new Error("offline fixture")) }));
vi.mock("../../context/PluginRegistryContext", () => ({ usePluginRegistry: () => ({ isPluginActive: () => false, activePlugins: [], isLiteMode: true }) }));
vi.mock("../plugins/ExtensionSlot", () => ({ ExtensionSlot: () => null }));
import { I18nProvider } from "../../context/I18nContext";
import { Sidebar } from "../Sidebar";
let host: HTMLDivElement;
let root: ReturnType<typeof createRoot>;
beforeEach(() => { (globalThis as any).IS_REACT_ACT_ENVIRONMENT = true; host = document.createElement("div"); document.body.append(host); root = createRoot(host); });
afterEach(async () => { await act(async () => root.unmount()); host.remove(); localStorage.clear(); });

it.each(["en", "tr", "de"])("keeps complete navigation labels and translated diagnostics in %s", async locale => {
  localStorage.setItem("kuantra_locale", locale);
  const change = vi.fn();
  await act(async () => root.render(<I18nProvider><Sidebar activeTab="journal" onTabChange={change} /></I18nProvider>));
  const journal = host.querySelector('[data-testid="nav-journal"]') as HTMLButtonElement;
  expect(journal.querySelector("span")?.classList.contains("truncate")).toBe(false);
  expect(journal.classList.contains("k-btn")).toBe(true);
  expect(host.textContent).not.toContain("sidebar.");
  if (locale !== "en") {
    expect(host.textContent).not.toContain("Engine Diagnostics");
    expect(host.textContent).not.toContain("Desktop Core");
    expect(host.textContent).not.toContain("ON DEMAND");
  }
  journal.focus();
  expect(document.activeElement).toBe(journal);
  await act(async () => journal.click());
  expect(change).toHaveBeenCalledWith("journal");
});
