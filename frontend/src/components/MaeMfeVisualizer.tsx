import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { MaeMfeAnalyticsResponse, MaeMfePoint } from "../types";
import { Crosshair, ShieldAlert, TrendingUp } from "lucide-react";
import { useTranslation } from "../context/I18nContext";
import { apiFetch, apiUrl } from "../lib/backend";

export const finite = (value: unknown): value is number => typeof value === "number" && Number.isFinite(value);
export const plotEligible = (point: MaeMfePoint) => finite(point.mae_r) && finite(point.mfe_r);
export const matchesSide = (side: string, filter: string) => filter === "ALL" || (filter === "BUY" ? side === "BUY" || side === "LONG" : side === "SELL" || side === "SHORT");
const display = (value: unknown, suffix = "") => finite(value) ? `${value.toFixed(2)}${suffix}` : "—";

const nullableFinite = (value: unknown) => value === null || finite(value);

function isMaeMfePoint(value: unknown): value is MaeMfePoint {
  if (!value || typeof value !== "object") return false;
  const point = value as Record<string, unknown>;
  return typeof point.trade_id === "string"
    && typeof point.symbol === "string"
    && typeof point.side === "string"
    && finite(point.entry_price)
    && finite(point.exit_price)
    && ["risk_unit", "mae_price", "mfe_price", "mae_r", "mfe_r", "exit_efficiency", "pnl", "r_multiple"]
      .every((field) => nullableFinite(point[field]))
    && (point.stop_loss === undefined || nullableFinite(point.stop_loss))
    && (point.take_profit === undefined || nullableFinite(point.take_profit))
    && typeof point.status === "string"
    && (point.entry_time === undefined || typeof point.entry_time === "string")
    && (point.exit_time === undefined || typeof point.exit_time === "string")
    && (point.risk_reason === undefined || point.risk_reason === null || typeof point.risk_reason === "string");
}

function isStopSensitivity(value: unknown): boolean {
  if (!value || typeof value !== "object") return false;
  const sensitivity = value as Record<string, unknown>;
  return finite(sensitivity.stop_distance_r)
    && finite(sensitivity.survival_rate_pct)
    && (sensitivity.sample_size === undefined || finite(sensitivity.sample_size));
}

function isMaeMfeResponse(value: unknown): value is MaeMfeAnalyticsResponse {
  if (!value || typeof value !== "object") return false;
  const response = value as Record<string, unknown>;
  return (response.status === "READY" || response.status === "NO_DATA" || response.status === "UNAVAILABLE")
    && (response.reason === null || typeof response.reason === "string")
    && (response.message === null || typeof response.message === "string")
    && (response.provenance === null || typeof response.provenance === "object")
    && ["total_candidates", "total_analyzed", "total_r_analyzed", "trades_left_money_on_table"]
      .every((field) => finite(response[field]) && (response[field] as number) >= 0)
    && ["average_mae_r", "average_mfe_r", "average_exit_efficiency_pct", "recommended_target_r"]
      .every((field) => nullableFinite(response[field]))
    && Array.isArray(response.excluded_trades)
    && response.excluded_trades.every((item) => {
      if (!item || typeof item !== "object") return false;
      const excluded = item as Record<string, unknown>;
      return typeof excluded.trade_id === "string"
        && typeof excluded.reason === "string"
        && typeof excluded.message === "string";
    })
    && Array.isArray(response.stop_loss_sensitivities)
    && response.stop_loss_sensitivities.every(isStopSensitivity)
    && Array.isArray(response.points)
    && response.points.every(isMaeMfePoint);
}

async function readMaeMfeResponse(response: Response): Promise<MaeMfeAnalyticsResponse> {
  if (!response.ok) {
    let detail = "";
    try {
      const payload = await response.json() as { detail?: unknown; message?: unknown; reason?: unknown };
      const candidate = [payload.detail, payload.message, payload.reason].find((item) => typeof item === "string");
      if (typeof candidate === "string") detail = candidate;
    } catch {
      // Keep the HTTP status as the bounded error when the body is not JSON.
    }
    throw new Error(detail || `MAE/MFE request failed (HTTP ${response.status})`);
  }

  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new Error("MAE/MFE response was malformed");
  }
  if (!isMaeMfeResponse(payload)) throw new Error("MAE/MFE response was malformed");
  return payload;
}

