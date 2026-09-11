import React, { useState } from "react";
import { X, Check, RefreshCw, Zap, AlertTriangle } from "lucide-react";
import { useMarketStore } from "../stores/marketStore";
import { useTradeStore } from "../stores/tradeStore";
import { useTranslation } from "../context/I18nContext";
import { MarketQuote, TradeSide } from "../types";
import { apiFetch, apiUrl } from "../lib/backend";

const FREE_QUOTE_SOURCE_IDS = new Set([
  "binance_public",
  "bybit_public",
  "yahoo_public",
  "stooq_public",
]);

function isMarketQuote(value: unknown): value is MarketQuote {
  if (!value || typeof value !== "object") return false;
  const quote = value as Partial<MarketQuote>;
  if (
    typeof quote.requested_symbol !== "string" ||
    !["LIVE", "DELAYED", "EOD", "UNAVAILABLE"].includes(String(quote.status)) ||
    quote.free_source !== true ||
    quote.credentials_required !== false
  ) {
    return false;
  }
  if (quote.status === "UNAVAILABLE") {
    return quote.price === null && quote.price_kind === null;
  }
  return Boolean(
    typeof quote.source_id === "string" &&
    FREE_QUOTE_SOURCE_IDS.has(quote.source_id) &&
    typeof quote.source_symbol === "string" &&
    quote.source_symbol.length > 0 &&
    typeof quote.observed_at === "string" &&
    quote.observed_at.length > 0 &&
    (quote.price_kind === "LAST" || quote.price_kind === "CLOSE") &&
    typeof quote.price === "number" &&
    Number.isFinite(quote.price) &&
    quote.price > 0
  );
}

interface NewTradeModalProps {
  isOpen: boolean;
  onClose: () => void;
  onOpenApiKeySettings?: () => void;
}

