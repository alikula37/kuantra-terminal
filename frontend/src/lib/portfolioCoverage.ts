export type ResultBasis = "NO_DATA" | "NOT_AVAILABLE" | "PARTIAL" | "COMPLETE";
export interface ResultCoverage {
  basis: ResultBasis;
  total: number;
  known: number | null;
  unknown: number | null;
}

const count = (value: unknown): value is number =>
  typeof value === "number" && Number.isSafeInteger(value) && value >= 0;

/** Wins/losses, flat results and unknown outcomes must be disjoint counts. */
export function validDailyResultCounts(value: unknown): boolean {
  if (!value || typeof value !== "object") return false;
  const sample = value as Record<string, unknown>;
  if (!count(sample.total) || !count(sample.wins) || !count(sample.losses)) return false;
  if (sample.unknown_pnl !== undefined && !count(sample.unknown_pnl)) return false;
  const unknown = (sample.unknown_pnl as number | undefined) ?? 0;
  return unknown <= sample.total && sample.wins + sample.losses <= sample.total - unknown;
}

/** Count coverage only. No performance arithmetic or missing-as-zero inference. */
export function closedResultCoverage(total: number, unknown?: number): ResultCoverage {
  if (!count(total) || (unknown !== undefined && (!count(unknown) || unknown > total))) {
    return { basis: "NOT_AVAILABLE", total, known: null, unknown: null };
  }
  if (total === 0) return { basis: "NO_DATA", total: 0, known: 0, unknown: 0 };
  if (unknown === undefined) return { basis: "NOT_AVAILABLE", total, known: null, unknown: null };
  const known = total - unknown;
  return { total, known, unknown,
    basis: known === 0 ? "NOT_AVAILABLE" : unknown > 0 ? "PARTIAL" : "COMPLETE" };
}

export function resultCoverageLabel(
  coverage: ResultCoverage,
  t: (key: string, params?: Record<string, string | number>) => string,
): string {
  if (coverage.basis === "NO_DATA") return t("portfolio.no_closed_results");
  if (coverage.known === null) return t("portfolio.result_coverage_unknown");
  if (coverage.basis === "NOT_AVAILABLE") return t("portfolio.results_unknown", { count: coverage.unknown ?? 0 });
  if (coverage.basis === "PARTIAL") return t("portfolio.known_results_partial", {
    known: coverage.known, total: coverage.total, unknown: coverage.unknown ?? 0,
  });
  return t("portfolio.known_results", { count: coverage.known });
}

/** Reject contradictory additive metadata instead of treating it as complete. */
export function validRealizedCoverage(value: Record<string, unknown>): boolean {
  if (!count(value.total_closed_trades)) return false;
  if (value.unknown_pnl_trades !== undefined &&
      (!count(value.unknown_pnl_trades) || value.unknown_pnl_trades > value.total_closed_trades)) return false;
  const coverage = closedResultCoverage(value.total_closed_trades, value.unknown_pnl_trades as number | undefined);
  if (value.known_pnl_trades !== undefined && value.known_pnl_trades !== coverage.known) return false;
  if (value.realized_pnl_basis !== undefined && value.realized_pnl_basis !== coverage.basis) return false;
  const pctBasis = (value.initial_balance as number) > 0 ? coverage.basis
    : value.total_closed_trades === 0 ? "NO_DATA" : "NOT_AVAILABLE";
  if (value.drawdown_pct_basis !== undefined && value.drawdown_pct_basis !== pctBasis) return false;
  return true;
}
