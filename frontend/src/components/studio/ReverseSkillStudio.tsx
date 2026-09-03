import React, { useState } from "react";
import { Code, FileSpreadsheet, Play, Rocket, CheckCircle2, Layers, Cpu, Copy, Check, BarChart3 } from "lucide-react";
import { apiUrl } from "../../lib/backend";

const SAMPLE_PINE_TEMPLATES = {
  rsi_reversal: `//@version=5
strategy("RSI Momentum Reversal", overlay=true)
length = 14
rsi_val = ta.rsi(close, length)
ema_fast = ta.ema(close, 20)
ema_slow = ta.ema(close, 50)

longCondition = ta.crossover(ema_fast, ema_slow) and rsi_val < 35
if (longCondition)
    strategy.entry("Long", strategy.long)

strategy.exit("TP/SL", "Long", loss=40, profit=100)`,

  ema_cross: `//@version=5
strategy("EMA Trend Crossover", overlay=true)
fast_len = 9
slow_len = 21
ema_fast = ta.ema(close, fast_len)
ema_slow = ta.ema(close, slow_len)
atr_val = ta.atr(14)

if (ta.crossover(ema_fast, ema_slow))
    strategy.entry("TrendLong", strategy.long)

strategy.exit("Bracket", "TrendLong", loss=50, profit=125)`,

  breakout_bb: `//@version=5
strategy("Bollinger Breakout Expansion", overlay=true)
len = 20
mult = 2.0
bb = ta.bb(close, len, mult)
rsi_val = ta.rsi(close, 14)

if (ta.crossover(close, ema_fast) and rsi_val > 55)
    strategy.entry("Breakout", strategy.long)

strategy.exit("ExitBB", "Breakout", loss=35, profit=95)`
};

const SAMPLE_CSV = `timestamp,symbol,side,entry_price,exit_price,qty,pnl,duration
2026-02-15T10:00:00,BTCUSDT,BUY,64000,64800,1.0,800.0,1800
2026-02-15T11:00:00,BTCUSDT,BUY,64800,64500,1.0,-300.0,900
2026-02-15T12:00:00,BTCUSDT,BUY,64600,65500,1.0,900.0,2400
2026-02-15T13:00:00,BTCUSDT,SELL,65400,64900,1.0,500.0,1200
2026-02-15T14:00:00,BTCUSDT,BUY,64900,64650,1.0,-250.0,750
2026-02-15T15:00:00,BTCUSDT,BUY,64700,65800,1.0,1100.0,3600`;

