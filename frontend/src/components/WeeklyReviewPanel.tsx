import React, { FormEvent, useEffect, useRef, useState } from "react";
import { AlertTriangle, CalendarClock, CheckCircle2, RefreshCw, X, XCircle } from "lucide-react";
import { useTranslation } from "../context/I18nContext";
import { apiFetch, apiUrl } from "../lib/backend";
import { useDialogAccessibility } from "../hooks/useDialogAccessibility";

type ReviewStatus = "NOT_READY" | "STALE_REVIEW" | "LIMITED" | "READY" | "COMPLETED" | string;

interface WeeklyReview {
  review_id: string;
  review_status: ReviewStatus;
  completion_allowed: boolean;
  is_pass: false;
  period: {
    start_local: string;
    end_local: string;
    start_utc: string;
    end_utc: string;
    timezone: string;
  };
  as_of_utc: string;
  snapshot_sha256?: string;
  source_event_hashes?: string[];
  trade_count: number;
  event_count: number;
  late_event_count: number;
  malformed_event_count: number;
  excluded_future_rule_count: number;
  coverage: Record<string, string>;
  applicable_rules: Array<Record<string, string | null>>;
  warnings: string[];
  completion?: {
    decision?: string;
    note?: string | null;
    reviewed_at_utc?: string;
  } | null;
}

interface WeeklyReviewPanelProps {
  onClose: () => void;
}

const isoDate = (value: Date): string => value.toISOString().slice(0, 10);

const defaultTimezone = (): string => {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  } catch {
    return "UTC";
  }
};

const shortHash = (value: string | undefined): string => {
  if (!value) return "—";
  return value.length > 18 ? `${value.slice(0, 10)}…${value.slice(-6)}` : value;
};

