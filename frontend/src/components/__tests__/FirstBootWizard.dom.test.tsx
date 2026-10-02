// @vitest-environment jsdom
import React, { act } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { createRoot, Root } from "react-dom/client";

const mocks = vi.hoisted(() => ({
  setTheme: vi.fn(),
  setLocale: vi.fn(),
  apiFetch: vi.fn(),
}));

vi.mock("../../context/ThemeContext", () => ({
  useTheme: () => ({ theme: "dark", setTheme: mocks.setTheme }),
}));
vi.mock("../../context/I18nContext", () => ({
  SUPPORTED_LOCALES: [{ id: "en", label: "English", flag: "🇬🇧" }],
  useTranslation: () => ({
    locale: "en",
    setLocale: mocks.setLocale,
    t: (key: string) => key,
  }),
}));
vi.mock("../../lib/backend", () => ({
  apiUrl: (path: string) => path,
  apiFetch: mocks.apiFetch,
}));

import { FirstBootWizard } from "../onboarding/FirstBootWizard";

let host: HTMLDivElement;
let root: Root;

beforeEach(() => {
  (globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  mocks.setTheme.mockReset();
  mocks.setLocale.mockReset();
  mocks.apiFetch.mockReset();
});

it("shows a preference summary, not fabricated diagnostic success, and retains failed completion", async () => {
  const completed = vi.fn();
  mocks.apiFetch.mockRejectedValue(new Error("offline"));
  await act(async () => root.render(<FirstBootWizard isOpen onCompleted={completed} />));
  for (let i = 0; i < 3; i++) {
    await act(async () => Array.from(host.querySelectorAll("button")).find(b => b.textContent?.includes("onboarding.buttons.next"))!.click());
  }
  expect(host.textContent).toContain("first_use.setup_summary");
  expect(host.textContent).not.toContain("onboarding.verification.all_systems_go");
  expect(host.textContent).not.toContain("onboarding.verification.checking_sqlite");
  await act(async () => Array.from(host.querySelectorAll("button")).find(b => b.textContent?.includes("onboarding.verification.complete_btn"))!.click());
  expect(completed).not.toHaveBeenCalled();
  expect(host.querySelector('[role=alert]')?.textContent).toContain("first_use.save_failed");
  mocks.apiFetch.mockResolvedValue(new Response("{}", { status: 200 }));
  await act(async () => Array.from(host.querySelectorAll("button")).find(b => b.textContent?.includes("onboarding.verification.complete_btn"))!.click());
  expect(completed).toHaveBeenCalledOnce();
});

afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
});

it("defaults to external journaling and does not collect live or credential inputs", async () => {
  await act(async () => {
    root.render(<FirstBootWizard isOpen onCompleted={vi.fn()} />);
  });

  expect(host.textContent).toContain("onboarding.mode.external_title");
  expect(host.textContent).toContain("onboarding.mode.simulation_title");
  expect(host.textContent).not.toContain("onboarding.mode.live_title");
  expect(host.querySelector('input[type="password"]')).toBeNull();

  const nextButton = host.querySelector("button") as HTMLButtonElement;
  await act(async () => nextButton.click());

  expect(host.querySelector("[data-testid=onboarding-no-credentials]")).not.toBeNull();
  expect(host.querySelector('input[type="password"]')).toBeNull();
  expect(host.textContent).toContain("onboarding.vault.disabled_notice");
});

it("supports keyboard mode selection and rejects HTTP completion failure", async () => {
  const completed = vi.fn();
  mocks.apiFetch.mockResolvedValue(new Response("{}", { status: 503 }));
  await act(async () => root.render(<FirstBootWizard isOpen onCompleted={completed} />));
  const simulation = Array.from(host.querySelectorAll('[role=button]')).find(b => b.textContent?.includes('onboarding.mode.simulation_title'))!;
  await act(async () => simulation.dispatchEvent(new KeyboardEvent('keydown', { key: ' ', bubbles: true })));
  expect(simulation.getAttribute('aria-pressed')).toBe('true');
  for (let i = 0; i < 3; i++) await act(async () => Array.from(host.querySelectorAll('button')).find(b => b.textContent?.includes('onboarding.buttons.next'))!.click());
  await act(async () => Array.from(host.querySelectorAll('button')).find(b => b.textContent?.includes('onboarding.verification.complete_btn'))!.click());
  expect(completed).not.toHaveBeenCalled();
  expect(host.querySelector('[role=alert]')).not.toBeNull();
  expect(JSON.parse(mocks.apiFetch.mock.calls[0][1].body).trading_mode).toBe('simulation');
});
