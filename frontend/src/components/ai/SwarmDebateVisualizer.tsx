import React, { useState } from "react";
import { Bot, MessageSquare, RefreshCw } from "lucide-react";

interface AgentVote {
  agent: string;
  vote: string;
  confidence: number;
  thesis: string;
  risk_score?: number;
  rr_ratio?: number;
}

interface SwarmResult {
  consensus_status: string;
  is_approved: boolean;
  final_confidence: number;
  risk_agent_veto: boolean;
  reason: string;
  debate_transcript: Array<{ speaker: string; message: string; vote: string }>;
  agent_votes: Record<string, AgentVote>;
}

export const SwarmDebateVisualizer: React.FC = () => {
  const [symbol, setSymbol] = useState<string>("BTCUSDT");
  const [side, setSide] = useState<string>("BUY");
  const [price, setPrice] = useState<number>(64800.0);
  const [sl, setSl] = useState<number>(63900.0);
  const [tp, setTp] = useState<number>(67000.0);

  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [result, setResult] = useState<SwarmResult | null>(null);

  const runDebate = async () => {
    setIsLoading(true);
    try {
      const res = await fetch("http://127.0.0.1:8000/api/v1/ai/swarm/debate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          symbol,
          side,
          price,
          stop_loss: sl,
          take_profit: tp,
          timeframe: "15m",
        }),
      });
      const data = await res.json();
      setResult(data);
    } catch (e) {
      console.error(e);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-[#0b0e14] overflow-y-auto p-4 select-none font-mono space-y-4">
      {/* Header */}
      <div className="pb-3 border-b border-surface-border flex items-center justify-between">
        <div>
          <div className="flex items-center space-x-2">
            <Bot className="w-5 h-5 text-accent" />
            <h2 className="text-sm font-bold text-white uppercase tracking-wider">
              MULTI-AGENT SWARM CONSENSUS DEBATE
            </h2>
          </div>
          <p className="text-xs text-slate-400">
            Tri-Agent Structured Round-Robin (MacroAgent, QuantAgent, RiskAgent) with VETO Authority
          </p>
        </div>

        <button
          onClick={runDebate}
          disabled={isLoading}
          className="flex items-center space-x-2 bg-accent hover:bg-sky-400 text-black font-bold px-4 py-2 rounded text-xs transition shadow-md"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />
          <span>{isLoading ? "DEBATING..." : "START SWARM DEBATE"}</span>
        </button>
      </div>

      {/* Trade Proposal Input Strip */}
      <div className="bg-[#0d121c] p-3 rounded-lg border border-surface-border grid grid-cols-2 md:grid-cols-5 gap-3 text-xs">
        <div>
          <span className="text-[10px] text-slate-400 block mb-1">SYMBOL</span>
          <input
            type="text"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            className="w-full bg-[#111722] border border-surface-border text-white px-2 py-1 rounded focus:outline-none focus:border-accent"
          />
        </div>
        <div>
          <span className="text-[10px] text-slate-400 block mb-1">SIDE</span>
          <select
            value={side}
            onChange={(e) => setSide(e.target.value)}
            className="w-full bg-[#111722] border border-surface-border text-white px-2 py-1 rounded focus:outline-none focus:border-accent"
          >
            <option value="BUY">BUY / LONG</option>
            <option value="SELL">SELL / SHORT</option>
          </select>
        </div>
        <div>
          <span className="text-[10px] text-slate-400 block mb-1">ENTRY PRICE</span>
          <input
            type="number"
            value={price}
            onChange={(e) => setPrice(parseFloat(e.target.value))}
            className="w-full bg-[#111722] border border-surface-border text-white px-2 py-1 rounded focus:outline-none focus:border-accent"
          />
        </div>
        <div>
          <span className="text-[10px] text-slate-400 block mb-1">STOP LOSS</span>
          <input
            type="number"
            value={sl}
            onChange={(e) => setSl(parseFloat(e.target.value))}
            className="w-full bg-[#111722] border border-surface-border text-white px-2 py-1 rounded focus:outline-none focus:border-accent"
          />
        </div>
        <div>
          <span className="text-[10px] text-slate-400 block mb-1">TAKE PROFIT</span>
          <input
            type="number"
            value={tp}
            onChange={(e) => setTp(parseFloat(e.target.value))}
            className="w-full bg-[#111722] border border-surface-border text-white px-2 py-1 rounded focus:outline-none focus:border-accent"
          />
        </div>
      </div>

      {/* Consensus Result Card */}
      {result && (
        <div className={`p-4 rounded-lg border flex items-center justify-between ${
          result.consensus_status === "APPROVED"
            ? "bg-gain/10 border-gain/40 text-gain"
            : result.consensus_status === "VETOED"
            ? "bg-rose-500/10 border-rose-500 text-rose-300"
            : "bg-amber-500/10 border-amber-500 text-amber-200"
        }`}>
          <div className="space-y-1">
            <div className="flex items-center space-x-2">
              <span className="text-xs font-bold text-white uppercase">SWARM CONSENSUS VERDICT:</span>
              <span className={`text-xs px-2 py-0.5 rounded font-black ${
                result.consensus_status === "APPROVED"
                  ? "bg-gain text-black"
                  : result.consensus_status === "VETOED"
                  ? "bg-rose-500 text-white"
                  : "bg-amber-500 text-black"
              }`}>
                {result.consensus_status}
              </span>
            </div>
            <p className="text-xs text-slate-300">{result.reason}</p>
          </div>

          <div className="text-right">
            <span className="text-[10px] text-slate-400 block">CONFIDENCE</span>
            <span className="text-xl font-bold text-white">{Math.round(result.final_confidence * 100)}%</span>
          </div>
        </div>
      )}

      {/* 3 Agent Cards Grid */}
      {result && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {Object.entries(result.agent_votes).map(([agentName, voteData]) => (
            <div key={agentName} className="bg-[#0d121c] p-4 rounded-lg border border-surface-border space-y-3">
              <div className="flex items-center justify-between border-b border-surface-border pb-2">
                <span className="font-bold text-white text-xs">{agentName}</span>
                <span className={`text-[10px] px-2 py-0.5 rounded font-bold ${
                  voteData.vote === "APPROVE"
                    ? "bg-gain/20 text-gain border border-gain/30"
                    : voteData.vote === "VETO"
                    ? "bg-rose-500/20 text-rose-400 border border-rose-500/40"
                    : "bg-amber-500/20 text-amber-300 border border-amber-500/30"
                }`}>
                  {voteData.vote}
                </span>
              </div>
              <p className="text-[11px] text-slate-300">{voteData.thesis}</p>
              <div className="flex items-center justify-between text-[10px] text-slate-500 pt-1">
                <span>Confidence: <strong className="text-white">{Math.round(voteData.confidence * 100)}%</strong></span>
                {voteData.rr_ratio && <span>R:R: <strong className="text-accent">{voteData.rr_ratio}R</strong></span>}
                {voteData.risk_score != null && <span>Risk: <strong className="text-rose-400">{voteData.risk_score}/100</strong></span>}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Debate Round-Robin Stream */}
      {result && (
        <div className="bg-[#0d121c] p-4 rounded-lg border border-surface-border space-y-3">
          <div className="flex items-center space-x-2 text-white font-bold text-xs">
            <MessageSquare className="w-4 h-4 text-purple-400" />
            <span>ROUND-ROBIN DEBATE TRANSCRIPT</span>
          </div>

          <div className="space-y-2">
            {result.debate_transcript.map((msg, idx) => (
              <div key={idx} className="bg-[#111722] p-2.5 rounded border border-surface-border text-xs flex items-start space-x-3">
                <span className="bg-accent/15 text-accent text-[10px] font-bold px-2 py-0.5 rounded flex-shrink-0">
                  {msg.speaker}
                </span>
                <p className="text-slate-300 flex-1 text-[11px]">{msg.message}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};