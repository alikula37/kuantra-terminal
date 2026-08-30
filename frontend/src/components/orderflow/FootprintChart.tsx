import React, { useState, useEffect } from "react";
import { Layers, RefreshCw, Zap } from "lucide-react";

interface FootprintBar {
  symbol: string;
  start_time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  total_volume: number;
  delta: number;
  poc_price: number;
  stacked_buy_imbalances: boolean;
  stacked_sell_imbalances: boolean;
  profile: Record<string, { bid_vol: number; ask_vol: number; total_vol: number }>;
}

export const FootprintChart: React.FC = () => {
  const [symbol, setSymbol] = useState<string>("BTCUSDT");
  const [bars, setBars] = useState<FootprintBar[]>([]);
  const [cvdDivergence, setCvdDivergence] = useState<string | null>("BULLISH_ABSORPTION");
  const [isLoading, setIsLoading] = useState<boolean>(false);

  const fetchFootprintData = () => {
    setIsLoading(true);
    fetch(`http://127.0.0.1:8000/api/v1/orderflow/footprint?symbol=${symbol}&limit=6`)
      .then((res) => res.json())
      .then((data) => {
        if (data.bars) setBars(data.bars);
      })
      .catch(() => {})
      .finally(() => setIsLoading(false));

    fetch(`http://127.0.0.1:8000/api/v1/orderflow/cvd?symbol=${symbol}`)
      .then((res) => res.json())
      .then((data) => {
        if (data.divergence?.has_divergence) {
          setCvdDivergence(data.divergence.detail);
        } else {
          setCvdDivergence(null);
        }
      })
      .catch(() => {});
  };

  useEffect(() => {
    fetchFootprintData();
    const interval = setInterval(fetchFootprintData, 3000);
    return () => clearInterval(interval);
  }, [symbol]);

  return (
    <div className="flex-1 flex flex-col h-full bg-[#0b0e14] overflow-hidden p-4 select-none font-mono space-y-4">
      {/* Header */}
      <div className="pb-3 border-b border-surface-border flex items-center justify-between">
        <div>
          <div className="flex items-center space-x-2">
            <Layers className="w-5 h-5 text-accent" />
            <h2 className="text-sm font-bold text-white uppercase tracking-wider">
              ORDER FLOW FOOTPRINT & VOLUME CLUSTERS
            </h2>
          </div>
          <p className="text-xs text-slate-400">
            Bid x Ask Diagonal Imbalance Matrix, Point of Control (POC), and Cumulative Volume Delta
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <select
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            className="bg-[#0d121c] border border-surface-border text-white px-3 py-1.5 rounded text-xs focus:outline-none focus:border-accent"
          >
            <option value="BTCUSDT">BTCUSDT (Crypto)</option>
            <option value="XAUUSD">XAUUSD (Gold)</option>
            <option value="ESM6">ESM6 (E-mini S&P 500)</option>
          </select>

          <button
            onClick={fetchFootprintData}
            disabled={isLoading}
            className="p-1.5 bg-[#0d121c] hover:bg-[#111722] border border-surface-border rounded text-slate-400 hover:text-white transition"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {/* CVD Divergence Alert Banner */}
      {cvdDivergence && (
        <div className="bg-accent/10 border border-accent/30 p-3 rounded-lg flex items-center justify-between text-xs">
          <div className="flex items-center space-x-2">
            <Zap className="w-4 h-4 text-accent animate-pulse" />
            <span className="font-bold text-white">INSTITUTIONAL ABSORPTION DETECTED:</span>
            <span className="text-slate-300">{cvdDivergence}</span>
          </div>
          <span className="bg-gain/20 text-gain text-[10px] px-2 py-0.5 rounded font-bold">
            ACCUMULATION
          </span>
        </div>
      )}

      {/* Footprint Bars Canvas Container */}
      <div className="flex-1 bg-[#0d121c] border border-surface-border rounded-lg p-4 overflow-x-auto overflow-y-auto flex space-x-4">
        {bars.map((bar, idx) => {
          const isUp = bar.close >= bar.open;
          const sortedPrices = Object.keys(bar.profile)
            .map((p) => parseFloat(p))
            .sort((a, b) => b - a); // Highest price top

          return (
            <div
              key={idx}
              className="flex-1 min-w-[170px] max-w-[220px] bg-[#111722] rounded border border-surface-border flex flex-col justify-between p-2.5 text-[11px]"
            >
              {/* Bar Header */}
              <div className="border-b border-surface-border pb-1.5 mb-2 text-center">
                <div className="flex items-center justify-between text-[10px]">
                  <span className="text-slate-400">Bar #{idx + 1}</span>
                  <span className={`font-bold ${isUp ? "text-gain" : "text-rose-500"}`}>
                    {bar.close.toFixed(1)}
                  </span>
                </div>
                {bar.stacked_buy_imbalances && (
                  <span className="inline-block mt-1 text-[9px] bg-gain/20 text-gain px-1.5 rounded font-bold">
                    STACKED BUY IMB
                  </span>
                )}
                {bar.stacked_sell_imbalances && (
                  <span className="inline-block mt-1 text-[9px] bg-rose-500/20 text-rose-400 px-1.5 rounded font-bold">
                    STACKED SELL IMB
                  </span>
                )}
              </div>

              {/* Price Ladder Ladder Clusters */}
              <div className="flex-1 space-y-1 overflow-y-auto pr-1">
                {sortedPrices.map((pVal) => {
                  const cluster = bar.profile[pVal.toString()] || bar.profile[pVal.toFixed(2)] || bar.profile[pVal.toFixed(0)];
                  if (!cluster) return null;
                  const isPoc = Math.abs(pVal - bar.poc_price) < 1.0;
                  const isBuyImbalance = cluster.ask_vol > cluster.bid_vol * 2.8 && cluster.bid_vol > 0;
                  const isSellImbalance = cluster.bid_vol > cluster.ask_vol * 2.8 && cluster.ask_vol > 0;

                  return (
                    <div
                      key={pVal}
                      className={`grid grid-cols-3 gap-1 px-1.5 py-0.5 rounded text-[10px] items-center ${
                        isPoc
                          ? "bg-accent/25 border border-accent/50 font-bold"
                          : "hover:bg-[#161f2e]"
                      }`}
                    >
                      {/* Bid Vol */}
                      <span className={`text-left font-mono ${isSellImbalance ? "text-rose-400 font-bold" : "text-slate-400"}`}>
                        {cluster.bid_vol.toFixed(1)}
                      </span>

                      {/* Price Level */}
                      <span className={`text-center font-mono ${isPoc ? "text-accent font-bold" : "text-slate-300"}`}>
                        {pVal.toFixed(0)}
                      </span>

                      {/* Ask Vol */}
                      <span className={`text-right font-mono ${isBuyImbalance ? "text-gain font-bold" : "text-slate-400"}`}>
                        {cluster.ask_vol.toFixed(1)}
                      </span>
                    </div>
                  );
                })}
              </div>

              {/* Bar Delta & Volume Footer */}
              <div className="border-t border-surface-border pt-2 mt-2 space-y-0.5 text-[10px]">
                <div className="flex items-center justify-between">
                  <span className="text-slate-400">Delta:</span>
                  <span className={`font-bold font-mono ${bar.delta >= 0 ? "text-gain" : "text-rose-500"}`}>
                    {bar.delta >= 0 ? `+${bar.delta.toFixed(1)}` : bar.delta.toFixed(1)}
                  </span>
                </div>
                <div className="flex items-center justify-between text-slate-400">
                  <span>Volume:</span>
                  <span className="font-mono text-white font-bold">{bar.total_volume.toFixed(1)}</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};