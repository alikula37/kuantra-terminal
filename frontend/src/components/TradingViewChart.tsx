import React, { useEffect, useRef, useState, useCallback } from "react";
import { createChart, IChartApi, ISeriesApi, CandlestickData, Time, HistogramData } from "lightweight-charts";
import { useMarketStore } from "../stores/marketStore";
import { useTranslation } from "../context/I18nContext";
import { RefreshCw, AlertCircle, BarChart2 } from "lucide-react";
import { apiBase } from "../lib/backend";

export interface CandleDataPoint {
  timestamp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

const POPULAR_SYMBOLS = [
  { symbol: "BTCUSDT", label: "BTC/USDT" },
  { symbol: "ETHUSDT", label: "ETH/USDT" },
  { symbol: "SOLUSDT", label: "SOL/USDT" },
  { symbol: "XAUUSD", label: "GOLD (XAU)" },
  { symbol: "EURUSD", label: "EUR/USD" },
  { symbol: "SPY", label: "S&P 500 (SPY)" },
  { symbol: "NVDA", label: "NVIDIA (NVDA)" },
];

const TIMEFRAMES = [
  { tf: "1m", label: "1m" },
  { tf: "5m", label: "5m" },
  { tf: "15m", label: "15m" },
  { tf: "1h", label: "1H" },
  { tf: "4h", label: "4H" },
  { tf: "1d", label: "1D" },
];

export const TradingViewChart: React.FC = () => {
  const { t } = useTranslation();
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);

  const { symbol: storeSymbol, setSymbol: setStoreSymbol, updateTick } = useMarketStore();
  const [activeSymbol, setActiveSymbol] = useState<string>(storeSymbol || "BTCUSDT");
  const [activeTimeframe, setActiveTimeframe] = useState<string>("15m");
  const [customInput, setCustomInput] = useState<string>("");
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [hoveredCandle, setHoveredCandle] = useState<CandleDataPoint | null>(null);
  const [latestCandle, setLatestCandle] = useState<CandleDataPoint | null>(null);

