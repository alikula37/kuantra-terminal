import React, { useState, useEffect } from "react";
import { ArrowRightLeft, ShieldCheck, Zap, RefreshCw, Layers, CheckCircle2, DollarSign, Activity, Compass } from "lucide-react";
import { apiUrl } from "../../lib/backend";

export const DEXArbitrageStudio: React.FC = () => {
  const [selectedChain, setSelectedChain] = useState<string>("ethereum");
  const [opportunities, setOpportunities] = useState<any[]>([]);
  const [selectedOpp, setSelectedOpp] = useState<any>(null);
  const [selectedProtocol, setSelectedProtocol] = useState<string>("BALANCER_VAULT");
  const [loanAmount, setLoanAmount] = useState<number>(100000);
  const [simResult, setSimResult] = useState<any>(null);
  const [defaiResult, setDefaiResult] = useState<any>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [executionMsg, setExecutionMsg] = useState<string | null>(null);

  // Chains Status
  const chainStatus: Record<string, { block: number; gas: string; latency: string }> = {
    ethereum: { block: 21854930, gas: "14.2 Gwei", latency: "28ms" },
    arbitrum: { block: 298412040, gas: "0.12 Gwei", latency: "14ms" },
    base: { block: 26849102, gas: "0.08 Gwei", latency: "18ms" },
    solana: { block: 314982300, gas: "15k CU", latency: "32ms" },
  };

  const fetchOpportunities = async () => {
    setIsLoading(true);
    try {
      const res = await fetch(apiUrl("/api/v1/dex/scan-opportunities"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ chain: selectedChain, min_profit_usd: 50.0, include_triangular: true }),
      });
      const data = await res.json();
      setOpportunities(data.opportunities || []);
      if (data.opportunities && data.opportunities.length > 0) {
        setSelectedOpp(data.opportunities[0]);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchOpportunities();
  }, [selectedChain]);

  useEffect(() => {
    if (selectedOpp) {
      handleSimulate();
    }
  }, [selectedOpp, selectedProtocol, loanAmount]);

  const handleSimulate = async () => {
    if (!selectedOpp) return;
    try {
      // 1. Run Flash Loan Simulation
      const simRes = await fetch(apiUrl("/api/v1/dex/simulate-flash-loan"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          chain: selectedChain,
          protocol: selectedProtocol,
          borrow_asset: "WETH",
          amount_usd: loanAmount,
          route_spread_pct: selectedOpp.gross_spread_pct || 0.58,
        }),
      });
      const simData = await simRes.json();
      setSimResult(simData);

      // 2. Run DeFAI Agent Evaluation
      const defaiRes = await fetch(apiUrl("/api/v1/dex/defai-evaluate"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ opportunity: selectedOpp }),
      });
      const defaiData = await defaiRes.json();
      setDefaiResult(defaiData);
    } catch (e) {
      console.error(e);
    }
  };

  const handleExecutePaperArbitrage = () => {
    if (!selectedOpp || !simResult) return;
    setExecutionMsg(
      `Paper Arbitrage Executed! Route ${selectedOpp.opportunity_id} filled with $${simResult.financial_breakdown.net_profit_usd} Net Profit via ${selectedProtocol} Flash Loan.`
    );
    setTimeout(() => setExecutionMsg(null), 5000);
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-[#0b0e14] overflow-y-auto p-4 select-none font-mono space-y-4 text-slate-100">
      {/* Header */}
      <div className="pb-3 border-b border-surface-border flex items-center justify-between">
        <div>
          <div className="flex items-center space-x-2">
            <ArrowRightLeft className="w-5 h-5 text-accent" />
            <h2 className="text-sm font-bold text-white uppercase tracking-wider">
              ON-CHAIN MULTI-CHAIN DEX ARBITRAGE & FLASH LOAN STUDIO
            </h2>
          </div>
          <p className="text-xs text-slate-400">
            Real-Time AMM Reserves Scanner &bull; Bellman-Ford Triangular Cycles &bull; MEV Private Bundle Protection
          </p>
        </div>

        <div className="flex items-center space-x-3">
          {selectedOpp && simResult && (
            <button
              onClick={handleExecutePaperArbitrage}
              className="flex items-center space-x-1.5 bg-gain hover:bg-emerald-400 text-black font-bold px-3 py-1.5 rounded text-xs transition shadow"
            >
              <Zap className="w-3.5 h-3.5" />
              <span>PAPER EXECUTE ROUTE</span>
            </button>
          )}

          <button
            onClick={fetchOpportunities}
            disabled={isLoading}
            className="p-1.5 bg-[#0d121c] hover:bg-[#111722] border border-surface-border rounded text-slate-400 hover:text-white transition"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {/* Execution Alert */}
      {executionMsg && (
        <div className="bg-gain/10 border border-gain/30 p-3 rounded-lg flex items-center space-x-2 text-gain text-xs">
          <CheckCircle2 className="w-4 h-4 text-gain" />
          <span>{executionMsg}</span>
        </div>
      )}

      {/* Multi-Chain Telemetry Bar */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {Object.entries(chainStatus).map(([chainName, info]: [string, any]) => (
          <button
            key={chainName}
            onClick={() => setSelectedChain(chainName)}
            className={`p-3 rounded-lg border text-left transition ${
              selectedChain === chainName
                ? "bg-accent/10 border-accent/40 text-white"
                : "bg-[#0d121c] border-surface-border text-slate-400 hover:bg-[#111722]"
            }`}
          >
            <div className="flex items-center justify-between text-xs font-bold mb-1">
              <span className="uppercase">{chainName}</span>
              <span className="text-[10px] text-gain">● {info.latency}</span>
            </div>
            <div className="text-[10px] space-y-0.5 text-slate-400 font-mono">
              <div>Block: #{info.block}</div>
              <div>Gas: {info.gas}</div>
            </div>
          </button>
        ))}
      </div>

      {/* Main Dual Pane Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 flex-1">
        {/* LEFT 2 COLUMNS: OPPORTUNITY SCANNER & PATH GRAPH */}
        <div className="lg:col-span-2 space-y-4">
          {/* Opportunities Table */}
          <div className="bg-[#0d121c] p-4 rounded-lg border border-surface-border space-y-3">
            <span className="text-xs font-bold text-white flex items-center space-x-1.5 border-b border-surface-border pb-2">
              <Compass className="w-4 h-4 text-accent" />
              <span>LIVE DETECTED ARBITRAGE OPPORTUNITIES ({opportunities.length})</span>
            </span>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="text-slate-400 border-b border-surface-border text-[10px]">
                    <th className="pb-2 font-bold">TYPE / ID</th>
                    <th className="pb-2 font-bold">PAIR / CYCLE</th>
                    <th className="pb-2 font-bold">VENUES / HOPS</th>
                    <th className="pb-2 font-bold">SPREAD %</th>
                    <th className="pb-2 font-bold">EST. GAS</th>
                    <th className="pb-2 font-bold">MEV SHIELD</th>
                    <th className="pb-2 font-bold">ACTION</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-border">
                  {opportunities.map((opp) => {
                    const isSelected = selectedOpp?.opportunity_id === opp.opportunity_id;
                    return (
                      <tr
                        key={opp.opportunity_id}
                        onClick={() => setSelectedOpp(opp)}
                        className={`cursor-pointer transition ${
                          isSelected ? "bg-accent/15 text-white" : "hover:bg-[#111722] text-slate-300"
                        }`}
                      >
                        <td className="py-2.5 font-bold font-mono">
                          <span className="text-[10px] bg-[#111722] px-1.5 py-0.5 rounded border border-surface-border">
                            {opp.type}
                          </span>
                        </td>
                        <td className="py-2.5 font-bold text-white">
                          {opp.pair || opp.cycle_path?.join(" → ")}
                        </td>
                        <td className="py-2.5 text-[11px] text-slate-400">
                          {opp.buy_venue ? `${opp.buy_venue} → ${opp.sell_venue}` : opp.venues?.join(" → ")}
                        </td>
                        <td className="py-2.5 font-bold text-gain">+{opp.gross_spread_pct}%</td>
                        <td className="py-2.5 text-slate-300 font-mono">${opp.estimated_gas_usd}</td>
                        <td className="py-2.5 text-[10px] text-accent">
                          <span className="flex items-center space-x-1">
                            <ShieldCheck className="w-3 h-3 text-accent" />
                            <span>{opp.mev_protection}</span>
                          </span>
                        </td>
                        <td className="py-2.5">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setSelectedOpp(opp);
                            }}
                            className="bg-accent/20 hover:bg-accent text-accent hover:text-black font-bold px-2 py-0.5 rounded text-[10px] transition"
                          >
                            SELECT
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Interactive Triangular Path Graph Visualizer */}
          {selectedOpp && (
            <div className="bg-[#0d121c] p-4 rounded-lg border border-surface-border space-y-3">
              <span className="text-xs font-bold text-white flex items-center space-x-1.5 border-b border-surface-border pb-2">
                <Layers className="w-4 h-4 text-purple-400" />
                <span>ASSET FLOW & POOL HOP GRAPH VISUALIZER</span>
              </span>

              <div className="bg-[#090d14] p-4 rounded border border-surface-border flex items-center justify-around text-xs">
                {selectedOpp.cycle_path ? (
                  selectedOpp.cycle_path.map((token: string, idx: number) => (
                    <React.Fragment key={idx}>
                      <div className="flex flex-col items-center space-y-1">
                        <div className="w-10 h-10 rounded-full bg-accent/20 border border-accent flex items-center justify-center font-bold text-accent">
                          {token}
                        </div>
                        <span className="text-[10px] text-slate-400">Hop {idx + 1}</span>
                      </div>
                      {idx < selectedOpp.cycle_path.length - 1 && (
                        <div className="flex-1 flex flex-col items-center px-2">
                          <span className="text-[9px] text-gain font-bold">
                            {selectedOpp.venues ? selectedOpp.venues[idx] : "Uniswap v3"}
                          </span>
                          <div className="w-full h-[2px] bg-gradient-to-r from-accent to-purple-500 my-1" />
                          <span className="text-[9px] text-slate-500">Low Slippage</span>
                        </div>
                      )}
                    </React.Fragment>
                  ))
                ) : (
                  <div className="flex items-center justify-between w-full px-8">
                    <div className="flex flex-col items-center space-y-1">
                      <div className="w-12 h-12 rounded-lg bg-gain/20 border border-gain flex items-center justify-center font-bold text-gain text-sm">
                        {selectedOpp.buy_venue}
                      </div>
                      <span className="text-[10px] text-gain font-bold">BUY @ ${selectedOpp.buy_price}</span>
                    </div>

                    <div className="flex-1 flex flex-col items-center px-6">
                      <span className="text-xs font-bold text-accent">+{selectedOpp.gross_spread_pct}% Gross Spread</span>
                      <div className="w-full h-[2px] bg-gradient-to-r from-gain to-accent my-2" />
                      <span className="text-[10px] text-slate-400">Atomic Flash Bundle</span>
                    </div>

                    <div className="flex flex-col items-center space-y-1">
                      <div className="w-12 h-12 rounded-lg bg-purple-500/20 border border-purple-400 flex items-center justify-center font-bold text-purple-300 text-sm">
                        {selectedOpp.sell_venue}
                      </div>
                      <span className="text-[10px] text-purple-300 font-bold">SELL @ ${selectedOpp.sell_price}</span>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* RIGHT COLUMN: MULTI-PROTOCOL FLASH LOAN CONSOLE & DeFAI */}
        <div className="space-y-4">
          {/* Flash Loan Simulator Console */}
          <div className="bg-[#0d121c] p-4 rounded-lg border border-surface-border space-y-4">
            <span className="text-xs font-bold text-white flex items-center space-x-1.5 border-b border-surface-border pb-2">
              <DollarSign className="w-4 h-4 text-gain" />
              <span>FLASH LOAN ROUTER & SIZING CONSOLE</span>
            </span>

            <div className="space-y-3 text-xs">
              <div>
                <label className="text-slate-400 text-[10px] block mb-1">FLASH LOAN PROTOCOL</label>
                <select
                  value={selectedProtocol}
                  onChange={(e) => setSelectedProtocol(e.target.value)}
                  className="w-full bg-[#111722] border border-surface-border text-white px-3 py-2 rounded text-xs focus:outline-none focus:border-accent"
                >
                  <option value="BALANCER_VAULT">Balancer Vault v2/v3 (0.00% Fee)</option>
                  <option value="MORPHO_BLUE">Morpho Blue (0.00% Fee)</option>
                  <option value="AAVE_V3">Aave v3 Pool (0.05% Fee / 5 bps)</option>
                </select>
              </div>

              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-slate-400 text-[10px]">BORROW SIZING (USD)</label>
                  <span className="text-accent font-bold font-mono">${loanAmount.toLocaleString()}</span>
                </div>
                <input
                  type="range"
                  min="25000"
                  max="1000000"
                  step="25000"
                  value={loanAmount}
                  onChange={(e) => setLoanAmount(Number(e.target.value))}
                  className="w-full h-1.5 bg-[#111722] rounded-lg appearance-none cursor-pointer accent-accent"
                />
              </div>
            </div>

            {/* Financial Balance Sheet */}
            {simResult && (
              <div className="bg-[#111722] p-3 rounded-lg border border-surface-border space-y-2 text-xs">
                <span className="font-bold text-white text-[11px] block border-b border-surface-border pb-1">
                  SIMULATED NET BALANCE SHEET
                </span>

                <div className="space-y-1.5 text-[11px] font-mono">
                  <div className="flex justify-between text-slate-300">
                    <span>Gross Arbitrage Spread:</span>
                    <span className="text-gain font-bold">+${simResult.financial_breakdown.gross_profit_usd}</span>
                  </div>
                  <div className="flex justify-between text-slate-400">
                    <span>Flash Loan Fee ({simResult.financial_breakdown.flash_loan_fee_pct}%):</span>
                    <span>-${simResult.financial_breakdown.flash_loan_fee_usd}</span>
                  </div>
                  <div className="flex justify-between text-slate-400">
                    <span>Pool Swap Fees (Hops):</span>
                    <span>-${simResult.financial_breakdown.pool_swap_fees_usd}</span>
                  </div>
                  <div className="flex justify-between text-slate-400">
                    <span>Estimated L2 Gas Cost:</span>
                    <span>-${simResult.financial_breakdown.gas_cost_usd}</span>
                  </div>
                  <div className="flex justify-between text-slate-400">
                    <span>MEV Builder Tip (Flashbots):</span>
                    <span>-${simResult.financial_breakdown.mev_builder_tip_usd}</span>
                  </div>

                  <div className="pt-2 border-t border-surface-border flex justify-between items-center text-xs">
                    <span className="font-bold text-white">ESTIMATED NET PROFIT:</span>
                    <span className="text-base font-bold text-gain font-mono">
                      +${simResult.financial_breakdown.net_profit_usd}
                    </span>
                  </div>
                  <div className="text-right text-[10px] text-accent">
                    Net Yield: +{simResult.financial_breakdown.net_yield_pct}%
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* DeFAI Sentinel Evaluation */}
          {defaiResult && (
            <div className="bg-[#0d121c] p-4 rounded-lg border border-surface-border space-y-2 text-xs">
              <div className="flex items-center justify-between border-b border-surface-border pb-2">
                <span className="text-xs font-bold text-white flex items-center space-x-1.5">
                  <Activity className="w-4 h-4 text-gain" />
                  <span>DeFAI AUTONOMOUS SENTINEL</span>
                </span>
                <span className="text-[10px] font-bold bg-gain/20 text-gain px-2 py-0.5 rounded">
                  {defaiResult.confidence_score}% CONVICTION
                </span>
              </div>

              <div className="space-y-1.5 pt-1 text-[11px]">
                <div className="flex justify-between text-slate-300">
                  <span>Recommendation:</span>
                  <span className="text-gain font-bold">{defaiResult.decision}</span>
                </div>
                <div className="flex justify-between text-slate-300">
                  <span>Gas to Profit Ratio:</span>
                  <span className="text-accent">{defaiResult.gas_to_profit_ratio_pct}%</span>
                </div>
                <p className="text-slate-400 text-[10px] leading-relaxed pt-1">{defaiResult.rationale}</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};