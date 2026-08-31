import React, { useState } from "react";
import { X, Check, RefreshCw, Zap } from "lucide-react";
import { useMarketStore } from "../stores/marketStore";
import { useTradeStore } from "../stores/tradeStore";
import { TradeSide } from "../types";

interface NewTradeModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const NewTradeModal: React.FC<NewTradeModalProps> = ({ isOpen, onClose }) => {
  const { symbol: defaultSymbol, currentPrice } = useMarketStore();
  const { addTrade } = useTradeStore();

  const [tradeSymbol, setTradeSymbol] = useState<string>(defaultSymbol || "BTCUSDT");
  const [side, setSide] = useState<TradeSide>("BUY");
  const [entryPrice, setEntryPrice] = useState<number>(currentPrice || 0);
  const [qty, setQty] = useState<number>(1.0);
  const [stopLoss, setStopLoss] = useState<number>(currentPrice ? currentPrice * 0.98 : 0);
  const [takeProfit, setTakeProfit] = useState<number>(currentPrice ? currentPrice * 1.04 : 0);
  const [notes, setNotes] = useState<string>("");
  const [isFetchingPrice, setIsFetchingPrice] = useState<boolean>(false);
  const [fetchNotice, setFetchNotice] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleFetchLatestPrice = async () => {
    setIsFetchingPrice(true);
    setFetchNotice(null);
    try {
      const res = await fetch(
        `http://127.0.0.1:8000/api/v1/market-data/candles?symbol=${encodeURIComponent(
          tradeSymbol.toUpperCase()
        )}&timeframe=1m&limit=1`
      );
      if (!res.ok) throw new Error("Fiyat çekilemedi");
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
        setFetchNotice(`Son Fiyat: $${markPrice.toLocaleString()}`);
      } else {
        throw new Error("Boş veri");
      }
    } catch {
      setFetchNotice("Canlı fiyat alınamadı");
    } finally {
      setIsFetchingPrice(false);
    }
  };

  const riskPerUnit = Math.abs(entryPrice - (stopLoss || entryPrice));
  const totalRisk = riskPerUnit * qty;
  const rewardPerUnit = Math.abs((takeProfit || entryPrice) - entryPrice);
  const totalReward = rewardPerUnit * qty;
  const rrRatio = totalRisk > 0 ? (totalReward / totalRisk).toFixed(2) : "0.00";

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const tradeData = {
      id: `TRD-${Date.now()}`,
      symbol: tradeSymbol.toUpperCase(),
      side,
      entry_price: Number(entryPrice),
      qty: Number(qty),
      stop_loss: stopLoss ? Number(stopLoss) : null,
      take_profit: takeProfit ? Number(takeProfit) : null,
      entry_time: new Date().toISOString(),
      status: "OPEN" as const,
      notes,
      unrealized_pnl: 0,
      r_multiple: 0,
    };

    // Post to backend
    fetch("http://127.0.0.1:8000/api/v1/trades", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(tradeData),
    })
      .then((res) => res.json())
      .then((saved) => {
        addTrade(saved);
      })
      .catch(() => {
        addTrade(tradeData);
      });

    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
      <div className="bg-[#111722] border border-surface-border rounded-lg w-full max-w-md p-5 shadow-2xl">
        <div className="flex items-center justify-between border-b border-surface-border pb-3">
          <h3 className="text-sm font-bold text-white font-mono flex items-center space-x-1.5">
            <Zap className="w-4 h-4 text-accent" />
            <span>RECORD TRADE TICKET</span>
          </h3>
          <button onClick={onClose} className="text-slate-400 hover:text-white cursor-pointer">
            <X className="w-4 h-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="mt-4 space-y-4 text-xs font-mono">
          {/* Symbol Input & Fetch Price Action */}
          <div>
            <div className="flex justify-between items-center mb-1">
              <label className="text-slate-400">Trading Symbol</label>
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
                title="Canlı Piyasa Fiyatını Çek"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${isFetchingPrice ? "animate-spin" : ""}`} />
                <span className="text-[11px] font-semibold">Son Fiyatı Çek</span>
              </button>
            </div>
          </div>

          {/* Side Selector */}
          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={() => setSide("BUY")}
              className={`py-2 rounded font-bold transition cursor-pointer ${
                side === "BUY" ? "bg-gain text-black shadow-lg shadow-emerald-500/20" : "bg-[#1a2234] text-slate-300"
              }`}
            >
              LONG / BUY
            </button>
            <button
              type="button"
              onClick={() => setSide("SELL")}
              className={`py-2 rounded font-bold transition cursor-pointer ${
                side === "SELL" ? "bg-loss text-white shadow-lg shadow-rose-500/20" : "bg-[#1a2234] text-slate-300"
              }`}
            >
              SHORT / SELL
            </button>
          </div>

          {/* Entry & Qty */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-slate-400 block mb-1">Entry Price ($)</label>
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
              <label className="text-slate-400 block mb-1">Quantity</label>
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
              <label className="text-slate-400 block mb-1">Stop Loss ($)</label>
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
              <label className="text-slate-400 block mb-1">Take Profit ($)</label>
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

          {/* Live Risk / Reward Math */}
          <div className="bg-[#0b0e14] p-3 rounded border border-surface-border space-y-1 text-[11px]">
            <div className="flex justify-between">
              <span className="text-slate-400">Risk Amount:</span>
              <span className="text-loss font-bold">${totalRisk.toFixed(2)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Reward Amount:</span>
              <span className="text-gain font-bold">${totalReward.toFixed(2)}</span>
            </div>
            <div className="flex justify-between border-t border-surface-border pt-1">
              <span className="text-slate-400">Risk/Reward (R:R):</span>
              <span className="text-accent font-bold">1 : {rrRatio}</span>
            </div>
          </div>

          {/* Notes */}
          <div>
            <label className="text-slate-400 block mb-1">Trade Rationale / Tags</label>
            <input
              type="text"
              placeholder="e.g. 15m breakout, liquidity sweep, high volume"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="w-full bg-[#0b0e14] border border-surface-border rounded px-3 py-1.5 text-slate-200 focus:outline-none focus:border-accent"
            />
          </div>

          {/* Submit */}
          <button
            type="submit"
            className="w-full py-2 bg-accent hover:bg-sky-400 text-black font-bold rounded flex items-center justify-center space-x-2 transition cursor-pointer"
          >
            <Check className="w-4 h-4" />
            <span>CONFIRM & EXECUTE</span>
          </button>
        </form>
      </div>
    </div>
  );
};