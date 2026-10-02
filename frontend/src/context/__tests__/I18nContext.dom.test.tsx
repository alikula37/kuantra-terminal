// @vitest-environment jsdom
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ apiFetch: vi.fn() }));
vi.mock("../../lib/backend", () => ({ apiUrl: (path: string) => path, apiFetch: mocks.apiFetch }));
import { I18nProvider, useTranslation } from "../I18nContext";

const response = (body: unknown) => new Response(JSON.stringify(body));
function Probe() {
  const { locale, setLocale, t } = useTranslation();
  return <button onClick={() => setLocale("tr")} data-testid="locale">{locale} · {t("journal.title")}</button>;
}
function CopyProbe() {
  const { t } = useTranslation();
  return <p>{t("order_ticket.estimate_units_notice")} · {t("journal.subtitle")} · {t("tracking.disclaimer")}</p>;
}
let host: HTMLDivElement;
let root: ReturnType<typeof createRoot>;
beforeEach(() => {
  (globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
  localStorage.clear();
  mocks.apiFetch.mockReset();
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
});
afterEach(async () => { await act(async () => root.unmount()); host.remove(); localStorage.clear(); });

it("preserves a user's language choice against a slower initial settings response", async () => {
  let resolve!: (value: Response) => void;
  const pending = new Promise<Response>(r => { resolve = r; });
  mocks.apiFetch.mockImplementation((_path: string, init?: RequestInit) => init?.method === "PUT"
    ? Promise.resolve(response({ active_locale: "tr" })) : pending);
  await act(async () => root.render(<I18nProvider><Probe /></I18nProvider>));
  await act(async () => (host.querySelector("button") as HTMLButtonElement).click());
  await act(async () => { resolve(response({ active_locale: "de" })); });
  expect(host.textContent).toContain("tr ·");
  expect(localStorage.getItem("kuantra_locale")).toBe("tr");
  expect(document.documentElement.lang).toBe("tr");
});

it("restores the backend language when no user choice intervenes", async () => {
  mocks.apiFetch.mockResolvedValue(response({ active_locale: "de" }));
  await act(async () => root.render(<I18nProvider><Probe /></I18nProvider>));
  expect(host.textContent).toContain("de ·");
  expect(document.documentElement.lang).toBe("de");
});

it.each([
  ["en", "declared USD position value", "does not multiply", "no broker orders", "not broker-verified", "approximate"],
  ["tr", "USD pozisyon değeri", "sonucu çarpmaz", "emir gönderilmez", "doğrulanmış kazanç değildir", "yaklaşık"],
  ["de", "USD-Positionswert", "multipliziert dieses Ergebnis nicht", "keine Brokeraufträge", "Kein vom Broker bestätigter Gewinn", "Näherung"],
])("preserves USD sizing, gross/local and recording boundaries in %s copy", async (locale, ...claims) => {
  localStorage.setItem("kuantra_locale", locale);
  mocks.apiFetch.mockRejectedValue(new Error("offline fixture"));
  await act(async () => root.render(<I18nProvider><CopyProbe /></I18nProvider>));
  for (const claim of claims) expect(host.textContent).toContain(claim);
  expect(host.textContent).not.toMatch(/order_ticket\.|journal\.|tracking\.|Price × quantity|Fiyat × miktar|Preis × Menge/);
});
