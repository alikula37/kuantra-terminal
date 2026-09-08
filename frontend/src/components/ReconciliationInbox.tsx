import React, { FormEvent, useEffect, useState } from "react";
import { Check, ClipboardCheck, X, XCircle } from "lucide-react";
import { useTranslation } from "../context/I18nContext";
import { apiFetch, apiUrl } from "../lib/backend";

type DecisionState = "UNRESOLVED" | "ACKNOWLEDGED" | "REJECTED" | "CORRECTED" | string;

interface ReconciliationInboxItem {
  review_id: string;
  status: DecisionState;
  decision: DecisionState;
  trade_id?: string | null;
  source: {
    event_id?: string;
    event_hash?: string;
    source_file_sha256?: string;
    source_row_number?: number;
    [key: string]: unknown;
  };
  discrepancy: { type?: string; [key: string]: unknown };
  coverage?: Record<string, unknown>;
  reconciliation?: Record<string, unknown>;
  decision_note?: string;
  [key: string]: unknown;
}

interface ReconciliationInboxProps {
  onClose?: () => void;
  onOpenEvidence?: (tradeId: string) => void;
}

const shortHash = (value: unknown): string => {
  const text = String(value || "");
  return text.length > 18 ? `${text.slice(0, 10)}…${text.slice(-6)}` : text || "—";
};

const displayValue = (value: unknown): string => {
  if (value === null || value === undefined || value === "") return "—";
  if (Array.isArray(value)) return value.join(", ");
  return String(value);
};

