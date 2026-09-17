import React, { useEffect, useRef, useState } from "react";
import { createChart, IChartApi, IPriceLine, ISeriesApi, LineStyle } from "lightweight-charts";
import { OpenReviewBlock, ReplayCloseEvidence, ReplayPlanReference, ReplaySessionResponse } from "../types";
import { formatIstanbulDateTime } from "../lib/tradeTime";
import { Play, Pause, SkipBack, SkipForward, FastForward, RotateCcw } from "lucide-react";
import { apiBase, apiFetch } from "../lib/backend";
import { useTranslation } from "../context/I18nContext";
import { useTheme } from "../context/ThemeContext";

interface TradeReplayCanvasProps { tradeId?: string; }
export const isFiniteNumber = (value: unknown): value is number => typeof value === "number" && Number.isFinite(value);
export const canRenderReplayChart = (session: ReplaySessionResponse | null) => Boolean(session?.status === "READY" && session.session_id && session.visible_candles.length);
export const shouldApplyReplayResponse = (responseGeneration: number, currentGeneration: number) => responseGeneration === currentGeneration;

const KNOWN_REASONS = new Set([
  "TRADE_NOT_CLOSED", "TRADE_NOT_FOUND", "CANDLE_STORE_UNAVAILABLE", "CANDLE_ROW_LIMIT",
  "WINDOW_TOO_LARGE", "NO_DATA", "NO_CANDLE_HISTORY", "INCOMPLETE_CANDLE_HISTORY",
  "CANDLE_IDENTITY_MISMATCH", "CONFLICTING_CANDLES", "UNALIGNED_CANDLE",
  "INVALID_CANDLE_PROVENANCE", "INVALID_OHLC", "INVALID_TIMESTAMP", "INVALID_VOLUME",
  "INVALID_TRADE", "INVALID_TRADE_WINDOW", "INVALID_CONTEXT_WINDOW",
  "NO_CACHED_CANDLES", "NO_CANDLES_SINCE_ENTRY", "TRADE_NOT_OPEN", "REFRESH_FAILED",
  "PROVIDER_MATCH_REQUIRED", "PROVIDER_NOT_DECLARED", "PROVIDER_IDENTITY_MISMATCH",
  "PROVIDER_NOT_SUPPORTED", "PROVIDER_INSTRUMENT_UNSUPPORTED", "PROVIDER_FETCH_FAILED",
]);

export const formatLevelPrice = (price: number): string => {
  const magnitude = Math.abs(price);
  return magnitude >= 100 ? price.toFixed(2) : magnitude >= 1 ? price.toFixed(3) : price.toFixed(5);
};

export const formatWeight = (weight: number): string => {
  const rounded = Math.round(weight * 100) / 100;
  return `${Number.isInteger(rounded) ? rounded : rounded.toFixed(2).replace(/0+$/, "").replace(/\\.$/, "")}%`;
};

export const levelLabelKey = (kind: string): string => {
  if (kind === "ENTRY") return "replay.level.entry";
  if (kind === "SL") return "replay.level.stop";
  return "replay.level.take_profit";
};

export const closeSourceKey = (source: ReplayCloseEvidence["source"] | undefined): string => {
  switch (source) {
    case "USER_REPORTED": return "replay.close_source.user";
    case "IMPORTED_FILE": return "replay.close_source.imported";
    case "SIMULATION": return "replay.close_source.simulation";
    case "SOURCE_DECLARED": return "replay.close_source.source_declared";
    default: return "replay.close_source.unknown";
  }
};

/** Raw close value stays visible for declarations and unknown sources. */
export const showsRawCloseSource = (evidence: ReplayCloseEvidence | null | undefined): boolean =>
  Boolean(evidence && (evidence.source === "SOURCE_DECLARED" || evidence.source === "UNKNOWN") && evidence.close_source_raw);

export const originKey = (origin: string | null | undefined): string => {
  if (origin === "JOURNAL") return "replay.origin.journal";
  if (origin === "IMPORTED_FILE") return "replay.origin.imported_file";
  return "replay.origin.unknown";
};

const LEVEL_COLORS: Record<string, string> = {
  ENTRY: "#38bdf8", SL: "#e11d48", TP1: "#10b981", TP2: "#22c55e", TP3: "#14b8a6", TP4: "#06b6d4",
};

