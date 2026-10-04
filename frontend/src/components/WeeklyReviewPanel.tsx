import React, { FormEvent, useEffect, useRef, useState } from "react";
import { AlertTriangle, CalendarClock, CheckCircle2, RefreshCw, X, XCircle } from "lucide-react";
import { useTranslation } from "../context/I18nContext";
import { apiFetch, apiUrl } from "../lib/backend";
import { useDialogAccessibility } from "../hooks/useDialogAccessibility";
import { formatIstanbulDateTime, istanbulDateKey } from "../lib/tradeTime";

const STATUS_KEYS: Record<string, string> = {
  NOT_READY: "weekly_review.status_no_data", STALE_REVIEW: "weekly_review.status_stale",
  LIMITED: "weekly_review.status_limited", READY: "weekly_review.status_ready",
  COMPLETED: "weekly_review.status_completed",
};
const COVERAGE_KEYS: Record<string, string> = {
  overall: "weekly_review.coverage_overall", realized_pnl: "weekly_review.coverage_pnl",
  fees: "weekly_review.coverage_fees", funding_transfer: "weekly_review.coverage_funding",
  market_context: "weekly_review.coverage_market", account_events: "weekly_review.coverage_account",
};
const STATE_KEYS: Record<string, string> = {
  UNKNOWN: "weekly_review.state_unknown", PARTIAL: "weekly_review.state_partial",
  NOT_AVAILABLE: "weekly_review.state_unavailable", COMPLETE: "weekly_review.state_complete",
};
const WARNING_KEYS: Record<string, string> = {
  NO_EVIDENCE_IN_PERIOD: "weekly_review.warning_no_evidence",
  LATE_EVENT_AFTER_AS_OF: "weekly_review.warning_late",
  MALFORMED_EVENT_EXCLUDED: "weekly_review.warning_malformed",
  RULE_EFFECTIVE_TIME_NOT_AVAILABLE: "weekly_review.warning_rule_time",
  FUTURE_RULE_EXCLUDED: "weekly_review.warning_future",
};
const hasKey = (mapping: Record<string, string>, key: string) => Object.prototype.hasOwnProperty.call(mapping, key);
const mappedKey = (mapping: Record<string, string>, key: string, fallback: string) => hasKey(mapping, key) ? mapping[key] : fallback;

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

const defaultTimezone = (): string => "Europe/Istanbul";

const shortHash = (value: string | undefined): string => {
  if (!value) return "—";
  return value.length > 18 ? `${value.slice(0, 10)}…${value.slice(-6)}` : value;
};

const reviewInputKey = (periodStart: string, periodEnd: string, timezone: string, asOfUtc: string): string =>
  JSON.stringify({ periodStart, periodEnd, timezone, asOfUtc });

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isFiniteCount(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
}

function isWeeklyReview(value: unknown): value is WeeklyReview {
  if (!isRecord(value)
    || typeof value.review_id !== "string"
    || typeof value.review_status !== "string"
    || typeof value.completion_allowed !== "boolean"
    || value.is_pass !== false
    || typeof value.as_of_utc !== "string"
    || !isFiniteCount(value.trade_count)
    || !isFiniteCount(value.event_count)
    || !isFiniteCount(value.late_event_count)
    || !isFiniteCount(value.malformed_event_count)
    || !isFiniteCount(value.excluded_future_rule_count)) return false;
  const period = value.period;
  const coverage = value.coverage;
  const rules = value.applicable_rules;
  const warnings = value.warnings;
  if (!isRecord(period)
    || !["start_local", "end_local", "start_utc", "end_utc", "timezone"].every((key) => typeof period[key] === "string")
    || !isRecord(coverage)
    || !Object.values(coverage).every((item) => typeof item === "string")
    || !Array.isArray(rules)
    || !rules.every((rule) => isRecord(rule)
      && Object.values(rule).every((item) => typeof item === "string" || item === null))
    || !Array.isArray(warnings)
    || !warnings.every((warning) => typeof warning === "string")) return false;
  if (value.snapshot_sha256 != null && typeof value.snapshot_sha256 !== "string") return false;
  if (value.source_event_hashes != null && (!Array.isArray(value.source_event_hashes)
    || !value.source_event_hashes.every((hash) => typeof hash === "string"))) return false;
  if (value.completion == null) return true;
  return isRecord(value.completion)
    && (value.completion.decision == null || typeof value.completion.decision === "string")
    && (value.completion.note == null || typeof value.completion.note === "string")
    && (value.completion.reviewed_at_utc == null || typeof value.completion.reviewed_at_utc === "string");
}

