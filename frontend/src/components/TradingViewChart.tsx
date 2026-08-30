import React, { useEffect, useRef } from "react";
import { createChart, IChartApi, ISeriesApi, CandlestickData, Time } from "lightweight-charts";
import { useMarketStore } from "../stores/marketStore";
import { useTradeStore } from "../stores/tradeStore";

export const TradingViewChart: React.FC = () => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);

  const { currentPrice, symbol } = useMarketStore();
  const { openPositions } = useTradeStore();

  useEffect(() => {
    if (!chartContainerRef.current) return;

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { color: "#0b0e14" },
        textColor: "#94a3b8",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: "rgba(30, 41, 59, 0.4)" },
        horzLines: { color: "rgba(30, 41, 59, 0.4)" },
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
        scaleMargins: { top: 0.1, bottom: 0.2 },
      },
      handleScale: true,
      handleScroll: true,
    });

    const candleSeries = chart.addCandlestickSeries({
      upColor: "#10b981",
      downColor: "#ef4444",
      borderVisible: false,
      wickUpColor: "#10b981",
      wickDownColor: "#ef4444",
    });

    const volumeSeries = chart.addHistogramSeries({
      color: "rgba(56, 189, 248, 0.3)",
      priceFormat: { type: "volume" },
      priceScaleId: "",
    });

    chart.priceScale("").applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    });

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;
    volumeSeriesRef.current = volumeSeries;

    const baseTime = Math.floor(Date.now() / 1000) - 120 * 60;
    const initialCandles: CandlestickData<Time>[] = [];
    const initialVolume: any[] = [];
    let p = currentPrice || 65000.0;

    for (let i = 0; i < 120; i++) {
      const open = p;
      const high = open + Math.random() * 40;
      const low = open - Math.random() * 40;
      const close = low + Math.random() * (high - low);
      const time = (baseTime + i * 60) as Time;
      const isUp = close >= open;

      initialCandles.push({ time, open, high, low, close });
      initialVolume.push({
        time,
        value: Math.random() * 50 + 10,
        color: isUp ? "rgba(16, 185, 129, 0.3)" : "rgba(239, 68, 68, 0.3)",
      });
      p = close;
    }

    candleSeries.setData(initialCandles);
    volumeSeries.setData(initialVolume);

    chart.timeScale().fitContent();

    const handleResize = () => {
      if (chartContainerRef.current) {
        chart.applyOptions({
          width: chartContainerRef.current.clientWidth,
          height: chartContainerRef.current.clientHeight,
        });
      }
    };

    window.addEventListener("resize", handleResize);
    const observer = new ResizeObserver(handleResize);
    observer.observe(chartContainerRef.current);

    return () => {
      window.removeEventListener("resize", handleResize);
      observer.disconnect();
      chart.remove();
    };
  }, []);

  useEffect(() => {
    if (!candleSeriesRef.current || !currentPrice) return;
    const nowSec = (Math.floor(Date.now() / 60000) * 60) as Time;

    try {
      candleSeriesRef.current.update({
        time: nowSec,
        open: currentPrice,
        high: currentPrice + 5,
        low: currentPrice - 5,
        close: currentPrice,
      });
    } catch {
      // ignore
    }
  }, [currentPrice]);

  return (
    <div className="relative flex-1 w-full h-full bg-[#0b0e14] overflow-hidden flex flex-col">
      <div className="flex items-center justify-between px-4 py-2 border-b border-surface-border bg-[#0d121c] text-xs">
        <div className="flex items-center space-x-3">
          <span className="font-bold text-white font-mono">{symbol}</span>
          <span className="text-slate-500">|</span>
          <div className="flex items-center space-x-1 bg-[#111722] p-0.5 rounded border border-surface-border">
            {["1m", "5m", "15m", "1h", "4h", "1D"].map((tf, i) => (
              <button
                key={tf}
                className={`px-2 py-0.5 rounded font-mono ${
                  i === 0 ? "bg-accent/20 text-accent font-semibold" : "text-slate-400 hover:text-white"
                }`}
              >
                {tf}
              </button>
            ))}
          </div>
        </div>
        <div className="flex items-center space-x-4 font-mono text-[11px]">
          <span className="text-slate-400">
            O: <span className="text-white">{(currentPrice * 0.999).toFixed(2)}</span>
          </span>
          <span className="text-slate-400">
            H: <span className="text-gain">{(currentPrice * 1.002).toFixed(2)}</span>
          </span>
          <span className="text-slate-400">
            L: <span className="text-loss">{(currentPrice * 0.997).toFixed(2)}</span>
          </span>
          <span className="text-slate-400">
            C: <span className="text-white font-bold">{currentPrice.toFixed(2)}</span>
          </span>
        </div>
      </div>

      <div ref={chartContainerRef} className="w-full flex-1 min-h-[350px]" />

      {openPositions.length > 0 && (
        <div className="absolute bottom-3 left-4 flex flex-wrap gap-2 z-10">
          {openPositions.map((pos) => (
            <div
              key={pos.id}
              className="bg-[#111722]/90 backdrop-blur border border-accent/40 px-2.5 py-1.5 rounded text-xs font-mono shadow-lg flex items-center space-x-3"
            >
              <span className={`font-bold ${pos.side === "BUY" || pos.side === "LONG" ? "text-gain" : "text-loss"}`}>
                {pos.side} {pos.qty} {pos.symbol}
              </span>
              <span className="text-slate-400">@ {pos.entry_price.toFixed(2)}</span>
              <span className={`font-bold ${(pos.unrealized_pnl || 0) >= 0 ? "text-gain" : "text-loss"}`}>
                {(pos.unrealized_pnl || 0) >= 0 ? "+" : ""}${pos.unrealized_pnl?.toFixed(2)}
                {pos.r_multiple != null && ` (${pos.r_multiple > 0 ? "+" : ""}${pos.r_multiple}R)`}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};