const PlanLevels: React.FC<{ plan: ReplayPlanReference | null | undefined }> = ({ plan }) => {
  const { t } = useTranslation();
  if (!plan || plan.levels.length === 0) return null;
  return (
    <ul data-testid="replay-levels" className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
      {plan.levels.map((level) => (
        <li key={level.kind} data-testid={`replay-level-${level.kind}`} className="flex items-center gap-1.5">
          <span className="inline-block w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: LEVEL_COLORS[level.kind] ?? "#94a3b8" }} aria-hidden="true" />
          <span className="text-slate-400">{t(levelLabelKey(level.kind))}{level.kind.startsWith("TP") ? ` ${level.kind}` : ""}</span>
          <span className="font-bold text-white">{formatLevelPrice(level.price)}</span>
          {isFiniteNumber(level.weight_pct ?? null) && (
            <span className="text-slate-400">{t("replay.level.weight", { weight: formatWeight(level.weight_pct as number) })}</span>
          )}
        </li>
      ))}
    </ul>
  );
};

const MarketInfo: React.FC<{ session: ReplaySessionResponse }> = ({ session }) => {
  const { t } = useTranslation();
  const context = (session.market_context ?? {}) as Record<string, unknown>;
  const gapCount = isFiniteNumber(context.sequence_gap_count) ? Number(context.sequence_gap_count) : 0;
  const text = (key: string, fallback: string) => (typeof context[key] === "string" && context[key] ? String(context[key]) : fallback);
  return (
    <div className="px-3 py-1 text-[10px] text-slate-400 flex flex-wrap gap-x-4 gap-y-1 border-b border-surface-border">
      <span data-testid="replay-source-strip">
        {`${text("symbol", session.symbol ?? "—")} · ${text("venue", "UNVERIFIED")} · ${text("feed", "UNVERIFIED")} · ${text("timeframe", session.provenance?.timeframe ?? "1m")}`}
      </span>
      {gapCount > 0 && (
        <span data-testid="replay-gap-note" className="text-amber-300">{t("replay.source_strip.gap_note", { count: gapCount })}</span>
      )}
      <span data-testid="replay-disclaimer" className="text-amber-300">{t("replay.disclaimer")}</span>
    </div>
  );
};

