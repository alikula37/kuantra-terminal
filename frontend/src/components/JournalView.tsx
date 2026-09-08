import React, { useState, useEffect } from "react";
import { useTradeStore } from "../stores/tradeStore";
import { Filter, Plus, PlayCircle, BookOpen, Upload, FileCheck2, ClipboardCheck, CalendarClock } from "lucide-react";
import { useTranslation } from "../context/I18nContext";
import { apiFetch, apiUrl } from "../lib/backend";
import { TradeEvidencePanel } from "./TradeEvidencePanel";
import { ReconciliationInbox } from "./ReconciliationInbox";
import { WeeklyReviewPanel } from "./WeeklyReviewPanel";

interface JournalViewProps {
  onOpenNewTrade: () => void;
  onOpenCsvImport?: () => void;
  onReplayTrade?: (tradeId: string) => void;
}

export const JournalView: React.FC<JournalViewProps> = ({ onOpenNewTrade, onOpenCsvImport, onReplayTrade }) => {
  const { t } = useTranslation();
  const { trades, setTrades } = useTradeStore();
  const [filterSymbol, setFilterSymbol] = useState<string>("ALL");
  const [filterStatus, setFilterStatus] = useState<string>("ALL");
  const [evidenceTradeId, setEvidenceTradeId] = useState<string | null>(null);
  const [reconciliationInboxOpen, setReconciliationInboxOpen] = useState(false);
  const [weeklyReviewOpen, setWeeklyReviewOpen] = useState(false);

  useEffect(() => {
    apiFetch(apiUrl("/api/v1/trades?limit=200"))
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
          <h2 className="text-base font-bold text-white">{t("journal.title")}</h2>
          <p className="text-xs text-slate-400">{t("journal.subtitle")}</p>
        </div>

        <div className="flex items-center space-x-3 text-xs">
          <div className="flex items-center space-x-2 bg-[#111722] px-3 py-1.5 rounded border border-surface-border">
            <Filter className="w-3.5 h-3.5 text-slate-400" />
            <select
              value={filterSymbol}
              onChange={(e) => setFilterSymbol(e.target.value)}
              className="bg-transparent text-white focus:outline-none"
            >
              <option value="ALL">{t("journal.filter_all_symbols")}</option>
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
              <option value="ALL">{t("journal.filter_all_status")}</option>
              <option value="OPEN">{t("journal.status_open")}</option>
              <option value="CLOSED">{t("journal.status_closed")}</option>
            </select>
          </div>

          <button
            onClick={onOpenCsvImport}
            className="flex items-center space-x-1.5 bg-[#162032] hover:bg-[#1f2d47] border border-surface-border text-slate-200 font-semibold px-3 py-1.5 rounded transition shadow-sm cursor-pointer"
          >
            <Upload className="w-3.5 h-3.5 text-accent" />
            <span>{t("journal.import_csv")}</span>
          </button>

          <button
            onClick={() => setReconciliationInboxOpen(true)}
            className="flex items-center space-x-1.5 bg-[#162032] hover:bg-[#1f2d47] border border-amber-400/40 text-amber-300 font-semibold px-3 py-1.5 rounded transition shadow-sm cursor-pointer"
          >
            <ClipboardCheck className="w-3.5 h-3.5" />
            <span>{t("journal.reconciliation_inbox")}</span>
          </button>

          <button
            onClick={() => setWeeklyReviewOpen(true)}
            className="flex items-center space-x-1.5 bg-[#162032] hover:bg-[#1f2d47] border border-accent/40 text-accent font-semibold px-3 py-1.5 rounded transition shadow-sm cursor-pointer"
          >
            <CalendarClock className="w-3.5 h-3.5" />
            <span>{t("journal.weekly_review")}</span>
          </button>

          <button
            onClick={onOpenNewTrade}
            className="flex items-center space-x-1.5 bg-accent hover:bg-sky-400 text-black font-bold px-3 py-1.5 rounded transition shadow-md cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>{t("journal.manual_entry")}</span>
          </button>
        </div>
      </div>

      {trades.length === 0 ? (
        <div className="flex-1 mt-4 rounded-lg border border-surface-border bg-[#0d121c] flex flex-col items-center justify-center p-8 text-center select-none font-mono">
          <div className="w-14 h-14 rounded-full bg-[#162032] flex items-center justify-center mb-3 border border-surface-border">
            <BookOpen className="w-7 h-7 text-accent" />
          </div>
          <h3 className="text-base font-bold text-white mb-1.5 uppercase tracking-wide">
            {t("journal.empty_title")}
          </h3>
          <p className="text-xs text-slate-400 max-w-md mb-6 leading-relaxed">
            {t("journal.empty_desc")}
          </p>
          <div className="flex items-center space-x-3">
            <button
              onClick={onOpenNewTrade}
              className="flex items-center space-x-1.5 px-4 py-2 bg-accent hover:bg-sky-400 text-black font-bold rounded text-xs transition shadow-md cursor-pointer"
            >
              <Plus className="w-4 h-4" />
              <span>{t("journal.manual_entry")}</span>
            </button>
            <button
              onClick={onOpenCsvImport}
              className="flex items-center space-x-1.5 px-4 py-2 bg-[#162032] hover:bg-[#1f2d47] border border-surface-border text-slate-200 font-semibold rounded text-xs transition cursor-pointer"
            >
              <Upload className="w-4 h-4 text-accent" />
              <span>{t("journal.import_csv")}</span>
            </button>
          </div>
        </div>
      ) : (
        <div className="flex-1 mt-4 overflow-y-auto rounded-lg border border-surface-border bg-[#0d121c]">
          <table className="w-full text-left text-xs">
            <thead className="bg-[#090d14] text-[10px] text-slate-400 uppercase tracking-wider sticky top-0 border-b border-surface-border">
              <tr>
                <th className="px-4 py-3">{t("journal.col_trade_id")}</th>
                <th className="px-4 py-3">{t("journal.col_symbol")}</th>
                <th className="px-4 py-3">{t("journal.col_side")}</th>
                <th className="px-4 py-3">{t("journal.col_entry")}</th>
                <th className="px-4 py-3">{t("journal.col_exit")}</th>
                <th className="px-4 py-3">{t("journal.col_qty")}</th>
                <th className="px-4 py-3">{t("journal.col_pnl")}</th>
                <th className="px-4 py-3">{t("journal.col_r")}</th>
                <th className="px-4 py-3">{t("journal.col_time")}</th>
                <th className="px-4 py-3">{t("journal.col_status")}</th>
                <th className="px-4 py-3 text-right">{t("journal.col_actions")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-border/40 text-[11px]">
              {filteredTrades.length === 0 ? (
                <tr>
                    <td colSpan={11} className="px-4 py-12 text-center text-slate-500">
                    {t("journal.no_matching")}
                  </td>
                </tr>
              ) : (
              filteredTrades.map((tItem) => {
                const pnl = tItem.pnl || 0;
                const isWin = pnl > 0;
                return (
                  <tr key={tItem.id} className="hover:bg-[#111722] transition">
                    <td className="px-4 py-2.5 font-bold text-accent">{tItem.id}</td>
                    <td className="px-4 py-2.5 font-bold text-white">{tItem.symbol}</td>
                    <td className="px-4 py-2.5">
                      <span
                        className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                          tItem.side === "BUY" || tItem.side === "LONG"
                            ? "bg-gain/20 text-gain"
                            : "bg-loss/20 text-loss"
                        }`}
                      >
                        {tItem.side}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-slate-200">${Number(tItem.entry_price).toFixed(2)}</td>
                    <td className="px-4 py-2.5 text-slate-200">
                      {tItem.exit_price != null ? `$${Number(tItem.exit_price).toFixed(2)}` : "-"}
                    </td>
                    <td className="px-4 py-2.5 text-slate-300">{tItem.qty}</td>
                    <td className={`px-4 py-2.5 font-bold ${isWin ? "text-gain" : pnl < 0 ? "text-loss" : "text-slate-400"}`}>
                      {tItem.status === "CLOSED" ? `${isWin ? "+" : ""}$${pnl.toFixed(2)}` : "-"}
                    </td>
                    <td className={`px-4 py-2.5 font-bold ${isWin ? "text-gain" : pnl < 0 ? "text-loss" : "text-slate-400"}`}>
                      {tItem.r_multiple != null ? `${tItem.r_multiple > 0 ? "+" : ""}${tItem.r_multiple}R` : "-"}
                    </td>
                    <td className="px-4 py-2.5 text-slate-400 text-[10px]">
                      {new Date(tItem.entry_time).toLocaleString()}
                    </td>
                    <td className="px-4 py-2.5">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          tItem.status === "OPEN"
                            ? "bg-sky-500/20 text-accent border border-accent/30"
                            : "bg-slate-800 text-slate-300"
                        }`}
                      >
                        {tItem.status}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-right">
                      <button
                        onClick={() => onReplayTrade && onReplayTrade(tItem.id)}
                        className="inline-flex items-center space-x-1 px-2 py-0.5 bg-accent/15 hover:bg-accent/30 border border-accent/40 text-accent font-bold rounded text-[10px] transition"
                        title="Replay this trade bar-by-bar"
                      >
                        <PlayCircle className="w-3 h-3" />
                        <span>{t("journal.replay_btn")}</span>
                      </button>
                      <button
                        onClick={() => setEvidenceTradeId(tItem.id)}
                        className="inline-flex items-center space-x-1 px-2 py-0.5 ml-1 bg-[#162032] hover:bg-[#1f2d47] border border-surface-border text-slate-200 font-bold rounded text-[10px] transition"
                        title="Open source-linked Trade Evidence Pack"
                      >
                        <FileCheck2 className="w-3 h-3 text-accent" />
                        <span>Evidence</span>
                      </button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    )}
      {evidenceTradeId && (
        <TradeEvidencePanel tradeId={evidenceTradeId} onClose={() => setEvidenceTradeId(null)} />
      )}
      {reconciliationInboxOpen && (
        <ReconciliationInbox
          onClose={() => setReconciliationInboxOpen(false)}
          onOpenEvidence={(tradeId) => {
            setReconciliationInboxOpen(false);
            setEvidenceTradeId(tradeId);
          }}
        />
      )}
      {weeklyReviewOpen && <WeeklyReviewPanel onClose={() => setWeeklyReviewOpen(false)} />}
  </div>
  );
};
