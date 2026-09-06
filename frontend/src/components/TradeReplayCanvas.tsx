import React, { useEffect, useRef, useState } from "react";
import { createChart, IChartApi, ISeriesApi } from "lightweight-charts";
import { ReplaySessionResponse } from "../types";
import { Play, Pause, SkipBack, SkipForward, FastForward, RotateCcw } from "lucide-react";
import { apiBase, apiFetch } from "../lib/backend";

interface TradeReplayCanvasProps { tradeId?: string; }
export const isFiniteNumber = (value: unknown): value is number => typeof value === "number" && Number.isFinite(value);
export const canRenderReplayChart = (session: ReplaySessionResponse | null) => Boolean(session?.status === "READY" && session.session_id && session.visible_candles.length);
export const shouldApplyReplayResponse = (responseGeneration: number, currentGeneration: number) => responseGeneration === currentGeneration;
const dash = (value: unknown, digits = 2) => isFiniteNumber(value) ? value.toFixed(digits) : "—";

export const TradeReplayCanvas: React.FC<TradeReplayCanvasProps> = ({ tradeId = "TRD-DEFAULT" }) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const stepInFlight = useRef(false);
  const generationRef = useRef(0);
  const updateAbortRef = useRef<AbortController | null>(null);
  const [session, setSession] = useState<ReplaySessionResponse | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isStepPending, setIsStepPending] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const generation = ++generationRef.current;
    updateAbortRef.current?.abort(); stepInFlight.current = false; setIsStepPending(false);
    const controller = new AbortController(); let active = true;
    setIsLoading(true); setError(null); setSession(null); setIsPlaying(false);
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

  // This runs after the async READY render; the prior [] effect could miss its container forever.
  useEffect(() => {
    if (!canRenderReplayChart(session) || !chartContainerRef.current) return;
    const container = chartContainerRef.current;
    const chart = createChart(container, { width: container.clientWidth, height: container.clientHeight, layout: { background: { color: "#090d14" }, textColor: "#94a3b8", fontSize: 11, fontFamily: "'JetBrains Mono', monospace" }, grid: { vertLines: { color: "#1e293b", style: 2 }, horzLines: { color: "#1e293b", style: 2 } }, timeScale: { borderColor: "#1e293b", timeVisible: true, secondsVisible: false }, rightPriceScale: { borderColor: "#1e293b", scaleMargins: { top: 0.1, bottom: 0.15 } } });
    const series = chart.addCandlestickSeries({ upColor: "#10b981", downColor: "#ef4444", borderUpColor: "#10b981", borderDownColor: "#ef4444", wickUpColor: "#10b981", wickDownColor: "#ef4444" });
    chartRef.current = chart; candleSeriesRef.current = series;
    const resize = () => chart.applyOptions({ width: container.clientWidth, height: container.clientHeight });
    window.addEventListener("resize", resize);
    return () => { window.removeEventListener("resize", resize); candleSeriesRef.current = null; chartRef.current = null; chart.remove(); };
  }, [session?.session_id, session?.status]);
  useEffect(() => {
    if (!candleSeriesRef.current || !session || session.status !== "READY") return;
    candleSeriesRef.current.setData(session.visible_candles.map((c) => ({ time: c.time as any, open: c.open, high: c.high, low: c.low, close: c.close })));
  }, [session?.visible_candles, session?.current_index, session?.status]);

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
  useEffect(() => {
    if (!isPlaying || !session?.session_id || session.current_index === null || session.current_index >= session.total_bars - 1) { if (isPlaying && (!session || session.current_index === null || session.current_index >= session.total_bars - 1)) setIsPlaying(false); return; }
    const timer = window.setTimeout(() => void requestUpdate("step", { direction: 1 }), Math.max(100, Math.floor(1000 / speed)));
    return () => window.clearTimeout(timer);
  }, [isPlaying, isStepPending, session?.session_id, session?.current_index, session?.total_bars, speed]);

  if (isLoading) return <ReplayState title="Loading recorded candle replay" detail="Waiting for valid recorded candle history." />;
  if (error) return <ReplayState title="Replay unavailable" detail={error} />;
  if (!session || session.status !== "READY") return <ReplayState title={session?.status === "NO_DATA" ? "No replay data" : "Replay unavailable"} detail={session?.message || session?.reason || "No valid recorded candle history is available."} />;
  const trade = session.trade; const currentIndex = session.current_index ?? 0; const totalBars = session.total_bars;
  return <div className="flex-1 flex flex-col h-full bg-[#0b0e14] overflow-hidden select-none font-mono">
    <div className="p-3 bg-[#0d121c] border-b border-surface-border flex items-center justify-between"><div className="flex items-center space-x-3"><span className="px-2 py-0.5 bg-accent/20 border border-accent/40 text-accent font-bold text-xs rounded">REPLAY</span><span className="font-bold text-white text-sm">{session.symbol}</span><span className="text-xs text-slate-400">Bar {currentIndex + 1} of {totalBars}</span></div><span className="text-[10px] text-amber-300">Candle-bar approximation • DuckDB candles • source unverified • R is gross price move, not net fees</span></div>
    <p className="px-3 py-1 text-[10px] text-slate-500">Boundary-bar highs/lows may include movement before entry or after exit.</p>
    {trade && <div className="px-3 py-2 bg-[#111722] flex flex-wrap gap-x-4 gap-y-1 text-xs"><span>{trade.phase}</span><span>Current: ${dash(trade.current_price)}</span><span>Unrealized: ${dash(trade.unrealized_pnl)}</span><span>Realized: ${dash(trade.realized_pnl)}</span><span>R: {dash(trade.r_multiple)}R</span><span>MAE: {dash(trade.mae_r)}R</span><span>MFE: {dash(trade.mfe_r)}R</span>{trade.risk_unit === null && <span className="text-amber-300">R metrics unavailable: no valid stop-loss risk unit.</span>}</div>}
    <div className="flex-1 relative"><div ref={chartContainerRef} className="w-full h-full" /></div>
    <div className="p-3 bg-[#0d121c] border-t border-surface-border flex flex-col space-y-2"><input aria-label="Replay position" type="range" min={0} max={Math.max(0, totalBars - 1)} value={currentIndex} onChange={(e) => void requestUpdate("seek", { target_index: Number(e.target.value) })} className="flex-1 accent-sky-500" /><div className="flex items-center justify-between"><div className="flex items-center space-x-2"><button aria-label="Reset replay" onClick={() => void requestUpdate("seek", { target_index: 0 })} className="p-1.5 bg-[#111722] border border-surface-border rounded"><RotateCcw className="w-3.5 h-3.5" /></button><button aria-label="Step backward" onClick={() => void requestUpdate("step", { direction: -1 })} disabled={currentIndex <= 0} className="p-1.5 bg-[#111722] border border-surface-border rounded disabled:opacity-40"><SkipBack className="w-3.5 h-3.5" /></button><button aria-label={isPlaying ? "Pause replay" : "Play replay"} onClick={() => setIsPlaying((value) => !value)} disabled={currentIndex >= totalBars - 1} className="flex items-center space-x-1.5 px-3 py-1.5 bg-accent text-black font-bold rounded text-xs">{isPlaying ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5 fill-black" />}<span>{isPlaying ? "PAUSE" : "PLAY"}</span></button><button aria-label="Step forward" onClick={() => void requestUpdate("step", { direction: 1 })} disabled={currentIndex >= totalBars - 1} className="p-1.5 bg-[#111722] border border-surface-border rounded disabled:opacity-40"><SkipForward className="w-3.5 h-3.5" /></button></div><div className="flex items-center space-x-1 bg-[#111722] p-1 rounded text-[11px]"><FastForward className="w-3 h-3 text-slate-500" />{[0.5, 1, 2, 5, 10].map((value) => <button key={value} onClick={() => setSpeed(value)} className={speed === value ? "bg-accent text-black font-bold px-2 rounded" : "text-slate-400 px-2"}>{value}x</button>)}</div></div></div>
  </div>;
};
const ReplayState = ({ title, detail }: { title: string; detail: string }) => <div className="p-8 text-center text-slate-400 font-mono"><p className="font-bold text-white">{title}</p><p className="mt-2 text-xs">{detail}</p></div>;
