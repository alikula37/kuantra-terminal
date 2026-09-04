import React, { useEffect, useRef, useState } from "react";
import { createChart, IChartApi, ISeriesApi } from "lightweight-charts";
import { ReplaySessionResponse } from "../types";
import { Play, Pause, SkipBack, SkipForward, FastForward, RotateCcw } from "lucide-react";
import { apiBase, apiFetch } from "../lib/backend";

interface TradeReplayCanvasProps {
  tradeId?: string;
}

export const TradeReplayCanvas: React.FC<TradeReplayCanvasProps> = ({ tradeId = "TRD-DEFAULT" }) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);

  const [session, setSession] = useState<ReplaySessionResponse | null>(null);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [speed, setSpeed] = useState<number>(1.0);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  // Initialize Replay Session
  useEffect(() => {
    setIsLoading(true);
    apiFetch(`${apiBase()}/api/v1/replay/session/${tradeId}`)
      .then((res) => res.json())
      .then((data: ReplaySessionResponse) => {
        setSession(data);
        setIsLoading(false);
      })
      .catch(() => {
        setIsLoading(false);
      });
  }, [tradeId]);

  // Initialize Lightweight Charts
  useEffect(() => {
    if (!chartContainerRef.current) return;

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { color: "#090d14" },
        textColor: "#94a3b8",
        fontSize: 11,
        fontFamily: "'JetBrains Mono', monospace",
      },
      grid: {
        vertLines: { color: "#1e293b", style: 2 },
        horzLines: { color: "#1e293b", style: 2 },
      },
      crosshair: {
        vertLine: { color: "#38bdf8", width: 1, style: 3 },
        horzLine: { color: "#38bdf8", width: 1, style: 3 },
      },
      timeScale: {
        borderColor: "#1e293b",
        timeVisible: true,
        secondsVisible: false,
      },
      rightPriceScale: {
        borderColor: "#1e293b",
        scaleMargins: { top: 0.1, bottom: 0.15 },
      },
    });

    const candleSeries = chart.addCandlestickSeries({
      upColor: "#10b981",
      downColor: "#ef4444",
      borderUpColor: "#10b981",
      borderDownColor: "#ef4444",
      wickUpColor: "#10b981",
      wickDownColor: "#ef4444",
    });

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;

    const handleResize = () => {
      if (chartContainerRef.current && chartRef.current) {
        chartRef.current.applyOptions({
          width: chartContainerRef.current.clientWidth,
          height: chartContainerRef.current.clientHeight,
        });
      }
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
    };
  }, []);

  // Update chart data whenever visible candles change
  useEffect(() => {
    if (!candleSeriesRef.current || !session) return;

    const formatted = session.visible_candles.map((c) => ({
      time: c.time as any,
      open: c.open,
      high: c.high,
      low: c.low,
      close: c.close,
    }));

    candleSeriesRef.current.setData(formatted);
  }, [session?.visible_candles, session?.current_index]);

  // Playback Step
  const handleStep = async (dir: number) => {
    if (!session) return;
    try {
      const res = await apiFetch(`${apiBase()}/api/v1/replay/${session.session_id}/step`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ direction: dir }),
      });
      const data: ReplaySessionResponse = await res.json();
      setSession(data);
    } catch (e) {
      console.error(e);
    }
  };

  // Seek Slider
  const handleSeek = async (idx: number) => {
    if (!session) return;
    try {
      const res = await apiFetch(`${apiBase()}/api/v1/replay/${session.session_id}/seek`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target_index: idx }),
      });
      const data: ReplaySessionResponse = await res.json();
      setSession(data);
    } catch (e) {
      console.error(e);
    }
  };

  // Playback Interval Loop
  useEffect(() => {
    let timer: any = null;
    if (isPlaying && session) {
      const intervalMs = Math.max(100, Math.floor(1000 / speed));
      timer = setInterval(() => {
        if (session.current_index >= session.total_bars - 1) {
          setIsPlaying(false);
        } else {
          handleStep(1);
        }
      }, intervalMs);
    }
    return () => {
      if (timer) clearInterval(timer);
    };
  }, [isPlaying, session?.current_index, session?.total_bars, speed]);

  if (isLoading || !session) {
    return <div className="p-8 text-center text-slate-400 font-mono">Initializing replay stream...</div>;
  }

  const trade = session.trade;

  return (
    <div className="flex-1 flex flex-col h-full bg-[#0b0e14] overflow-hidden select-none font-mono">
      {/* Top Replay HUD Bar */}
      <div className="p-3 bg-[#0d121c] border-b border-surface-border flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="flex items-center space-x-2">
            <span className="px-2 py-0.5 bg-accent/20 border border-accent/40 text-accent font-bold text-xs rounded">
              REPLAY
            </span>
            <span className="font-bold text-white text-sm">{session.symbol}</span>
            <span className="text-xs text-slate-400">
              Bar {session.current_index + 1} of {session.total_bars}
            </span>
          </div>

          {trade && (
            <div className="flex items-center space-x-2 pl-3 border-l border-surface-border text-xs">
              <span className={`font-bold px-1.5 py-0.5 rounded text-[10px] ${trade.side === "BUY" || trade.side === "LONG" ? "bg-gain/20 text-gain" : "bg-loss/20 text-loss"}`}>
                {trade.side}
              </span>
              <span className="text-slate-400">Entry: <strong className="text-white">${trade.entry_price}</strong></span>
              {trade.stop_loss && <span className="text-slate-400">SL: <strong className="text-loss">${trade.stop_loss}</strong></span>}
              {trade.take_profit && <span className="text-slate-400">TP: <strong className="text-gain">${trade.take_profit}</strong></span>}
            </div>
          )}
        </div>

        {/* Live Replay Position Status Badge */}
        {trade && (
          <div className="flex items-center space-x-3">
            <div className="bg-[#111722] px-3 py-1 rounded border border-surface-border flex items-center space-x-3 text-xs">
              <span className="text-slate-400">Unrealized PnL:</span>
              <span className={`font-bold ${trade.unrealized_pnl >= 0 ? "text-gain" : "text-loss"}`}>
                {trade.unrealized_pnl >= 0 ? "+" : ""}${trade.unrealized_pnl.toFixed(2)} ({trade.r_multiple >= 0 ? "+" : ""}{trade.r_multiple}R)
              </span>
              <span className="text-slate-500">|</span>
              <span className="text-slate-400">Endured: <strong className="text-loss">{trade.mae_r}R</strong></span>
              <span className="text-slate-400">Peak: <strong className="text-gain">+{trade.mfe_r}R</strong></span>
            </div>
          </div>
        )}
      </div>

      {/* Main Chart Canvas */}
      <div className="flex-1 relative">
        <div ref={chartContainerRef} className="w-full h-full" />
      </div>

      {/* Bottom Playback HUD Controller */}
      <div className="p-3 bg-[#0d121c] border-t border-surface-border flex flex-col space-y-2">
        {/* Timeline Slider */}
        <div className="flex items-center space-x-3 text-xs">
          <span className="text-slate-500 text-[10px]">PRE-TRADE</span>
          <input
            type="range"
            min={0}
            max={session.total_bars - 1}
            value={session.current_index}
            onChange={(e) => handleSeek(parseInt(e.target.value))}
            className="flex-1 accent-sky-500 cursor-pointer h-1.5 bg-[#1e293b] rounded-lg"
          />
          <span className="text-slate-500 text-[10px]">EXIT</span>
        </div>

        {/* Control Buttons */}
        <div className="flex items-center justify-between pt-1">
          <div className="flex items-center space-x-2">
            <button
              onClick={() => handleSeek(0)}
              className="p-1.5 bg-[#111722] hover:bg-[#1a2234] border border-surface-border text-slate-300 rounded"
              title="Reset to Start"
            >
              <RotateCcw className="w-3.5 h-3.5" />
            </button>

            <button
              onClick={() => handleStep(-1)}
              disabled={session.current_index <= 0}
              className="p-1.5 bg-[#111722] hover:bg-[#1a2234] border border-surface-border text-slate-300 rounded disabled:opacity-40"
              title="Step Backward"
            >
              <SkipBack className="w-3.5 h-3.5" />
            </button>

            <button
              onClick={() => setIsPlaying(!isPlaying)}
              className="flex items-center space-x-1.5 px-3 py-1.5 bg-accent hover:bg-sky-400 text-black font-bold rounded text-xs transition"
            >
              {isPlaying ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5 fill-black" />}
              <span>{isPlaying ? "PAUSE" : "PLAY"}</span>
            </button>

            <button
              onClick={() => handleStep(1)}
              disabled={session.current_index >= session.total_bars - 1}
              className="p-1.5 bg-[#111722] hover:bg-[#1a2234] border border-surface-border text-slate-300 rounded disabled:opacity-40"
              title="Step Forward"
            >
              <SkipForward className="w-3.5 h-3.5" />
            </button>
          </div>

          {/* Speed Selector */}
          <div className="flex items-center space-x-1 bg-[#111722] p-1 rounded border border-surface-border text-[11px]">
            <FastForward className="w-3 h-3 text-slate-500 ml-1" />
            {[0.5, 1.0, 2.0, 5.0, 10.0].map((s) => (
              <button
                key={s}
                onClick={() => setSpeed(s)}
                className={`px-2 py-0.5 rounded transition ${
                  speed === s
                    ? "bg-accent text-black font-bold"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                {s}x
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};