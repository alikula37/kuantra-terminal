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