export const MaeMfeVisualizer: React.FC = () => {
  const { t } = useTranslation();
  const [data, setData] = useState<MaeMfeAnalyticsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [cancelled, setCancelled] = useState(false);
  const [filterSide, setFilterSide] = useState("ALL");
  const [hoveredPoint, setHoveredPoint] = useState<MaeMfePoint | null>(null);
  const loadControllerRef = useRef<AbortController | null>(null);
  const requestIdRef = useRef(0);

  const loadAnalytics = useCallback(async () => {
    loadControllerRef.current?.abort();
    const controller = new AbortController();
    const requestId = ++requestIdRef.current;
    loadControllerRef.current = controller;
    setIsLoading(true);
    setError(null);
    setCancelled(false);
    setData(null);
    setHoveredPoint(null);

    try {
      const response = await apiFetch(apiUrl("/api/v1/analytics/mae-mfe"), { signal: controller.signal });
      const result = await readMaeMfeResponse(response);
      if (controller.signal.aborted || requestId !== requestIdRef.current) return;
      setData(result);
    } catch (cause) {
      if (controller.signal.aborted || requestId !== requestIdRef.current) return;
      if (!(cause instanceof Error && cause.name === "AbortError")) {
        console.warn("[MaeMfeVisualizer] Failed to fetch excursion analytics:", cause);
        setError(cause instanceof Error ? cause.message : t("mae_mfe.error"));
      }
    } finally {
      if (requestId === requestIdRef.current) {
        setIsLoading(false);
        loadControllerRef.current = null;
      }
    }
  }, [t]);

  useEffect(() => {
    void loadAnalytics();
    return () => {
      requestIdRef.current += 1;
      loadControllerRef.current?.abort();
      loadControllerRef.current = null;
    };
  }, [loadAnalytics]);

  const cancelLoad = () => {
    const controller = loadControllerRef.current;
    if (!controller) return;
    requestIdRef.current += 1;
    controller.abort();
    loadControllerRef.current = null;
    setIsLoading(false);
    setCancelled(true);
    setError(t("mae_mfe.cancelled"));
    setData(null);
    setHoveredPoint(null);
  };

  const points = useMemo(() => (data?.points || []).filter((point) => matchesSide(point.side.toUpperCase(), filterSide) && plotEligible(point)), [data, filterSide]);
  const diagnostics = (content: React.ReactNode) => <details className="text-sm text-muted text-left"><summary className="cursor-pointer focus-visible:outline focus-visible:outline-accent">{t("mae_mfe.diagnostics")}</summary><div className="mt-2 break-words">{content}</div></details>;
  if (isLoading) return <State role="status" testId="mae-mfe-loading" title={t("mae_mfe.loading")} detail={t("mae_mfe.loading_detail")} actionLabel={t("mae_mfe.cancel_load")} onAction={cancelLoad} />;
  if (error) return <State role="alert" testId={cancelled ? "mae-mfe-cancelled" : "mae-mfe-error"} title={cancelled ? t("mae_mfe.cancelled") : t("mae_mfe.error")} detail={t(cancelled ? "mae_mfe.cancelled" : "mae_mfe.error_detail")} diagnostics={cancelled ? undefined : diagnostics(error)} actionLabel={t("mae_mfe.retry")} onAction={() => void loadAnalytics()} />;
  if (!data || data.status !== "READY") {
    const noData = data?.status === "NO_DATA";
    return <State
      role={noData ? "status" : "alert"}
      testId={noData ? "mae-mfe-no-data" : "mae-mfe-unavailable"}
      title={t(noData ? "mae_mfe.no_data_title" : "mae_mfe.unavailable_title")}
      detail={t(noData ? "mae_mfe.no_data_detail" : "mae_mfe.unavailable_detail")}
      diagnostics={data && diagnostics(<>{data.reason}<br />{data.message}</>)}
      actionLabel={noData ? undefined : t("mae_mfe.retry")}
      onAction={noData ? undefined : () => void loadAnalytics()}
    />;
  }
  const width = 640, height = 360, padding = 45;
  const minX = points.length ? Math.min(-0.1, ...points.map((p) => p.mae_r!)) : -1;
  const maxY = points.length ? Math.max(1, ...points.map((p) => p.mfe_r!)) : 1;
  const x = (value: number) => padding + ((Math.max(minX, Math.min(0, value)) - minX) / (0 - minX || 1)) * (width - 2 * padding);
  const y = (value: number) => height - padding - (Math.max(0, Math.min(maxY, value)) / maxY) * (height - 2 * padding);
  return <div className="flex-1 flex flex-col h-full bg-background text-ink overflow-y-auto p-4 font-sans space-y-4">
    <div className="pb-3 border-b border-surface-border flex flex-wrap items-center justify-between gap-3">
      <div className="flex-1 min-w-0"><h2 className="text-base font-bold flex items-center gap-2"><Crosshair className="w-4 h-4 shrink-0 text-accent" />{t("mae_mfe.title")}</h2><p data-testid="mae-mfe-boundary" className="text-sm text-warn mt-2">{t("mae_mfe.boundary")}</p></div>
      <select aria-label={t("mae_mfe.side_filter")} value={filterSide} onChange={(e) => setFilterSide(e.target.value)} className="k-input w-auto"><option value="ALL">{t("mae_mfe.all_trades")}</option><option value="BUY">{t("mae_mfe.long_only")}</option><option value="SELL">{t("mae_mfe.short_only")}</option></select>
    </div>
    <div className="text-sm text-muted">{t("mae_mfe.counts", { candidates: data.total_candidates, analyzed: data.total_analyzed, samples: data.total_r_analyzed })}</div>
    {!points.length ? <State title={t("mae_mfe.no_risk_title")} detail={t("mae_mfe.no_risk_detail")} /> : <><div className="grid grid-cols-1 md:grid-cols-4 gap-3"><Metric label={t("mae_mfe.avg_exit_efficiency")} value={display(data.average_exit_efficiency_pct, "%")} /><Metric label={t("mae_mfe.target_unavailable")} value="—" detail={t("mae_mfe.no_target")} /><Metric label={t("mae_mfe.money_on_table")} value={String(data.trades_left_money_on_table)} /><Metric label={t("mae_mfe.avg_adverse_excursion")} value={display(data.average_mae_r, " R")} /></div>
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4"><div className="lg:col-span-2 bg-surface p-4 rounded-lg border border-surface-border relative"><div className="text-sm text-ink font-bold mb-2 flex gap-2"><TrendingUp className="w-3.5 h-3.5 text-accent" />{t("mae_mfe.finite_points")}</div><svg width={width} height={height} className="max-w-full"><rect x={padding} y={padding} width={width - 2 * padding} height={height - 2 * padding} fill="var(--bg-deep)" stroke="var(--border-color)" /><text x={padding} y={height - 12} fill="var(--text-muted)" fontSize="12">{minX.toFixed(2)}R</text><text x={width - padding} y={height - 12} fill="var(--text-muted)" fontSize="12" textAnchor="end">0.00R</text><text x={padding + 4} y={padding - 8} fill="var(--text-muted)" fontSize="12">MFE 0.00R → {maxY.toFixed(2)}R</text>{points.map((point) => <circle key={point.trade_id} cx={x(point.mae_r!)} cy={y(point.mfe_r!)} r={hoveredPoint?.trade_id === point.trade_id ? 7 : 5} fill={point.pnl === null ? "#94a3b8" : point.pnl > 0 ? "#10b981" : point.pnl < 0 ? "#ef4444" : "#94a3b8"} onMouseEnter={() => setHoveredPoint(point)} onMouseLeave={() => setHoveredPoint(null)} />)}</svg>{hoveredPoint && <div className="absolute top-8 right-6 p-3 text-sm bg-elevated border border-accent rounded"><b>{hoveredPoint.trade_id}</b><br />MAE {display(hoveredPoint.mae_r, " R")} • MFE {display(hoveredPoint.mfe_r, " R")}<br />{t("mae_mfe.pnl_label")} {display(hoveredPoint.pnl)} • R {display(hoveredPoint.r_multiple)}</div>}</div>
    <div className="bg-surface p-4 rounded-lg border border-surface-border"><h3 className="text-sm font-bold text-ink flex gap-2"><ShieldAlert className="w-3.5 h-3.5 text-warn" />{t("mae_mfe.sensitivity_title")}</h3><p className="text-sm text-muted mt-2">{t("mae_mfe.sensitivity_detail")}</p>{data.stop_loss_sensitivities.length ? <div className="mt-3 space-y-2">{data.stop_loss_sensitivities.map((s) => <div key={s.stop_distance_r} className="text-sm"><div className="flex justify-between"><span>{s.stop_distance_r.toFixed(2)} R</span><span>{t("mae_mfe.observed_pct", { pct: s.survival_rate_pct })}</span></div><div className="h-2 bg-elevated"><div className="h-full bg-accent" style={{ width: `${Math.max(0, Math.min(100, s.survival_rate_pct))}%` }} /></div></div>)}</div> : <p className="text-sm text-muted mt-3">{t("mae_mfe.sensitivity_empty")}</p>}</div></div></>}
    {data.excluded_trades.length > 0 && <div className="text-sm text-muted"><p>{t("mae_mfe.excluded", { count: data.excluded_trades.length })}</p>{diagnostics(data.excluded_trades.map((trade) => `${trade.trade_id} (${trade.reason})`).join(", "))}</div>}
  </div>;
};
const Metric = ({ label, value, detail }: { label: string; value: string; detail?: string }) => <div className="k-card"><span className="text-sm text-muted block">{label}</span><span className="text-xl font-bold text-ink">{value}</span>{detail && <span className="text-sm text-muted block">{detail}</span>}</div>;
const State = ({
  title,
  detail,
  role = "status",
  testId,
  actionLabel,
  onAction,
  diagnostics,
}: {
  title: string;
  detail: string;
  role?: "status" | "alert";
  testId?: string;
  actionLabel?: string;
  onAction?: () => void;
  diagnostics?: React.ReactNode;
}) => <div role={role} data-testid={testId} className="p-8 text-center text-muted font-sans space-y-3"><p className="font-bold text-white text-base">{title}</p><p className="text-sm">{detail}</p>{diagnostics}{actionLabel && onAction && <button type="button" onClick={onAction} data-testid={testId === "mae-mfe-loading" ? "mae-mfe-cancel" : "mae-mfe-retry"} className="k-btn">{actionLabel}</button>}</div>;
