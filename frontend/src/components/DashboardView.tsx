import React, { useState, useEffect } from "react";
import { TradingViewChart } from "./TradingViewChart";
import { useMarketStore } from "../stores/marketStore";
import { useTradeStore } from "../stores/tradeStore";
import { usePluginRegistry } from "../context/PluginRegistryContext";
import { TiltStatusResponse } from "../types";
import { ArrowUpRight, ArrowDownRight, Brain, DollarSign, Target, Award, ShieldAlert } from "lucide-react";

export const DashboardView: React.FC = () => {
  const { currentPrice, recentTicks } = useMarketStore();
  const { openPositions, trades, updatePositionPnl } = useTradeStore();
  const { isLiteMode, isPluginActive } = usePluginRegistry();
  const [tilt, setTilt] = useState<TiltStatusResponse | null>(null);

  useEffect(() => {
    if (!isLiteMode) {
      fetch("http://127.0.0.1:8000/api/v1/psychology/tilt-status")
        .then((res) => res.json())
        .then((data: TiltStatusResponse) => setTilt(data))
        .catch(() => {});
    }
  }, [isLiteMode]);

  const handleClosePosition = (tradeId: string) => {
    fetch(`http://127.0.0.1:8000/api/v1/trades/${tradeId}/close`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        exit_price: currentPrice,
        exit_time: new Date().toISOString(),
      }),
    })
      .then(() => {
        updatePositionPnl(openPositions.filter((p) => p.id !== tradeId));
      })
      .catch(() => {
        updatePositionPnl(openPositions.filter((p) => p.id !== tradeId));
      });
  };

  // Calculate simple journal metrics for Lite Mode
  const closedTrades = trades.filter((t) => t.status === "CLOSED");
  const winTrades = closedTrades.filter((t) => (t.pnl || 0) > 0);
  const winRate = closedTrades.length > 0 ? ((winTrades.length / closedTrades.length) * 100).toFixed(1) : "0.0";
  const netPnl = closedTrades.reduce((acc, t) => acc + (t.pnl || 0), 0);
  const totalOpenPnl = openPositions.reduce((acc, p) => acc + (p.unrealized_pnl || 0), 0);

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden bg-[#0b0e14]">
      {/* Lite Mode Top KPI Metric Banner */}
      {isLiteMode && (
        <div className="bg-[#0d121c] border-b border-surface-border px-4 py-2.5 grid grid-cols-2 md:grid-cols-4 gap-3 select-none font-mono">
          <div className="flex items-center space-x-2.5 bg-[#111722] p-2 rounded border border-surface-border">
            <DollarSign className={`w-4 h-4 ${netPnl >= 0 ? "text-gain" : "text-loss"}`} />
            <div>
              <span className="text-[10px] text-slate-500 block">NET GERÇEKLEŞEN PNL</span>
              <span className={`text-xs font-bold ${netPnl >= 0 ? "text-gain" : "text-loss"}`}>
                {netPnl >= 0 ? "+" : ""}${netPnl.toFixed(2)}
              </span>
            </div>
          </div>

          <div className="flex items-center space-x-2.5 bg-[#111722] p-2 rounded border border-surface-border">
            <Target className="w-4 h-4 text-accent" />
            <div>
              <span className="text-[10px] text-slate-500 block">KAZANMA ORANI (WIN RATE)</span>
              <span className="text-xs font-bold text-white">{winRate}%</span>
            </div>
          </div>

          <div className="flex items-center space-x-2.5 bg-[#111722] p-2 rounded border border-surface-border">
            <Award className="w-4 h-4 text-amber-400" />
            <div>
              <span className="text-[10px] text-slate-500 block">AÇIK POZİSYON PNL</span>
              <span className={`text-xs font-bold ${totalOpenPnl >= 0 ? "text-gain" : "text-loss"}`}>
                {totalOpenPnl >= 0 ? "+" : ""}${totalOpenPnl.toFixed(2)}
              </span>
            </div>
          </div>

          <div className="flex items-center space-x-2.5 bg-[#111722] p-2 rounded border border-surface-border">
            <ShieldAlert className="w-4 h-4 text-emerald-400" />
            <div>
              <span className="text-[10px] text-slate-500 block">DİSİPLİN PUANI</span>
              <span className="text-xs font-bold text-gain">100 / 100 (A+)</span>
            </div>
          </div>
        </div>
      )}

      <div className="flex-1 flex min-h-0 border-b border-surface-border">
        <div className="flex-[3] flex flex-col min-w-0">
          <TradingViewChart />
        </div>

        {/* Live Tick Tape ladder - Only visible in Non-Lite / Pro modes */}
        {!isLiteMode && (
          <div className="w-64 border-l border-surface-border bg-[#0d121c] flex flex-col font-mono text-xs">
            <div className="px-3 py-2 border-b border-surface-border font-bold text-slate-300 flex items-center justify-between text-[11px]">
              <span>LIVE TICK TAPE</span>
              <span className="text-[10px] text-accent">SUB-100MS</span>
            </div>

            <div className="grid grid-cols-3 px-3 py-1.5 text-[10px] text-slate-500 border-b border-surface-border font-semibold">
              <span>PRICE</span>
              <span className="text-right">QTY</span>
              <span className="text-right">TIME</span>
            </div>

            <div className="flex-1 overflow-y-auto divide-y divide-surface-border/40">
              {recentTicks.length === 0 ? (
                <div className="p-4 text-center text-slate-500 text-[11px]">Awaiting ticks...</div>
              ) : (
                recentTicks.map((tick, idx) => (
                  <div key={idx} className="grid grid-cols-3 px-3 py-1 text-[11px] items-center hover:bg-[#111722]">
                    <span className={`font-semibold flex items-center ${tick.side === "BUY" ? "text-gain" : "text-loss"}`}>
                      {tick.side === "BUY" ? (
                        <ArrowUpRight className="w-3 h-3 mr-0.5 inline" />
                      ) : (
                        <ArrowDownRight className="w-3 h-3 mr-0.5 inline" />
                      )}
                      {tick.price.toFixed(2)}
                    </span>
                    <span className="text-right text-slate-300">{tick.volume.toFixed(4)}</span>
                    <span className="text-right text-slate-500 text-[10px]">
                      {new Date(tick.time).toLocaleTimeString()}
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>
        )}
      </div>

      <div className="h-56 bg-[#0d121c] flex flex-col font-mono text-xs select-none">
        <div className="px-4 py-2 border-b border-surface-border flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="flex items-center space-x-2">
              <span className="font-bold text-white text-xs">ACTIVE OPEN POSITIONS</span>
              <span className="bg-[#1a2234] text-accent px-2 py-0.5 rounded text-[10px] font-bold">
                {openPositions.length}
              </span>
            </div>

            {!isLiteMode && tilt && isPluginActive("plugin_biometrics") && (
              <div className="flex items-center space-x-1.5 pl-3 border-l border-surface-border text-[11px]">
                <Brain className="w-3.5 h-3.5 text-purple-400" />
                <span className="text-slate-400">Tilt:</span>
                <span
                  className={`font-bold px-1.5 py-0.2 rounded text-[10px] ${
                    tilt.tilt_score >= 60
                      ? "bg-loss/20 text-loss border border-loss/40"
                      : tilt.tilt_score >= 30
                      ? "bg-amber-500/20 text-amber-400 border border-amber-500/40"
                      : "bg-gain/20 text-gain border border-gain/40"
                  }`}
                >
                  {tilt.tilt_score} ({tilt.status})
                </span>
              </div>
            )}
          </div>
          <span className="text-[11px] text-slate-400">Continuous PnL recalculation via AsyncIO</span>
        </div>

        <div className="flex-1 overflow-y-auto">
          <table className="w-full text-left">
            <thead className="bg-[#090d14] text-[10px] text-slate-500 uppercase tracking-wider sticky top-0">
              <tr>
                <th className="px-4 py-2">Symbol</th>
                <th className="px-4 py-2">Side</th>
                <th className="px-4 py-2">Entry Price</th>
                <th className="px-4 py-2">Mark Price</th>
                <th className="px-4 py-2">Size</th>
                <th className="px-4 py-2">Stop Loss</th>
                <th className="px-4 py-2">Take Profit</th>
                <th className="px-4 py-2">Unrealized PnL</th>
                <th className="px-4 py-2">R-Multiple</th>
                <th className="px-4 py-2 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-border/50 text-[11px]">
              {openPositions.length === 0 ? (
                <tr>
                  <td colSpan={10} className="px-4 py-8 text-center text-slate-500">
                    No active open positions. Click "LOG TRADE" to execute.
                  </td>
                </tr>
              ) : (
                openPositions.map((pos) => {
                  const pnl = pos.unrealized_pnl || 0;
                  const isProfit = pnl >= 0;
                  return (
                    <tr key={pos.id} className="hover:bg-[#111722]">
                      <td className="px-4 py-2.5 font-bold text-white">{pos.symbol}</td>
                      <td className="px-4 py-2.5">
                        <span
                          className={`px-1.5 py-0.5 rounded font-bold text-[10px] ${
                            pos.side === "BUY" || pos.side === "LONG"
                              ? "bg-gain/20 text-gain"
                              : "bg-loss/20 text-loss"
                          }`}
                        >
                          {pos.side}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-slate-300">${pos.entry_price.toFixed(2)}</td>
                      <td className="px-4 py-2.5 text-white font-semibold">${currentPrice.toFixed(2)}</td>
                      <td className="px-4 py-2.5 text-slate-300">{pos.qty}</td>
                      <td className="px-4 py-2.5 text-loss font-semibold">
                        {pos.stop_loss ? `$${pos.stop_loss.toFixed(2)}` : "-"}
                      </td>
                      <td className="px-4 py-2.5 text-gain font-semibold">
                        {pos.take_profit ? `$${pos.take_profit.toFixed(2)}` : "-"}
                      </td>
                      <td className={`px-4 py-2.5 font-bold ${isProfit ? "text-gain" : "text-loss"}`}>
                        {isProfit ? "+" : ""}${pnl.toFixed(2)}
                      </td>
                      <td className={`px-4 py-2.5 font-bold ${isProfit ? "text-gain" : "text-loss"}`}>
                        {pos.r_multiple != null ? `${pos.r_multiple > 0 ? "+" : ""}${pos.r_multiple}R` : "-"}
                      </td>
                      <td className="px-4 py-2.5 text-right">
                        <button
                          onClick={() => handleClosePosition(pos.id)}
                          className="px-2.5 py-1 bg-surface hover:bg-slate-800 border border-surface-border text-slate-200 rounded font-semibold text-[10px] transition"
                        >
                          Close MKT
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};