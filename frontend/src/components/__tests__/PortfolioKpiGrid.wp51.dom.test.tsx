// @vitest-environment jsdom
import React, { act } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { createRoot } from "react-dom/client";

vi.mock("../../context/I18nContext", () => ({ useTranslation: () => ({
  t: (key: string, params?: Record<string, string | number>) =>
    params ? `${key}:${Object.values(params).join("|")}` : key,
}) }));
import { PortfolioKpiGrid, type PortfolioSummaryData } from "../dashboard/PortfolioKpiGrid";
import { MultiAssetBreakdown, type AssetBreakdownItem } from "../dashboard/MultiAssetBreakdown";
import { PnlCalendarHeatmap } from "../dashboard/PnlCalendarHeatmap";

let host: HTMLDivElement;
let root: ReturnType<typeof createRoot>;
const base: PortfolioSummaryData = {
  initial_balance: 1000, total_equity: 1000, net_pnl: 0, net_pnl_pct: 0,
  today_pnl: 0, today_pnl_pct: 0, today_trades_count: { wins: 0, losses: 0, total: 0 },
  open_risk_usd: 0, open_risk_r: 0, active_positions_count: 0,
  total_closed_trades: 0, unknown_pnl_trades: 0, win_rate: 0,
  profit_factor: 0, avg_r_multiple: null, gross_profit: 0, gross_loss: 0,
  max_drawdown_usd: 0, max_drawdown_pct: 0,
};
const card = (key: string) => Array.from(host.querySelectorAll("span"))
  .find((el) => el.textContent === key)?.closest(".k-kpi-strip-item, .k-kpi") as HTMLElement;