export const WeeklyReviewPanel: React.FC<WeeklyReviewPanelProps> = ({ onClose }) => {
  const { t, locale } = useTranslation();
  const dialogRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  useDialogAccessibility(dialogRef, onClose, closeRef);
  const today = new Date();
  const [periodStart, setPeriodStart] = useState(() => isoDate(new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000)));
  const [periodEnd, setPeriodEnd] = useState(() => isoDate(today));
  const [timezone, setTimezone] = useState(defaultTimezone);
  const [asOfUtc, setAsOfUtc] = useState(() => new Date().toISOString());
  const [note, setNote] = useState("");
  const [review, setReview] = useState<WeeklyReview | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [decisionMessage, setDecisionMessage] = useState<string | null>(null);

  const loadReview = async () => {
    setLoading(true);
    setError(null);
    setDecisionMessage(null);
    const query = new URLSearchParams({
      period_start: periodStart,
      period_end: periodEnd,
      timezone,
      as_of_utc: asOfUtc,
    });
    try {
      const response = await apiFetch(apiUrl(`/api/v1/reviews/weekly?${query.toString()}`));
      if (!response.ok) {
        let detail = t("weekly_review.error");
        try {
          const body = await response.json() as { detail?: string };
          if (body.detail) detail = body.detail;
        } catch {
          // Keep the bounded safe error when the server did not return JSON.
        }
        throw new Error(detail);
      }
      setReview(await response.json() as WeeklyReview);
    } catch (reason: unknown) {
      setReview(null);
      setError(reason instanceof Error ? reason.message : t("weekly_review.error"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadReview();
  }, []);

  const recordDecision = async (decision: "COMPLETE" | "REOPEN") => {
    if (!review) return;
    setSaving(true);
    setError(null);
    setDecisionMessage(null);
    try {
      const response = await apiFetch(apiUrl("/api/v1/reviews/weekly/decision"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          period_start: periodStart,
          period_end: periodEnd,
          timezone,
          as_of_utc: asOfUtc,
          decision,
          note: note.trim() || undefined,
        }),
      });
      if (!response.ok) throw new Error(t("weekly_review.decision_error"));
      setDecisionMessage(t("weekly_review.decision_saved"));
      await loadReview();
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : t("weekly_review.decision_error"));
    } finally {
      setSaving(false);
    }
  };

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    void loadReview();
  };

  const formatCount = (value: number): string => new Intl.NumberFormat(locale).format(value);
  const stateMessage = review?.review_status === "STALE_REVIEW"
    ? t("weekly_review.stale")
    : t("weekly_review.limited");

  const statusClass = review?.review_status === "COMPLETED"
    ? "border-gain/40 bg-gain/10 text-gain"
    : review?.review_status === "READY"
      ? "border-accent/40 bg-accent/10 text-accent"
      : "border-amber-400/40 bg-amber-400/10 text-amber-300";

  return (
    <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-label={t("weekly_review.title")}>
      <div ref={dialogRef} data-testid="weekly-review-panel" className="w-full max-w-5xl max-h-[92vh] overflow-y-auto overflow-x-hidden bg-[#0b0e14] border border-surface-border rounded-lg shadow-2xl font-mono">
        <div className="sticky top-0 z-10 bg-[#0d121c] border-b border-surface-border px-4 py-3 flex items-center justify-between">
          <div>
            <h2 className="text-sm font-bold text-white flex items-center gap-2"><CalendarClock className="w-4 h-4 text-accent" />{t("weekly_review.title")}</h2>
            <p className="text-[11px] text-slate-400 mt-1">{t("weekly_review.subtitle")}</p>
          </div>
          <button ref={closeRef} type="button" onClick={onClose} aria-label={t("weekly_review.close")} className="p-1.5 text-slate-400 hover:text-white hover:bg-slate-800 rounded focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"><X className="w-4 h-4" /></button>
        </div>

        <form onSubmit={submit} className="p-4 space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3 text-[10px] text-slate-400">
            <label htmlFor="weekly-period-start">{t("weekly_review.period_start")}
              <input id="weekly-period-start" name="period_start" type="date" value={periodStart} onChange={(event) => setPeriodStart(event.target.value)} className="mt-1 w-full bg-[#090d14] border border-surface-border rounded px-2 py-1.5 text-xs text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-accent" />
            </label>
            <label htmlFor="weekly-period-end">{t("weekly_review.period_end")}
              <input id="weekly-period-end" name="period_end" type="date" value={periodEnd} onChange={(event) => setPeriodEnd(event.target.value)} className="mt-1 w-full bg-[#090d14] border border-surface-border rounded px-2 py-1.5 text-xs text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-accent" />
            </label>
            <label htmlFor="weekly-timezone">{t("weekly_review.timezone")}
              <input id="weekly-timezone" name="timezone" value={timezone} onChange={(event) => setTimezone(event.target.value)} className="mt-1 w-full bg-[#090d14] border border-surface-border rounded px-2 py-1.5 text-xs text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-accent" />
            </label>
            <label htmlFor="weekly-as-of">{t("weekly_review.as_of_label")}
              <input id="weekly-as-of" name="as_of_utc" value={asOfUtc} onChange={(event) => setAsOfUtc(event.target.value)} className="mt-1 w-full bg-[#090d14] border border-surface-border rounded px-2 py-1.5 text-xs text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-accent" />
            </label>
          </div>
          <div className="flex justify-end">
            <button type="submit" disabled={loading} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded border border-accent/50 text-accent text-[10px] font-bold hover:bg-accent/10 disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent">
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />{t("weekly_review.load")}
            </button>
          </div>
        </form>

        {loading && <div className="p-8 text-center text-slate-400 text-xs">{t("weekly_review.loading")}</div>}
        {!loading && error && <div role="alert" className="m-4 p-4 rounded border border-loss/50 bg-loss/10 text-loss text-xs flex items-start gap-2"><XCircle className="w-4 h-4 shrink-0" /><div className="flex-1 space-y-2"><span className="block break-words">{error}</span><button type="button" data-testid="weekly-review-retry" onClick={() => void loadReview()} className="px-2 py-1 rounded border border-loss/50 text-loss font-bold hover:bg-loss/10 focus:outline-none focus-visible:ring-2 focus-visible:ring-loss">{t("weekly_review.retry")}</button></div></div>}

        {!loading && !error && review && (
          <div className="px-4 pb-4 space-y-4">
            <div className="flex flex-wrap items-start justify-between gap-3 border-b border-surface-border pb-3">
              <div>
                <p className="text-[10px] text-slate-500">{review.review_id} · {t("weekly_review.as_of")}: {review.as_of_utc}</p>
                <p className="text-[11px] text-slate-400 mt-1">{review.period.start_local} → {review.period.end_local} ({review.period.timezone})</p>
              </div>
              <span className={`px-2 py-1 rounded border text-[10px] font-bold ${statusClass}`}>{review.review_status}</span>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-5 gap-2 text-[10px]">
              <div className="bg-[#111722] border border-surface-border rounded p-2"><span className="block text-slate-500">{t("weekly_review.events")}</span><span className="block mt-1 text-white font-bold">{formatCount(review.event_count)}</span></div>
              <div className="bg-[#111722] border border-surface-border rounded p-2"><span className="block text-slate-500">{t("weekly_review.trades")}</span><span className="block mt-1 text-white font-bold">{formatCount(review.trade_count)}</span></div>
              <div className="bg-[#111722] border border-surface-border rounded p-2"><span className="block text-slate-500">{t("weekly_review.late_events")}</span><span className="block mt-1 text-amber-300 font-bold">{formatCount(review.late_event_count)}</span></div>
              <div className="bg-[#111722] border border-surface-border rounded p-2"><span className="block text-slate-500">{t("weekly_review.future_rules")}</span><span className="block mt-1 text-amber-300 font-bold">{formatCount(review.excluded_future_rule_count)}</span></div>
              <div className="bg-[#111722] border border-surface-border rounded p-2 min-w-0"><span className="block text-slate-500">{t("weekly_review.snapshot")}</span><span className="block mt-1 text-white font-bold break-all" title={review.snapshot_sha256}>{shortHash(review.snapshot_sha256)}</span></div>
            </div>

            <section className="bg-[#0d121c] border border-amber-400/30 rounded-lg p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="text-xs font-bold text-white uppercase tracking-wide">{t("weekly_review.coverage_title")}</h3>
                <span className="px-2 py-1 rounded border border-amber-400/40 bg-amber-400/10 text-amber-300 text-[10px] font-bold">{review.coverage.overall || "UNKNOWN"}</span>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-2 mt-3 text-[10px]">
                {Object.entries(review.coverage).filter(([key]) => key !== "overall").map(([key, value]) => (
                  <div key={key} className="border border-surface-border/70 bg-[#111722] rounded p-2"><span className="block text-slate-500">{key}</span><span className="block mt-1 text-amber-300 font-bold">{value}</span></div>
                ))}
              </div>
            </section>

            <section className="bg-[#0d121c] border border-surface-border rounded-lg p-4">
              <h3 className="text-xs font-bold text-white uppercase tracking-wide">{t("weekly_review.rules_title")}</h3>
              {review.applicable_rules.length ? review.applicable_rules.map((rule) => (
                <div key={`${rule.kind}-${rule.rule_id}-${rule.event_hash}`} className="mt-2 border border-surface-border/70 bg-[#111722] rounded p-2 text-[10px] text-slate-400 break-all">
                  <span className="text-accent font-bold">{rule.rule_id}</span><span className="ml-3">{rule.kind}</span><span className="ml-3">v{rule.version}</span>
                </div>
              )) : <p className="text-[11px] text-amber-300 mt-2">{t("weekly_review.no_rules")}</p>}
            </section>

            {review.warnings.length > 0 && <div role="status" className="border border-amber-400/30 bg-amber-400/10 rounded-lg p-3 text-[10px] text-amber-200"><div className="flex items-center gap-2 font-bold"><AlertTriangle className="w-3.5 h-3.5" />{stateMessage}</div><ul className="mt-2 space-y-1 list-disc list-inside">{review.warnings.map((warning) => <li key={warning} className="break-words">{warning}</li>)}</ul></div>}

            <div className="border-t border-surface-border pt-3 space-y-2">
              <p className="text-[10px] text-slate-500">{t("weekly_review.completion_not_validation")}</p>
              <label className="block text-[10px] text-slate-400">{t("weekly_review.note")}
                <textarea id="weekly-review-note" value={note} onChange={(event) => setNote(event.target.value)} maxLength={500} placeholder={t("weekly_review.note_placeholder")} className="mt-1 w-full min-h-16 bg-[#090d14] border border-surface-border rounded px-2 py-1.5 text-xs text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-accent" />
              </label>
              <div className="flex flex-wrap items-center gap-2">
                {review.completion?.decision === "COMPLETED" ? <button type="button" disabled={saving} onClick={() => void recordDecision("REOPEN")} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded border border-amber-400/50 text-amber-300 text-[10px] font-bold hover:bg-amber-400/10 disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400"><AlertTriangle className="w-3.5 h-3.5" />{t("weekly_review.reopen")}</button> : <button type="button" disabled={saving || !review.completion_allowed} onClick={() => void recordDecision("COMPLETE")} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded border border-accent/50 text-accent text-[10px] font-bold hover:bg-accent/10 disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"><CheckCircle2 className="w-3.5 h-3.5" />{t("weekly_review.record_complete")}</button>}
                {decisionMessage && <span aria-live="polite" className="text-[10px] text-gain">{decisionMessage}</span>}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
