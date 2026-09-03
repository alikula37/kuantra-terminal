import React, { useState, useEffect } from "react";
import { Terminal, Send, Activity, ShieldCheck, Zap } from "lucide-react";
import { apiFetch, apiUrl } from "../../lib/backend";

interface FixStatus {
  begin_string: string;
  sender_comp_id: string;
  target_comp_id: string;
  is_logged_on: boolean;
  outbound_seq_num: number;
  inbound_seq_num: number;
  round_trip_latency_us: number;
  heartbeat_interval_sec: number;
  supported_venues: string[];
}

interface FixExecReport {
  status: string;
  cl_ord_id: string;
  exec_id: string;
  symbol: string;
  side: string;
  last_qty: number;
  last_px: number;
  round_trip_latency_us: number;
  raw_fix_wire: string;
}

export const FixStatusWidget: React.FC = () => {
  const [status, setStatus] = useState<FixStatus>({
    begin_string: "FIX.4.4",
    sender_comp_id: "KUANTRA_DMA_01",
    target_comp_id: "CME_GLOBEX",
    is_logged_on: true,
    outbound_seq_num: 14,
    inbound_seq_num: 14,
    round_trip_latency_us: 380.5,
    heartbeat_interval_sec: 30,
    supported_venues: ["CME_GLOBEX", "ICE_FUTURES", "EUREX_DMA"],
  });

  const [symbol, setSymbol] = useState<string>("ESM6");
  const [side, setSide] = useState<string>("BUY");
  const [qty, setQty] = useState<number>(1);
  const [price, setPrice] = useState<number>(5620.25);
  const [isSending, setIsSending] = useState<boolean>(false);
  const [lastExec, setLastExec] = useState<FixExecReport | null>(null);

  const fetchStatus = () => {
    apiFetch(apiUrl("/api/v1/fix/status"))
      .then((res) => res.json())
      .then((data) => setStatus(data))
      .catch(() => {});
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 2000);
    return () => clearInterval(interval);
  }, []);

  const sendFixOrder = async () => {
    setIsSending(true);
    try {
      const res = await apiFetch(apiUrl("/api/v1/fix/order"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbol, side, qty, price }),
      });
      const data = await res.json();
      setLastExec(data);
      fetchStatus();
    } catch (e) {
      console.error(e);
    } finally {
      setIsSending(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-[#0b0e14] overflow-y-auto p-4 select-none font-mono space-y-4">
      {/* Header */}
      <div className="pb-3 border-b border-surface-border flex items-center justify-between">
        <div>
          <div className="flex items-center space-x-2">
            <Terminal className="w-5 h-5 text-accent" />
            <h2 className="text-sm font-bold text-white uppercase tracking-wider">
              CME / ICE QUICKFIX PROTOCOL DMA GATEWAY
            </h2>
          </div>
          <p className="text-xs text-slate-400">
            Institutional FIX 4.4 & FIX 5.0 SP2 Execution Engine with Microsecond Latency Tracking
          </p>
        </div>

        <div className="flex items-center space-x-2 bg-[#0d121c] border border-surface-border px-3 py-1.5 rounded-lg text-xs">
          <Activity className="w-4 h-4 text-gain animate-pulse" />
          <span className="text-white font-bold">{status.target_comp_id}</span>
          <span className="text-[10px] bg-gain/20 text-gain px-1.5 py-0.2 rounded font-bold">
            35=A LOGON OK
          </span>
        </div>
      </div>

      {/* Metrics Strip */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
        <div className="bg-[#0d121c] p-3 rounded border border-surface-border">
          <span className="text-[10px] text-slate-400 block">FIX PROTOCOL</span>
          <span className="text-base font-bold text-white">{status.begin_string}</span>
        </div>
        <div className="bg-[#0d121c] p-3 rounded border border-surface-border">
          <span className="text-[10px] text-slate-400 block">ROUND-TRIP LATENCY</span>
          <div className="flex items-baseline space-x-1">
            <span className="text-base font-bold text-gain font-mono">{status.round_trip_latency_us.toFixed(1)}</span>
            <span className="text-xs text-slate-500 font-bold">µs</span>
          </div>
        </div>
        <div className="bg-[#0d121c] p-3 rounded border border-surface-border">
          <span className="text-[10px] text-slate-400 block">OUTBOUND SEQ #</span>
          <span className="text-base font-bold text-accent font-mono">#{status.outbound_seq_num}</span>
        </div>
        <div className="bg-[#0d121c] p-3 rounded border border-surface-border">
          <span className="text-[10px] text-slate-400 block">HEARTBEAT (35=0)</span>
          <span className="text-base font-bold text-white">{status.heartbeat_interval_sec}s Active</span>
        </div>
      </div>

      {/* DMA Order Dispatch Sandbox */}
      <div className="bg-[#0d121c] p-4 rounded-lg border border-surface-border space-y-3">
        <div className="flex items-center space-x-2 text-white font-bold text-xs">
          <Zap className="w-4 h-4 text-accent" />
          <span>DIRECT MARKET ACCESS (DMA) ORDER DISPATCH</span>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
          <div>
            <span className="text-[10px] text-slate-400 block mb-1">CME CONTRACT</span>
            <input
              type="text"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
              className="w-full bg-[#111722] border border-surface-border text-white px-2 py-1.5 rounded focus:outline-none focus:border-accent"
            />
          </div>
          <div>
            <span className="text-[10px] text-slate-400 block mb-1">SIDE (TAG 54)</span>
            <select
              value={side}
              onChange={(e) => setSide(e.target.value)}
              className="w-full bg-[#111722] border border-surface-border text-white px-2 py-1.5 rounded focus:outline-none focus:border-accent"
            >
              <option value="BUY">BUY / 1</option>
              <option value="SELL">SELL / 2</option>
            </select>
          </div>
          <div>
            <span className="text-[10px] text-slate-400 block mb-1">LOTS (TAG 38)</span>
            <input
              type="number"
              value={qty}
              onChange={(e) => setQty(parseFloat(e.target.value))}
              className="w-full bg-[#111722] border border-surface-border text-white px-2 py-1.5 rounded focus:outline-none focus:border-accent"
            />
          </div>
          <div>
            <span className="text-[10px] text-slate-400 block mb-1">PRICE (TAG 44)</span>
            <input
              type="number"
              step="0.25"
              value={price}
              onChange={(e) => setPrice(parseFloat(e.target.value))}
              className="w-full bg-[#111722] border border-surface-border text-white px-2 py-1.5 rounded focus:outline-none focus:border-accent"
            />
          </div>
        </div>

        <button
          onClick={sendFixOrder}
          disabled={isSending}
          className="flex items-center space-x-2 bg-accent hover:bg-sky-400 text-black font-bold px-4 py-2 rounded text-xs transition"
        >
          <Send className="w-3.5 h-3.5" />
          <span>{isSending ? "DISPATCHING FIX PACKET..." : "SEND FIX 35=D NEW ORDER SINGLE"}</span>
        </button>
      </div>

      {/* Live FIX Wire Stream Inspector */}
      {lastExec && (
        <div className="bg-[#0d121c] p-4 rounded-lg border border-surface-border space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-white flex items-center space-x-1.5">
              <ShieldCheck className="w-4 h-4 text-gain" />
              <span>RAW FIX WIRE INSPECTOR (EXECUTION REPORT 35=8)</span>
            </span>
            <span className="text-[10px] bg-gain/20 text-gain px-2 py-0.5 rounded font-bold">
              {lastExec.status} ({lastExec.round_trip_latency_us} µs)
            </span>
          </div>

          <div className="bg-[#111722] p-3 rounded border border-surface-border text-[11px] font-mono text-slate-300 break-all">
            {lastExec.raw_fix_wire}
          </div>
        </div>
      )}
    </div>
  );
};