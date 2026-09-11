import React, { useEffect, useRef, useState, useCallback } from "react";
import { createChart, IChartApi, ISeriesApi, CandlestickData, Time, HistogramData } from "lightweight-charts";
import { useMarketStore } from "../stores/marketStore";
import { useTranslation } from "../context/I18nContext";
import { getChartTheme, useTheme } from "../context/ThemeContext";
import { RefreshCw, AlertCircle, BarChart2, Plus, X } from "lucide-react";
import { apiBase, apiFetch } from "../lib/backend";
import {
  MARKET_SYMBOL_CATALOG,
  createManualMarketInstrument,
  getMarketSymbolDefinition,
  resolveMarketSymbol,
} from "../lib/marketSymbols";
import { MarketInstrument } from "../lib/marketSymbols";
import { useInstrumentSearch } from "../hooks/useInstrumentSearch";

export interface CandleDataPoint {
  timestamp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function normalizeCandle(value: unknown): CandleDataPoint | null {
  if (!value || typeof value !== "object") return null;
  const candle = value as Record<string, unknown>;
  if (!isFiniteNumber(candle.timestamp) || candle.timestamp <= 0) return null;
  const prices = [candle.open, candle.high, candle.low, candle.close];
  if (!prices.every((price) => isFiniteNumber(price) && price > 0) || !isFiniteNumber(candle.volume) || candle.volume < 0) return null;
  const [open, high, low, close] = prices as number[];
  if (high < Math.max(open, low, close) || low > Math.min(open, high, close)) return null;
  return {
    timestamp: candle.timestamp > 1e11 ? Math.floor(candle.timestamp / 1000) : Math.floor(candle.timestamp),
    open,
    high,
    low,
    close,
    volume: candle.volume,
  };
}

const DEFAULT_CHART_SYMBOLS = MARKET_SYMBOL_CATALOG.map((item) => item.symbol);
const CHART_WATCHLIST_STORAGE_KEY = "kuantra.market-chart.symbols.v1";

function loadChartWatchlist(): string[] {
  if (typeof window === "undefined") return DEFAULT_CHART_SYMBOLS;
  try {
    const raw = window.localStorage.getItem(CHART_WATCHLIST_STORAGE_KEY);
    if (!raw) return DEFAULT_CHART_SYMBOLS;
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return DEFAULT_CHART_SYMBOLS;
    const normalized = parsed
      .filter((item): item is string => typeof item === "string")
      .map((item) => resolveMarketSymbol(item))
      .filter((item): item is string => Boolean(item));
    return Array.from(new Set(normalized)).length > 0
      ? Array.from(new Set(normalized))
      : DEFAULT_CHART_SYMBOLS;
  } catch {
    return DEFAULT_CHART_SYMBOLS;
  }
}

const TIMEFRAMES = [
  { tf: "1m", label: "1m" },
  { tf: "5m", label: "5m" },
  { tf: "15m", label: "15m" },
  { tf: "1h", label: "1H" },
  { tf: "4h", label: "4H" },
  { tf: "1d", label: "1D" },
];

function getVolumeColor(theme: "dark" | "light"): string {
  return theme === "light" ? "rgba(2, 132, 199, 0.25)" : "rgba(56, 189, 248, 0.25)";
}

export const TradingViewChart: React.FC = () => {
  const { t } = useTranslation();
  const { theme } = useTheme();
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);

