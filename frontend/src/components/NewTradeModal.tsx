import React, { useState, useEffect } from "react";
import { X, Check, RefreshCw, Zap, AlertTriangle } from "lucide-react";
import { useMarketStore } from "../stores/marketStore";
import { useTradeStore } from "../stores/tradeStore";
import { useTranslation } from "../context/I18nContext";
import { TradeSide } from "../types";
import { apiBase, apiUrl } from "../lib/backend";

interface NewTradeModalProps {
  isOpen: boolean;
  onClose: () => void;
  onOpenApiKeySettings?: () => void;
}

export const NewTradeModal: React.FC<NewTradeModalProps> = ({
  isOpen,
  onClose,
  onOpenApiKeySettings,
}) => {
  const { t } = useTranslation();
  const { symbol: defaultSymbol, currentPrice } = useMarketStore();
  const { addTrade } = useTradeStore();

  const [mode, setMode] = useState<"PAPER" | "LIVE">("PAPER");
  const [exchange, setExchange] = useState<string>("binance_futures");
  const [tradeSymbol, setTradeSymbol] = useState<string>(defaultSymbol || "BTCUSDT");
  const [side, setSide] = useState<TradeSide>("BUY");
  const [orderType, setOrderType] = useState<"LIMIT" | "MARKET">("LIMIT");
  const [entryPrice, setEntryPrice] = useState<number>(currentPrice || 0);
  const [qty, setQty] = useState<number>(1.0);
  const [stopLoss, setStopLoss] = useState<number>(currentPrice ? currentPrice * 0.98 : 0);
  const [takeProfit, setTakeProfit] = useState<number>(currentPrice ? currentPrice * 1.04 : 0);
  const [notes, setNotes] = useState<string>("");

  const [isFetchingPrice, setIsFetchingPrice] = useState<boolean>(false);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [fetchNotice, setFetchNotice] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [liveBalance, setLiveBalance] = useState<number | null>(null);

  useEffect(() => {
    if (mode === "LIVE" && isOpen) {
      fetch(`${apiBase()}/api/v1/exchange/balances?exchange_id=${exchange}`)
        .then((res) => res.json())
        .then((data) => {
          if (data.free_quote !== undefined) {
            setLiveBalance(data.free_quote);
          }
        })
        .catch(() => {});
    }
  }, [mode, exchange, isOpen]);

  if (!isOpen) return null;

  const handleFetchLatestPrice = async () => {
    setIsFetchingPrice(true);
    setFetchNotice(null);
    setErrorMessage(null);
    try {
      const res = await fetch(
        `${apiBase()}/api/v1/market-data/candles?symbol=${encodeURIComponent(
          tradeSymbol.toUpperCase()
        )}&timeframe=1m&limit=1`
      );
      if (!res.ok) throw new Error("Price fetch failed");
      const candles = await res.json();
      if (Array.isArray(candles) && candles.length > 0) {
        const markPrice = Number(candles[candles.length - 1].close);
        setEntryPrice(markPrice);
        if (side === "BUY") {
          setStopLoss(Number((markPrice * 0.98).toFixed(2)));
          setTakeProfit(Number((markPrice * 1.04).toFixed(2)));
        } else {
          setStopLoss(Number((markPrice * 1.02).toFixed(2)));
          setTakeProfit(Number((markPrice * 0.96).toFixed(2)));
        }
        setFetchNotice(`${t("order_ticket.latest_price")}: $${markPrice.toLocaleString()}`);
      } else {
        throw new Error("No candle data");
      }
    } catch {
      setFetchNotice(t("order_ticket.price_fetch_error"));
    } finally {
      setIsFetchingPrice(false);
    }
  };

  const riskPerUnit = Math.abs(entryPrice - (stopLoss || entryPrice));
  const totalRisk = riskPerUnit * qty;
  const rewardPerUnit = Math.abs((takeProfit || entryPrice) - entryPrice);
  const totalReward = rewardPerUnit * qty;
  const rrRatio = totalRisk > 0 ? (totalReward / totalRisk).toFixed(2) : "0.00";

  const accountRefBalance = liveBalance || 10000.0;
  const riskPct = accountRefBalance > 0 ? (totalRisk / accountRefBalance) * 100 : 0;
  const isHighRisk = riskPct > 2.5;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setErrorMessage(null);

    const orderPayload = {
      symbol: tradeSymbol.toUpperCase(),
      side,
      order_type: orderType,
      qty: Number(qty),
      price: Number(entryPrice),
      stop_loss: stopLoss ? Number(stopLoss) : null,
      take_profit: takeProfit ? Number(takeProfit) : null,
      exchange,
      mode,
      notes: notes || undefined,
    };

    try {
      const res = await fetch(apiUrl("/api/v1/execution/order"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(orderPayload),
      });

      const data = await res.json();
      if (!res.ok || !data.success) {
        const errorDetail = data.detail?.reason || data.reason || data.detail || t("order_ticket.execution_failed");
        setErrorMessage(errorDetail);
        setIsSubmitting(false);
        return;
      }

      if (data.trade) {
        addTrade(data.trade);
      }
      onClose();
    } catch (err: any) {
      setErrorMessage(err.message || t("order_ticket.execution_failed"));
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

        {/* Mode Switcher: Paper Sandbox vs Live Exchange */}
        <div className="grid grid-cols-2 gap-2 mt-4 p-1 bg-[#090d14] rounded-lg border border-surface-border text-xs">
          <button
            type="button"
            onClick={() => setMode("PAPER")}
            className={`py-1.5 rounded-md font-bold transition flex items-center justify-center space-x-1.5 cursor-pointer ${
              mode === "PAPER"
                ? "bg-[#162032] text-accent border border-accent/40 shadow-sm"
                : "text-slate-400 hover:text-white"
            }`}
          >
            <span>{t("order_ticket.mode_paper")}</span>
          </button>
          <button
            type="button"
            onClick={() => setMode("LIVE")}
            className={`py-1.5 rounded-md font-bold transition flex items-center justify-center space-x-1.5 cursor-pointer ${
              mode === "LIVE"
                ? "bg-loss/20 text-rose-300 border border-loss/50 shadow-sm"
                : "text-slate-400 hover:text-white"
            }`}
          >
            <span>{t("order_ticket.mode_live")}</span>
          </button>
        </div>

        {/* Error Alert */}
        {errorMessage && (
          <div className="mt-3 p-3 bg-loss/15 border border-loss/30 rounded-lg text-loss text-xs flex items-start space-x-2">
            <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
            <div className="flex-1">
              <span>{errorMessage}</span>
              {errorMessage.includes("Missing API credentials") && onOpenApiKeySettings && (
                <button
                  type="button"
                  onClick={() => {
                    onClose();
                    onOpenApiKeySettings();
                  }}
                  className="block mt-1 text-accent underline font-bold"
                >
                  {t("order_ticket.configure_keys_prompt")}
                </button>
              )}
            </div>
          </div>
        )}

        <form onSubmit={handleSubmit} className="mt-4 space-y-3 text-xs font-mono overflow-y-auto flex-1 pr-1">
          {/* Live Venue Selection & Balance */}
          {mode === "LIVE" && (
            <div className="p-3 bg-[#090d14] rounded-lg border border-surface-border space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-slate-400">{t("order_ticket.exchange_label")}:</label>
                <select
                  value={exchange}
                  onChange={(e) => setExchange(e.target.value)}
                  className="bg-[#111722] text-white border border-surface-border rounded px-2 py-1 focus:outline-none focus:border-accent text-xs"
                >
                  <option value="binance_futures">Binance USDⓈ-M Futures</option>
                  <option value="binance_spot">Binance Spot</option>
                  <option value="okx">OKX V5 Unified</option>
                </select>
              </div>
              {liveBalance !== null && (
                <div className="flex justify-between text-[11px] pt-1 border-t border-surface-border/50 text-slate-300">
                  <span>{t("order_ticket.live_free_balance")}:</span>
                  <span className="font-bold text-accent">${liveBalance.toLocaleString()}</span>
                </div>
              )}
            </div>
          )}

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
                onChange={(e) => setTradeSymbol(e.target.value.toUpperCase())}
                placeholder="e.g. BTCUSDT, EURUSD, SPY"
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
          </div>

          {/* Order Type Selector */}
          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={() => setOrderType("LIMIT")}
              className={`py-1.5 rounded font-bold transition text-center cursor-pointer ${
                orderType === "LIMIT"
                  ? "bg-[#162032] text-accent border border-accent/40 shadow-sm"
                  : "bg-[#0b0e14] text-slate-400 border border-surface-border hover:text-slate-200"
              }`}
            >
              {t("order_ticket.type_limit")}
            </button>
            <button
              type="button"
              onClick={() => setOrderType("MARKET")}
              className={`py-1.5 rounded font-bold transition text-center cursor-pointer ${
                orderType === "MARKET"
                  ? "bg-[#162032] text-accent border border-accent/40 shadow-sm"
                  : "bg-[#0b0e14] text-slate-400 border border-surface-border hover:text-slate-200"
              }`}
            >
              {t("order_ticket.type_market")}
            </button>
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
                onChange={(e) => setEntryPrice(Number(e.target.value))}
                placeholder="0.00"
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
                placeholder="1.0"
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
                placeholder="Optional"
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
                placeholder="Optional"
                className="w-full bg-[#0b0e14] border border-surface-border rounded px-3 py-1.5 text-gain focus:outline-none focus:border-gain"
              />
            </div>
          </div>

          {/* Live Risk / Reward Math & Risk Meter */}
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
              placeholder="e.g. 15m breakout, liquidity sweep, high volume"
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
              mode === "LIVE"
                ? "bg-rose-500 hover:bg-rose-400 text-white shadow-lg shadow-rose-500/30"
                : "bg-accent hover:bg-sky-400 text-black shadow-lg shadow-sky-500/20"
            }`}
          >
            {isSubmitting ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin" />
                <span>{t("order_ticket.executing_btn")}</span>
              </>
            ) : (
              <>
                <Check className="w-4 h-4" />
                <span>{mode === "LIVE" ? t("order_ticket.execute_live_btn") : t("order_ticket.execute_paper_btn")}</span>
              </>
            )}
          </button>
        </form>
      </div>
    </div>
  );
};