export const ReverseSkillStudio: React.FC = () => {
  const [inputMode, setInputMode] = useState<"pinescript" | "csv">("pinescript");
  const [pineCode, setPineCode] = useState<string>(SAMPLE_PINE_TEMPLATES.rsi_reversal);
  const [csvContent, setCsvContent] = useState<string>(SAMPLE_CSV);

  const [outputTab, setOutputTab] = useState<"dsl" | "python" | "metrics">("dsl");
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [transpileResult, setTranspileResult] = useState<any>(null);
  const [csvResult, setCsvResult] = useState<any>(null);
  const [deployMsg, setDeployMsg] = useState<string | null>(null);
  const [isCopied, setIsCopied] = useState<boolean>(false);

  const handleTranspile = async () => {
    setIsProcessing(true);
    setDeployMsg(null);
    try {
      if (inputMode === "pinescript") {
        const res = await fetch(apiUrl("/api/v1/reverse-skill/transpile-pinescript"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ pine_code: pineCode }),
        });
        const data = await res.json();
        setTranspileResult(data);
        setOutputTab("dsl");
      } else {
        const res = await fetch(apiUrl("/api/v1/reverse-skill/analyze-csv"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ csv_content: csvContent }),
        });
        const data = await res.json();
        setCsvResult(data);
        setOutputTab("metrics");
      }
    } catch (e) {
      console.error(e);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleDeployAgent = async () => {
    try {
      const agentName = transpileResult?.strategy_name || "Synthesized_Quant_Agent";
      const config = transpileResult?.ruleset || csvResult?.signature || {};

      const res = await fetch(apiUrl("/api/v1/reverse-skill/deploy-agent"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          agent_name: agentName,
          strategy_config: config,
          initial_capital: 50000.0,
        }),
      });
      const data = await res.json();
      setDeployMsg(`Agent '${data.agent_name}' [${data.agent_id}] successfully deployed into live AI Swarm!`);
      setTimeout(() => setDeployMsg(null), 5000);
    } catch (e) {
      console.error(e);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setIsCopied(true);
    setTimeout(() => setIsCopied(false), 2000);
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-[#0b0e14] overflow-hidden p-4 select-none font-mono space-y-4 text-slate-100">
      {/* Header */}
      <div className="pb-3 border-b border-surface-border flex items-center justify-between">
        <div>
          <div className="flex items-center space-x-2">
            <Cpu className="w-5 h-5 text-accent" />
            <h2 className="text-sm font-bold text-white uppercase tracking-wider">
              REVERSE-SKILL QUANT STRATEGY TRANSPILER & SYNTHESIS STUDIO
            </h2>
          </div>
          <p className="text-xs text-slate-400">
            Automated Pine Script AST Transpilation & Statistical CSV Execution Reverse-Engineering (zhaoxuya520/reverse-skill)
          </p>
        </div>

        <div className="flex items-center space-x-3">
          {(transpileResult || csvResult) && (
            <button
              onClick={handleDeployAgent}
              className="flex items-center space-x-1.5 bg-gain hover:bg-emerald-400 text-black font-bold px-3 py-1.5 rounded text-xs transition shadow"
            >
              <Rocket className="w-3.5 h-3.5" />
              <span>DEPLOY TO AI SWARM</span>
            </button>
          )}

          <button
            onClick={handleTranspile}
            disabled={isProcessing}
            className="flex items-center space-x-1.5 bg-accent hover:bg-sky-400 text-black font-bold px-4 py-1.5 rounded text-xs transition shadow"
          >
            <Play className={`w-3.5 h-3.5 ${isProcessing ? "animate-spin" : ""}`} />
            <span>{isProcessing ? "TRANSPILING RULES..." : "TRANSPILER & EXTRACT STRATEGY"}</span>
          </button>
        </div>
      </div>

      {/* Deploy Alert Banner */}
      {deployMsg && (
        <div className="bg-gain/10 border border-gain/30 p-3 rounded-lg flex items-center space-x-2 text-gain text-xs">
          <CheckCircle2 className="w-4 h-4 text-gain" />
          <span>{deployMsg}</span>
        </div>
      )}

      {/* Dual Pane Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 flex-1 overflow-hidden">
        {/* LEFT PANE: INPUT SOURCE */}
        <div className="bg-[#0d121c] p-4 rounded-lg border border-surface-border flex flex-col space-y-3 overflow-hidden">
          <div className="flex items-center justify-between border-b border-surface-border pb-2">
            <div className="flex items-center space-x-2">
              <button
                onClick={() => setInputMode("pinescript")}
                className={`flex items-center space-x-1.5 px-3 py-1 rounded text-xs font-bold transition ${
                  inputMode === "pinescript"
                    ? "bg-accent/15 text-accent border border-accent/30"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                <Code className="w-3.5 h-3.5" />
                <span>TradingView Pine Script (v5)</span>
              </button>

              <button
                onClick={() => setInputMode("csv")}
                className={`flex items-center space-x-1.5 px-3 py-1 rounded text-xs font-bold transition ${
                  inputMode === "csv"
                    ? "bg-accent/15 text-accent border border-accent/30"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                <FileSpreadsheet className="w-3.5 h-3.5" />
                <span>CSV Trade History Logs</span>
              </button>
            </div>

            {inputMode === "pinescript" && (
              <select
                onChange={(e) => setPineCode(SAMPLE_PINE_TEMPLATES[e.target.value as keyof typeof SAMPLE_PINE_TEMPLATES])}
                className="bg-[#111722] border border-surface-border text-white text-[10px] px-2 py-1 rounded focus:outline-none focus:border-accent"
              >
                <option value="rsi_reversal">Template: RSI Reversal</option>
                <option value="ema_cross">Template: EMA Crossover</option>
                <option value="breakout_bb">Template: Bollinger Breakout</option>
              </select>
            )}
          </div>

          {inputMode === "pinescript" ? (
            <textarea
              value={pineCode}
              onChange={(e) => setPineCode(e.target.value)}
              className="flex-1 w-full bg-[#090d14] border border-surface-border text-slate-200 text-xs font-mono p-3 rounded focus:outline-none focus:border-accent resize-none leading-relaxed"
              spellCheck={false}
            />
          ) : (
            <textarea
              value={csvContent}
              onChange={(e) => setCsvContent(e.target.value)}
              placeholder="Paste trade logs CSV (timestamp, symbol, side, entry_price, exit_price, qty, pnl)..."
              className="flex-1 w-full bg-[#090d14] border border-surface-border text-slate-200 text-xs font-mono p-3 rounded focus:outline-none focus:border-accent resize-none leading-relaxed"
              spellCheck={false}
            />
          )}
        </div>

        {/* RIGHT PANE: SYNTHESIZED OUTPUT */}
        <div className="bg-[#0d121c] p-4 rounded-lg border border-surface-border flex flex-col space-y-3 overflow-hidden">
          <div className="flex items-center justify-between border-b border-surface-border pb-2">
            <div className="flex items-center space-x-2">
              <button
                onClick={() => setOutputTab("dsl")}
                className={`flex items-center space-x-1.5 px-3 py-1 rounded text-xs font-bold transition ${
                  outputTab === "dsl"
                    ? "bg-accent/15 text-accent border border-accent/30"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                <Layers className="w-3.5 h-3.5" />
                <span>Kuantra Swarm DSL Ruleset</span>
              </button>

              <button
                onClick={() => setOutputTab("python")}
                className={`flex items-center space-x-1.5 px-3 py-1 rounded text-xs font-bold transition ${
                  outputTab === "python"
                    ? "bg-accent/15 text-accent border border-accent/30"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                <Code className="w-3.5 h-3.5" />
                <span>Native Python Agent Code</span>
              </button>

              <button
                onClick={() => setOutputTab("metrics")}
                className={`flex items-center space-x-1.5 px-3 py-1 rounded text-xs font-bold transition ${
                  outputTab === "metrics"
                    ? "bg-accent/15 text-accent border border-accent/30"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                <BarChart3 className="w-3.5 h-3.5" />
                <span>Statistical Signature</span>
              </button>
            </div>

            <button
              onClick={() => {
                const text =
                  outputTab === "dsl"
                    ? JSON.stringify(transpileResult?.ruleset || {}, null, 2)
                    : outputTab === "python"
                    ? transpileResult?.python_agent_code || ""
                    : JSON.stringify(csvResult?.signature || {}, null, 2);
                copyToClipboard(text);
              }}
              className="text-[10px] text-slate-400 hover:text-white flex items-center space-x-1 p-1 bg-[#111722] rounded border border-surface-border"
              title="Copy Output"
            >
              {isCopied ? <Check className="w-3 h-3 text-gain" /> : <Copy className="w-3 h-3" />}
              <span>{isCopied ? "COPIED" : "COPY"}</span>
            </button>
          </div>

          <div className="flex-1 overflow-y-auto">
            {outputTab === "dsl" && (
              <pre className="bg-[#090d14] p-3 rounded border border-surface-border text-xs text-accent font-mono overflow-x-auto h-full leading-relaxed">
                {transpileResult?.ruleset
                  ? JSON.stringify(transpileResult.ruleset, null, 2)
                  : "// Execute 'Transpile & Extract Strategy' to view synthesized Kuantra DSL rules."}
              </pre>
            )}

            {outputTab === "python" && (
              <pre className="bg-[#090d14] p-3 rounded border border-surface-border text-xs text-slate-300 font-mono overflow-x-auto h-full leading-relaxed">
                {transpileResult?.python_agent_code ||
                  "# Python execution agent code will be dynamically generated upon transpilation."}
              </pre>
            )}

            {outputTab === "metrics" && csvResult && (
              <div className="space-y-3">
                <div className="bg-[#111722] p-3 rounded-lg border border-surface-border space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] text-slate-400">INFERRED EXECUTION ARCHETYPE</span>
                    <span className="text-xs font-bold text-accent bg-accent/15 px-2 py-0.5 rounded">
                      {csvResult.archetype}
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-300">{csvResult.signature?.statistical_rationale}</p>
                </div>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
                  <div className="bg-[#111722] p-2.5 rounded border border-surface-border">
                    <span className="text-[9px] text-slate-400 block">WIN RATE</span>
                    <span className="text-sm font-bold text-gain">{csvResult.signature?.metrics?.win_rate_pct}%</span>
                  </div>
                  <div className="bg-[#111722] p-2.5 rounded border border-surface-border">
                    <span className="text-[9px] text-slate-400 block">PROFIT FACTOR</span>
                    <span className="text-sm font-bold text-white">{csvResult.signature?.metrics?.profit_factor}</span>
                  </div>
                  <div className="bg-[#111722] p-2.5 rounded border border-surface-border">
                    <span className="text-[9px] text-slate-400 block">SHARPE RATIO</span>
                    <span className="text-sm font-bold text-accent">{csvResult.signature?.metrics?.sharpe_ratio}</span>
                  </div>
                  <div className="bg-[#111722] p-2.5 rounded border border-surface-border">
                    <span className="text-[9px] text-slate-400 block">TRADES ANALYZED</span>
                    <span className="text-sm font-bold text-slate-300">{csvResult.signature?.metrics?.total_trades_analyzed}</span>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};