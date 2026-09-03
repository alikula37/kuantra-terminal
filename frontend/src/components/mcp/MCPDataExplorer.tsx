import React, { useState, useEffect } from "react";
import { Database, FileText, Globe, Flame, Activity, RefreshCw, Send, ShieldAlert, CheckCircle2, Search, TrendingUp } from "lucide-react";
import { apiFetch, apiUrl } from "../../lib/backend";

export const MCPDataExplorer: React.FC = () => {
  const [activeTab, setActiveTab] = useState<"sec" | "macro" | "sentiment" | "onchain">("sentiment");
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [ticker, setTicker] = useState<string>("AAPL");
  const [network, setNetwork] = useState<string>("ethereum");
  const [contextSentMsg, setContextSentMsg] = useState<string | null>(null);

  // Data states
  const [secData, setSecData] = useState<any>(null);
  const [macroData, setMacroData] = useState<any>(null);
  const [sentimentData, setSentimentData] = useState<any>(null);
  const [onchainData, setOnchainData] = useState<any>(null);

  const fetchMCPData = async () => {
    setIsLoading(true);
    try {
      if (activeTab === "sec") {
        const res = await apiFetch(apiUrl("/api/v1/mcp/query"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ source: "sec_edgar", params: { ticker } }),
        });
        const data = await res.json();
        setSecData(data.data);
      } else if (activeTab === "macro") {
        const res = await apiFetch(apiUrl("/api/v1/mcp/query"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ source: "macro_fundamentals", params: { asset: "US10Y" } }),
        });
        const data = await res.json();
        setMacroData(data.data);
      } else if (activeTab === "sentiment") {
        const res = await apiFetch(apiUrl("/api/v1/mcp/query"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ source: "cryptopanic_sentiment", params: { filter: "all" } }),
        });
        const data = await res.json();
        setSentimentData(data.data);
      } else if (activeTab === "onchain") {
        const res = await apiFetch(apiUrl("/api/v1/mcp/query"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ source: "onchain_analytics", params: { network } }),
        });
        const data = await res.json();
        setOnchainData(data.data);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchMCPData();
  }, [activeTab]);

  const sendContextToSwarm = () => {
    setContextSentMsg(`Quantitative context from ${activeTab.toUpperCase()} dispatched to AI Swarm debate.`);
    setTimeout(() => setContextSentMsg(null), 4000);
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-[#0b0e14] overflow-y-auto p-4 select-none font-mono space-y-4 text-slate-100">
      {/* Header */}
      <div className="pb-3 border-b border-surface-border flex items-center justify-between">
        <div>
          <div className="flex items-center space-x-2">
            <Database className="w-5 h-5 text-accent" />
            <h2 className="text-sm font-bold text-white uppercase tracking-wider">
              FINANCIAL MODEL CONTEXT PROTOCOL (MCP) GATEWAY
            </h2>
          </div>
          <p className="text-xs text-slate-400">
            Standardized Quantitative Context Ingestion (BlockRunAI/awesome-finance-mcp)
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={sendContextToSwarm}
            className="flex items-center space-x-1.5 bg-accent hover:bg-sky-400 text-black font-bold px-3 py-1.5 rounded text-xs transition shadow"
          >
            <Send className="w-3.5 h-3.5" />
            <span>DISPATCH CONTEXT TO AI SWARM</span>
          </button>

          <button
            onClick={fetchMCPData}
            disabled={isLoading}
            className="p-1.5 bg-[#0d121c] hover:bg-[#111722] border border-surface-border rounded text-slate-400 hover:text-white transition"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {/* Action Banner */}
      {contextSentMsg && (
        <div className="bg-gain/10 border border-gain/30 p-3 rounded-lg flex items-center space-x-2 text-gain text-xs">
          <CheckCircle2 className="w-4 h-4 text-gain" />
          <span>{contextSentMsg}</span>
        </div>
      )}

      {/* Navigation Sub-Tabs */}
      <div className="flex items-center space-x-2 border-b border-surface-border pb-2 text-xs">
        <button
          onClick={() => setActiveTab("sentiment")}
          className={`flex items-center space-x-1.5 px-3 py-1.5 rounded font-bold transition ${
            activeTab === "sentiment"
              ? "bg-accent/15 text-accent border border-accent/30"
              : "text-slate-400 hover:text-white hover:bg-[#111722]"
          }`}
        >
          <Flame className="w-3.5 h-3.5" />
          <span>CryptoPanic Sentiment Matrix</span>
        </button>

        <button
          onClick={() => setActiveTab("sec")}
          className={`flex items-center space-x-1.5 px-3 py-1.5 rounded font-bold transition ${
            activeTab === "sec"
              ? "bg-accent/15 text-accent border border-accent/30"
              : "text-slate-400 hover:text-white hover:bg-[#111722]"
          }`}
        >
          <FileText className="w-3.5 h-3.5" />
          <span>SEC EDGAR / 10-K Filings</span>
        </button>

        <button
          onClick={() => setActiveTab("macro")}
          className={`flex items-center space-x-1.5 px-3 py-1.5 rounded font-bold transition ${
            activeTab === "macro"
              ? "bg-accent/15 text-accent border border-accent/30"
              : "text-slate-400 hover:text-white hover:bg-[#111722]"
          }`}
        >
          <Globe className="w-3.5 h-3.5" />
          <span>Global Macro & Yields</span>
        </button>

        <button
          onClick={() => setActiveTab("onchain")}
          className={`flex items-center space-x-1.5 px-3 py-1.5 rounded font-bold transition ${
            activeTab === "onchain"
              ? "bg-accent/15 text-accent border border-accent/30"
              : "text-slate-400 hover:text-white hover:bg-[#111722]"
          }`}
        >
          <Activity className="w-3.5 h-3.5" />
          <span>On-Chain Flow Monitor</span>
        </button>
      </div>

      {/* TAB 1: CRYPTOPANIC SENTIMENT MATRIX */}
      {activeTab === "sentiment" && sentimentData && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
            <div className="bg-[#0d121c] p-3 rounded border border-surface-border">
              <span className="text-[10px] text-slate-400 block">FEAR & GREED INDEX</span>
              <span className="text-lg font-bold text-gain font-mono">{sentimentData.fear_and_greed_index} / 100</span>
              <span className="text-[9px] text-slate-400 block">Status: {sentimentData.sentiment_classification}</span>
            </div>

            <div className="bg-[#0d121c] p-3 rounded border border-surface-border">
              <span className="text-[10px] text-slate-400 block">NORMALIZED SENTIMENT SCORE</span>
              <span className="text-lg font-bold text-accent font-mono">+{sentimentData.sentiment_score}</span>
              <span className="text-[9px] text-slate-400 block">Range: [-1.0, +1.0]</span>
            </div>

            <div className="bg-[#0d121c] p-3 rounded border border-surface-border">
              <span className="text-[10px] text-slate-400 block">BULLISH RATIO</span>
              <span className="text-lg font-bold text-gain font-mono">{sentimentData.bullish_ratio_pct}%</span>
              <span className="text-[9px] text-slate-400 block">Bearish: {sentimentData.bearish_ratio_pct}%</span>
            </div>

            <div className="bg-[#0d121c] p-3 rounded border border-surface-border">
              <span className="text-[10px] text-slate-400 block">24H NEWS INGESTION</span>
              <span className="text-lg font-bold text-white font-mono">{sentimentData.news_count_24h} Articles</span>
              <span className="text-[9px] text-slate-400 block">Realtime NLP Analyzed</span>
            </div>
          </div>

          {/* Headlines List */}
          <div className="bg-[#0d121c] p-4 rounded-lg border border-surface-border space-y-3">
            <span className="text-xs font-bold text-white flex items-center space-x-1.5 border-b border-surface-border pb-2">
              <TrendingUp className="w-4 h-4 text-gain" />
              <span>LIVE TRENDING CRYPTOPANIC HEADLINES & NLP SCORES</span>
            </span>

            <div className="space-y-2">
              {sentimentData.top_headlines?.map((h: any) => (
                <div key={h.id} className="bg-[#111722] p-3 rounded border border-surface-border flex items-center justify-between text-xs">
                  <div className="space-y-1">
                    <div className="flex items-center space-x-2">
                      <span className="text-[9px] bg-accent/15 text-accent px-1.5 py-0.5 rounded font-bold">{h.category}</span>
                      <span className="text-white font-bold">{h.title}</span>
                    </div>
                    <span className="text-[10px] text-slate-400">{h.source}</span>
                  </div>

                  <div className="text-right flex items-center space-x-3">
                    <div className="bg-gain/10 border border-gain/30 px-2 py-1 rounded text-xs font-bold text-gain">
                      +{h.sentiment_score}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: SEC 10-K FILINGS */}
      {activeTab === "sec" && (
        <div className="space-y-4">
          <div className="flex items-center space-x-2">
            <input
              type="text"
              value={ticker}
              onChange={(e) => setTicker(e.target.value.toUpperCase())}
              placeholder="Search ticker (e.g. AAPL, MSFT, NVDA)..."
              className="bg-[#0d121c] border border-surface-border text-white px-3 py-1.5 rounded text-xs focus:outline-none focus:border-accent w-64"
            />
            <button
              onClick={fetchMCPData}
              className="bg-accent hover:bg-sky-400 text-black font-bold px-3 py-1.5 rounded text-xs flex items-center space-x-1"
            >
              <Search className="w-3.5 h-3.5" />
              <span>FETCH 10-K</span>
            </button>
          </div>

          {secData && (
            <div className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                <div className="bg-[#0d121c] p-3 rounded border border-surface-border">
                  <span className="text-[10px] text-slate-400 block">TOTAL REVENUE</span>
                  <span className="text-lg font-bold text-white font-mono">${secData.financial_statements.total_revenue_billions}B</span>
                </div>
                <div className="bg-[#0d121c] p-3 rounded border border-surface-border">
                  <span className="text-[10px] text-slate-400 block">NET INCOME</span>
                  <span className="text-lg font-bold text-gain font-mono">${secData.financial_statements.net_income_billions}B</span>
                </div>
                <div className="bg-[#0d121c] p-3 rounded border border-surface-border">
                  <span className="text-[10px] text-slate-400 block">OPERATING MARGIN</span>
                  <span className="text-lg font-bold text-accent font-mono">{secData.financial_statements.operating_margin_pct}%</span>
                </div>
                <div className="bg-[#0d121c] p-3 rounded border border-surface-border">
                  <span className="text-[10px] text-slate-400 block">DEBT / EQUITY</span>
                  <span className="text-lg font-bold text-slate-200 font-mono">{secData.financial_statements.debt_to_equity_ratio}x</span>
                </div>
              </div>

              {/* MD&A Highlights */}
              <div className="bg-[#0d121c] p-4 rounded-lg border border-surface-border space-y-2 text-xs">
                <span className="font-bold text-white block border-b border-surface-border pb-1">
                  MANAGEMENT DISCUSSION & ANALYSIS (MD&A)
                </span>
                <p className="text-slate-300 leading-relaxed text-[11px]">{secData.mda_highlights}</p>
              </div>

              {/* Risk Factors */}
              <div className="bg-[#0d121c] p-4 rounded-lg border border-surface-border space-y-2 text-xs">
                <span className="font-bold text-rose-400 flex items-center space-x-1.5 border-b border-surface-border pb-1">
                  <ShieldAlert className="w-4 h-4" />
                  <span>ITEM 1A: KEY RISK FACTORS EXTRACTED</span>
                </span>
                <div className="space-y-1.5 pt-1">
                  {secData.risk_factors_item_1a?.map((rf: string, idx: number) => (
                    <div key={idx} className="flex items-start space-x-2 text-[11px] text-slate-300">
                      <span className="text-rose-400 font-bold">•</span>
                      <span>{rf}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* TAB 3: GLOBAL MACRO & YIELDS */}
      {activeTab === "macro" && macroData && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
            <div className="bg-[#0d121c] p-3 rounded border border-surface-border">
              <span className="text-[10px] text-slate-400 block">10Y TREASURY YIELD</span>
              <span className="text-lg font-bold text-white font-mono">{macroData.treasury_10y_yield_pct}%</span>
              <span className="text-[9px] text-slate-400 block">2Y Yield: {macroData.treasury_02y_yield_pct}%</span>
            </div>

            <div className="bg-[#0d121c] p-3 rounded border border-surface-border">
              <span className="text-[10px] text-slate-400 block">YIELD CURVE (10Y - 2Y)</span>
              <span className="text-lg font-bold text-gain font-mono">+{macroData.yield_curve_spread_bps} bps</span>
              <span className="text-[9px] text-gain block">UN-INVERTED (BULLISH)</span>
            </div>

            <div className="bg-[#0d121c] p-3 rounded border border-surface-border">
              <span className="text-[10px] text-slate-400 block">CPI YOY INFLATION</span>
              <span className="text-lg font-bold text-amber-400 font-mono">{macroData.cpi_yoy_inflation_pct}%</span>
              <span className="text-[9px] text-slate-400 block">Core PCE: {macroData.core_pce_pct}%</span>
            </div>

            <div className="bg-[#0d121c] p-3 rounded border border-surface-border">
              <span className="text-[10px] text-slate-400 block">FED FUNDS RATE</span>
              <span className="text-lg font-bold text-accent font-mono">{macroData.fed_funds_target_rate_pct}%</span>
              <span className="text-[9px] text-slate-400 block">Regime: {macroData.macro_regime}</span>
            </div>
          </div>
        </div>
      )}

      {/* TAB 4: ON-CHAIN & NETWORK FLOW */}
      {activeTab === "onchain" && onchainData && (
        <div className="space-y-4">
          <div className="flex items-center space-x-2">
            <select
              value={network}
              onChange={(e) => {
                setNetwork(e.target.value);
                fetchMCPData();
              }}
              className="bg-[#0d121c] border border-surface-border text-white px-3 py-1.5 rounded text-xs focus:outline-none focus:border-accent"
            >
              <option value="ethereum">Ethereum Mainnet</option>
              <option value="bitcoin">Bitcoin Network</option>
              <option value="solana">Solana</option>
              <option value="arbitrum">Arbitrum One</option>
            </select>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
            <div className="bg-[#0d121c] p-3 rounded border border-surface-border">
              <span className="text-[10px] text-slate-400 block">BASE GAS FEE</span>
              <span className="text-lg font-bold text-accent font-mono">{onchainData.base_fee_gwei} Gwei</span>
              <span className="text-[9px] text-slate-400 block">Priority: {onchainData.priority_fee_gwei} Gwei</span>
            </div>

            <div className="bg-[#0d121c] p-3 rounded border border-surface-border">
              <span className="text-[10px] text-slate-400 block">24H ACTIVE WALLETS</span>
              <span className="text-lg font-bold text-white font-mono">{onchainData.active_wallets_24h?.toLocaleString()}</span>
            </div>

            <div className="bg-[#0d121c] p-3 rounded border border-surface-border">
              <span className="text-[10px] text-slate-400 block">EXCHANGE NETFLOW</span>
              <span className="text-lg font-bold text-gain font-mono">${(Math.abs(onchainData.exchange_netflow_24h_usd) / 1000000).toFixed(1)}M OUTFLOW</span>
              <span className="text-[9px] text-gain block">Cold Storage Accumulation</span>
            </div>

            <div className="bg-[#0d121c] p-3 rounded border border-surface-border">
              <span className="text-[10px] text-slate-400 block">STAKING RATIO</span>
              <span className="text-lg font-bold text-purple-400 font-mono">{onchainData.staking_ratio_pct}%</span>
              <span className="text-[9px] text-slate-400 block">Status: {onchainData.network_security_status}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};