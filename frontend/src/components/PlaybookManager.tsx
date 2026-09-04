import React, { useState, useEffect } from "react";
import { Playbook } from "../types";
import { BookOpen, CheckCircle2, XCircle, CheckSquare, Square } from "lucide-react";
import { apiFetch, apiUrl } from "../lib/backend";

export const PlaybookManager: React.FC = () => {
  const [playbooks, setPlaybooks] = useState<Playbook[]>([]);
  const [selectedPlaybook, setSelectedPlaybook] = useState<Playbook | null>(null);
  const [auditTradeId, setAuditTradeId] = useState<string>("TRD-1001");
  const [checkedRules, setCheckedRules] = useState<string[]>([]);
  const [auditResult, setAuditResult] = useState<any>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const fetchPlaybooks = () => {
    setIsLoading(true);
    apiFetch(apiUrl("/api/v1/playbooks"))
      .then((res) => res.json())
      .then((data: Playbook[]) => {
        setPlaybooks(data);
        if (data.length > 0 && !selectedPlaybook) {
          setSelectedPlaybook(data[0]);
          setCheckedRules(data[0].rules.map((r) => r.id));
        }
        setIsLoading(false);
      })
      .catch(() => {
        setIsLoading(false);
      });
  };

  useEffect(() => {
    fetchPlaybooks();
  }, []);

  const handleSelectPlaybook = (pb: Playbook) => {
    setSelectedPlaybook(pb);
    setCheckedRules(pb.rules.map((r) => r.id));
    setAuditResult(null);
  };

  const toggleRuleCheck = (ruleId: string) => {
    if (checkedRules.includes(ruleId)) {
      setCheckedRules(checkedRules.filter((id) => id !== ruleId));
    } else {
      setCheckedRules([...checkedRules, ruleId]);
    }
  };

  const handleAudit = async () => {
    if (!selectedPlaybook) return;
    try {
      const res = await apiFetch(apiUrl("/api/v1/playbooks/audit"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          trade_id: auditTradeId,
          playbook_id: selectedPlaybook.id,
          checked_rule_ids: checkedRules,
        }),
      });
      const data = await res.json();
      setAuditResult(data);
    } catch (e) {
      console.error(e);
    }
  };

  if (isLoading) {
    return <div className="p-8 text-center text-slate-400 font-mono">Loading Strategy Playbooks...</div>;
  }

  return (
    <div className="flex-1 flex flex-col h-full bg-[#0b0e14] overflow-y-auto p-4 select-none font-mono space-y-4">
      {/* Header */}
      <div className="pb-3 border-b border-surface-border flex items-center justify-between">
        <div>
          <h2 className="text-base font-bold text-white flex items-center space-x-2">
            <BookOpen className="w-4 h-4 text-accent" />
            <span>STRATEGY PLAYBOOK & DISCIPLINE SCORING ENGINE</span>
          </h2>
          <p className="text-xs text-slate-400">
            Pre-Execution Checklists, Rule Compliance Tracking & Setup Edge Analytics
          </p>
        </div>
      </div>

      {/* Main Playbook Selection & Strategy Detail Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Playbook List Sidebar */}
        <div className="space-y-3">
          <div className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center justify-between">
            <span>Playbook Strategies ({playbooks.length})</span>
          </div>

          <div className="space-y-2">
            {playbooks.map((pb) => {
              const isSelected = selectedPlaybook?.id === pb.id;
              return (
                <div
                  key={pb.id}
                  onClick={() => handleSelectPlaybook(pb)}
                  className={`p-3 rounded-lg border cursor-pointer transition ${
                    isSelected
                      ? "bg-[#111722] border-accent"
                      : "bg-[#0d121c] border-surface-border hover:border-slate-600"
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-bold text-white text-xs">{pb.title}</span>
                    <span className="text-[10px] text-accent px-1.5 py-0.2 bg-accent/10 rounded">
                      {pb.id}
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-400 line-clamp-2 mb-2">{pb.description}</p>
                  <div className="flex items-center justify-between text-[10px] text-slate-400 border-t border-surface-border/50 pt-1.5">
                    <span>Target Win: <strong className="text-gain">{pb.win_rate_target}%</strong></span>
                    <span>Target R:R: <strong className="text-accent">{pb.rr_target}R</strong></span>
                    <span>Rules: <strong className="text-white">{pb.rules.length}</strong></span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Selected Strategy Audit & Performance */}
        {selectedPlaybook && (
          <div className="lg:col-span-2 space-y-4">
            {/* Strategy Header & Targets */}
            <div className="bg-[#0d121c] p-4 rounded-lg border border-surface-border space-y-3">
              <div className="flex items-center justify-between border-b border-surface-border pb-2">
                <div>
                  <h3 className="text-sm font-bold text-white">{selectedPlaybook.title}</h3>
                  <p className="text-xs text-slate-400">{selectedPlaybook.description}</p>
                </div>
                <div className="text-right text-xs">
                  <span className="text-slate-400 block text-[10px]">REALIZED SQN</span>
                  <span className="text-base font-bold text-purple-400">
                    {selectedPlaybook.performance?.sqn || "2.45"}
                  </span>
                </div>
              </div>

              {/* Targets vs Realized */}
              <div className="grid grid-cols-4 gap-2 text-xs">
                <div className="bg-[#111722] p-2 rounded border border-surface-border">
                  <span className="text-[10px] text-slate-400 block">TARGET WIN RATE</span>
                  <span className="font-bold text-gain">{selectedPlaybook.win_rate_target}%</span>
                </div>
                <div className="bg-[#111722] p-2 rounded border border-surface-border">
                  <span className="text-[10px] text-slate-400 block">TARGET R:R</span>
                  <span className="font-bold text-accent">{selectedPlaybook.rr_target} R</span>
                </div>
                <div className="bg-[#111722] p-2 rounded border border-surface-border">
                  <span className="text-[10px] text-slate-400 block">AUDITED TRADES</span>
                  <span className="font-bold text-white">{selectedPlaybook.trades_count}</span>
                </div>
                <div className="bg-[#111722] p-2 rounded border border-surface-border">
                  <span className="text-[10px] text-slate-400 block">PROFIT FACTOR</span>
                  <span className="font-bold text-gain">
                    {selectedPlaybook.performance?.profit_factor || "2.80"}
                  </span>
                </div>
              </div>
            </div>

            {/* Interactive Rule Checklist & Discipline Audit */}
            <div className="bg-[#0d121c] p-4 rounded-lg border border-surface-border space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="text-xs font-bold text-white">STRATEGY CRITERIA CHECKLIST & DISCIPLINE AUDIT</h4>
                  <p className="text-[11px] text-slate-400">
                    Verify rules for trade execution. Mandatory rules require 100% adherence.
                  </p>
                </div>

                <div className="flex items-center space-x-2">
                  <span className="text-[11px] text-slate-400">Trade ID:</span>
                  <input
                    type="text"
                    value={auditTradeId}
                    onChange={(e) => setAuditTradeId(e.target.value)}
                    className="bg-[#111722] border border-surface-border px-2 py-0.5 rounded text-white text-xs w-28 focus:outline-none"
                  />
                  <button
                    onClick={handleAudit}
                    className="px-3 py-1 bg-accent hover:bg-sky-400 text-black font-bold rounded text-xs transition"
                  >
                    AUDIT TRADE
                  </button>
                </div>
              </div>

              {/* Rules List */}
              <div className="space-y-2 pt-1">
                {selectedPlaybook.rules.map((rule) => {
                  const isChecked = checkedRules.includes(rule.id);
                  return (
                    <div
                      key={rule.id}
                      onClick={() => toggleRuleCheck(rule.id)}
                      className={`p-2.5 rounded border flex items-center justify-between cursor-pointer transition ${
                        isChecked
                          ? "bg-[#111722] border-slate-600 text-slate-100"
                          : "bg-[#090d14] border-surface-border/60 text-slate-400"
                      }`}
                    >
                      <div className="flex items-center space-x-3 text-xs">
                        {isChecked ? (
                          <CheckSquare className="w-4 h-4 text-gain" />
                        ) : (
                          <Square className="w-4 h-4 text-slate-600" />
                        )}
                        <span className={isChecked ? "font-semibold text-white" : ""}>
                          {rule.rule_text}
                        </span>
                      </div>

                      <div className="flex items-center space-x-2">
                        {Boolean(rule.is_mandatory) && (
                          <span className="px-2 py-0.5 bg-rose-950/80 border border-loss/40 text-loss text-[10px] font-bold rounded">
                            MANDATORY
                          </span>
                        )}
                        <span className="text-[10px] text-slate-500 font-mono">
                          Weight: {rule.weight}x
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Audit Result Display */}
              {auditResult && (
                <div
                  className={`p-3 rounded-lg border flex items-center justify-between mt-3 ${
                    auditResult.mandatory_violation
                      ? "bg-rose-950/60 border-loss text-loss"
                      : "bg-emerald-950/60 border-gain text-gain"
                  }`}
                >
                  <div className="flex items-center space-x-3">
                    {auditResult.mandatory_violation ? (
                      <XCircle className="w-5 h-5 flex-shrink-0" />
                    ) : (
                      <CheckCircle2 className="w-5 h-5 flex-shrink-0" />
                    )}
                    <div>
                      <span className="font-bold text-xs block">
                        {auditResult.mandatory_violation
                          ? "DISCIPLINE WARNING: Mandatory Strategy Rules Violated!"
                          : "EXECUTION AUDIT PASSED: 100% Rule Compliance"}
                      </span>
                      <span className="text-[11px] opacity-90">
                        {auditResult.details.passed_rules} of {auditResult.details.total_rules} rules met.
                      </span>
                    </div>
                  </div>

                  <div className="text-right font-bold">
                    <span className="text-[10px] block opacity-80">DISCIPLINE SCORE</span>
                    <span className="text-lg">{auditResult.discipline_score}%</span>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};