  // Initialize Lightweight Charts Canvas
  useEffect(() => {
    if (!chartContainerRef.current) return;

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { color: "#0b0e14" },
        textColor: "#94a3b8",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: "rgba(30, 41, 59, 0.3)" },
        horzLines: { color: "rgba(30, 41, 59, 0.3)" },
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
        scaleMargins: { top: 0.08, bottom: 0.2 },
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
      color: "rgba(56, 189, 248, 0.25)",
      priceFormat: { type: "volume" },
      priceScaleId: "",
    });

    chart.priceScale("").applyOptions({
      scaleMargins: { top: 0.82, bottom: 0 },
    });

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;
    volumeSeriesRef.current = volumeSeries;

    // Crosshair move handler
    chart.subscribeCrosshairMove((param) => {
      if (!param || !param.time || !param.seriesData.get(candleSeries)) {
        setHoveredCandle(null);
        return;
      }
      const cData = param.seriesData.get(candleSeries) as any;
      const vData = param.seriesData.get(volumeSeries) as any;
      if (cData && cData.open !== undefined) {
        setHoveredCandle({
          timestamp: typeof param.time === "number" ? param.time * 1000 : 0,
          open: cData.open,
          high: cData.high,
          low: cData.low,
          close: cData.close,
          volume: vData?.value || 0,
        });
      }
    });

    const handleResize = () => {
      if (chartContainerRef.current && chartRef.current) {
        chartRef.current.applyOptions({
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
      chartRef.current = null;
    };
  }, []);

  // Fetch 100% Real Historical Market Data from Backend with Timeout & AbortController Guard
  const fetchMarketCandles = useCallback(async () => {
    setIsLoading(true);
    setErrorMsg(null);

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 6000);

    try {
      const url = `${apiBase()}/api/v1/market-data/candles?symbol=${encodeURIComponent(
        activeSymbol
      )}&timeframe=${encodeURIComponent(activeTimeframe)}&limit=500`;

      const response = await fetch(url, { signal: controller.signal });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${activeSymbol} verisi alınamadı.`);
      }

      const jsonRes = await response.json();
      const rawData: CandleDataPoint[] = Array.isArray(jsonRes)
        ? jsonRes
        : Array.isArray(jsonRes?.candles)
        ? jsonRes.candles
        : [];

      if (!rawData || rawData.length === 0) {
        throw new Error(t("market_chart.no_candles", { symbol: activeSymbol }));
      }

      // Deduplicate and sort strictly ascending by time
      const timeMap = new Map<number, CandleDataPoint>();
      rawData.forEach((c) => {
        const timeSec = c.timestamp > 1e11 ? Math.floor(c.timestamp / 1000) : c.timestamp;
        if (!timeMap.has(timeSec)) {
          timeMap.set(timeSec, {
            timestamp: timeSec,
            open: Number(c.open),
            high: Number(c.high),
            low: Number(c.low),
            close: Number(c.close),
            volume: Number(c.volume || 0),
          });
        }
      });

      const sortedCandles = Array.from(timeMap.values()).sort((a, b) => a.timestamp - b.timestamp);

      if (sortedCandles.length === 0) {
        throw new Error(t("market_chart.no_candles", { symbol: activeSymbol }));
      }

      const chartCandles: CandlestickData<Time>[] = sortedCandles.map((c) => ({
        time: c.timestamp as Time,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      }));

      const chartVolumes: HistogramData<Time>[] = sortedCandles.map((c) => ({
        time: c.timestamp as Time,
        value: c.volume,
        color: c.close >= c.open ? "rgba(16, 185, 129, 0.3)" : "rgba(239, 68, 68, 0.3)",
      }));

      if (candleSeriesRef.current && volumeSeriesRef.current) {
        candleSeriesRef.current.setData(chartCandles);
        volumeSeriesRef.current.setData(chartVolumes);
        chartRef.current?.timeScale().fitContent();
      }

      const last = sortedCandles[sortedCandles.length - 1];
      setLatestCandle(last);
      updateTick(last.close, 12, Date.now(), last.volume);
      setErrorMsg(null);
    } catch (err: any) {
      console.warn("[TradingViewChart] Real market data error:", err);
      const isAbort = err.name === "AbortError";
      const message = isAbort
        ? t("market_chart.fetch_timeout", { symbol: activeSymbol })
        : err.message || `${activeSymbol} piyasa verisi alınamadı.`;
      setErrorMsg(message);
      if (candleSeriesRef.current && volumeSeriesRef.current) {
        candleSeriesRef.current.setData([]);
        volumeSeriesRef.current.setData([]);
      }
      setLatestCandle(null);
    } finally {
      clearTimeout(timeoutId);
      setIsLoading(false);
    }
  }, [activeSymbol, activeTimeframe, updateTick, t]);

  // Trigger real data fetch on symbol or timeframe change
  useEffect(() => {
    fetchMarketCandles();
    const interval = setInterval(fetchMarketCandles, 8000);
    return () => clearInterval(interval);
  }, [fetchMarketCandles]);

  const handleSymbolChange = (sym: string) => {
    setActiveSymbol(sym.toUpperCase());
    setStoreSymbol(sym.toUpperCase());
  };

  const handleCustomSymbolSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (customInput.trim()) {
      handleSymbolChange(customInput.trim());
      setCustomInput("");
    }
  };

  const displayCandle = hoveredCandle || latestCandle;
  const priceChange = displayCandle ? displayCandle.close - displayCandle.open : 0;
  const priceChangePct = displayCandle && displayCandle.open > 0 ? (priceChange / displayCandle.open) * 100 : 0;
  const isUp = priceChange >= 0;

  return (
    <div className="relative flex-1 w-full h-full bg-[#0b0e14] overflow-hidden flex flex-col font-mono select-none">
      {/* Top Controls Bar */}
      <div className="flex flex-wrap items-center justify-between px-3 py-2 border-b border-surface-border bg-[#0d121c] gap-2 text-xs">
        {/* Symbol Selector Pills & Search */}
        <div className="flex items-center space-x-2 overflow-x-auto custom-scrollbar">
          <div className="flex items-center space-x-1">
            {POPULAR_SYMBOLS.map((item) => (
              <button
                key={item.symbol}
                onClick={() => handleSymbolChange(item.symbol)}
                className={`px-2 py-1 rounded text-[11px] font-bold transition ${
                  activeSymbol === item.symbol
                    ? "bg-accent text-black shadow-sm shadow-cyan-500/30"
                    : "bg-[#111722] text-slate-300 hover:text-white hover:bg-[#1a2234] border border-surface-border"
                }`}
              >
                {item.label}
              </button>
            ))}
          </div>

          <form onSubmit={handleCustomSymbolSubmit} className="flex items-center">
            <input
              type="text"
              placeholder={t("market_chart.search_placeholder")}
              value={customInput}
              onChange={(e) => setCustomInput(e.target.value.toUpperCase())}
              className="bg-[#111722] border border-surface-border rounded px-2 py-1 text-[11px] text-white w-24 focus:outline-none focus:border-accent uppercase"
            />
          </form>
        </div>

        {/* Timeframe Selector & Refresh */}
        <div className="flex items-center space-x-2">
          <div className="flex items-center space-x-1 bg-[#111722] p-0.5 rounded border border-surface-border">
            {TIMEFRAMES.map((item) => (
              <button
                key={item.tf}
                onClick={() => setActiveTimeframe(item.tf)}
                className={`px-2 py-0.5 rounded font-mono text-[11px] transition ${
                  activeTimeframe === item.tf
                    ? "bg-accent/20 text-accent font-bold"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                {item.label}
              </button>
            ))}
          </div>

          <button
            onClick={fetchMarketCandles}
            disabled={isLoading}
            className="p-1.5 rounded bg-[#111722] hover:bg-[#1a2234] border border-surface-border text-slate-300 hover:text-white transition disabled:opacity-50"
            title={t("market_chart.refresh_tooltip")}
          >
            <RefreshCw className={`w-3.5 h-3.5 text-accent ${isLoading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {/* Real OHLCV Telemetry Crosshair Bar */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-[#090d14] border-b border-surface-border text-[11px] text-slate-400 font-mono">
        <div className="flex items-center space-x-3">
          <span className="font-bold text-white flex items-center space-x-1">
            <BarChart2 className="w-3.5 h-3.5 text-accent inline mr-1" />
            <span>{activeSymbol}</span>
            <span className="text-slate-500 text-[10px]">({activeTimeframe})</span>
          </span>

          {displayCandle && (
            <div className="flex items-center space-x-3">
              <span>
                O: <span className="text-slate-200">${displayCandle.open.toFixed(2)}</span>
              </span>
              <span>
                H: <span className="text-emerald-400">${displayCandle.high.toFixed(2)}</span>
              </span>
              <span>
                L: <span className="text-rose-400">${displayCandle.low.toFixed(2)}</span>
              </span>
              <span>
                C: <span className="text-white font-bold">${displayCandle.close.toFixed(2)}</span>
              </span>
              <span>
                Vol: <span className="text-cyan-400">{displayCandle.volume.toLocaleString()}</span>
              </span>
            </div>
          )}
        </div>

        {displayCandle && (
          <div className="flex items-center space-x-2">
            <span className={`font-bold ${isUp ? "text-emerald-400" : "text-rose-400"}`}>
              {isUp ? "+" : ""}${priceChange.toFixed(2)} ({isUp ? "+" : ""}{priceChangePct.toFixed(2)}%)
            </span>
          </div>
        )}
      </div>

      {/* Chart Canvas Area */}
      <div className="relative flex-1 w-full h-full">
        <div ref={chartContainerRef} className="w-full h-full" />

        {/* Loading Overlay */}
        {isLoading && !latestCandle && (
          <div className="absolute inset-0 bg-[#0b0e14]/80 flex flex-col items-center justify-center space-y-2 z-10">
            <RefreshCw className="w-6 h-6 text-accent animate-spin" />
            <span className="text-xs text-slate-400">{t("market_chart.loading_candles", { symbol: activeSymbol })}</span>
          </div>
        )}

        {/* Authentic Error State Banner */}
        {errorMsg && (
          <div className="absolute inset-0 bg-[#0b0e14]/90 flex flex-col items-center justify-center p-6 space-y-3 z-20 text-center">
            <AlertCircle className="w-8 h-8 text-rose-400" />
            <div className="text-sm font-bold text-white">{t("market_chart.error_title")}</div>
            <p className="text-xs text-slate-400 max-w-md">{errorMsg}</p>
            <button
              onClick={fetchMarketCandles}
              className="px-4 py-1.5 bg-accent hover:bg-sky-400 text-black font-bold text-xs rounded transition shadow-md cursor-pointer"
            >
              {t("market_chart.retry_btn")}
            </button>
          </div>
        )}
      </div>
    </div>
  );
};