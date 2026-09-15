// @vitest-environment jsdom
import React, { act } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  t: (key: string, params?: Record<string, string | number>) =>
    params ? `${key}:${Object.values(params).join("|")}` : key,
}));

vi.mock("../../context/I18nContext", () => ({
  useTranslation: () => ({ t: mocks.t }),
}));

import { PortfolioKpiGrid, type PortfolioSummaryData } from "../dashboard/PortfolioKpiGrid";
import { createRoot } from "react-dom/client";

const baseSummary: PortfolioSummaryData = {
  initial_balance: 5000,
  total_equity: 5071.5,
  net_pnl: 71.5,
  net_pnl_pct: 1.43,
  today_pnl: 71.5,
  today_pnl_pct: 1.43,
  today_trades_count: { wins: 1, losses: 0, total: 1 },
  open_risk_usd: 0,
  open_risk_r: 0,
  active_positions_count: 1,
  total_closed_trades: 1,
  win_rate: 100,
  profit_factor: 999,
  avg_r_multiple: null,
  max_drawdown_usd: 0,
  max_drawdown_pct: 0,
  unknown_pnl_trades: 0,
  unverified_open_positions: 1,
  known_r_trades: 0,
  open_risk_basis: "NOT_AVAILABLE",
  profit_factor_basis: "INFINITE_NO_LOSS",
};

let host: HTMLDivElement;
let root: ReturnType<typeof createRoot>;

beforeEach(async () => {
  (globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
  host = document.createElement("div");
  document.body.append(host);
  const { createRoot: create } = await import("react-dom/client");
  root = create(host);
});

afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
});

it("shows unknown average R and open risk as unavailable, not zero", async () => {
  await act(async () => root.render(<PortfolioKpiGrid summary={baseSummary} />));

  expect(host.textContent).toContain("portfolio.no_r_data");
  expect(host.textContent).not.toContain("+0.00R");
  expect(host.textContent).toContain("portfolio.open_risk_unverified:1");
  expect(host.textContent).not.toContain("$0.00 (1 header.positions)");
  expect(host.textContent).toContain("portfolio.no_losses");
});

it("keeps zero drawdown without a negative sign", async () => {
  await act(async () => root.render(<PortfolioKpiGrid summary={baseSummary} />));

  expect(host.textContent).toContain("0.00%");
  expect(host.textContent).not.toContain("-0.00%");
});

it("shows a computed average R only when R observations exist", async () => {
  await act(async () => root.render(
    <PortfolioKpiGrid
      summary={{
        ...baseSummary,
        known_r_trades: 3,
        avg_r_multiple: 1.25,
        open_risk_basis: "COMPLETE",
        open_risk_usd: 120.5,
        open_risk_r: 1,
        profit_factor: 2.1,
        profit_factor_basis: "READY",
      }}
    />,
  ));

  expect(host.textContent).toContain("+1.25R");
  expect(host.textContent).toContain("portfolio.r_over_trades:3");
  expect(host.textContent).toContain("$120.50 (1 header.positions)");
  expect(host.textContent).not.toContain("portfolio.open_risk_unverified");
});