export const NewTradeModal: React.FC<NewTradeModalProps> = ({
  isOpen,
  onClose,
}) => {
  const { t } = useTranslation();
  const { symbol: defaultSymbol } = useMarketStore();
  const { addTrade } = useTradeStore();

  const [recordMode, setRecordMode] = useState<"EXTERNAL" | "SIMULATION">("EXTERNAL");
  const [tradeSymbol, setTradeSymbol] = useState<string>(defaultSymbol || "BTCUSDT");
  const [side, setSide] = useState<TradeSide>("BUY");
  const [entryPrice, setEntryPrice] = useState<number>(0);
  const [qty, setQty] = useState<number>(1.0);
  const [stopLoss, setStopLoss] = useState<number>(0);
  const [takeProfit, setTakeProfit] = useState<number>(0);
  const [executionVenue, setExecutionVenue] = useState<string>("");
  const [notes, setNotes] = useState<string>("");

  const [isFetchingPrice, setIsFetchingPrice] = useState<boolean>(false);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [fetchNotice, setFetchNotice] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [quote, setQuote] = useState<MarketQuote | null>(null);
  const [priceOrigin, setPriceOrigin] = useState<"MANUAL" | "PUBLIC_QUOTE">("MANUAL");

  if (!isOpen) return null;

  const handleFetchLatestPrice = async () => {
    setIsFetchingPrice(true);
    setFetchNotice(null);
    setErrorMessage(null);
    try {
      const res = await apiFetch(
        apiUrl(`/api/v1/market-data/quote?symbol=${encodeURIComponent(
          tradeSymbol.toUpperCase()
        )}&source=auto`)
      );
      if (!res.ok) throw new Error("Price fetch failed");
      const candidateValue: unknown = await res.json();
      const candidate = isMarketQuote(candidateValue) ? candidateValue : null;
      if (!candidate || candidate.requested_symbol !== tradeSymbol.toUpperCase()) {
        throw new Error("Malformed free quote response");
      }
      setQuote(candidate);
      if (candidate && Number.isFinite(candidate.price) && Number(candidate.price) > 0 && candidate.status !== "UNAVAILABLE") {
        const markPrice = Number(candidate.price);
        setPriceOrigin("PUBLIC_QUOTE");
        setEntryPrice(markPrice);
        if (side === "BUY") {
          setStopLoss(Number((markPrice * 0.98).toFixed(2)));
          setTakeProfit(Number((markPrice * 1.04).toFixed(2)));
        } else {
          setStopLoss(Number((markPrice * 1.02).toFixed(2)));
          setTakeProfit(Number((markPrice * 0.96).toFixed(2)));
        }
        setFetchNotice(t("order_ticket.latest_price", {
          price: markPrice.toLocaleString(),
          source: candidate.source_symbol || candidate.source_id || "",
          status: candidate.status,
        }));
      } else {
        setPriceOrigin("MANUAL");
        setFetchNotice(t("order_ticket.price_unavailable_manual"));
      }
    } catch {
      setQuote(null);
      setPriceOrigin("MANUAL");
      setFetchNotice(t("order_ticket.price_unavailable_manual"));
    } finally {
      setIsFetchingPrice(false);
    }
  };

  const riskPerUnit = Math.abs(entryPrice - (stopLoss || entryPrice));
  const totalRisk = riskPerUnit * qty;
  const rewardPerUnit = Math.abs((takeProfit || entryPrice) - entryPrice);
  const totalReward = rewardPerUnit * qty;
  const rrRatio = totalRisk > 0 ? (totalReward / totalRisk).toFixed(2) : "0.00";

  const accountRefBalance = 10000.0;
  const riskPct = accountRefBalance > 0 ? (totalRisk / accountRefBalance) * 100 : 0;
  const isHighRisk = riskPct > 2.5;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setErrorMessage(null);

    if (!Number.isFinite(entryPrice) || entryPrice <= 0 || !Number.isFinite(qty) || qty <= 0) {
      setErrorMessage(t("order_ticket.invalid_price_or_qty"));
      setIsSubmitting(false);
      return;
    }

    const useQuoteProvenance = Boolean(
      priceOrigin === "PUBLIC_QUOTE" && quote?.source_id && quote.price === entryPrice
    );
    const selectedQuote = useQuoteProvenance ? quote : null;
    const tradePayload = {
      symbol: tradeSymbol.toUpperCase(),
      side,
      entry_price: Number(entryPrice),
      qty: Number(qty),
      stop_loss: stopLoss ? Number(stopLoss) : null,
      take_profit: takeProfit ? Number(takeProfit) : null,
      record_mode: recordMode,
      execution_venue: executionVenue.trim() || null,
      price_source: selectedQuote?.source_id || "manual",
      price_source_symbol: selectedQuote?.source_symbol || null,
      price_status: selectedQuote?.status || "UNAVAILABLE",
      price_observed_at: selectedQuote?.observed_at || null,
      price_origin: useQuoteProvenance ? "PUBLIC_QUOTE" : "MANUAL",
      notes: notes || undefined,
    };

    try {
      const res = await apiFetch(apiUrl("/api/v1/trades"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(tradePayload),
      });

      const data = await res.json();
      if (!res.ok || !data.id) {
        const errorDetail = data.detail?.reason || data.reason || data.detail || t("order_ticket.record_failed");
        setErrorMessage(errorDetail);
        setIsSubmitting(false);
        return;
      }

      // The journal endpoint returns the persisted trade directly.  Do not
      // invent a nested execution response shape here: this action records a
      // reviewable journal entry and never dispatches an order.
      addTrade(data);
      onClose();
    } catch (err: any) {
      setErrorMessage(err.message || t("order_ticket.record_failed"));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 font-mono select-none animate-fadeIn">
      <div className="bg-[#111722] border border-surface-border rounded-xl w-full max-w-md p-5 shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-surface-border pb-3">
          <h3 className="text-sm font-bold text-white font-mono flex items-center space-x-2">
            <Zap className="w-4 h-4 text-accent" />
            <span>{t("order_ticket.modal_title")}</span>
          </h3>
          <button onClick={onClose} className="text-slate-400 hover:text-white cursor-pointer">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Record mode: real external journal entry is the safe default. */}
        <div className="grid grid-cols-2 gap-2 mt-4 p-1 bg-[#090d14] rounded-lg border border-surface-border text-xs">
          <button
            type="button"
            onClick={() => setRecordMode("EXTERNAL")}
            className={`py-1.5 rounded-md font-bold transition flex items-center justify-center space-x-1.5 cursor-pointer ${
              recordMode === "EXTERNAL"
                ? "bg-[#162032] text-accent border border-accent/40 shadow-sm"
                : "text-slate-400 hover:text-white"
            }`}
          >
            <span>{t("order_ticket.mode_external")}</span>
          </button>
          <button
            type="button"
            onClick={() => setRecordMode("SIMULATION")}
            className={`py-1.5 rounded-md font-bold transition flex items-center justify-center space-x-1.5 cursor-pointer ${
              recordMode === "SIMULATION"
                ? "bg-[#162032] text-amber-300 border border-amber-400/40 shadow-sm"
                : "text-slate-400 hover:text-white"
            }`}
          >
            <span>{t("order_ticket.mode_simulation")}</span>
          </button>
        </div>

        <div className="mt-2 rounded border border-surface-border/70 bg-[#0b0e14] px-3 py-2 text-[10px] text-slate-400" data-testid="trade-record-mode-note">
          {recordMode === "EXTERNAL"
            ? t("order_ticket.external_record_notice")
            : t("order_ticket.simulation_notice")}
        </div>

        {/* Error Alert */}
        {errorMessage && (
          <div className="mt-3 p-3 bg-loss/15 border border-loss/30 rounded-lg text-loss text-xs flex items-start space-x-2">
            <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
            <div className="flex-1">
              <span>{errorMessage}</span>
            </div>
          </div>
        )}

        <form onSubmit={handleSubmit} className="mt-4 space-y-3 text-xs font-mono overflow-y-auto flex-1 pr-1">
          {/* Optional execution venue metadata; this never sends an order. */}
          <div className="p-3 bg-[#090d14] rounded-lg border border-surface-border space-y-2">
            <label className="text-slate-400 block">{t("order_ticket.execution_venue_label")}</label>
            <input
              type="text"
              value={executionVenue}
              onChange={(e) => setExecutionVenue(e.target.value)}
              placeholder={t("order_ticket.execution_venue_placeholder")}
              className="w-full bg-[#111722] text-white border border-surface-border rounded px-2 py-1.5 focus:outline-none focus:border-accent text-xs"
            />
          </div>

          {/* Symbol Input & Fetch Price Action */}
          <div>
            <div className="flex justify-between items-center mb-1">
              <label className="text-slate-400">{t("order_ticket.symbol_label")}</label>
              {fetchNotice && (
                <span className="text-[10px] text-accent font-semibold">{fetchNotice}</span>
              )}
            </div>
            <div className="flex items-center space-x-2">
              <input
                type="text"
                value={tradeSymbol}
                onChange={(e) => {
                  setTradeSymbol(e.target.value.toUpperCase());
                  setQuote(null);
                  setPriceOrigin("MANUAL");
                }}
                placeholder={t("order_ticket.symbol_placeholder")}
                className="flex-1 bg-[#0b0e14] border border-surface-border rounded px-3 py-1.5 text-white uppercase focus:outline-none focus:border-accent"
                required
              />
              <button
                type="button"
                onClick={handleFetchLatestPrice}
                disabled={isFetchingPrice}
                className="px-2.5 py-1.5 bg-[#162032] hover:bg-[#1f2d47] border border-surface-border text-accent rounded flex items-center space-x-1 transition disabled:opacity-50 cursor-pointer"
                title={t("order_ticket.fetch_price_btn")}
              >
                <RefreshCw className={`w-3.5 h-3.5 ${isFetchingPrice ? "animate-spin" : ""}`} />
                <span className="text-[11px] font-semibold">{t("order_ticket.fetch_price_btn")}</span>
              </button>
            </div>
            {quote && (
              <div className="mt-2 text-[10px] text-slate-400" data-testid="trade-quote-status">
                <span>{t("order_ticket.quote_status", { status: quote.status })}</span>
                {quote.source_symbol && <span> · {quote.source_id}: {quote.source_symbol}</span>}
                {quote.observed_at && <span> · {quote.observed_at}</span>}
              </div>
            )}
          </div>

          {/* Side Selector */}
          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={() => setSide("BUY")}
              className={`py-2 rounded font-bold transition cursor-pointer ${
                side === "BUY"
                  ? "bg-gain text-black shadow-lg shadow-emerald-500/20"
                  : "bg-[#1a2234] text-slate-300"
              }`}
            >
              {t("order_ticket.side_buy")}
            </button>
            <button
              type="button"
              onClick={() => setSide("SELL")}
              className={`py-2 rounded font-bold transition cursor-pointer ${
                side === "SELL"
                  ? "bg-loss text-white shadow-lg shadow-rose-500/20"
                  : "bg-[#1a2234] text-slate-300"
              }`}
            >
              {t("order_ticket.side_sell")}
            </button>
          </div>

          {/* Entry & Qty */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-slate-400 block mb-1">{t("order_ticket.entry_label")}</label>
              <input
                type="number"
                step="any"
                value={entryPrice || ""}
                onChange={(e) => {
                  setEntryPrice(Number(e.target.value));
                  setPriceOrigin("MANUAL");
                }}
                placeholder={t("order_ticket.price_placeholder")}
                min="0"
                className="w-full bg-[#0b0e14] border border-surface-border rounded px-3 py-1.5 text-white focus:outline-none focus:border-accent"
                required
              />
            </div>
            <div>
              <label className="text-slate-400 block mb-1">{t("order_ticket.qty_label")}</label>
              <input
                type="number"
                step="any"
                value={qty || ""}
                onChange={(e) => setQty(Number(e.target.value))}
                placeholder={t("order_ticket.qty_placeholder")}
                min="0"
                className="w-full bg-[#0b0e14] border border-surface-border rounded px-3 py-1.5 text-white focus:outline-none focus:border-accent"
                required
              />
            </div>
          </div>

          {/* SL & TP */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-slate-400 block mb-1">{t("order_ticket.sl_label")}</label>
              <input
                type="number"
                step="any"
                value={stopLoss || ""}
                onChange={(e) => setStopLoss(Number(e.target.value))}
                placeholder={t("order_ticket.optional_placeholder")}
                className="w-full bg-[#0b0e14] border border-surface-border rounded px-3 py-1.5 text-loss focus:outline-none focus:border-loss"
              />
            </div>
            <div>
              <label className="text-slate-400 block mb-1">{t("order_ticket.tp_label")}</label>
              <input
                type="number"
                step="any"
                value={takeProfit || ""}
                onChange={(e) => setTakeProfit(Number(e.target.value))}
                placeholder={t("order_ticket.optional_placeholder")}
                className="w-full bg-[#0b0e14] border border-surface-border rounded px-3 py-1.5 text-gain focus:outline-none focus:border-gain"
              />
            </div>
          </div>

          {/* Risk / Reward Math & Risk Meter */}
          <div className={`p-3 rounded border space-y-1 text-[11px] ${
            isHighRisk ? "bg-loss/10 border-loss/40" : "bg-[#0b0e14] border-surface-border"
          }`}>
            <div className="flex justify-between">
              <span className="text-slate-400">{t("order_ticket.risk_amount")}:</span>
              <span className={`font-bold ${isHighRisk ? "text-rose-400" : "text-loss"}`}>
                ${totalRisk.toFixed(2)} ({riskPct.toFixed(2)}% of equity)
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">{t("order_ticket.reward_amount")}:</span>
              <span className="text-gain font-bold">${totalReward.toFixed(2)}</span>
            </div>
            <div className="flex justify-between border-t border-surface-border/50 pt-1">
              <span className="text-slate-400">{t("order_ticket.rr_ratio")}:</span>
              <span className="text-accent font-bold">1 : {rrRatio}</span>
            </div>
            {isHighRisk && (
              <div className="flex items-center space-x-1.5 pt-1 text-[10px] text-rose-300 font-bold">
                <AlertTriangle className="w-3 h-3" />
                <span>{t("order_ticket.high_risk_warning")}</span>
              </div>
            )}
          </div>

          {/* Notes */}
          <div>
            <label className="text-slate-400 block mb-1">{t("order_ticket.notes_label")}</label>
            <input
              type="text"
              placeholder={t("order_ticket.notes_placeholder")}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="w-full bg-[#0b0e14] border border-surface-border rounded px-3 py-1.5 text-slate-200 focus:outline-none focus:border-accent"
            />
          </div>

          {/* Submit Action */}
          <button
            type="submit"
            disabled={isSubmitting}
            className={`w-full py-2.5 font-bold rounded flex items-center justify-center space-x-2 transition cursor-pointer ${
              recordMode === "SIMULATION"
                ? "bg-amber-400 hover:bg-amber-300 text-black shadow-lg shadow-amber-500/20"
                : "bg-accent hover:bg-sky-400 text-black shadow-lg shadow-sky-500/20"
            }`}
          >
            {isSubmitting ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin" />
                <span>{t("order_ticket.recording_btn")}</span>
              </>
            ) : (
              <>
                <Check className="w-4 h-4" />
                <span>{recordMode === "SIMULATION"
                  ? t("order_ticket.record_simulation_btn")
                  : t("order_ticket.record_external_btn")}</span>
              </>
            )}
          </button>
        </form>
      </div>
    </div>
  );
};