export const WeeklyReviewPanel: React.FC<WeeklyReviewPanelProps> = ({ onClose }) => {
  const { t, locale } = useTranslation();
  const dialogRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  useDialogAccessibility(dialogRef, onClose, closeRef, true);
  const today = new Date();
  const [periodStart, setPeriodStart] = useState(() => istanbulDateKey(new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000).toISOString()) || isoDate(today));
  const [periodEnd, setPeriodEnd] = useState(() => istanbulDateKey(today.toISOString()) || isoDate(today));
  const [timezone, setTimezone] = useState(defaultTimezone);
  const [asOfUtc, setAsOfUtc] = useState(() => new Date().toISOString());
  const [note, setNote] = useState("");
  const [review, setReview] = useState<WeeklyReview | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [decisionMessage, setDecisionMessage] = useState<string | null>(null);
  const [loadedReviewKey, setLoadedReviewKey] = useState<string | null>(null);
  const loadControllerRef = useRef<AbortController | null>(null);
  const [cancelled, setCancelled] = useState(false);

  const currentReviewKey = reviewInputKey(periodStart, periodEnd, timezone, asOfUtc);
  const reviewIsCurrent = Boolean(review && loadedReviewKey === currentReviewKey);

  const invalidateLoadedReview = () => {
    setLoadedReviewKey(null);
    setDecisionMessage(null);
  };

  const loadReview = async () => {
    loadControllerRef.current?.abort();
    const controller = new AbortController();
    loadControllerRef.current = controller;
    setLoading(true);
    setError(null);
    setDecisionMessage(null);
    setCancelled(false);
    setReview(null);
    setLoadedReviewKey(null);
    const requestedReviewKey = reviewInputKey(periodStart, periodEnd, timezone, asOfUtc);
    const query = new URLSearchParams({
      period_start: periodStart,
      period_end: periodEnd,
      timezone,
      as_of_utc: asOfUtc,
    });
    try {
      const response = await apiFetch(apiUrl(`/api/v1/reviews/weekly?${query.toString()}`), { signal: controller.signal });
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
      const payload = await response.json();
      if (!isWeeklyReview(payload)) throw new Error(t("weekly_review.malformed"));
      const nextReview = payload;
      if (loadControllerRef.current === controller && !controller.signal.aborted) {
        setReview(nextReview);
        setLoadedReviewKey(requestedReviewKey);
      }
    } catch (reason: unknown) {
      if (loadControllerRef.current === controller && !controller.signal.aborted) {
        setCancelled(false);
        setReview(null);
        setError(reason instanceof Error ? reason.message : t("weekly_review.error"));
      }
    } finally {
      if (loadControllerRef.current === controller) {
        loadControllerRef.current = null;
        if (!controller.signal.aborted) setLoading(false);
      }
    }
  };

  useEffect(() => {
    void loadReview();
    return () => {
      loadControllerRef.current?.abort();
      loadControllerRef.current = null;
    };
  }, []);

  const cancelLoad = () => {
    const controller = loadControllerRef.current;
    if (!controller) return;
    controller.abort();
    loadControllerRef.current = null;
    setLoading(false);
    setReview(null);
    setLoadedReviewKey(null);
    setCancelled(true);
    setError(t("weekly_review.cancelled"));
  };

  const recordDecision = async (decision: "COMPLETE" | "REOPEN") => {
    if (!review || !reviewIsCurrent || !hasKey(STATUS_KEYS, review.review_status) || review.event_count === 0
      || review.review_status === "STALE_REVIEW" || review.review_status === "NOT_READY"
      || (decision === "COMPLETE" && !review.completion_allowed)) return;
    setSaving(true);
    setError(null);
    setDecisionMessage(null);
    setCancelled(false);
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
  const coverageName = (key: string) => t(mappedKey(COVERAGE_KEYS, key, "weekly_review.coverage_other"));
  const coverageState = (value: string) => t(mappedKey(STATE_KEYS, value, "weekly_review.state_unknown"));
  const warningText = (code: string) => {
    if (hasKey(WARNING_KEYS, code)) return t(WARNING_KEYS[code]);
    const match = /^(FEES|FUNDING_TRANSFER|MARKET_CONTEXT)_(UNKNOWN|PARTIAL|NOT_AVAILABLE)$/.exec(code);
    return match ? `${coverageName(match[1].toLowerCase())}: ${coverageState(match[2])}`
      : t("weekly_review.warning_unknown");
  };
  const decisionSupported = Boolean(review && hasKey(STATUS_KEYS, review.review_status)
    && review.event_count > 0 && !["NOT_READY", "STALE_REVIEW"].includes(review.review_status));
  const unknownCoverage = review && Object.entries(review.coverage)
    .some(([key, value]) => !hasKey(COVERAGE_KEYS, key) || !hasKey(STATE_KEYS, value));

  return (
    <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-3 sm:p-4" role="dialog" aria-modal="true" aria-label={t("weekly_review.title")}>
      <div ref={dialogRef} data-testid="weekly-review-panel" className="w-full min-w-0 max-w-5xl max-h-[92vh] overflow-y-auto overflow-x-hidden bg-background border border-surface-border rounded-lg shadow-2xl text-sm text-slate-200">
        <header className="sticky top-0 z-10 bg-background border-b border-surface-border p-4 flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="k-section-title flex items-center gap-2"><CalendarClock className="w-5 h-5 text-accent shrink-0" />{t("weekly_review.title")}</h2>
            <p className="k-help mt-1">{t("weekly_review.guide")}</p>
          </div>
          <button ref={closeRef} type="button" onClick={onClose} aria-label={t("weekly_review.close")} className="k-btn border border-surface-border shrink-0"><X className="w-5 h-5" /></button>
        </header>

        <form onSubmit={submit} className="p-4 space-y-3">
          <p className="k-help">{t("weekly_review.period_help")}</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <label htmlFor="weekly-period-start" className="k-label">{t("weekly_review.period_start")}
              <input id="weekly-period-start" name="period_start" type="date" required disabled={saving} value={periodStart} onChange={(event) => { setPeriodStart(event.target.value); invalidateLoadedReview(); }} className="k-input mt-1" />
            </label>
            <label htmlFor="weekly-period-end" className="k-label">{t("weekly_review.period_end")}
              <input id="weekly-period-end" name="period_end" type="date" required disabled={saving} value={periodEnd} onChange={(event) => { setPeriodEnd(event.target.value); invalidateLoadedReview(); }} className="k-input mt-1" />
            </label>
          </div>
          <p className="k-help">{t("weekly_review.cutoff_help")} <span className="font-semibold">{formatIstanbulDateTime(asOfUtc, locale)} · Europe/Istanbul</span></p>
          <button type="button" disabled={saving || loading} data-testid="weekly-review-now" onClick={() => { setAsOfUtc(new Date().toISOString()); invalidateLoadedReview(); }} className="k-btn border border-surface-border">{t("weekly_review.use_now")}</button>
          <details className="k-card">
            <summary tabIndex={0} className="cursor-pointer font-semibold focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent">{t("weekly_review.time_settings")}</summary>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-3">
              <label htmlFor="weekly-timezone" className="k-label">{t("weekly_review.timezone")}
                <input id="weekly-timezone" name="timezone" required disabled={saving} value={timezone} onChange={(event) => { setTimezone(event.target.value); invalidateLoadedReview(); }} className="k-input mt-1" />
              </label>
              <label htmlFor="weekly-as-of" className="k-label">{t("weekly_review.as_of_label")}
                <input id="weekly-as-of" name="as_of_utc" required disabled={saving} value={asOfUtc} onChange={(event) => { setAsOfUtc(event.target.value); invalidateLoadedReview(); }} className="k-input mt-1" />
              </label>
            </div>
            <p className="k-help mt-2">{t("weekly_review.time_help")}</p>
          </details>
          <button type="submit" disabled={loading || saving} className="k-btn k-primary disabled:opacity-50">
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />{t("weekly_review.load")}
          </button>
        </form>

        {loading && <div role="status" className="p-6 text-center space-y-3"><p>{t("weekly_review.loading")}</p><button type="button" data-testid="weekly-review-cancel" onClick={cancelLoad} className="k-btn border border-surface-border">{t("weekly_review.cancel_load")}</button></div>}
        {!loading && error && <div role="alert" data-testid={cancelled ? "weekly-review-cancelled" : undefined} className="m-4 k-card border-loss bg-loss/10 text-loss space-y-2">
          <p className="flex items-center gap-2"><XCircle className="w-5 h-5 shrink-0" />{cancelled ? t("weekly_review.cancelled") : t("weekly_review.error")}</p>
          {!cancelled && <details><summary tabIndex={0} className="cursor-pointer">{t("weekly_review.diagnostics")}</summary><p className="break-words mt-2">{error}</p></details>}
          <button type="button" data-testid="weekly-review-retry" disabled={saving} onClick={() => void loadReview()} className="k-btn border border-loss">{t("weekly_review.retry")}</button>
        </div>}

        {!loading && !error && review && !reviewIsCurrent && <div role="status" data-testid="weekly-review-inputs-changed" className="m-4 k-card text-warn border-warn bg-warn/10">{t("weekly_review.inputs_changed")}</div>}

        {!loading && !error && review && (
          <div className="px-4 pb-4 space-y-4">
            <section className="k-card space-y-2">
              <h3 data-testid="weekly-review-status" className="k-section-title">{t(mappedKey(STATUS_KEYS, review.review_status, "weekly_review.status_unknown"))}</h3>
              <p data-testid="weekly-review-period" className="break-words">{t("weekly_review.loaded_period")}: {formatIstanbulDateTime(review.period.start_utc, locale)} → {formatIstanbulDateTime(review.period.end_utc, locale)} · Europe/Istanbul</p>
              <p data-testid="weekly-review-cutoff" className="k-help">{t("weekly_review.as_of")}: {formatIstanbulDateTime(review.as_of_utc, locale)} · Europe/Istanbul</p>
              <p className="k-help">{review.event_count === 0 ? t("weekly_review.no_data_help") : t("weekly_review.summary_help")}</p>
              <p className="k-help">{t("weekly_review.completion_not_validation")}</p>
            </section>

            <dl data-testid="weekly-review-summary" className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              {[
                ["weekly_review.trades", review.trade_count], ["weekly_review.events", review.event_count],
                ["weekly_review.late_events", review.late_event_count], ["weekly_review.malformed_events", review.malformed_event_count],
                ["weekly_review.rule_count", review.applicable_rules.length], ["weekly_review.future_rules", review.excluded_future_rule_count],
              ].map(([key, count]) => <div key={key} className="k-card min-w-0"><dt className="k-label">{t(key as string)}</dt><dd className="mt-1 text-lg font-semibold">{formatCount(count as number)}</dd></div>)}
            </dl>

            <section data-testid="weekly-review-coverage" className="k-card space-y-3">
              <h3 className="k-section-title">{t("weekly_review.coverage_title")}: {coverageState(review.coverage.overall || "UNKNOWN")}</h3>
              <p className="k-help">{t("weekly_review.coverage_help")}</p>
              <dl className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                {Object.entries(review.coverage).filter(([key]) => key !== "overall").map(([key, value]) => <div key={key} className="border border-surface-border rounded p-3 min-w-0">
                  <dt className="k-label">{coverageName(key)}</dt><dd className={`mt-1 font-semibold ${value === "COMPLETE" ? "text-slate-200" : "text-warn"}`}>{coverageState(value)}</dd>
                </div>)}
              </dl>
              {unknownCoverage && <p className="text-warn">{t("weekly_review.warning_unknown")}</p>}
            </section>

            <section className="k-card">
              <h3 className="k-section-title">{t("weekly_review.rules_title")}</h3>
              <p className="k-help mt-2">{t("weekly_review.rules_help")}</p>
              {review.applicable_rules.length ? <ul className="mt-3 space-y-2">{review.applicable_rules.map((rule, index) => <li key={`${rule.event_hash}-${index}`} className="border border-surface-border rounded p-3 break-words">
                <span className="font-semibold">{rule.rule_id || t("weekly_review.rule_unknown")}</span> · {t("weekly_review.rule_version", { version: rule.version || "—" })}
              </li>)}</ul> : <p className="text-warn mt-2">{t("weekly_review.no_rules")}</p>}
            </section>

            {review.warnings.length > 0 && <section data-testid="weekly-review-warnings" role="status" className="k-card border-warn bg-warn/10 text-warn">
              <h3 className="flex items-center gap-2 font-semibold"><AlertTriangle className="w-5 h-5 shrink-0" />{t(review.review_status === "STALE_REVIEW" ? "weekly_review.stale" : "weekly_review.limited")}</h3>
              <ul className="mt-2 space-y-2 list-disc pl-5">{review.warnings.map((warning, index) => <li key={`${warning}-${index}`} className="break-words">{warningText(warning)}</li>)}</ul>
            </section>}

            <section className="k-card space-y-3">
              <p>{t("weekly_review.completion_not_validation")}</p>
              {review.completion?.note && <p className="break-words">{t("weekly_review.saved_note")}: {review.completion.note}</p>}
              <label className="k-label" htmlFor="weekly-review-note">{t("weekly_review.note")}
                <textarea id="weekly-review-note" disabled={saving} value={note} onChange={(event) => setNote(event.target.value)} maxLength={500} placeholder={t("weekly_review.note_placeholder")} className="k-input mt-1 min-h-24" />
              </label>
              <p className="k-help">{t("weekly_review.note_limit")}</p>
              <div className="flex flex-wrap items-center gap-3">
                {review.completion?.decision === "COMPLETED"
                  ? <button type="button" data-testid="weekly-review-reopen" disabled={saving || !reviewIsCurrent || !decisionSupported} onClick={() => void recordDecision("REOPEN")} className="k-btn border border-warn text-warn disabled:opacity-50">{t("weekly_review.reopen")}</button>
                  : <button type="button" data-testid="weekly-review-complete" disabled={saving || !review.completion_allowed || !reviewIsCurrent || !decisionSupported} onClick={() => void recordDecision("COMPLETE")} className="k-btn k-primary disabled:opacity-50"><CheckCircle2 className="w-5 h-5" />{t("weekly_review.record_complete")}</button>}
                {decisionMessage && <span aria-live="polite">{decisionMessage}</span>}
              </div>
            </section>

            <details data-testid="weekly-review-diagnostics" className="k-card">
              <summary tabIndex={0} className="cursor-pointer font-semibold focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent">{t("weekly_review.diagnostics")}</summary>
              <div className="mt-3 space-y-2 break-all">
                <p>{review.review_id} · {review.review_status}</p>
                <p>{review.period.start_local} → {review.period.end_local} · {review.period.timezone}</p>
                <p>{t("weekly_review.as_of_label")}: {review.as_of_utc}</p>
                <p>{t("weekly_review.snapshot")}: <span title={review.snapshot_sha256}>{shortHash(review.snapshot_sha256)}</span></p>
                <pre className="whitespace-pre-wrap text-sm">{JSON.stringify({ coverage: review.coverage, warnings: review.warnings, rules: review.applicable_rules }, null, 2)}</pre>
              </div>
            </details>
          </div>
        )}
      </div>
    </div>
  );
};