  const { symbol: storeSymbol, setSymbol: setStoreSymbol } = useMarketStore();
  const [watchlist, setWatchlist] = useState<string[]>(() => loadChartWatchlist());
  const [activeSymbol, setActiveSymbol] = useState<string>(() => {
    const initialWatchlist = loadChartWatchlist();
    const normalizedStoreSymbol = resolveMarketSymbol(storeSymbol || "");
    return (normalizedStoreSymbol && initialWatchlist.includes(normalizedStoreSymbol))
      ? normalizedStoreSymbol
      : initialWatchlist[0] || normalizedStoreSymbol || "BTCUSDT";
  });
  const [activeTimeframe, setActiveTimeframe] = useState<string>("15m");
  const [customInput, setCustomInput] = useState<string>("");
  const [pendingInstrument, setPendingInstrument] = useState<MarketInstrument | null>(null);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [isCancelled, setIsCancelled] = useState<boolean>(false);
  const [hoveredCandle, setHoveredCandle] = useState<CandleDataPoint | null>(null);
  const [latestCandle, setLatestCandle] = useState<CandleDataPoint | null>(null);
  const candleControllerRef = useRef<AbortController | null>(null);
  const candleTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const candleRequestIdRef = useRef(0);
  const initialChartTheme = getChartTheme(theme);

  useEffect(() => {
    try {
      window.localStorage.setItem(CHART_WATCHLIST_STORAGE_KEY, JSON.stringify(watchlist));
    } catch {
      // Local persistence is a convenience; chart selection must still work if storage is unavailable.
    }
  }, [watchlist]);

  const { results: searchResults, status: searchStatus } = useInstrumentSearch(customInput);

