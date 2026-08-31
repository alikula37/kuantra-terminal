import React from "react";
import { Crosshair, Plus, Shield, Edit3, XCircle } from "lucide-react";
import { useTranslation } from "../../context/I18nContext";
import { Trade } from "../../types";

interface OpenPositionsTableProps {
  positions: Trade[];
  loading?: boolean;
  onClosePosition: (tradeId: string) => void;
  onEditPosition?: (trade: Trade) => void;
  onOpenNewTrade?: () => void;
}

export const OpenPositionsTable: React.FC<OpenPositionsTableProps> = ({
  positions,
  loading,
  onClosePosition,
  onEditPosition,
  onOpenNewTrade,
}) => {
  const { t } = useTranslation();

  if (loading) {
    return (
      <div className="bg-[#111722] p-4 rounded-lg border border-surface-border animate-pulse h-48 flex items-center justify-center text-slate-500 font-mono text-xs">
        <span>{t("open_positions.loading")}</span>
      </div>
    );
  }

  return (
    <div className="bg-[#111722] p-4 rounded-lg border border-surface-border flex flex-col select-none font-mono">
      <div className="flex items-center justify-between pb-3 border-b border-surface-border">
        <div className="flex items-center space-x-2">
          <Crosshair className="w-4 h-4 text-accent" />
          <span className="text-xs font-bold text-white uppercase tracking-wider">
            {t("open_positions.title")}
          </span>
        </div>
        <span className="text-[10px] text-slate-400 font-semibold">
          {t("open_positions.active_count", { count: positions.length })}
        </span>
      </div>

      {positions.length === 0 ? (
        <div className="py-10 flex flex-col items-center justify-center text-center select-none font-mono">
          <div className="w-10 h-10 rounded-full bg-[#162032] flex items-center justify-center mb-2.5 border border-surface-border">
            <Shield className="w-5 h-5 text-slate-500" />
          </div>
          <h4 className="text-xs font-bold text-slate-200 mb-1 uppercase tracking-wide">
            {t("open_positions.empty_title")}
          </h4>
          <p className="text-[11px] text-slate-500 max-w-sm mb-3">
            {t("open_positions.empty_desc")}
          </p>
          {onOpenNewTrade && (
            <button
              onClick={onOpenNewTrade}
              className="flex items-center space-x-1.5 px-3 py-1 bg-[#162032] hover:bg-[#1f2d47] border border-surface-border text-accent font-semibold rounded text-xs transition cursor-pointer"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>{t("open_positions.open_action")}</span>
            </button>
          )}
        </div>
      ) : (
        <div className="overflow-x-auto mt-2">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="text-[10px] text-slate-400 uppercase border-b border-surface-border pb-1">
                <th className="py-2 px-3">{t("open_positions.col_symbol")}</th>
                <th className="py-2 px-3">{t("open_positions.col_side")}</th>
                <th className="py-2 px-3">{t("open_positions.col_qty")}</th>
                <th className="py-2 px-3">{t("open_positions.col_entry")}</th>
                <th className="py-2 px-3">{t("open_positions.col_sl")}</th>
                <th className="py-2 px-3">{t("open_positions.col_tp")}</th>
                <th className="py-2 px-3">{t("open_positions.col_pnl")}</th>
                <th className="py-2 px-3">{t("open_positions.col_r")}</th>
                <th className="py-2 px-3 text-right">{t("open_positions.col_actions")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-border/50">
              {positions.map((p) => {
                const isLong = (p.side || "BUY").toUpperCase() === "BUY" || (p.side || "").toUpperCase() === "LONG";
                const pnl = p.pnl || 0.0;
                const isProfitable = pnl >= 0;
                const rMult = p.r_multiple ?? 0.0;

                return (
                  <tr key={p.id} className="hover:bg-[#0d121c] transition">
                    <td className="py-2.5 px-3 font-bold text-white flex items-center space-x-1.5">
                      <span>{p.symbol}</span>
                    </td>
                    <td className="py-2.5 px-3">
                      <span className={`text-[10px] px-2 py-0.5 rounded font-bold ${isLong ? "bg-emerald-500/10 text-gain border border-emerald-500/20" : "bg-rose-500/10 text-loss border border-rose-500/20"}`}>
                        {isLong ? "LONG" : "SHORT"}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-slate-300">{p.qty}</td>
                    <td className="py-2.5 px-3 text-slate-200 font-semibold">${p.entry_price.toLocaleString("en-US", { minimumFractionDigits: 2 })}</td>
                    <td className="py-2.5 px-3 text-loss font-semibold">{p.stop_loss ? `$${p.stop_loss.toLocaleString("en-US", { minimumFractionDigits: 2 })}` : "-"}</td>
                    <td className="py-2.5 px-3 text-gain font-semibold">{p.take_profit ? `$${p.take_profit.toLocaleString("en-US", { minimumFractionDigits: 2 })}` : "-"}</td>
                    <td className="py-2.5 px-3">
                      <span className={`font-bold ${isProfitable ? "text-gain" : "text-loss"}`}>
                        {isProfitable ? "+" : ""}${pnl.toFixed(2)}
                      </span>
                    </td>
                    <td className="py-2.5 px-3">
                      <span className={`font-bold ${rMult >= 0 ? "text-purple-300" : "text-loss"}`}>
                        {rMult >= 0 ? "+" : ""}{rMult.toFixed(2)}R
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-right">
                      <div className="flex items-center justify-end space-x-1.5">
                        {onEditPosition && (
                          <button
                            onClick={() => onEditPosition(p)}
                            className="p-1 rounded bg-[#161f2e] hover:bg-[#1f2c42] text-slate-300 hover:text-white transition"
                            title="SL/TP"
                          >
                            <Edit3 className="w-3.5 h-3.5" />
                          </button>
                        )}
                        <button
                          onClick={() => onClosePosition(p.id)}
                          className="px-2 py-1 rounded bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 border border-rose-500/30 text-[10px] font-bold transition active:scale-95 flex items-center space-x-1"
                          title={t("open_positions.close_btn")}
                        >
                          <XCircle className="w-3 h-3 mr-1" />
                          <span>{t("open_positions.close_btn")}</span>
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
