import React, { useState, useEffect } from "react";
import { useTradeStore } from "../stores/tradeStore";
import { Filter, Plus, PlayCircle } from "lucide-react";

interface JournalViewProps {
  onOpenNewTrade: () => void;
  onReplayTrade?: (tradeId: string) => void;
}

export const JournalView: React.FC<JournalViewProps> = ({ onOpenNewTrade, onReplayTrade }) => {
  const { trades, setTrades } = useTradeStore();
  const [filterSymbol, setFilterSymbol] = useState<string>("ALL");
  const [filterStatus, setFilterStatus] = useState<string>("ALL");

  useEffect(() => {
    fetch("http://127.0.0.1:8000/api/v1/trades?limit=200")
      .then((res) => res.json())
      .then((data) => {
        if (Array.isArray(data)) {
          setTrades(data);
        }
      })
      .catch(() => {});
  }, [setTrades]);

  const filteredTrades = trades.filter((t) => {
    if (filterSymbol !== "ALL" && t.symbol !== filterSymbol) return false;
    if (filterStatus !== "ALL" && t.status !== filterStatus) return false;
    return true;
  });

  return (
    <div className="flex-1 flex flex-col h-full bg-[#0b0e14] overflow-hidden p-4 select-none font-mono">
      <div className="flex items-center justify-between pb-4 border-b border-surface-border">
        <div>
          <h2 className="text-base font-bold text-white">TRADE LOGGING JOURNAL</h2>
          <p className="text-xs text-slate-400">Institutional Execution Records & Audit Trail</p>
        </div>

        <div className="flex items-center space-x-3 text-xs">
          <div className="flex items-center space-x-2 bg-[#111722] px-3 py-1.5 rounded border border-surface-border">
            <Filter className="w-3.5 h-3.5 text-slate-400" />
            <select
              value={filterSymbol}
              onChange={(e) => setFilterSymbol(e.target.value)}
              className="bg-transparent text-white focus:outline-none"
            >
              <option value="ALL">All Symbols</option>
              <option value="BTCUSDT">BTCUSDT</option>
              <option value="ETHUSDT">ETHUSDT</option>
              <option value="SOLUSDT">SOLUSDT</option>
            </select>
          </div>

          <div className="flex items-center space-x-2 bg-[#111722] px-3 py-1.5 rounded border border-surface-border">
            <select
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
              className="bg-transparent text-white focus:outline-none"
            >
              <option value="ALL">All Status</option>
              <option value="OPEN">Open</option>
              <option value="CLOSED">Closed</option>
            </select>
          </div>

          <button
            onClick={onOpenNewTrade}
            className="flex items-center space-x-1.5 bg-accent hover:bg-sky-400 text-black font-bold px-3 py-1.5 rounded transition shadow-md"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>RECORD TRADE</span>
          </button>
        </div>
      </div>

      <div className="flex-1 mt-4 overflow-y-auto rounded-lg border border-surface-border bg-[#0d121c]">
        <table className="w-full text-left text-xs">
          <thead className="bg-[#090d14] text-[10px] text-slate-400 uppercase tracking-wider sticky top-0 border-b border-surface-border">
            <tr>
              <th className="px-4 py-3">Trade ID</th>
              <th className="px-4 py-3">Symbol</th>
              <th className="px-4 py-3">Side</th>
              <th className="px-4 py-3">Entry ($)</th>
              <th className="px-4 py-3">Exit ($)</th>
              <th className="px-4 py-3">Qty</th>
              <th className="px-4 py-3">PnL ($)</th>
              <th className="px-4 py-3">R-Multiple</th>
              <th className="px-4 py-3">Entry Time</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-surface-border/40 text-[11px]">
            {filteredTrades.length === 0 ? (
              <tr>
                <td colSpan={11} className="px-4 py-12 text-center text-slate-500">
                  No trades found matching current filter criteria.
                </td>
              </tr>
            ) : (
              filteredTrades.map((t) => {
                const pnl = t.pnl || 0;
                const isWin = pnl > 0;
                return (
                  <tr key={t.id} className="hover:bg-[#111722] transition">
                    <td className="px-4 py-2.5 font-bold text-accent">{t.id}</td>
                    <td className="px-4 py-2.5 font-bold text-white">{t.symbol}</td>
                    <td className="px-4 py-2.5">
                      <span
                        className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                          t.side === "BUY" || t.side === "LONG"
                            ? "bg-gain/20 text-gain"
                            : "bg-loss/20 text-loss"
                        }`}
                      >
                        {t.side}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-slate-200">${Number(t.entry_price).toFixed(2)}</td>
                    <td className="px-4 py-2.5 text-slate-200">
                      {t.exit_price != null ? `$${Number(t.exit_price).toFixed(2)}` : "-"}
                    </td>
                    <td className="px-4 py-2.5 text-slate-300">{t.qty}</td>
                    <td className={`px-4 py-2.5 font-bold ${isWin ? "text-gain" : pnl < 0 ? "text-loss" : "text-slate-400"}`}>
                      {t.status === "CLOSED" ? `${isWin ? "+" : ""}$${pnl.toFixed(2)}` : "-"}
                    </td>
                    <td className={`px-4 py-2.5 font-bold ${isWin ? "text-gain" : pnl < 0 ? "text-loss" : "text-slate-400"}`}>
                      {t.r_multiple != null ? `${t.r_multiple > 0 ? "+" : ""}${t.r_multiple}R` : "-"}
                    </td>
                    <td className="px-4 py-2.5 text-slate-400 text-[10px]">
                      {new Date(t.entry_time).toLocaleString()}
                    </td>
                    <td className="px-4 py-2.5">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          t.status === "OPEN"
                            ? "bg-sky-500/20 text-accent border border-accent/30"
                            : "bg-slate-800 text-slate-300"
                        }`}
                      >
                        {t.status}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-right">
                      <button
                        onClick={() => onReplayTrade && onReplayTrade(t.id)}
                        className="inline-flex items-center space-x-1 px-2 py-0.5 bg-accent/15 hover:bg-accent/30 border border-accent/40 text-accent font-bold rounded text-[10px] transition"
                        title="Replay this trade bar-by-bar"
                      >
                        <PlayCircle className="w-3 h-3" />
                        <span>Replay</span>
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
  );
};