  // Initialize Lightweight Charts Canvas
  useEffect(() => {
    if (!chartContainerRef.current) return;

    const chart = createChart(chartContainerRef.current, {
      layout: { ...initialChartTheme.layout, fontSize: 11 },
      grid: initialChartTheme.grid,
      crosshair: {
        vertLine: { color: initialChartTheme.palette.accent, width: 1, style: 3 },
        horzLine: { color: initialChartTheme.palette.accent, width: 1, style: 3 },
      },
      timeScale: {
        borderColor: initialChartTheme.palette.surfaceBorder,
        timeVisible: true,
        secondsVisible: false,
      },
      rightPriceScale: {
        borderColor: initialChartTheme.palette.surfaceBorder,
        scaleMargins: { top: 0.08, bottom: 0.2 },
      },
      handleScale: true,
      handleScroll: true,
    });

    const candleSeries = chart.addCandlestickSeries({
      ...initialChartTheme.candlestick,
      borderVisible: false,
    });

    const volumeSeries = chart.addHistogramSeries({
      color: getVolumeColor(theme),
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

  // Lightweight Charts owns its canvas, so update its palette explicitly when
  // the application theme changes instead of relying on CSS variables alone.
  useEffect(() => {
    const chart = chartRef.current;
    const candleSeries = candleSeriesRef.current;
    const volumeSeries = volumeSeriesRef.current;
    if (!chart || !candleSeries || !volumeSeries) return;

    const nextChartTheme = getChartTheme(theme);
    chart.applyOptions({
      ...nextChartTheme.layout,
      grid: nextChartTheme.grid,
      crosshair: {
        vertLine: { color: nextChartTheme.palette.accent, width: 1, style: 3 },
        horzLine: { color: nextChartTheme.palette.accent, width: 1, style: 3 },
      },
      timeScale: { borderColor: nextChartTheme.palette.surfaceBorder },
      rightPriceScale: { borderColor: nextChartTheme.palette.surfaceBorder },
    });
    candleSeries.applyOptions({ ...nextChartTheme.candlestick, borderVisible: false });
    volumeSeries.applyOptions({ color: getVolumeColor(theme) });
  }, [theme]);

  // Fetch 100% Real Historical Market Data from Backend with Timeout & AbortController Guard
  const fetchMarketCandles = useCallback(async () => {
    candleControllerRef.current?.abort();
    if (candleTimeoutRef.current) clearTimeout(candleTimeoutRef.current);
    const requestId = ++candleRequestIdRef.current;
    const controller = new AbortController();
    candleControllerRef.current = controller;
    let timedOut = false;
    setIsLoading(true);
    setErrorMsg(null);
    setIsCancelled(false);

    candleTimeoutRef.current = setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, 6000);

    try {
      const url = `${apiBase()}/api/v1/market-data/candles?symbol=${encodeURIComponent(
        activeSymbol
      )}&timeframe=${encodeURIComponent(activeTimeframe)}&limit=500`;

      const response = await apiFetch(url, { signal: controller.signal });
      if (!response.ok) {
        let detail = "";
        try {
          const payload = await response.json() as { detail?: unknown; message?: unknown };
          const candidate = [payload.detail, payload.message].find((item) => typeof item === "string");
          if (typeof candidate === "string") detail = candidate;
        } catch {
          // Keep the HTTP status as the bounded error when the body is not JSON.
        }
        throw new Error(detail || t("market_chart.http_error", { status: response.status, symbol: activeSymbol }));
      }

      let jsonRes: unknown;
      try {
        jsonRes = await response.json();
      } catch {
        throw new Error(t("market_chart.malformed"));
      }
      const rawData = jsonRes && typeof jsonRes === "object" && Array.isArray((jsonRes as Record<string, unknown>).candles)
        ? (jsonRes as { candles: unknown[] }).candles
        : null;

      if (!rawData) {
        throw new Error(t("market_chart.malformed"));
      }
      if (rawData.length === 0) {
        throw new Error(t("market_chart.no_candles", { symbol: activeSymbol }));
      }

      // Deduplicate and sort strictly ascending by time
      const timeMap = new Map<number, CandleDataPoint>();
      rawData.forEach((rawCandle) => {
        const c = normalizeCandle(rawCandle);
        if (!c) throw new Error(t("market_chart.malformed"));
        const timeSec = c.timestamp;
        if (!timeMap.has(timeSec)) {
          timeMap.set(timeSec, c);
        }
      });

      const sortedCandles = Array.from(timeMap.values()).sort((a, b) => a.timestamp - b.timestamp);

      if (sortedCandles.length === 0) {
        throw new Error(t("market_chart.no_candles", { symbol: activeSymbol }));
      }

      if (requestId !== candleRequestIdRef.current || controller.signal.aborted) return;

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
      setErrorMsg(null);
      setIsCancelled(false);
    } catch (err: any) {
      if (requestId !== candleRequestIdRef.current || (controller.signal.aborted && !timedOut)) return;
      console.warn("[TradingViewChart] Real market data error:", err);
      const message = timedOut
        ? t("market_chart.fetch_timeout", { symbol: activeSymbol })
        : err.message || t("market_chart.fetch_failed", { symbol: activeSymbol });
      setErrorMsg(message);
      if (candleSeriesRef.current && volumeSeriesRef.current) {
        candleSeriesRef.current.setData([]);
        volumeSeriesRef.current.setData([]);
      }
      setLatestCandle(null);
    } finally {
      if (requestId === candleRequestIdRef.current) {
        if (candleTimeoutRef.current) clearTimeout(candleTimeoutRef.current);
        candleTimeoutRef.current = null;
        candleControllerRef.current = null;
        setIsLoading(false);
      }
    }
  }, [activeSymbol, activeTimeframe, t]);

  // Trigger real data fetch on symbol or timeframe change
  useEffect(() => {
    void fetchMarketCandles();
    const interval = setInterval(() => void fetchMarketCandles(), 8000);
    return () => {
      clearInterval(interval);
      candleRequestIdRef.current += 1;
      candleControllerRef.current?.abort();
      candleControllerRef.current = null;
      if (candleTimeoutRef.current) clearTimeout(candleTimeoutRef.current);
      candleTimeoutRef.current = null;
    };
  }, [fetchMarketCandles]);

  const cancelMarketFetch = () => {
    if (!candleControllerRef.current) return;
    candleRequestIdRef.current += 1;
    candleControllerRef.current.abort();
    candleControllerRef.current = null;
    if (candleTimeoutRef.current) clearTimeout(candleTimeoutRef.current);
    candleTimeoutRef.current = null;
    setIsLoading(false);
    setIsCancelled(true);
    setErrorMsg(null);
  };

  const handleSymbolChange = (sym: string) => {
    setActiveSymbol(sym.toUpperCase());
    setStoreSymbol(sym.toUpperCase());
    setSearchError(null);
  };

  const handleConfirmSymbol = () => {
    if (!pendingInstrument) {
      setSearchError(t("market_chart.select_result_to_confirm"));
      return;
    }
    const symbol = pendingInstrument.symbol;
    if (!watchlist.includes(symbol)) {
      setWatchlist([...watchlist, symbol]);
    }
    handleSymbolChange(symbol);
    setCustomInput("");
    setPendingInstrument(null);
    setSearchError(null);
  };

  const handleSelectSearchResult = (instrument: MarketInstrument) => {
    setPendingInstrument(instrument);
    setCustomInput("");
    setSearchError(null);
  };

  const handleCustomSymbolSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!customInput.trim()) return;
    setSearchError(t("market_chart.select_result_to_confirm"));
  };

  const handleRemoveSymbol = (symbol: string) => {
    if (watchlist.length <= 1) {
      setSearchError(t("market_chart.keep_one_symbol"));
      return;
    }
    const nextWatchlist = watchlist.filter((item) => item !== symbol);
    setWatchlist(nextWatchlist);
    if (activeSymbol === symbol) {
      handleSymbolChange(nextWatchlist[0]);
    }
  };

  const displayCandle = hoveredCandle || latestCandle;
  const priceChange = displayCandle ? displayCandle.close - displayCandle.open : 0;
  const priceChangePct = displayCandle && displayCandle.open > 0 ? (priceChange / displayCandle.open) * 100 : 0;
  const isUp = priceChange >= 0;

  return (
    <div className="relative flex-1 w-full h-full bg-[#0b0e14] overflow-hidden flex flex-col font-mono select-none">
      <div className="shrink-0 border-b border-surface-border bg-[#0b0e14] px-3 py-2">
        <h1 data-testid="market-chart-page-title" className="text-sm font-bold text-white uppercase tracking-wider">
          {t("market_chart.title")}
        </h1>
        <p className="mt-0.5 text-[10px] text-slate-400">{t("market_chart.subtitle")}</p>
      </div>

      {/* Top Controls Bar */}
      <div className="flex flex-wrap items-center justify-between px-3 py-2 border-b border-surface-border bg-[#0d121c] gap-2 text-xs">
        {/* Symbol Selector Pills & Search */}
        <div className="relative flex items-center space-x-2 overflow-visible custom-scrollbar">
          <div data-testid="market-chart-watchlist" className="flex items-center space-x-1 overflow-x-auto custom-scrollbar">
              {watchlist.map((symbol) => {
                const definition = getMarketSymbolDefinition(symbol);
              const label = definition ? t(definition.labelKey) : symbol;
              return (
                <div key={symbol} className="flex items-center shrink-0">
                  <button
                    type="button"
                    data-testid={`market-chart-symbol-${symbol}`}
                    aria-pressed={activeSymbol === symbol}
                    aria-label={t("market_chart.select_symbol", { symbol: label })}
                    onClick={() => handleSymbolChange(symbol)}
                    className={`px-2 py-1 rounded-l text-[11px] font-bold transition ${
                      activeSymbol === symbol
                        ? "bg-accent text-black shadow-sm shadow-cyan-500/30"
                        : "bg-[#111722] text-slate-300 hover:text-white hover:bg-[#1a2234] border border-surface-border"
                    }`}
                  >
                    {label}
                  </button>
                  <button
                    type="button"
                    data-testid={`market-chart-remove-${symbol}`}
                    aria-label={t("market_chart.remove_symbol", { symbol: label })}
                    title={t("market_chart.remove_symbol", { symbol: label })}
                    onClick={() => handleRemoveSymbol(symbol)}
                    className={`px-1 py-1 rounded-r border-y border-r border-surface-border text-slate-500 hover:text-rose-300 hover:bg-rose-950/40 transition ${
                      activeSymbol === symbol ? "bg-accent/80 text-slate-800" : "bg-[#111722]"
                    }`}
                  >
                    <X className="w-3 h-3" />
                  </button>
                </div>
              );
            })}
          </div>

          <form onSubmit={handleCustomSymbolSubmit} className="flex items-center shrink-0">
            <input
              type="text"
              placeholder={t("market_chart.search_placeholder")}
              aria-label={t("market_chart.search_label")}
              data-testid="market-chart-symbol-search"
              value={customInput}
              onChange={(e) => setCustomInput(e.target.value.toUpperCase())}
              className="bg-[#111722] border border-surface-border rounded-l px-2 py-1 text-[11px] text-white w-28 focus:outline-none focus:border-accent uppercase"
            />
            <button
              type="submit"
              aria-label={t("market_chart.add_symbol")}
              title={t("market_chart.add_symbol")}
              className="p-1.5 rounded-r bg-[#111722] hover:bg-[#1a2234] border-y border-r border-surface-border text-accent transition"
            >
              <Plus className="w-3.5 h-3.5" />
            </button>
          </form>

          {customInput.trim() && (
            <div role="listbox" data-testid="market-chart-search-results" className="absolute left-0 top-full mt-1 z-30 min-w-64 max-w-80 rounded border border-surface-border bg-[#111722] p-1 shadow-xl">
              {searchResults.map((item) => (
                <button
                  key={item.symbol}
                  type="button"
                  role="option"
                  data-testid={`market-chart-search-result-${item.symbol}`}
                  onClick={() => handleSelectSearchResult(item)}
                  className="w-full flex items-center justify-between gap-3 rounded px-2 py-1.5 text-left text-[11px] text-slate-200 hover:bg-[#1a2234]"
                >
                    <span>
                      <span className="block">{item.name}</span>
                      <span className="block text-[10px] text-slate-400">{item.symbol} · {item.exchange || item.source_id}</span>
                    </span>
                    <span className="text-[10px] text-accent">
                    {watchlist.includes(item.symbol) ? t("market_chart.already_added") : t("market_chart.select_result")}
                  </span>
                </button>
              ))}
              {searchStatus === "SEARCHING" && (
                <div className="px-2 py-1.5 text-[11px] text-slate-400">{t("market_chart.searching")}</div>
              )}
              {searchStatus === "UNAVAILABLE" && (
                <div className="px-2 py-1.5 text-[11px] text-amber-300">{t("market_chart.search_unavailable")}</div>
              )}
              {searchStatus === "NO_MATCH" && (
                <div className="px-2 py-1.5 text-[11px] text-slate-400">{t("market_chart.no_search_results")}</div>
              )}
              {searchStatus !== "SEARCHING" && (() => {
                const manualInstrument = createManualMarketInstrument(customInput);
                if (!manualInstrument) return null;
                return (
                  <button
                    type="button"
                    role="option"
                    data-testid="market-chart-manual-symbol-result"
                    onClick={() => handleSelectSearchResult(manualInstrument)}
                    className="mt-1 w-full rounded border border-amber-400/30 bg-amber-950/20 px-2 py-1.5 text-left text-[11px] text-amber-200 hover:bg-amber-950/40"
                  >
                    <span className="block">{t("market_chart.manual_symbol_option", { symbol: manualInstrument.symbol })}</span>
                    <span className="block text-[10px] text-amber-300/80">{t("market_chart.manual_symbol_notice")}</span>
                  </button>
                );
              })()}
            </div>
          )}
          {searchError && <span role="alert" className="absolute left-0 top-full mt-1 z-30 rounded bg-rose-950/90 px-2 py-1 text-[10px] text-rose-200">{searchError}</span>}
          {pendingInstrument && (
            <div
              role="dialog"
              data-testid="market-chart-symbol-confirmation"
              className="absolute left-0 top-[calc(100%+2rem)] z-20 flex items-center gap-2 rounded border border-accent/40 bg-[#111722] px-2 py-1.5 text-[10px] text-slate-200 shadow-xl"
            >
              <span>
                {t("market_chart.confirm_symbol", { symbol: pendingInstrument.name })} <span className="text-slate-400">({pendingInstrument.symbol})</span>
                {pendingInstrument.source_id === "manual" && <span className="block text-amber-300">{t("market_chart.manual_symbol_notice")}</span>}
              </span>
              <button
                type="button"
                data-testid="market-chart-confirm-symbol"
                onClick={handleConfirmSymbol}
                className="rounded bg-accent px-2 py-1 font-bold text-black hover:bg-sky-300"
              >
                {t("market_chart.confirm")}
              </button>
              <button
                type="button"
                data-testid="market-chart-cancel-symbol"
                onClick={() => setPendingInstrument(null)}
                className="rounded border border-surface-border px-2 py-1 text-slate-300 hover:text-white"
              >
                {t("market_chart.cancel")}
              </button>
            </div>
          )}
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
            onClick={() => void fetchMarketCandles()}
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
                {t("market_chart.open")}: <span className="text-slate-200">${displayCandle.open.toFixed(2)}</span>
              </span>
              <span>
                {t("market_chart.high")}: <span className="text-emerald-400">${displayCandle.high.toFixed(2)}</span>
              </span>
              <span>
                {t("market_chart.low")}: <span className="text-rose-400">${displayCandle.low.toFixed(2)}</span>
              </span>
              <span>
                {t("market_chart.close")}: <span className="text-white font-bold">${displayCandle.close.toFixed(2)}</span>
              </span>
              <span>
                {t("market_chart.volume")}: <span className="text-cyan-400">{displayCandle.volume.toLocaleString()}</span>
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
        {isLoading && (
          <div className="absolute inset-0 bg-[#0b0e14]/80 flex flex-col items-center justify-center space-y-2 z-10">
            <RefreshCw className="w-6 h-6 text-accent animate-spin" />
            <span className="text-xs text-slate-400">{t("market_chart.loading_candles", { symbol: activeSymbol })}</span>
            <button type="button" data-testid="market-chart-cancel" onClick={cancelMarketFetch} className="px-3 py-1.5 rounded border border-surface-border text-slate-300 hover:bg-slate-800 text-xs">
              {t("market_chart.cancel_request")}
            </button>
          </div>
        )}

        {/* Authentic Error State Banner */}
        {errorMsg && (
          <div role="alert" data-testid="market-chart-error" className="absolute inset-0 bg-[#0b0e14]/90 flex flex-col items-center justify-center p-6 space-y-3 z-20 text-center">
            <AlertCircle className="w-8 h-8 text-rose-400" />
            <div className="text-sm font-bold text-white">{t("market_chart.error_title")}</div>
            <p className="text-xs text-slate-400 max-w-md">{errorMsg}</p>
            <button
              onClick={() => void fetchMarketCandles()}
              className="px-4 py-1.5 bg-accent hover:bg-sky-400 text-black font-bold text-xs rounded transition shadow-md cursor-pointer"
            >
              {t("market_chart.retry_btn")}
            </button>
          </div>
        )}
        {isCancelled && !isLoading && !errorMsg && (
          <div role="alert" data-testid="market-chart-cancelled" className="absolute inset-0 bg-[#0b0e14]/90 flex flex-col items-center justify-center p-6 space-y-3 z-20 text-center">
            <AlertCircle className="w-8 h-8 text-amber-400" />
            <div className="text-sm font-bold text-white">{t("market_chart.request_cancelled")}</div>
            <button
              type="button"
              onClick={() => void fetchMarketCandles()}
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