export const TradeReplayCanvas: React.FC<TradeReplayCanvasProps> = ({ tradeId = "TRD-DEFAULT" }) => {
  const { t, locale } = useTranslation();
  const { getChartTheme } = useTheme();
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const priceLinesRef = useRef<IPriceLine[]>([]);
  const stepInFlight = useRef(false);
  const generationRef = useRef(0);
  const updateAbortRef = useRef<AbortController | null>(null);
  const [session, setSession] = useState<ReplaySessionResponse | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isStepPending, setIsStepPending] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshState, setRefreshState] = useState<"idle" | "refreshing" | "error">("idle");

  useEffect(() => {
    const generation = ++generationRef.current;
    updateAbortRef.current?.abort(); stepInFlight.current = false; setIsStepPending(false);
    const controller = new AbortController(); let active = true;
    setIsLoading(true); setError(null); setSession(null); setIsPlaying(false); setRefreshState("idle");
    (async () => {
      try {
        const res = await apiFetch(`${apiBase()}/api/v1/replay/session/${encodeURIComponent(tradeId)}`, { signal: controller.signal });
        const data = await res.json() as ReplaySessionResponse;
        if (!res.ok) throw new Error(data.message || data.reason || `Replay request failed (${res.status})`);
        if (active && shouldApplyReplayResponse(generation, generationRef.current)) setSession(data);
      } catch (cause) {
        if (active && shouldApplyReplayResponse(generation, generationRef.current) && !(cause instanceof DOMException && cause.name === "AbortError")) setError(cause instanceof Error ? cause.message : "Replay request failed.");
      } finally { if (active && shouldApplyReplayResponse(generation, generationRef.current)) setIsLoading(false); }
    })();
    return () => {
      active = false; controller.abort();
      if (generationRef.current === generation) {
        generationRef.current++; updateAbortRef.current?.abort(); updateAbortRef.current = null;
        stepInFlight.current = false;
      }
    };
  }, [tradeId]);

  useEffect(() => {
    if (!canRenderReplayChart(session) || !chartContainerRef.current) return;
    const container = chartContainerRef.current;
    const chartTheme = getChartTheme();
    const chart = createChart(container, {
      width: container.clientWidth, height: container.clientHeight,
      layout: chartTheme.layout, grid: chartTheme.grid,
      timeScale: { borderColor: chartTheme.grid.horzLines.color, timeVisible: true, secondsVisible: false },
      rightPriceScale: { borderColor: chartTheme.grid.horzLines.color, scaleMargins: { top: 0.1, bottom: 0.15 } },
    });
    const series = chart.addCandlestickSeries(chartTheme.candlestick);
    chartRef.current = chart; candleSeriesRef.current = series;
    const resize = () => chart.applyOptions({ width: container.clientWidth, height: container.clientHeight });
    window.addEventListener("resize", resize);
    return () => {
      window.removeEventListener("resize", resize);
      priceLinesRef.current = [];
      candleSeriesRef.current = null; chartRef.current = null; chart.remove();
    };
    // The chart is created once per READY session; the theme is applied at this point.
  }, [session?.session_id, session?.status]);

  useEffect(() => {
    if (!candleSeriesRef.current || !session || session.status !== "READY") return;
    candleSeriesRef.current.setData(session.visible_candles.map((c) => ({ time: c.time as any, open: c.open, high: c.high, low: c.low, close: c.close })));
  }, [session?.visible_candles, session?.current_index, session?.status]);

  // Plan level lines are rebuilt per session; the previous trade's lines are
  // removed first so a late or replaced session can never leave stale levels.
  useEffect(() => {
    const series = candleSeriesRef.current;
    if (!series) return;
    for (const line of priceLinesRef.current) series.removePriceLine(line);
    priceLinesRef.current = [];
    if (!session || session.status !== "READY" || !session.plan) return;
    for (const level of session.plan.levels) {
      const weight = isFiniteNumber(level.weight_pct ?? null) ? ` · ${formatWeight(level.weight_pct as number)}` : "";
      const line = series.createPriceLine({
        price: level.price,
        color: LEVEL_COLORS[level.kind] ?? "#94a3b8",
        lineWidth: 1,
        lineStyle: level.kind === "ENTRY" ? LineStyle.Solid : LineStyle.Dashed,
        axisLabelVisible: true,
        title: `${level.kind} ${formatLevelPrice(level.price)}${weight}`,
      });
      priceLinesRef.current.push(line);
    }
  }, [session?.session_id, session?.plan, session?.status]);

  useEffect(() => {
    const series = candleSeriesRef.current;
    if (!series || !session || session.status !== "READY") return;
    const evidence = session.close_evidence;
    const lastCandle = session.visible_candles[session.visible_candles.length - 1];
    if (session.trade?.phase === "CLOSED" && evidence && lastCandle) {
      series.setMarkers([{
        time: lastCandle.time as any,
        position: session.trade.side === "SELL" || session.trade.side === "SHORT" ? "aboveBar" : "belowBar",
        color: "#f59e0b",
        shape: session.trade.side === "SELL" || session.trade.side === "SHORT" ? "arrowDown" : "arrowUp",
        text: `${t("replay.close_marker")}: ${t(closeSourceKey(evidence.source))}${showsRawCloseSource(evidence) ? ` (${evidence.close_source_raw})` : ""}`,
      }]);
    } else {
      series.setMarkers([]);
    }
  }, [session?.session_id, session?.current_index, session?.trade?.phase, session?.status]);

  const requestUpdate = async (path: "step" | "seek", payload: Record<string, number>) => {
    if (!session?.session_id || session.status !== "READY" || stepInFlight.current) return;
    const generation = generationRef.current;
    const controller = new AbortController(); updateAbortRef.current?.abort(); updateAbortRef.current = controller;
    stepInFlight.current = true; setIsStepPending(true);
    try {
      const res = await apiFetch(`${apiBase()}/api/v1/replay/${session.session_id}/${path}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload), signal: controller.signal });
      const data = await res.json() as ReplaySessionResponse;
      if (!res.ok) throw new Error(data.message || data.reason || `Replay ${path} failed (${res.status})`);
      if (!shouldApplyReplayResponse(generation, generationRef.current)) return;
      setSession(data);
      if (data.status !== "READY" || data.current_index === null || data.current_index >= data.total_bars - 1) setIsPlaying(false);
    } catch (cause) { if (shouldApplyReplayResponse(generation, generationRef.current) && !(cause instanceof DOMException && cause.name === "AbortError")) { setIsPlaying(false); setSession(null); setError(cause instanceof Error ? cause.message : "Replay update failed."); } }
    finally {
      if (updateAbortRef.current === controller) {
        updateAbortRef.current = null; stepInFlight.current = false;
        if (shouldApplyReplayResponse(generation, generationRef.current)) setIsStepPending(false);
      }
    }
  };
  const runManualRefresh = async () => {
    if (refreshState === "refreshing") return;
    const generation = generationRef.current;
    setRefreshState("refreshing");
    try {
      const res = await apiFetch(`${apiBase()}/api/v1/replay/session/${encodeURIComponent(tradeId)}?refresh=true`);
      const data = await res.json() as ReplaySessionResponse;
      if (!res.ok) throw new Error(data.message || data.reason || `Refresh failed (${res.status})`);
      if (!shouldApplyReplayResponse(generation, generationRef.current)) return;
      if (data.status === "READY" && data.review_mode === "OPEN") {
        setSession(data);
        setRefreshState("idle");
      } else {
        // Keep the previous chart visible; the refresh itself did not succeed.
        setRefreshState("error");
      }
    } catch {
      if (shouldApplyReplayResponse(generation, generationRef.current)) setRefreshState("error");
    }
  };

  useEffect(() => {
    if (!isPlaying || !session?.session_id || session.current_index === null || session.current_index >= session.total_bars - 1) { if (isPlaying && (!session || session.current_index === null || session.current_index >= session.total_bars - 1)) setIsPlaying(false); return; }
    const timer = window.setTimeout(() => void requestUpdate("step", { direction: 1 }), Math.max(100, Math.floor(1000 / speed)));
    return () => window.clearTimeout(timer);
  }, [isPlaying, isStepPending, session?.session_id, session?.current_index, session?.total_bars, speed]);

  if (isLoading) return <ReplayState title={t("replay.state.loading")} detail={t("replay.state.loading_detail")} />;
  if (error) return <ReplayState title={t("replay.state.unavailable")} detail={error} />;
  if (!session || session.status !== "READY") {
    const reason = session?.reason ?? "NO_DATA";
    const known = KNOWN_REASONS.has(reason);
    const localized = known ? t(`replay.reason.${reason}`) : `${t("replay.reason.unknown")} (${reason})`;
    const canRefreshFromState = session?.review_mode === "OPEN"
      && Boolean(session?.provider && session?.provider_symbol)
      && ["PROVIDER_MATCH_REQUIRED", "PROVIDER_IDENTITY_MISMATCH", "PROVIDER_FETCH_FAILED", "PROVIDER_NOT_SUPPORTED"].includes(reason);
    return (
      <ReplayState
        title={reason === "TRADE_NOT_CLOSED" ? t("replay.state.open_trade") : t("replay.state.no_data")}
        detail={localized}
        reason={reason}
        extra={known ? undefined : session?.message ?? undefined}
        note={reason === "TRADE_NOT_CLOSED" ? t("replay.closed_only_note") : undefined}
        action={canRefreshFromState ? (
          <div className="mt-3 space-y-1">
            <p className="text-xs text-slate-400" data-testid="replay-declared-identity" data-provider={session?.provider ?? ""} data-provider-symbol={session?.provider_symbol ?? ""}>
              {t("replay.open_review.provider", { provider: session?.provider ?? "—" })} · {session?.provider_symbol ?? "—"}
            </p>
            <button
              type="button"
              data-testid="replay-refresh"
              onClick={() => void runManualRefresh()}
              disabled={refreshState === "refreshing"}
              className="px-3 py-1.5 rounded border border-accent/50 text-accent hover:bg-accent/10 disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
            >
              {refreshState === "refreshing" ? t("replay.refresh.refreshing") : t("replay.refresh.action")}
            </button>
            {refreshState === "error" && (
              <span data-testid="replay-refresh-error" role="alert" className="block text-loss text-xs">{t("replay.refresh.error")}</span>
            )}
          </div>
        ) : undefined}
      />
    );
  }

  const trade = session.trade;
  const currentIndex = session.current_index ?? 0;
  const totalBars = session.total_bars;
  const evidence = session.close_evidence;
  const openReview: OpenReviewBlock | null = session.review_mode === "OPEN" ? session.open_review ?? null : null;
  const istanbul = (value: string | null | undefined) => value ? formatIstanbulDateTime(value, locale) : "—";
  return <div className="flex-1 flex flex-col h-full bg-[#0b0e14] overflow-hidden select-none font-mono">
    <div className="p-3 bg-[#0d121c] border-b border-surface-border flex items-center justify-between">
      <div className="flex items-center space-x-3">
        <span className="px-2 py-0.5 bg-accent/20 border border-accent/40 text-accent font-bold text-xs rounded">REPLAY</span>
        {openReview && (
          <span data-testid="replay-open-badge" className="px-2 py-0.5 bg-amber-400/20 border border-amber-400/40 text-amber-300 font-bold text-xs rounded">
            {t("replay.open_review.badge")}
          </span>
        )}
        <span className="font-bold text-white text-sm">{session.symbol}</span>
        <span className="text-xs text-slate-400">{t("replay.bar_of", { current: currentIndex + 1, total: totalBars })}</span>
      </div>
      <span className="text-[10px] text-amber-300">{t(openReview ? "replay.boundary_note_open" : "replay.boundary_note")}</span>
    </div>
    {session.plan && (
      <section className="px-3 py-2 bg-[#111722] border-b border-surface-border space-y-1">
        <p data-testid="replay-reference-banner" className="text-[11px] text-amber-300">{t("replay.reference_banner")}</p>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
          <span className="px-2 py-0.5 rounded border border-surface-border font-bold text-white">{trade?.side ? t(`replay.side.${trade.side === "SELL" || trade.side === "SHORT" ? "short" : "long"}`) : "—"}</span>
          <span data-testid="replay-plan-kind" className="text-slate-400">{t(`replay.plan_kind.${session.plan.kind === "LOCAL_PLAN" ? "local" : "trade_row"}`)}</span>
          {session.plan.created_after_entry === true && (
            <span data-testid="replay-plan-created-after" className="text-amber-300">{t("replay.plan_after_entry")}</span>
          )}
          <span data-testid="replay-origin" className="text-slate-400">{t(originKey(session.origin_class))}</span>
        </div>
        <PlanLevels plan={session.plan} />
        {evidence && (
          <p className="text-xs text-slate-300">
            <span data-testid="replay-close-source">
              {t(closeSourceKey(evidence.source))}
              {showsRawCloseSource(evidence) ? ` (${evidence.close_source_raw})` : ""}
            </span>
            {isFiniteNumber(evidence.price) ? <span className="ml-2 text-white font-bold">{formatLevelPrice(evidence.price)}</span> : null}
          </p>
        )}
      </section>
    )}
    <MarketInfo session={session} />
    {openReview && (
      <section className="px-3 py-2 text-[11px] text-slate-300 space-y-1 border-b border-surface-border">
        <p data-testid="replay-freshness">
          {t(openReview.delay_indicator === "FRESH_DELAY" ? "replay.open_review.freshness_fresh"
            : openReview.delay_indicator === "DELAYED" ? "replay.open_review.freshness_delayed"
            : "replay.open_review.freshness_unknown")}
          {" · "}
          {t("replay.open_review.last_candle", {
            time: istanbul(openReview.last_candle_time_utc),
            state: t(`replay.open_review.candle_state_${String(openReview.last_candle_state).toLowerCase()}`),
          })}
          {openReview.last_download_at ? ` · ${t("replay.open_review.last_download", { time: istanbul(openReview.last_download_at) })}` : ""}
        </p>
        <p className="flex flex-wrap gap-x-3">
          <span data-testid="replay-provider" data-provider={openReview.provider ?? ""}>
            {openReview.provider
              ? t("replay.open_review.provider", { provider: openReview.provider })
              : t("replay.open_review.provider_unknown")}
          </span>
          <span data-testid="replay-identity">{t("replay.open_review.identity_note", { instrument: openReview.instrument ?? session.symbol ?? "—" })}</span>
        </p>
        {openReview.history_status === "PARTIAL_SINCE_ENTRY" && (
          <p data-testid="replay-partial-history" className="text-amber-300">
            {t("replay.open_review.partial_history", {
              start: istanbul(openReview.coverage_start_utc),
              end: istanbul(openReview.coverage_end_utc),
              minutes: openReview.missing_before_entry_minutes,
            })}
          </p>
        )}
        <div className="flex items-center gap-2 pt-0.5">
          <button
            type="button"
            data-testid="replay-refresh"
            onClick={() => void runManualRefresh()}
            disabled={refreshState === "refreshing"}
            className="px-2.5 py-1 rounded border border-accent/50 text-accent hover:bg-accent/10 disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
          >
            {refreshState === "refreshing" ? t("replay.refresh.refreshing") : t("replay.refresh.action")}
          </button>
          {refreshState === "error" && (
            <span data-testid="replay-refresh-error" role="alert" className="text-loss">
              {t("replay.refresh.error")}
            </span>
          )}
        </div>
      </section>
    )}
    {trade && (
      <div className="px-3 py-2 bg-[#111722] flex flex-wrap gap-x-4 gap-y-1 text-xs">
        <span>{t(`replay.phase.${trade.phase.toLowerCase()}`)}</span>
        <span>{t("replay.summary.current")}: {isFiniteNumber(trade.current_price) ? formatLevelPrice(trade.current_price) : "—"}</span>
        {openReview ? (
          <span className="text-amber-300">{t("replay.open_review.no_performance")}</span>
        ) : (
          <>
            <span>{t("replay.summary.unrealized")}: {isFiniteNumber(trade.unrealized_pnl) ? trade.unrealized_pnl.toFixed(2) : "—"}</span>
            <span>{t("replay.summary.realized")}: {isFiniteNumber(trade.realized_pnl) ? trade.realized_pnl.toFixed(2) : "—"}</span>
            <span>{t("replay.summary.r")}: {isFiniteNumber(trade.r_multiple) ? `${trade.r_multiple.toFixed(2)}R` : "—"}</span>
            <span>{t("replay.summary.mae")}: {isFiniteNumber(trade.mae_r) ? `${trade.mae_r.toFixed(2)}R` : "—"}</span>
            <span>{t("replay.summary.mfe")}: {isFiniteNumber(trade.mfe_r) ? `${trade.mfe_r.toFixed(2)}R` : "—"}</span>
            {trade.risk_unit === null && <span className="text-amber-300">{t("replay.summary.risk_unavailable")}</span>}
          </>
        )}
      </div>
    )}
    <div className="flex-1 relative" data-testid="replay-chart"><div ref={chartContainerRef} className="w-full h-full" /></div>
    <div className="p-3 bg-[#0d121c] border-t border-surface-border flex flex-col space-y-2">
      <input data-testid="replay-slider" aria-label={t("replay.action.seek")} type="range" min={0} max={Math.max(0, totalBars - 1)} value={currentIndex} onChange={(e) => void requestUpdate("seek", { target_index: Number(e.target.value) })} className="flex-1 accent-sky-500" />
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <button data-testid="replay-reset" aria-label={t("replay.action.reset")} onClick={() => void requestUpdate("seek", { target_index: 0 })} className="p-1.5 bg-[#111722] border border-surface-border rounded text-slate-300"><RotateCcw className="w-3.5 h-3.5" /></button>
          <button data-testid="replay-back" aria-label={t("replay.action.step_back")} onClick={() => void requestUpdate("step", { direction: -1 })} disabled={currentIndex <= 0} className="p-1.5 bg-[#111722] border border-surface-border rounded disabled:opacity-40 text-slate-300"><SkipBack className="w-3.5 h-3.5" /></button>
          <button data-testid="replay-play" aria-label={isPlaying ? t("replay.action.pause") : t("replay.action.play")} onClick={() => setIsPlaying((value) => !value)} disabled={currentIndex >= totalBars - 1} className="flex items-center space-x-1.5 px-3 py-1.5 bg-accent text-black font-bold rounded text-xs">{isPlaying ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5 fill-black" />}<span>{isPlaying ? t("replay.action.pause") : t("replay.action.play")}</span></button>
          <button data-testid="replay-forward" aria-label={t("replay.action.step_forward")} onClick={() => void requestUpdate("step", { direction: 1 })} disabled={currentIndex >= totalBars - 1} className="p-1.5 bg-[#111722] border border-surface-border rounded disabled:opacity-40 text-slate-300"><SkipForward className="w-3.5 h-3.5" /></button>
        </div>
        <div className="flex items-center space-x-1 bg-[#111722] p-1 rounded text-[11px]">
          <FastForward className="w-3 h-3 text-slate-500" />
          {[0.5, 1, 2, 5, 10].map((value) => <button key={value} data-testid={`replay-speed-${value}`} onClick={() => setSpeed(value)} className={speed === value ? "bg-accent text-black font-bold px-2 rounded" : "text-slate-400 px-2"}>{value}x</button>)}
        </div>
      </div>
    </div>
  </div>;
};

const ReplayState = ({ title, detail, reason, extra, note, action }: {
  title: string; detail: string; reason?: string; extra?: string; note?: string; action?: React.ReactNode;
}) =>
  <div data-testid="replay-state" data-reason={reason} className="p-8 text-center text-slate-400 font-mono">
    <p className="font-bold text-white">{title}</p>
    <p className="mt-2 text-xs">{detail}</p>
    {extra && <p className="mt-1 text-[10px] text-slate-500">{extra}</p>}
    {note && <p data-testid="replay-closed-only-note" className="mt-2 text-xs text-amber-300">{note}</p>}
    {action}
  </div>;