export const ReconciliationInbox: React.FC<ReconciliationInboxProps> = ({ onClose, onOpenEvidence }) => {
  const { t } = useTranslation();
  const [items, setItems] = useState<ReconciliationInboxItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pendingReviewId, setPendingReviewId] = useState<string | null>(null);
  const [correctionReviewId, setCorrectionReviewId] = useState<string | null>(null);
  const [correctionValues, setCorrectionValues] = useState<Record<string, string>>({});
  const [decisionNotes, setDecisionNotes] = useState<Record<string, string>>({});

  const loadItems = () => {
    setLoading(true);
    setError(null);
    apiFetch(apiUrl("/api/v1/reconciliation/inbox?status=UNRESOLVED&limit=100"))
      .then(async (response) => {
        if (!response.ok) throw new Error(t("reconciliation_inbox.error"));
        return response.json() as Promise<{ items?: ReconciliationInboxItem[] }>;
      })
      .then((payload) => setItems(Array.isArray(payload.items) ? payload.items : []))
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : t("reconciliation_inbox.error")))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadItems();
  }, []);

  const recordDecision = async (
    item: ReconciliationInboxItem,
    decision: "ACKNOWLEDGE" | "REJECT" | "CORRECT",
    correction?: Record<string, number | string>,
  ) => {
    setPendingReviewId(item.review_id);
    setError(null);
    try {
      const response = await apiFetch(apiUrl(`/api/v1/reconciliation/inbox/${encodeURIComponent(item.review_id)}/decision`), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          decision,
          note: decisionNotes[item.review_id] || undefined,
          correction,
        }),
      });
      if (!response.ok) throw new Error(t("reconciliation_inbox.decision_error"));
      const result = await response.json() as { status?: DecisionState; decision?: DecisionState };
      const state = result.status || result.decision || decision;
      setItems((current) => current.map((candidate) => (
        candidate.review_id === item.review_id
          ? { ...candidate, status: state, decision: state }
          : candidate
      )));
      setCorrectionReviewId(null);
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : t("reconciliation_inbox.decision_error"));
    } finally {
      setPendingReviewId(null);
    }
  };

  const submitCorrection = (event: FormEvent<HTMLFormElement>, item: ReconciliationInboxItem) => {
    event.preventDefault();
    const correction: Record<string, number | string> = {};
    for (const field of ["exit_price", "pnl", "commission"]) {
      const raw = correctionValues[`${item.review_id}:${field}`];
      if (raw && raw.trim() !== "") {
        const numeric = Number(raw);
        if (!Number.isFinite(numeric)) {
          setError(t("reconciliation_inbox.correction_invalid"));
          return;
        }
        correction[field] = numeric;
      }
    }
    if (Object.keys(correction).length === 0) {
      setError(t("reconciliation_inbox.correction_required"));
      return;
    }
    void recordDecision(item, "CORRECT", correction);
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-label={t("reconciliation_inbox.title")}>
      <div data-testid="reconciliation-inbox" className="w-full max-w-5xl max-h-[92vh] overflow-y-auto bg-[#0b0e14] border border-surface-border rounded-lg shadow-2xl font-mono">
        <div className="sticky top-0 z-10 bg-[#0d121c] border-b border-surface-border px-4 py-3 flex items-center justify-between">
          <div>
            <h2 className="text-sm font-bold text-white flex items-center gap-2"><ClipboardCheck className="w-4 h-4 text-accent" />{t("reconciliation_inbox.title")}</h2>
            <p className="text-[11px] text-slate-400 mt-1">{t("reconciliation_inbox.subtitle")}</p>
          </div>
          {onClose && <button type="button" onClick={onClose} aria-label={t("reconciliation_inbox.close")} className="p-1.5 text-slate-400 hover:text-white hover:bg-slate-800 rounded"><X className="w-4 h-4" /></button>}
        </div>

        {loading && <div className="p-8 text-center text-slate-400 text-xs">{t("reconciliation_inbox.loading")}</div>}
        {!loading && error && (
          <div className="m-4 p-4 rounded border border-loss/50 bg-loss/10 text-loss text-xs flex items-start gap-2">
            <XCircle className="w-4 h-4 shrink-0" /><span>{error}</span>
          </div>
        )}
        {!loading && !error && items.length === 0 && (
          <div data-testid="reconciliation-inbox-empty" className="p-10 text-center text-slate-400 text-xs">
            <Check className="w-8 h-8 text-slate-500 mx-auto mb-2" />
            {t("reconciliation_inbox.empty")}
          </div>
        )}

        {!loading && !error && items.length > 0 && (
          <div className="p-4 space-y-3">
            {items.map((item) => {
              const isUnresolved = item.status === "UNRESOLVED";
              const isCorrecting = correctionReviewId === item.review_id;
              return (
                <article key={item.review_id} data-testid={`reconciliation-item-${item.review_id}`} className="bg-[#0d121c] border border-amber-400/30 rounded-lg p-4 space-y-3">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <h3 className="text-xs font-bold text-white uppercase tracking-wide">{displayValue(item.discrepancy?.type)}</h3>
                      <p className="text-[10px] text-slate-500 mt-1">{item.review_id} · {item.trade_id || t("reconciliation_inbox.no_trade")}</p>
                    </div>
                    <span className={`px-2 py-1 rounded border text-[10px] font-bold ${isUnresolved ? "border-amber-400/40 bg-amber-400/10 text-amber-300" : "border-gain/40 bg-gain/10 text-gain"}`}>
                      {item.status}
                    </span>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-2 text-[10px] text-slate-400">
                    <div><span className="text-slate-500 block uppercase">{t("reconciliation_inbox.source")}</span>{shortHash(item.source?.source_file_sha256 || item.source?.event_hash)}</div>
                    <div><span className="text-slate-500 block uppercase">{t("reconciliation_inbox.source_row")}</span>{displayValue(item.discrepancy?.source_row_number || item.source?.source_row_number)}</div>
                    <div><span className="text-slate-500 block uppercase">{t("reconciliation_inbox.reconciliation")}</span>{displayValue(item.reconciliation?.status)}</div>
                  </div>

                  <div className="flex flex-wrap gap-x-4 gap-y-1 text-[10px] text-slate-400">
                    <span>{t("reconciliation_inbox.coverage")}: {displayValue(item.coverage?.status)}</span>
                    {Object.entries(item.coverage || {}).filter(([key]) => key !== "status").slice(0, 5).map(([key, value]) => (
                      <span key={key}>{key}: {displayValue(value)}</span>
                    ))}
                  </div>

                  {isUnresolved && (
                    <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-surface-border/50">
                      <input
                        aria-label={t("reconciliation_inbox.note")}
                        value={decisionNotes[item.review_id] || ""}
                        onChange={(event) => setDecisionNotes((current) => ({ ...current, [item.review_id]: event.target.value }))}
                        placeholder={t("reconciliation_inbox.note_placeholder")}
                        className="flex-1 min-w-[180px] bg-[#090d14] border border-surface-border rounded px-2 py-1.5 text-[10px] text-white"
                      />
                      <button type="button" data-testid="reconciliation-acknowledge" disabled={pendingReviewId === item.review_id} onClick={() => void recordDecision(item, "ACKNOWLEDGE")} className="px-2 py-1.5 rounded border border-accent/50 text-accent text-[10px] font-bold hover:bg-accent/10 disabled:opacity-50">{t("reconciliation_inbox.acknowledge")}</button>
                      <button type="button" data-testid="reconciliation-reject" disabled={pendingReviewId === item.review_id} onClick={() => void recordDecision(item, "REJECT")} className="px-2 py-1.5 rounded border border-loss/50 text-loss text-[10px] font-bold hover:bg-loss/10 disabled:opacity-50">{t("reconciliation_inbox.reject")}</button>
                      {item.trade_id && <button type="button" data-testid="reconciliation-correct-toggle" disabled={pendingReviewId === item.review_id} onClick={() => setCorrectionReviewId(isCorrecting ? null : item.review_id)} className="px-2 py-1.5 rounded border border-amber-400/50 text-amber-300 text-[10px] font-bold hover:bg-amber-400/10 disabled:opacity-50">{isCorrecting ? t("reconciliation_inbox.cancel_correction") : t("reconciliation_inbox.correct")}</button>}
                      {item.trade_id && onOpenEvidence && <button type="button" onClick={() => onOpenEvidence(item.trade_id as string)} className="px-2 py-1.5 rounded border border-surface-border text-slate-300 text-[10px] font-bold hover:bg-slate-800">{t("reconciliation_inbox.view_evidence")}</button>}
                    </div>
                  )}

                  {isCorrecting && (
                    <form data-testid="reconciliation-correction-form" onSubmit={(event) => submitCorrection(event, item)} className="grid grid-cols-1 md:grid-cols-4 gap-2 pt-2 border-t border-amber-400/30">
                      <label className="text-[10px] text-slate-400">{t("reconciliation_inbox.exit_price")}<input inputMode="decimal" value={correctionValues[`${item.review_id}:exit_price`] || ""} onChange={(event) => setCorrectionValues((current) => ({ ...current, [`${item.review_id}:exit_price`]: event.target.value }))} className="mt-1 w-full bg-[#090d14] border border-surface-border rounded px-2 py-1.5 text-xs text-white" /></label>
                      <label className="text-[10px] text-slate-400">{t("reconciliation_inbox.pnl")}<input inputMode="decimal" value={correctionValues[`${item.review_id}:pnl`] || ""} onChange={(event) => setCorrectionValues((current) => ({ ...current, [`${item.review_id}:pnl`]: event.target.value }))} className="mt-1 w-full bg-[#090d14] border border-surface-border rounded px-2 py-1.5 text-xs text-white" /></label>
                      <label className="text-[10px] text-slate-400">{t("reconciliation_inbox.commission")}<input inputMode="decimal" value={correctionValues[`${item.review_id}:commission`] || ""} onChange={(event) => setCorrectionValues((current) => ({ ...current, [`${item.review_id}:commission`]: event.target.value }))} className="mt-1 w-full bg-[#090d14] border border-surface-border rounded px-2 py-1.5 text-xs text-white" /></label>
                      <button type="submit" disabled={pendingReviewId === item.review_id} className="self-end px-2 py-1.5 rounded border border-amber-400/50 text-amber-300 text-[10px] font-bold hover:bg-amber-400/10 disabled:opacity-50">{t("reconciliation_inbox.record_correction")}</button>
                    </form>
                  )}

                  {!isUnresolved && item.decision_note && <p className="text-[10px] text-slate-500">{item.decision_note}</p>}
                </article>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
