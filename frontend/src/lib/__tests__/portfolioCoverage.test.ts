import { expect, it } from "vitest";
import { closedResultCoverage, validDailyResultCounts, validRealizedCoverage } from "../portfolioCoverage";

it("rejects overlapping daily outcomes, preserving flat and legacy samples", () => {
  expect(validDailyResultCounts({ total: 1, wins: 1, losses: 0, unknown_pnl: 1 })).toBe(false);
  expect(validDailyResultCounts({ total: 3, wins: 1, losses: 1, unknown_pnl: 0 })).toBe(true);
  expect(validDailyResultCounts({ total: 3, wins: 1, losses: 0 })).toBe(true);
  expect(validDailyResultCounts({ total: 0, wins: 0, losses: 0, unknown_pnl: 0 })).toBe(true);
  expect(validDailyResultCounts({ total: 1, wins: -1, losses: 0 })).toBe(false);
  expect(validDailyResultCounts({ total: 1, wins: 0.5, losses: 0 })).toBe(false);
  expect(validDailyResultCounts({ total: 1, wins: 0, losses: 0, unknown_pnl: 2 })).toBe(false);
});

it("distinguishes empty, unknown, partial and complete without manufacturing results", () => {
  expect(closedResultCoverage(0)).toEqual({ basis: "NO_DATA", total: 0, known: 0, unknown: 0 });
  expect(closedResultCoverage(2, 2)).toEqual({ basis: "NOT_AVAILABLE", total: 2, known: 0, unknown: 2 });
  expect(closedResultCoverage(3, 1)).toEqual({ basis: "PARTIAL", total: 3, known: 2, unknown: 1 });
  expect(closedResultCoverage(1, 0)).toEqual({ basis: "COMPLETE", total: 1, known: 1, unknown: 0 });
  expect(closedResultCoverage(1).known).toBeNull();
});

it.each([-1, 1.5, Number.NaN, Number.POSITIVE_INFINITY])("rejects malformed count %s", (value) => {
  expect(validRealizedCoverage({ total_closed_trades: value })).toBe(false);
  expect(closedResultCoverage(2, value).known).toBeNull();
});

it("rejects contradictory additive coverage, preserving legacy responses", () => {
  const valid = { initial_balance: 1000, total_closed_trades: 3, unknown_pnl_trades: 1,
    known_pnl_trades: 2, realized_pnl_basis: "PARTIAL", drawdown_pct_basis: "PARTIAL" };
  expect(validRealizedCoverage(valid)).toBe(true);
  expect(validRealizedCoverage({ ...valid, known_pnl_trades: 3 })).toBe(false);
  expect(validRealizedCoverage({ ...valid, realized_pnl_basis: "COMPLETE" })).toBe(false);
  expect(validRealizedCoverage({ ...valid, drawdown_pct_basis: "READY" })).toBe(false);
  expect(validRealizedCoverage({ ...valid, unknown_pnl_trades: 4 })).toBe(false);
  expect(validRealizedCoverage({ initial_balance: 1000, total_closed_trades: 3 })).toBe(true);
  expect(validRealizedCoverage({ ...valid, initial_balance: 0, drawdown_pct_basis: "NOT_AVAILABLE" })).toBe(true);
});
