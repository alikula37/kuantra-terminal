import React, { useEffect, useRef, useState } from "react";
import { Crosshair, Plus, Shield, Edit3, XCircle, RefreshCw } from "lucide-react";
import { useTranslation } from "../../context/I18nContext";
import { Trade } from "../../types";
import { useOpenQuoteRefresh, quoteAgeSeconds } from "../../hooks/useOpenQuoteRefresh";
import { apiFetch, apiUrl } from "../../lib/backend";
import { formatIstanbulDateTime, relativeAgeLabel } from "../../lib/tradeTime";
import { formatPositionValue, formatPrice, positionSizing } from "../../lib/positionMath";

interface OpenPositionsTableProps {
  positions: Trade[];
  loading?: boolean;
  onClosePosition: (tradeId: string) => void;
  onEditPosition?: (trade: Trade) => void;
  onOpenNewTrade?: () => void;
  refreshNonce?: number;
}

export const OpenPositionsTable: React.FC<OpenPositionsTableProps> = ({
  positions,
  loading,
  onClosePosition,
  onEditPosition,
  onOpenNewTrade,
  refreshNonce = 0,
}) => {
  const { t, locale } = useTranslation();
  const [verifiedSymbols, setVerifiedSymbols] = useState<Record<string, boolean>>({});
  const verificationRequested = useRef<Set<string>>(new Set());
  const {
    quotes,
    refresh,
    busy,
    error,
    lastSuccessAt,
    lastAttemptAt,
    nowMs,
  } = useOpenQuoteRefresh(positions.length > 0);

  // A parent-driven refresh (for example the Dashboard refresh button) must
  // also refresh the open-position quotes, not just the portfolio aggregates.
  useEffect(() => {
    if (refreshNonce > 0) void refresh();
  }, [refreshNonce, refresh]);

  // One bounded server-side instrument verification per symbol: a verified
  // provider spot instrument enables base-unit money math without a manual
  // declaration.
  useEffect(() => {
    const candidates = positions
      .filter((position) => position.sizing?.instrument?.verification !== "PROVIDER_CATALOG")
      .map((position) => position.symbol)
      .filter((symbol) => !verificationRequested.current.has(symbol));
    if (candidates.length === 0) return;
    for (const symbol of candidates) {
      verificationRequested.current.add(symbol);
      void apiFetch(apiUrl(`/api/v1/market-data/instrument?symbol=${encodeURIComponent(symbol)}`))
        .then((response: Response) => (response.ok ? response.json() : null))
        .then((payload: { status?: string } | null) => {
          if (payload?.status === "VERIFIED") {
            setVerifiedSymbols((current) => ({ ...current, [symbol]: true }));
            void refresh();
          }
        })
        .catch(() => {});
    }
  }, [positions, refresh]);

  if (loading) {
    return (
      <div className="bg-elevated p-4 rounded-lg border border-surface-border animate-pulse h-48 flex items-center justify-center text-slate-500 text-sm">
        <span>{t("open_positions.loading")}</span>
      </div>
    );
  }

  return (
    <div className="bg-elevated p-4 rounded-lg border border-surface-border flex flex-col select-none">
      <div className="flex flex-wrap items-center justify-between gap-2 pb-3 border-b border-surface-border">
        <div className="flex items-center space-x-2">
          <Crosshair className="w-4 h-4 text-accent" />
          <span className="text-sm font-bold text-white uppercase tracking-wide">
            {t("tracking.external_title")}
          </span>
          <span className="text-sm text-slate-400 font-semibold">
            {t("open_positions.active_count", { count: positions.length })}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            data-testid="open-positions-refresh"
            onClick={() => void refresh()}
            disabled={busy || positions.length === 0}
            className="k-btn border border-surface-border bg-soft hover:bg-hover-strong text-slate-200 disabled:opacity-50"
            title={t("journal.refresh_all_title")}
          >
            <RefreshCw className={`w-4 h-4 text-accent ${busy ? "animate-spin" : ""}`} />
            <span>{busy ? t("journal.refresh_busy") : t("journal.refresh_all")}</span>
          </button>
        </div>
      </div>
      {(error || lastSuccessAt) && (
        <p role="status" className={`mt-2 text-sm ${error ? "text-amber-300" : "text-slate-400"}`}>
          {error
            ? `${t("journal.refresh_failed")}: ${error}${lastAttemptAt ? ` · ${t("journal.refresh_attempt", { time: formatIstanbulDateTime(lastAttemptAt, locale) })}` : ""}${lastSuccessAt ? ` · ${t("journal.refresh_last_success", { time: formatIstanbulDateTime(lastSuccessAt, locale) })}` : ""}`
            : t("journal.refresh_checked", { time: formatIstanbulDateTime(lastSuccessAt, locale) })}
        </p>
      )}

      {positions.length === 0 ? (
        <div className="py-10 flex flex-col items-center justify-center text-center select-none font-mono">
          <div className="w-10 h-10 rounded-full bg-soft flex items-center justify-center mb-2.5 border border-surface-border">
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
              className="flex items-center space-x-1.5 px-3 py-1 bg-soft hover:bg-hover-strong border border-surface-border text-accent font-semibold rounded text-xs transition cursor-pointer"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>{t("open_positions.open_action")}</span>
            </button>
          )}
        </div>
      ) : (
        <div className="overflow-x-auto mt-2">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="text-sm text-slate-400 uppercase border-b border-surface-border pb-1">
                <th className="py-2 px-3">{t("open_positions.col_symbol")}</th>
                <th className="py-2 px-3">{t("open_positions.col_side")}</th>
                <th className="py-2 px-3">{t("open_positions.col_qty")}</th>
                <th className="py-2 px-3">{t("open_positions.col_entry")}</th>
                <th className="py-2 px-3">{t("journal.col_quote")}</th>
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
                const rMult = p.r_multiple;
                const hasRMultiple = rMult != null;
                const quote = quotes[p.id];
                const quotePrice = quote?.price ?? null;
                const sizing = positionSizing({
                  symbol: p.symbol,
                  positionType: (p.position_type || "UNKNOWN") as "SPOT" | "LONG" | "SHORT" | "UNKNOWN",
                  side: p.side,
                  entryPrice: p.entry_price ?? null,
                  qty: p.qty ?? null,
                  leverage: p.leverage ?? null,
                  qtyUnit: p.qty_unit ?? null,
                  serverVerified: verifiedSymbols[p.symbol] === true
                    || p.sizing?.instrument?.verification === "PROVIDER_CATALOG",
                });
                const monetaryReady = sizing.monetaryCalculation.status === "READY";
                const usdValue = p.qty_unit === "USD";
                const unrealized = monetaryReady && quotePrice != null && p.entry_price != null && p.qty != null
                  ? (usdValue
                    ? (isLong ? 1 : -1) * (quotePrice - p.entry_price) / p.entry_price * p.qty
                    : (isLong ? 1 : -1) * (quotePrice - p.entry_price) * p.qty)
                  : null;
                const quoteAge = quoteAgeSeconds(quote, nowMs);

                return (
                  <tr key={p.id} className="hover:bg-[#0d121c] transition">
                    <td className="py-3 px-3 font-bold text-white">
                      <span>{p.symbol}</span>
                      {p.record_mode === "SIMULATION" && (
                        <span
                          data-testid={`open-sim-badge-${p.id}`}
                          className="ml-2 align-middle px-2 py-0.5 rounded text-sm font-bold bg-amber-400/15 text-amber-300 border border-amber-400/40"
                        >
                          {t("journal.simulation_badge")}
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-3">
                      <span className={`text-sm px-2 py-0.5 rounded font-bold ${isLong ? "bg-emerald-500/10 text-gain border border-emerald-500/20" : "bg-rose-500/10 text-loss border border-rose-500/20"}`}>
                        {p.position_type === "SPOT" ? t("order_ticket.side_spot") : isLong ? "LONG" : "SHORT"}
                      </span>
                    </td>
                    <td className="py-3 px-3 text-slate-300">{p.qty_unit === "USD" ? formatPositionValue(p.qty) : p.qty}</td>
                    <td className="py-3 px-3 text-slate-200 font-semibold">{formatPrice(p.symbol, p.entry_price)}</td>
                    <td className="py-3 px-3">
                      {quotePrice != null ? (
                        <span className="leading-tight">
                          <span className="block font-semibold text-slate-100">{formatPrice(p.symbol, quotePrice)}</span>
                          <span className={`block text-sm ${quote?.quote_status === "LIVE" ? "text-gain" : "text-amber-300"}`}>
                            {quote?.quote_status}
                            {quoteAge != null && <span className="ml-1 text-slate-400">· {relativeAgeLabel(quoteAge)}</span>}
                          </span>
                          {unrealized != null && (
                            <span className={`block text-sm font-semibold ${unrealized >= 0 ? "text-gain" : "text-loss"}`} data-testid={`open-local-unrealized-${p.id}`}>
                              {t("open_positions.local_unrealized", { value: `${unrealized >= 0 ? "+" : ""}${unrealized.toFixed(2)}` })}
                            </span>
                          )}
                          {!monetaryReady && (
                            <span className="block k-help text-amber-300">{t("open_positions.monetary_unavailable")}</span>
                          )}
                        </span>
                      ) : quote ? (
                        <span className="text-sm text-amber-300">
                          {t("journal.quote_unavailable")}
                          {quote.last_known && (
                            <span className="block k-help">
                              {t("journal.quote_last_known", {
                                price: formatPrice(p.symbol, quote.last_known.price),
                                time: formatIstanbulDateTime(quote.last_known.observed_at, locale),
                              })}
                            </span>
                          )}
                        </span>
                      ) : (
                        <span className="k-help">{t("journal.quote_pending")}</span>
                      )}
                    </td>
                    <td className="py-3 px-3 text-loss font-semibold">{p.stop_loss ? formatPrice(p.symbol, p.stop_loss) : "—"}</td>
                    <td className="py-3 px-3 text-gain font-semibold">{p.take_profit ? formatPrice(p.symbol, p.take_profit) : "—"}</td>
                    <td className="py-3 px-3">
                      <span className={`font-bold ${unrealized == null ? "text-slate-400" : unrealized >= 0 ? "text-gain" : "text-loss"}`}
                            data-testid={`open-pnl-${p.id}`}>
                        {unrealized == null ? t("open_positions.unknown_value") : `${unrealized >= 0 ? "+" : ""}${unrealized.toFixed(2)}`}
                      </span>
                      {!monetaryReady && onEditPosition && (
                        <button
                          type="button"
                          data-testid={`declare-unit-${p.id}`}
                          onClick={() => onEditPosition(p)}
                          title={t("open_positions.declare_unit_help")}
                          className="block text-sm text-accent underline focus:outline-none"
                        >
                          {t("open_positions.declare_unit")}
                        </button>
                      )}
                    </td>
                    <td className="py-3 px-3">
                      <span className={`font-bold ${!hasRMultiple ? "text-slate-400" : rMult >= 0 ? "text-purple-300" : "text-loss"}`}>
                        {hasRMultiple ? `${rMult >= 0 ? "+" : ""}${rMult.toFixed(2)}R` : t("open_positions.unknown_value")}
                      </span>
                    </td>
                    <td className="py-3 px-3 text-right">
                      <div className="flex items-center justify-end space-x-1.5">
                        {onEditPosition && (
                          <button
                            onClick={() => onEditPosition(p)}
                            className="p-2 rounded bg-[#161f2e] hover:bg-[#1f2c42] text-slate-300 hover:text-white transition"
                            title={t("tracking.edit")}
                            aria-label={t("tracking.edit")}
                          >
                            <Edit3 className="w-4 h-4" />
                          </button>
                        )}
                        <button
                          onClick={() => onClosePosition(p.id)}
                          className="px-2 py-1.5 rounded bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 border border-rose-500/30 text-sm font-bold transition active:scale-95 flex items-center space-x-1"
                          title={t("tracking.manage_close")}
                        >
                          <XCircle className="w-4 h-4 mr-1" />
                          <span>{t("tracking.manage_close")}</span>
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
