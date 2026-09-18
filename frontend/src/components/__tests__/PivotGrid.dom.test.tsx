// @vitest-environment jsdom
import React, { act } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { createRoot, type Root } from "react-dom/client";

const mocks = vi.hoisted(() => ({ apiFetch: vi.fn() }));
vi.mock("../../lib/backend", () => ({ apiUrl: (path: string) => path, apiFetch: mocks.apiFetch }));
vi.mock("../../context/I18nContext", () => ({ useTranslation: () => ({ t: (key: string) => key }) }));
vi.mock("../../lib/desktop", () => ({ saveTextFile: vi.fn() }));

import { PivotGrid } from "../PivotGrid";

const response = (body: unknown) => new Response(JSON.stringify(body), { status: 200 });
let host: HTMLDivElement;
let root: Root;
const flush = async () => { await act(async () => { await Promise.resolve(); await Promise.resolve(); }); };

beforeEach(() => {
  (globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  mocks.apiFetch.mockReset();
});
afterEach(async () => { await act(async () => root.unmount()); host.remove(); });

it("never fabricates pivot rows and states the empty basis explicitly", async () => {
  mocks.apiFetch.mockImplementation(() => Promise.resolve(response(
    { dimensions: ["symbol"], total_buckets: 0, rows: [], basis: "NO_CLOSED_TRADES" })));
  await act(async () => root.render(<PivotGrid />));
  await flush();

  const empty = host.querySelector('[data-testid="pivot-empty"]');
  expect(empty?.textContent).toContain("analytics.pivot_empty_title");
  expect(host.querySelectorAll("tbody tr")).toHaveLength(0);
  expect(host.textContent).not.toContain("9450");
});