const render = async (values: Partial<PortfolioSummaryData> = {}) => {
  await act(async () => root.render(<PortfolioKpiGrid summary={{ ...base, ...values }} />));
};
beforeEach(() => {
  (globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
  window.localStorage.clear();
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
});
afterEach(async () => { await act(async () => root.unmount()); host.remove(); });

it("does not present empty win rate/drawdown/profit factor as measured zero", async () => {
  await render();
  for (const key of ["portfolio.win_rate", "portfolio.max_drawdown", "portfolio.profit_factor"]) {
    expect(card(key).textContent).toContain("—");
    expect(card(key).textContent).toContain("portfolio.no_closed_results");
    expect(card(key).textContent).not.toContain("0.0%");
    expect(card(key).textContent).not.toContain("0.00%");
  }
  expect(host.textContent).toContain("$1,000.00"); // valid balance survives
});

it("keeps all-unknown results distinct from an empty journal", async () => {
  await render({ total_closed_trades: 2, unknown_pnl_trades: 2 });
  expect(card("portfolio.win_rate").textContent).toContain("portfolio.results_unknown:2");
  expect(card("portfolio.max_drawdown").textContent).toContain("portfolio.results_unknown:2");
  expect(card("portfolio.win_rate").textContent).not.toContain("0.0%");
});

it("shows the known denominator and incomplete coverage beside partial results", async () => {
  await render({ total_closed_trades: 3, unknown_pnl_trades: 1, win_rate: 50,
    max_drawdown_pct: 1, max_drawdown_usd: 10, profit_factor: 1, gross_profit: 10, gross_loss: 10 });
  expect(card("portfolio.win_rate").textContent).toContain("50.0%");
  expect(card("portfolio.win_rate").textContent).toContain("portfolio.known_results_partial:2|3|1");
  expect(card("portfolio.max_drawdown").textContent).toContain("portfolio.known_results_partial:2|3|1");
  expect(card("portfolio.profit_factor").textContent).toContain("portfolio.known_results_partial:2|3|1");
});

it("retains genuine zero win rate and drawdown but not a 0/0 profit ratio", async () => {
  await render({ total_closed_trades: 1 });
  expect(card("portfolio.win_rate").textContent).toContain("0.0%");
  expect(card("portfolio.max_drawdown").textContent).toContain("0.00%");
  expect(card("portfolio.win_rate").textContent).toContain("portfolio.known_results:1");
  expect(card("portfolio.profit_factor").textContent).toContain("portfolio.pf_no_gains_losses");
});

it("does not invent complete coverage for legacy responses missing unknown counts", async () => {
  await render({ total_closed_trades: 3, unknown_pnl_trades: undefined, win_rate: 50 });
  expect(card("portfolio.win_rate").textContent).toContain("portfolio.result_coverage_unknown");
  expect(card("portfolio.win_rate").textContent).not.toContain("50.0%");
});

it("keeps dollar drawdown but hides percentage without configured capital", async () => {
  await render({ initial_balance: 0, total_closed_trades: 1, max_drawdown_usd: 10, max_drawdown_pct: 0 });
  expect(card("portfolio.max_drawdown").textContent).toContain("portfolio.drawdown_no_capital");
  expect(card("portfolio.max_drawdown").textContent).not.toContain("0.00%");
  expect(card("portfolio.max_drawdown").textContent).toContain("10.00");
});

it("shows unavailable open PnL instead of an entry-price zero", async () => {
  await render({ active_positions_count: 1, live_equity: null, live_equity_basis: "NOT_AVAILABLE",
    live_positions_covered: 0, live_positions_unpriced: 1, unrealized_pnl_usd: 0 });
  expect(card("portfolio.open_unrealized").textContent).toContain("—");
  expect(card("portfolio.open_unrealized").textContent).not.toContain("+$0.00");
});

it("labels partial open PnL and preserves a priced zero", async () => {
  await render({ active_positions_count: 2, live_equity: 1000, live_equity_basis: "PARTIAL",
    live_positions_covered: 1, live_positions_unpriced: 1, unrealized_pnl_usd: 0 });
  expect(card("portfolio.open_unrealized").textContent).toContain("+$0.00");
  expect(card("portfolio.open_unrealized").textContent).toContain("portfolio.live_equity_partial:1");
});

it("never counts a known break-even today as an unknown result", async () => {
  await render({ today_trades_count: { wins: 0, losses: 0, total: 1, unknown_pnl: 0 } } as any);
  expect(card("portfolio.today_pnl").textContent).not.toContain("portfolio.today_unknown");
  expect(card("portfolio.today_pnl").textContent).toContain("portfolio.today_break_even:1");
});

it("shows unknown daily PnL as unavailable and does not show performance while loading", async () => {
  await render({ today_trades_count: { wins: 0, losses: 0, total: 1, unknown_pnl: 1 } } as any);
  expect(card("portfolio.today_pnl").textContent).toContain("—");
  expect(card("portfolio.today_pnl").textContent).not.toContain("+$0.00");
  await act(async () => root.render(<PortfolioKpiGrid summary={base} loading />));
  expect(host.textContent).not.toContain("portfolio.no_closed_results");
  expect(host.textContent).not.toContain("0.0%");
});

const asset: AssetBreakdownItem = { symbol: "XAUUSD", asset_class: "commodity", net_pnl: 0,
  pnl_percentage: 0, trade_count: 1, closed_count: 1, open_positions: 0,
  win_rate: 0, total_volume: 200, unknown_pnl_trades: 1 };

it("does not draw an artificial profit bar or WR for an all-unknown instrument", async () => {
  await act(async () => root.render(<MultiAssetBreakdown items={[asset]} />));
  expect(host.textContent).toContain("portfolio.results_unknown:1");
  expect(host.textContent).not.toContain("+$0.00");
  expect(host.textContent).not.toContain("0% WR");
  expect(host.querySelector('[style*="width: 8%"]')).toBeNull();
});

it("uses known closed sample counts for instrument WR, not open/unknown trades", async () => {
  await act(async () => root.render(<MultiAssetBreakdown items={[{ ...asset, closed_count: 3,
    open_positions: 1, trade_count: 4, net_pnl: 10, win_rate: 50 }]} />));
  expect(host.textContent).toContain("portfolio.known_results_partial:2|3|1");
  expect(host.textContent).toContain("breakdown.win_rate:50");
});

it("does not summarize an empty heatmap as a measured net gain", async () => {
  await act(async () => root.render(<PnlCalendarHeatmap data={[]} />));
  expect(host.textContent).not.toContain("+$0.00");
  expect(host.textContent).toContain("portfolio.no_known_results");
});

it("does not label an all-unknown realized delta as zero profit while keeping configured cash", async () => {
  await render({ total_closed_trades: 1, unknown_pnl_trades: 1 });
  expect(host.querySelector(".k-kpi-delta")?.textContent).not.toContain("$0.00");
  expect(host.querySelector(".k-kpi-delta")?.textContent).toContain("portfolio.results_unknown:1");
  expect(host.textContent).toContain("$1,000.00");
});

it("keeps a real flat instrument and heatmap neutral, not unavailable", async () => {
  await act(async () => root.render(<MultiAssetBreakdown items={[{ ...asset, unknown_pnl_trades: 0 }]} />));
  expect(host.textContent).toContain("+$0.00");
  expect(host.textContent).toContain("portfolio.known_results:1");
  expect(host.querySelector('[style*="width: 8%"]')).toBeNull();
  await act(async () => root.render(<PnlCalendarHeatmap data={[{
    date: "2026-10-02", pnl: 0, trades_count: 1, wins: 0, losses: 0, win_rate: 0, intensity: 0,
  }]} />));
  expect(host.textContent).toContain("+$0.00");
  expect(host.textContent).not.toContain("portfolio.no_known_results");
});
