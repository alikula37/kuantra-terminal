import React, { useState, useEffect } from "react";
import { AiAuditReportResponse, AiQueryResult } from "../types";
import { Bot, Sparkles, AlertTriangle, CheckCircle2, Search, ArrowRight } from "lucide-react";
import { useTranslation } from "../context/I18nContext";
import { apiUrl } from "../lib/backend";

export const AiCoachPanel: React.FC = () => {
  const { t } = useTranslation();
  const [report, setReport] = useState<AiAuditReportResponse | null>(null);
  const [queryText, setQueryText] = useState<string>("");
  const [queryResult, setQueryResult] = useState<AiQueryResult | null>(null);
  const [isQuerying, setIsQuerying] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const fetchReport = () => {
    setIsLoading(true);
    fetch(apiUrl("/api/v1/ai/audit-report"))
      .then((res) => res.json())
      .then((data: AiAuditReportResponse) => {
        setReport(data);
        setIsLoading(false);
      })
      .catch(() => {
        setIsLoading(false);
      });
  };

  useEffect(() => {
    fetchReport();
  }, []);

  const handleRunQuery = async (customPrompt?: string) => {
    const promptToSend = customPrompt || queryText;
    if (!promptToSend.trim()) return;

    setIsQuerying(true);
    try {
      const res = await fetch(apiUrl("/api/v1/ai/query"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: promptToSend }),
      });
      const data: AiQueryResult = await res.json();
      setQueryResult(data);
    } catch (err) {
      console.error(err);
    } finally {
      setIsQuerying(false);
    }
  };

  if (isLoading || !report) {
    return <div className="p-8 text-center text-slate-400 font-mono">{t("ai_coach.loading")}</div>;
  }

  const sampleQueries = [
    t("ai_coach.sample_worst_btc"),
    t("ai_coach.sample_high_r"),
    t("ai_coach.sample_breakdown"),
    t("ai_coach.sample_open_positions"),
  ];

  return (
    <div className="flex-1 flex flex-col h-full bg-[#0b0e14] overflow-y-auto p-4 select-none font-mono space-y-4">
      {/* Header */}
      <div className="pb-3 border-b border-surface-border flex items-center justify-between">
        <div>
          <h2 className="text-base font-bold text-white flex items-center space-x-2">
            <Bot className="w-4 h-4 text-accent" />
            <span>{t("ai_coach.title")}</span>
          </h2>
          <p className="text-xs text-slate-400">
            {t("ai_coach.subtitle")}
          </p>
        </div>
      </div>

      {/* Executive Report Card with Grade */}
      <div className="bg-[#0d121c] p-4 rounded-lg border border-surface-border space-y-3">
        <div className="flex items-center justify-between border-b border-surface-border pb-3">
          <div className="flex items-center space-x-3">
            <div className="w-12 h-12 rounded-lg bg-accent/15 border border-accent/40 flex items-center justify-center font-black text-2xl text-accent">
              {report.grade}
            </div>
            <div>
              <span className="text-xs text-slate-400 block font-semibold">{t("ai_coach.overall_grade")}</span>
              <span className="text-sm font-bold text-white">{t("ai_coach.institutional_quality")}</span>
            </div>
          </div>

          <div className="text-right text-xs">
            <span className="text-slate-400 block text-[10px]">{t("ai_coach.verified_sqn_wr")}</span>
            <span className="font-bold text-gain">
              {t("ai_coach.sqn_wr_val", { sqn: report.deterministic_context.sqn, wr: report.deterministic_context.win_rate_pct })}
            </span>
          </div>
        </div>

        <p className="text-xs text-slate-300 leading-relaxed bg-[#111722] p-3 rounded border border-surface-border">
          {report.executive_summary}
        </p>

        {/* Strengths & Risks Columns */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
          {/* Strengths */}
          <div className="bg-[#111722] p-3 rounded border border-surface-border space-y-2">
            <span className="font-bold text-gain flex items-center space-x-1.5 text-[11px]">
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>{t("ai_coach.quant_strengths")}</span>
            </span>
            <ul className="space-y-1.5 text-[11px] text-slate-300">
              {report.strengths.map((s, idx) => (
                <li key={idx} className="flex items-start space-x-1.5">
                  <span className="text-gain font-bold">•</span>
                  <span>{s}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* Critical Risks */}
          <div className="bg-[#111722] p-3 rounded border border-surface-border space-y-2">
            <span className="font-bold text-loss flex items-center space-x-1.5 text-[11px]">
              <AlertTriangle className="w-3.5 h-3.5" />
              <span>{t("ai_coach.critical_risks")}</span>
            </span>
            <ul className="space-y-1.5 text-[11px] text-slate-300">
              {report.critical_risks.map((r, idx) => (
                <li key={idx} className="flex items-start space-x-1.5">
                  <span className="text-loss font-bold">•</span>
                  <span>{r}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* Actionable Directives */}
        <div className="bg-[#111722] p-3 rounded border border-surface-border space-y-2 text-xs">
          <span className="font-bold text-accent flex items-center space-x-1.5 text-[11px]">
            <Sparkles className="w-3.5 h-3.5" />
            <span>{t("ai_coach.directives_title")}</span>
          </span>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
            {report.actionable_directives.map((d, idx) => (
              <div key={idx} className="bg-[#0d121c] p-2 rounded border border-surface-border text-[11px] text-slate-200">
                <span className="text-accent font-bold block mb-1">{t("ai_coach.directive_num", { num: idx + 1 })}</span>
                <span>{d}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Natural Language AI Query Engine */}
      <div className="bg-[#0d121c] p-4 rounded-lg border border-surface-border space-y-3">
        <div className="flex items-center space-x-2 border-b border-surface-border pb-2">
          <Search className="w-4 h-4 text-purple-400" />
          <div>
            <h3 className="text-xs font-bold text-white">{t("ai_coach.duckdb_title")}</h3>
            <p className="text-[10px] text-slate-400">
              {t("ai_coach.duckdb_desc")}
            </p>
          </div>
        </div>

        {/* Query Input Bar */}
        <div className="flex items-center space-x-2">
          <input
            type="text"
            value={queryText}
            onChange={(e) => setQueryText(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleRunQuery()}
            placeholder={t("ai_coach.query_placeholder")}
            className="flex-1 bg-[#111722] border border-surface-border px-3 py-2 rounded text-white text-xs focus:outline-none focus:border-accent"
          />
          <button
            onClick={() => handleRunQuery()}
            disabled={isQuerying}
            className="flex items-center space-x-1.5 bg-accent hover:bg-sky-400 text-black font-bold px-4 py-2 rounded text-xs transition"
          >
            <span>{isQuerying ? t("ai_coach.querying") : t("ai_coach.run_query")}</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* Quick Suggestion Chips */}
        <div className="flex flex-wrap items-center gap-1.5 text-[10px]">
          <span className="text-slate-500 mr-1">{t("ai_coach.suggestions")}</span>
          {sampleQueries.map((q, idx) => (
            <button
              key={idx}
              onClick={() => {
                setQueryText(q);
                handleRunQuery(q);
              }}
              className="bg-[#111722] hover:bg-[#1a2234] border border-surface-border px-2 py-0.5 rounded text-slate-300 transition"
            >
              {q}
            </button>
          ))}
        </div>

        {/* Query Result Table & Commentary */}
        {queryResult && (
          <div className="space-y-2 pt-2 border-t border-surface-border">
            <div className="bg-[#111722] p-2.5 rounded border border-surface-border text-xs flex items-center justify-between">
              <span className="text-slate-300">
                <strong className="text-accent">{t("ai_coach.ai_commentary")}</strong> {queryResult.ai_commentary}
              </span>
              <span className="text-[10px] text-slate-400 font-mono bg-black/40 px-2 py-0.5 rounded">
                SQL: {queryResult.sql.slice(0, 45)}...
              </span>
            </div>

            <div className="overflow-x-auto max-h-56 rounded border border-surface-border bg-[#090d14]">
              <table className="w-full text-left text-xs">
                <thead className="bg-[#0b0e14] text-[9px] text-slate-400 uppercase tracking-wider sticky top-0 border-b border-surface-border">
                  <tr>
                    {queryResult.columns.map((col) => (
                      <th key={col} className="px-3 py-2">
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-border/30 text-[11px]">
                  {queryResult.rows.length === 0 ? (
                    <tr>
                      <td colSpan={queryResult.columns.length} className="p-4 text-center text-slate-500">
                        {t("ai_coach.no_rows")}
                      </td>
                    </tr>
                  ) : (
                    queryResult.rows.map((row, rIdx) => (
                      <tr key={rIdx} className="hover:bg-[#111722]">
                        {queryResult.columns.map((col) => {
                          const val = row[col];
                          const isPnl = col.toLowerCase().includes("pnl");
                          const isNum = typeof val === "number";
                          return (
                            <td
                              key={col}
                              className={`px-3 py-1.5 ${
                                isPnl
                                  ? val >= 0
                                    ? "text-gain font-bold"
                                    : "text-loss font-bold"
                                  : "text-slate-200"
                              }`}
                            >
                              {isNum ? Number(val).toLocaleString() : String(val ?? "-")}
                            </td>
                          );
                        })}
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};