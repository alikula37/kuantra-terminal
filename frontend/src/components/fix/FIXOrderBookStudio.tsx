import React, { useState, useEffect } from "react";
import { Terminal, Shield, RefreshCw, Send, CheckCircle2, DollarSign, Layers } from "lucide-react";
import { apiUrl } from "../../lib/backend";

export const FIXOrderBookStudio: React.FC = () => {
  const [snapshot, setSnapshot] = useState<any>(null);
  const [fixSession, setFixSession] = useState<any>(null);
  const [orderSide, setOrderSide] = useState<"BUY" | "SELL">("BUY");
  const [orderPrice, setOrderPrice] = useState<number>(65000.0);
  const [orderQty, setOrderQty] = useState<number>(1.0);
  const [orderType, setOrderType] = useState<string>("LIMIT");
  const [destination, setDestination] = useState<string>("INTERNAL_MATCHING_ENGINE");
  const [actionMsg, setActionMsg] = useState<string | null>(null);
  const [sweepResult, setSweepResult] = useState<any>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  const fetchOrderBook = async () => {
    try {
      const res = await fetch(apiUrl("/api/v1/orderbook/l2-snapshot?depth=12"));
      const data = await res.json();
      setSnapshot(data);
      if (data.best_bid && orderPrice === 65000.0) {
        setOrderPrice(data.best_bid);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const fetchFixSession = async () => {
    try {
      const res = await fetch(apiUrl("/api/v1/fix/sessions"));
      const data = await res.json();
      setFixSession(data);
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    fetchOrderBook();
    fetchFixSession();
    const interval = setInterval(fetchOrderBook, 3000);
    return () => clearInterval(interval);
  }, []);

  const handleLogon = async () => {
    setIsLoading(true);
    try {
      const res = await fetch(apiUrl("/api/v1/fix/session/logon"), { method: "POST" });
      const data = await res.json();
      setActionMsg(`FIX Session Logged On successfully! State: ${data.session_state}`);
      fetchFixSession();
      setTimeout(() => setActionMsg(null), 4000);
    } catch (e) {
      console.error(e);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmitOrder = async (overrideSide?: "BUY" | "SELL", overridePrice?: number) => {
    const side = overrideSide || orderSide;
    const price = overridePrice || orderPrice;
    try {
      const res = await fetch(apiUrl("/api/v1/fix/order/submit"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          symbol: "BTCUSDT",
          side: side,
          price: price,
          qty: orderQty,
          order_type: orderType,
          destination: destination,
        }),
      });
      const data = await res.json();
      setActionMsg(
        `Order ${data.cl_ord_id} [${side} ${orderQty} @ ${price}] -> ${data.matching_status} (Filled: ${data.filled_size})`
      );
      fetchOrderBook();
      fetchFixSession();
      setTimeout(() => setActionMsg(null), 5000);
    } catch (e) {
      console.error(e);
    }
  };

  const handleSimulateSweep = async (side: "BUY" | "SELL") => {
    try {
      const res = await fetch(apiUrl("/api/v1/orderbook/simulate-fill"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ side: side, size: 5.0 }),
      });
      const data = await res.json();
      setSweepResult(data);
    } catch (e) {
      console.error(e);
    }
  };

  const maxVolume = snapshot
    ? Math.max(
        ...snapshot.bids.map((b: any) => b.volume),
        ...snapshot.asks.map((a: any) => a.volume),
        10.0
      )
    : 10.0;

  return (
    <div className="flex-1 flex flex-col h-full bg-[#0b0e14] overflow-y-auto p-4 select-none font-mono space-y-4 text-slate-100">
      {/* Header */}
      <div className="pb-3 border-b border-surface-border flex items-center justify-between">
        <div>
          <div className="flex items-center space-x-2">
            <Terminal className="w-5 h-5 text-accent" />
            <h2 className="text-sm font-bold text-white uppercase tracking-wider">
              L2/L3 LIMIT ORDER BOOK & FIX 4.4 / 5.0 SP2 PROTOCOL GATEWAY
            </h2>
          </div>
          <p className="text-xs text-slate-400">
            Sub-10μs Native Matching Engine &bull; CME/ICE DMA Smart Router &bull; Real-Time DOM Ladder
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={handleLogon}
            disabled={isLoading}
            className="flex items-center space-x-1.5 bg-accent hover:bg-sky-400 text-black font-bold px-3 py-1.5 rounded text-xs transition shadow"
          >
            <Shield className="w-3.5 h-3.5" />
            <span>FIX 35=A LOGON</span>
          </button>

          <button
            onClick={() => {
              fetchOrderBook();
              fetchFixSession();
            }}
            className="p-1.5 bg-[#0d121c] hover:bg-[#111722] border border-surface-border rounded text-slate-400 hover:text-white transition"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Action Banner */}
      {actionMsg && (
        <div className="bg-gain/10 border border-gain/30 p-3 rounded-lg flex items-center space-x-2 text-gain text-xs">
          <CheckCircle2 className="w-4 h-4 text-gain" />
          <span>{actionMsg}</span>
        </div>
      )}

      {/* Main Grid Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 flex-1">
        {/* LEFT COLUMN: DEPTH OF MARKET (DOM) LADDER */}
        <div className="bg-[#0d121c] p-4 rounded-lg border border-surface-border flex flex-col space-y-3">
          <div className="flex items-center justify-between border-b border-surface-border pb-2">
            <span className="text-xs font-bold text-white flex items-center space-x-1.5">
              <Layers className="w-4 h-4 text-accent" />
              <span>DEPTH OF MARKET (DOM LADDER)</span>
            </span>
            {snapshot && (
              <span className="text-[10px] text-accent font-bold">
                Imbalance: {snapshot.book_imbalance_ratio > 0 ? `+${snapshot.book_imbalance_ratio}` : snapshot.book_imbalance_ratio}
              </span>
            )}
          </div>

          {snapshot && (
            <div className="space-y-1 text-xs">
              {/* Asks (Desc - Top to Bottom) */}
              <div className="space-y-0.5">
                {snapshot.asks.slice().reverse().map((ask: any, idx: number) => {
                  const depthPct = (ask.volume / maxVolume) * 100;
                  return (
                    <div
                      key={`ask-${idx}`}
                      onClick={() => {
                        setOrderPrice(ask.price);
                        setOrderSide("BUY");
                      }}
                      className="relative flex items-center justify-between px-2 py-1 bg-[#111722]/60 hover:bg-rose-950/40 rounded cursor-pointer transition text-[11px]"
                    >
                      <div
                        className="absolute right-0 top-0 bottom-0 bg-loss/15 rounded pointer-events-none"
                        style={{ width: `${depthPct}%` }}
                      />
                      <span className="font-bold text-loss z-10">${ask.price.toFixed(2)}</span>
                      <span className="text-slate-300 z-10">{ask.volume.toFixed(2)} Lots</span>
                    </div>
                  );
                })}
              </div>

              {/* Spread Banner */}
              <div className="bg-[#090d14] py-1.5 px-3 rounded border border-surface-border flex items-center justify-between text-[10px] text-slate-400 font-bold my-2">
                <span>SPREAD: ${snapshot.spread_absolute} ({snapshot.spread_bps} bps)</span>
                <span className="text-accent">MICRO-PX: ${snapshot.micro_price}</span>
              </div>

              {/* Bids (Top to Bottom) */}
              <div className="space-y-0.5">
                {snapshot.bids.map((bid: any, idx: number) => {
                  const depthPct = (bid.volume / maxVolume) * 100;
                  return (
                    <div
                      key={`bid-${idx}`}
                      onClick={() => {
                        setOrderPrice(bid.price);
                        setOrderSide("SELL");
                      }}
                      className="relative flex items-center justify-between px-2 py-1 bg-[#111722]/60 hover:bg-emerald-950/40 rounded cursor-pointer transition text-[11px]"
                    >
                      <div
                        className="absolute left-0 top-0 bottom-0 bg-gain/15 rounded pointer-events-none"
                        style={{ width: `${depthPct}%` }}
                      />
                      <span className="font-bold text-gain z-10">${bid.price.toFixed(2)}</span>
                      <span className="text-slate-300 z-10">{bid.volume.toFixed(2)} Lots</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {/* CENTER COLUMN: ORDER SUBMISSION & DMA ROUTER */}
        <div className="bg-[#0d121c] p-4 rounded-lg border border-surface-border space-y-4">
          <span className="text-xs font-bold text-white flex items-center space-x-1.5 border-b border-surface-border pb-2">
            <DollarSign className="w-4 h-4 text-gain" />
            <span>DMA SMART ORDER ROUTER & ORDER ENTRY</span>
          </span>

          <div className="space-y-3 text-xs">
            <div className="grid grid-cols-2 gap-2">
              <button
                onClick={() => setOrderSide("BUY")}
                className={`py-2 rounded font-bold transition ${
                  orderSide === "BUY" ? "bg-gain text-black shadow" : "bg-[#111722] text-slate-400"
                }`}
              >
                BUY / LONG
              </button>
              <button
                onClick={() => setOrderSide("SELL")}
                className={`py-2 rounded font-bold transition ${
                  orderSide === "SELL" ? "bg-loss text-white shadow" : "bg-[#111722] text-slate-400"
                }`}
              >
                SELL / SHORT
              </button>
            </div>

            <div>
              <label className="text-slate-400 text-[10px] block mb-1">ROUTING DESTINATION</label>
              <select
                value={destination}
                onChange={(e) => setDestination(e.target.value)}
                className="w-full bg-[#111722] border border-surface-border text-white px-3 py-2 rounded text-xs focus:outline-none focus:border-accent"
              >
                <option value="INTERNAL_MATCHING_ENGINE">Internal Matching Engine (Sub-10μs L3 Book)</option>
                <option value="CME_DMA_FIX">CME Group FIX 4.4 DMA Gateway</option>
                <option value="ICE_DMA_FIX">ICE Direct Market Access FIX 5.0 SP2</option>
              </select>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-slate-400 text-[10px] block mb-1">LIMIT PRICE (USD)</label>
                <input
                  type="number"
                  step="0.5"
                  value={orderPrice}
                  onChange={(e) => setOrderPrice(Number(e.target.value))}
                  className="w-full bg-[#111722] border border-surface-border text-white px-3 py-2 rounded text-xs focus:outline-none focus:border-accent font-mono"
                />
              </div>

              <div>
                <label className="text-slate-400 text-[10px] block mb-1">ORDER QUANTITY</label>
                <input
                  type="number"
                  step="0.1"
                  value={orderQty}
                  onChange={(e) => setOrderQty(Number(e.target.value))}
                  className="w-full bg-[#111722] border border-surface-border text-white px-3 py-2 rounded text-xs focus:outline-none focus:border-accent font-mono"
                />
              </div>
            </div>

            <div>
              <label className="text-slate-400 text-[10px] block mb-1">ORDER TYPE / TIME IN FORCE</label>
              <select
                value={orderType}
                onChange={(e) => setOrderType(e.target.value)}
                className="w-full bg-[#111722] border border-surface-border text-white px-3 py-2 rounded text-xs focus:outline-none focus:border-accent"
              >
                <option value="LIMIT">Limit Order (Resting GTC)</option>
                <option value="MARKET">Market Order (Immediate Cross)</option>
                <option value="IOC">Immediate-Or-Cancel (IOC)</option>
                <option value="FOK">Fill-Or-Kill (FOK)</option>
                <option value="POST_ONLY">Post-Only (Resting Maker Only)</option>
              </select>
            </div>

            <button
              onClick={() => handleSubmitOrder()}
              className={`w-full py-2.5 rounded font-bold text-xs transition shadow flex items-center justify-center space-x-1.5 ${
                orderSide === "BUY" ? "bg-gain hover:bg-emerald-400 text-black" : "bg-loss hover:bg-rose-500 text-white"
              }`}
            >
              <Send className="w-3.5 h-3.5" />
              <span>SUBMIT {orderSide} ORDER VIA {destination}</span>
            </button>
          </div>

          {/* Sweep Simulator */}
          <div className="bg-[#111722] p-3 rounded-lg border border-surface-border space-y-2 text-xs">
            <span className="font-bold text-white text-[11px] block">AGGRESSIVE 5.0 LOT MARKET SWEEP</span>
            <div className="grid grid-cols-2 gap-2">
              <button
                onClick={() => handleSimulateSweep("BUY")}
                className="bg-accent/20 hover:bg-accent text-accent hover:text-black font-bold py-1.5 rounded text-[10px] transition"
              >
                SWEEP ASKS (BUY)
              </button>
              <button
                onClick={() => handleSimulateSweep("SELL")}
                className="bg-loss/20 hover:bg-loss text-loss hover:text-white font-bold py-1.5 rounded text-[10px] transition"
              >
                SWEEP BIDS (SELL)
              </button>
            </div>

            {sweepResult && (
              <div className="space-y-1 text-[10px] font-mono text-slate-300 pt-1 border-t border-surface-border">
                <div className="flex justify-between">
                  <span>Execution VWAP:</span>
                  <span className="text-accent font-bold">${sweepResult.execution_vwap}</span>
                </div>
                <div className="flex justify-between">
                  <span>Slippage:</span>
                  <span className="text-amber-400 font-bold">{sweepResult.slippage_bps} bps</span>
                </div>
                <div className="flex justify-between">
                  <span>Levels Swept:</span>
                  <span>{sweepResult.depth_levels_swept} Price Ticks</span>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* RIGHT COLUMN: FIX SESSION & MESSAGE LOG STREAM */}
        <div className="bg-[#0d121c] p-4 rounded-lg border border-surface-border flex flex-col space-y-3">
          <div className="flex items-center justify-between border-b border-surface-border pb-2">
            <span className="text-xs font-bold text-white flex items-center space-x-1.5">
              <Terminal className="w-4 h-4 text-accent" />
              <span>FIX SESSION & MESSAGE STREAM</span>
            </span>
            {fixSession && (
              <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${
                fixSession.status === "ACTIVE" ? "bg-gain/20 text-gain" : "bg-amber-500/20 text-amber-400"
              }`}>
                {fixSession.status}
              </span>
            )}
          </div>

          {fixSession && (
            <div className="grid grid-cols-2 gap-2 text-[10px] font-mono bg-[#111722] p-2.5 rounded border border-surface-border">
              <div>
                <span className="text-slate-500 block">SENDER COMP ID</span>
                <span className="text-white font-bold">{fixSession.sender_comp_id}</span>
              </div>
              <div>
                <span className="text-slate-500 block">TARGET COMP ID</span>
                <span className="text-white font-bold">{fixSession.target_comp_id}</span>
              </div>
              <div>
                <span className="text-slate-500 block">OUT SEQ NUM</span>
                <span className="text-accent font-bold">#{fixSession.out_seq_num}</span>
              </div>
              <div>
                <span className="text-slate-500 block">IN SEQ NUM</span>
                <span className="text-gain font-bold">#{fixSession.in_seq_num}</span>
              </div>
            </div>
          )}

          {/* Raw Message Log */}
          <div className="flex-1 bg-[#090d14] p-2.5 rounded border border-surface-border overflow-y-auto space-y-2 text-[10px] font-mono">
            <span className="text-slate-500 block text-[9px] border-b border-surface-border pb-1">
              LIVE TAG-VALUE FIX PROTOCOL STREAM
            </span>
            {fixSession?.message_history?.length > 0 ? (
              fixSession.message_history.slice().reverse().map((msg: any, idx: number) => (
                <div key={idx} className="space-y-0.5 border-b border-surface-border/50 pb-1.5">
                  <div className="flex items-center justify-between text-[9px]">
                    <span className={msg.direction === "OUT" ? "text-accent font-bold" : "text-gain font-bold"}>
                      {msg.direction} &bull; {msg.msg_name}
                    </span>
                    <span className="text-slate-500">{new Date(msg.timestamp * 1000).toLocaleTimeString()}</span>
                  </div>
                  <div className="text-slate-300 break-all leading-tight bg-[#111722] p-1 rounded">
                    {msg.raw}
                  </div>
                </div>
              ))
            ) : (
              <p className="text-slate-500">No FIX messages recorded yet. Click 'FIX 35=A LOGON' to initialize connection.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};