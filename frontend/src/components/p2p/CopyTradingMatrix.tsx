import React, { useState, useEffect } from "react";
import { Users, Layers, Send, RefreshCw, CheckCircle2 } from "lucide-react";

interface SubAccount {
  account_id: string;
  name: string;
  venue: string;
  equity: number;
  risk_multiplier: number;
  max_daily_loss: number;
  current_daily_loss: number;
  is_active: boolean;
}

interface FanoutReport {
  status: string;
  symbol: string;
  side: string;
  total_allocated_lots: number;
  sub_account_results: Array<{
    account_id: string;
    name: string;
    venue?: string;
    allocated_qty?: number;
    execution_status?: string;
    status?: string;
    reason?: string;
  }>;
}

export const CopyTradingMatrix: React.FC = () => {
  const [accounts, setAccounts] = useState<SubAccount[]>([]);
  const [symbol, setSymbol] = useState<string>("BTCUSDT");
  const [side, setSide] = useState<string>("BUY");
  const [baseQty, setBaseQty] = useState<number>(1.0);
  const [price, setPrice] = useState<number>(64800.0);
  const [isDispatching, setIsDispatching] = useState<boolean>(false);
  const [fanoutReport, setFanoutReport] = useState<FanoutReport | null>(null);

  const fetchAccounts = () => {
    fetch("http://127.0.0.1:8000/api/v1/accounts/list")
      .then((res) => res.json())
      .then((data) => {
        if (data.accounts) setAccounts(data.accounts);
      })
      .catch(() => {});
  };

  useEffect(() => {
    fetchAccounts();
    const interval = setInterval(fetchAccounts, 3000);
    return () => clearInterval(interval);
  }, []);

  const dispatchFanout = async () => {
    setIsDispatching(true);
    try {
      const res = await fetch("http://127.0.0.1:8000/api/v1/accounts/fanout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbol, side, qty: baseQty, price }),
      });
      const data = await res.json();
      setFanoutReport(data);
      fetchAccounts();
    } catch (e) {
      console.error(e);
    } finally {
      setIsDispatching(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-[#0b0e14] overflow-y-auto p-4 select-none font-mono space-y-4">
      {/* Header */}
      <div className="pb-3 border-b border-surface-border flex items-center justify-between">
        <div>
          <div className="flex items-center space-x-2">
            <Users className="w-5 h-5 text-accent" />
            <h2 className="text-sm font-bold text-white uppercase tracking-wider">
              MULTI-ACCOUNT PROP FIRM RISK ALLOCATOR & COPY MATRIX
            </h2>
          </div>
          <p className="text-xs text-slate-400">
            Simultaneous Multi-Broker Fan-Out Execution with Per-Account Drawdown Shield Protection
          </p>
        </div>

        <button
          onClick={fetchAccounts}
          className="p-1.5 bg-[#0d121c] hover:bg-[#111722] border border-surface-border rounded text-slate-400 hover:text-white transition"
        >
          <RefreshCw className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Fanout Order Control Strip */}
      <div className="bg-[#0d121c] p-4 rounded-lg border border-surface-border space-y-3">
        <div className="flex items-center space-x-2 text-white font-bold text-xs">
          <Layers className="w-4 h-4 text-accent" />
          <span>MULTI-BROKER FANOUT DISPATCH CONTROLLER</span>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
          <div>
            <span className="text-[10px] text-slate-400 block mb-1">TARGET SYMBOL</span>
            <input
              type="text"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
              className="w-full bg-[#111722] border border-surface-border text-white px-2 py-1.5 rounded focus:outline-none focus:border-accent"
            />
          </div>
          <div>
            <span className="text-[10px] text-slate-400 block mb-1">SIDE</span>
            <select
              value={side}
              onChange={(e) => setSide(e.target.value)}
              className="w-full bg-[#111722] border border-surface-border text-white px-2 py-1.5 rounded focus:outline-none focus:border-accent"
            >
              <option value="BUY">BUY / LONG</option>
              <option value="SELL">SELL / SHORT</option>
            </select>
          </div>
          <div>
            <span className="text-[10px] text-slate-400 block mb-1">BASE QUANTITY</span>
            <input
              type="number"
              step="0.1"
              value={baseQty}
              onChange={(e) => setBaseQty(parseFloat(e.target.value))}
              className="w-full bg-[#111722] border border-surface-border text-white px-2 py-1.5 rounded focus:outline-none focus:border-accent"
            />
          </div>
          <div>
            <span className="text-[10px] text-slate-400 block mb-1">LIMIT PRICE</span>
            <input
              type="number"
              value={price}
              onChange={(e) => setPrice(parseFloat(e.target.value))}
              className="w-full bg-[#111722] border border-surface-border text-white px-2 py-1.5 rounded focus:outline-none focus:border-accent"
            />
          </div>
        </div>

        <button
          onClick={dispatchFanout}
          disabled={isDispatching}
          className="flex items-center space-x-2 bg-accent hover:bg-sky-400 text-black font-bold px-4 py-2 rounded text-xs transition"
        >
          <Send className="w-3.5 h-3.5" />
          <span>{isDispatching ? "FANNING OUT TRADES..." : "DISPATCH MULTI-ACCOUNT FANOUT"}</span>
        </button>
      </div>

      {/* Fanout Report Banner */}
      {fanoutReport && (
        <div className="bg-gain/10 border border-gain/30 p-3 rounded-lg flex items-center justify-between text-xs text-gain">
          <div className="flex items-center space-x-2">
            <CheckCircle2 className="w-4 h-4 text-gain" />
            <span className="font-bold">FANOUT COMPLETED:</span>
            <span>
              {fanoutReport.side} {fanoutReport.total_allocated_lots} Lots filled across {fanoutReport.sub_account_results.length} accounts.
            </span>
          </div>
          <span className="font-bold">{fanoutReport.symbol}</span>
        </div>
      )}

      {/* Sub-Accounts Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {accounts.map((acc) => {
          const isDrawdownBreached = acc.current_daily_loss >= acc.max_daily_loss;
          const lossPct = Math.min(100, (acc.current_daily_loss / acc.max_daily_loss) * 100);

          return (
            <div
              key={acc.account_id}
              className={`p-4 rounded-lg border flex flex-col justify-between space-y-3 ${
                isDrawdownBreached
                  ? "bg-rose-500/10 border-rose-500/50"
                  : "bg-[#0d121c] border-surface-border"
              }`}
            >
              <div className="flex items-center justify-between border-b border-surface-border pb-2">
                <div>
                  <span className="font-bold text-white text-xs block">{acc.name}</span>
                  <span className="text-[10px] text-slate-400 font-mono">{acc.venue}</span>
                </div>
                <span className={`text-[10px] px-2 py-0.5 rounded font-bold ${
                  isDrawdownBreached
                    ? "bg-rose-500 text-white"
                    : "bg-gain/20 text-gain border border-gain/30"
                }`}>
                  {isDrawdownBreached ? "DRAWDOWN BREACH" : "ARMED"}
                </span>
              </div>

              <div className="space-y-1 text-xs">
                <div className="flex items-center justify-between text-slate-400">
                  <span>Equity:</span>
                  <span className="font-bold text-white">${acc.equity.toLocaleString()}</span>
                </div>
                <div className="flex items-center justify-between text-slate-400">
                  <span>Risk Scale:</span>
                  <span className="font-bold text-accent font-mono">{acc.risk_multiplier}x</span>
                </div>
                <div className="flex items-center justify-between text-slate-400">
                  <span>Daily Loss:</span>
                  <span className={`font-bold font-mono ${isDrawdownBreached ? "text-rose-400" : "text-slate-300"}`}>
                    ${acc.current_daily_loss.toFixed(0)} / ${acc.max_daily_loss.toFixed(0)}
                  </span>
                </div>
              </div>

              {/* Loss Progress Bar */}
              <div className="space-y-1">
                <div className="w-full bg-[#111722] h-1.5 rounded-full overflow-hidden">
                  <div
                    className={`h-full ${isDrawdownBreached ? "bg-rose-500" : lossPct > 70 ? "bg-amber-400" : "bg-gain"}`}
                    style={{ width: `${lossPct}%` }}
                  />
                </div>
                <div className="flex justify-between text-[9px] text-slate-500">
                  <span>Drawdown Util</span>
                  <span>{lossPct.toFixed(1)}%</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};