import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AlertTriangle, ChevronDown, History, Pencil, PlayCircle, RefreshCw, Save, X } from "lucide-react";
import { apiFetch, apiUrl } from "../lib/backend";
import { useTranslation } from "../context/I18nContext";
import { isTrackingState, type TrackingState } from "../lib/localTracking";
import { targetPayload, validTargets, type TargetDraft } from "../lib/localTracking";
import { TargetPlanFields } from "./TargetPlanFields";
import {
  formatIstanbulDateTime,
  istanbulInputToUtcIso,
  isFutureIstanbulInput,
  utcIsoToIstanbulInput,
} from "../lib/tradeTime";
import { formatNotional, positionSizing } from "../lib/positionMath";
import type { Trade, TradeQuote, TradeRevision, TradeRevisionHistory } from "../types";

const REASON_KEYS: Record<string, string> = {
  REVISION_CONFLICT: "journal_edit.reason_revision_conflict",
  TRACKING_PARTIAL_CLOSE_LOCKS_SIZE: "journal_edit.reason_partial_close_locked",
  TRACKING_PLAN_INVALID_AFTER_EDIT: "journal_edit.reason_plan_invalid",
  TRADE_CLOSED_NOTES_ONLY: "journal_edit.reason_closed_notes_only",
  TRADE_NOT_FOUND: "journal_edit.reason_not_found",
  ENTRY_AFTER_EXIT: "journal_edit.reason_entry_after_exit",
  STOP_WRONG_SIDE: "journal_edit.reason_stop_wrong_side",
  TARGET_WRONG_SIDE: "journal_edit.reason_target_wrong_side",
  LEVERAGE_SPOT_NOT_ALLOWED: "journal_edit.reason_leverage_spot",
  LEVERAGE_OUT_OF_RANGE: "journal_edit.reason_leverage_range",
  TIME_IN_FUTURE: "journal_edit.reason_time_future",
  ENTRY_INVALID: "journal_edit.reason_entry_invalid",
  QTY_INVALID: "journal_edit.reason_qty_invalid",
  EXIT_REQUIRED_FOR_CLOSED: "journal_edit.reason_exit_required",
  EXIT_FIELDS_REQUIRE_CLOSE: "journal_edit.reason_exit_fields_require_close",
  TRADE_STATUS_INVALID: "journal_edit.reason_status_invalid",
  TARGETS_MANAGED_BY_PLAN: "journal_edit.reason_targets_managed_by_plan",
  AMBIGUOUS_ORDER_EDIT: "journal_edit.reason_ambiguous_order_edit",
  TRACKING_UNIT_UNVERIFIED: "journal_edit.reason_tracking_unit_unverified",
  TRACKING_CONFLICT: "journal_edit.reason_revision_conflict",
  QTY_UNIT_INVALID: "journal_edit.reason_qty_unit_invalid",
};

function isTrade(value: unknown): value is Trade {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Record<string, unknown>;
  return typeof candidate.id === "string" && typeof candidate.symbol === "string"
    && typeof candidate.entry_time === "string" && Number.isFinite(Number(candidate.entry_price));
}

interface TradeEditModalProps {
  tradeId: string;
  onClose: () => void;
  onSaved?: (trade: Trade) => void;
  onOpenReplay?: (tradeId: string) => void;
}

export const TradeEditModal: React.FC<TradeEditModalProps> = ({ tradeId, onClose, onSaved, onOpenReplay }) => {
  const { t } = useTranslation();
  const [trade, setTrade] = useState<Trade | null>(null);
  const [tracking, setTracking] = useState<TrackingState | null>(null);
  const [revisions, setRevisions] = useState<TradeRevision[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [conflict, setConflict] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [showHistory, setShowHistory] = useState(false);
  const [quote, setQuote] = useState<TradeQuote | null>(null);
  const [quoteBusy, setQuoteBusy] = useState(false);
  const [quoteError, setQuoteError] = useState<string | null>(null);

  const [entryPrice, setEntryPrice] = useState("");
  const [entryTime, setEntryTime] = useState("");
  const [qty, setQty] = useState("");
  const [leverage, setLeverage] = useState("");
  const [stopLoss, setStopLoss] = useState("");
  const [takeProfit, setTakeProfit] = useState("");
  const [notes, setNotes] = useState("");
  const [qtyUnit, setQtyUnit] = useState<"BASE" | "UNKNOWN">("UNKNOWN");
  const [serverVerified, setServerVerified] = useState(false);
  const [statusSelection, setStatusSelection] = useState<"OPEN" | "CLOSED" | "CANCELED">("OPEN");
  const [exitPrice, setExitPrice] = useState("");
  const [exitTime, setExitTime] = useState("");
  const [planTargets, setPlanTargets] = useState<TargetDraft[]>([]);
  const [planStop, setPlanStop] = useState("");
  const [planEnabled, setPlanEnabled] = useState(true);
  const [planError, setPlanError] = useState<string | null>(null);
  const loadRef = useRef<AbortController | null>(null);

  const applyTrade = useCallback((next: Trade) => {
    setTrade(next);
    setEntryPrice(next.entry_price != null ? String(next.entry_price) : "");
    setEntryTime(utcIsoToIstanbulInput(next.entry_time) || "");
    setQty(next.qty != null ? String(next.qty) : "");
    setLeverage(next.leverage != null ? String(next.leverage) : "");
    setStopLoss(next.stop_loss != null ? String(next.stop_loss) : "");
    setTakeProfit(next.take_profit != null ? String(next.take_profit) : "");
    setNotes(next.notes || "");
    setQtyUnit(next.qty_unit === "BASE" ? "BASE" : "UNKNOWN");
    setServerVerified(next.sizing?.instrument?.verification === "PROVIDER_CATALOG");
    setStatusSelection((next.status as "OPEN" | "CLOSED" | "CANCELED") || "OPEN");
    setExitPrice(next.exit_price != null ? String(next.exit_price) : "");
    setExitTime(utcIsoToIstanbulInput(next.exit_time) || "");
  }, []);

  const applyTracking = useCallback((state: TrackingState | null) => {
    setTracking(state);
    if (state) {
      setPlanTargets(state.targets.map((target) => ({ price: String(target.price), percent: String(target.percent) })));
      setPlanStop(state.stop_loss != null ? String(state.stop_loss) : "");
      setPlanEnabled(state.enabled);
    } else {
      setPlanTargets([]);
      setPlanStop("");
      setPlanEnabled(true);
    }
    setPlanError(null);
  }, []);

  const load = useCallback(async () => {
    loadRef.current?.abort();
    const controller = new AbortController();
    loadRef.current = controller;
    setIsLoading(true);
    setLoadError(null);
    setConflict(false);
    setSaveError(null);
    try {
      const [tradeResponse, trackingResponse, revisionResponse] = await Promise.all([
        apiFetch(apiUrl(`/api/v1/trades/${encodeURIComponent(tradeId)}`), { signal: controller.signal }),
        apiFetch(apiUrl(`/api/v1/trades/${encodeURIComponent(tradeId)}/tracking`), { signal: controller.signal }),
        apiFetch(apiUrl(`/api/v1/trades/${encodeURIComponent(tradeId)}/revisions`), { signal: controller.signal }),
      ]);
      const tradeData: unknown = await tradeResponse.json();
      if (!tradeResponse.ok || !isTrade(tradeData)) throw new Error(t("journal_edit.load_failed"));
      const trackingData: unknown = await trackingResponse.json();
      const revisionData: unknown = await revisionResponse.json();
      if (controller.signal.aborted) return;
      applyTrade(tradeData);
      void apiFetch(apiUrl(`/api/v1/market-data/instrument?symbol=${encodeURIComponent(tradeData.symbol)}`))
        .then((response) => (response.ok ? response.json() : null))
        .then((payload: { status?: string } | null) => {
          if (payload?.status === "VERIFIED") setServerVerified(true);
        })
        .catch(() => {});
      const plan = (trackingData as { plan?: unknown })?.plan;
      applyTracking(plan == null ? null : isTrackingState(plan) ? plan : null);
      const history = (revisionData as TradeRevisionHistory)?.revisions;
      setRevisions(Array.isArray(history) ? history : []);
    } catch (cause) {
      if (!controller.signal.aborted) {
        setLoadError(cause instanceof Error ? cause.message : t("journal_edit.load_failed"));
      }
    } finally {
      if (!controller.signal.aborted) setIsLoading(false);
      if (loadRef.current === controller) loadRef.current = null;
    }
  }, [applyTracking, applyTrade, t, tradeId]);

  useEffect(() => {
    void load();
    return () => {
      loadRef.current?.abort();
      loadRef.current = null;
    };
  }, [load]);

  const hasClosures = Boolean(tracking?.closures?.length);
  const status = trade?.status || "OPEN";
  const statusChange = statusSelection !== status;
  const closingFromHere = statusSelection === "CLOSED" && status !== "CLOSED";
  const showExitFields = statusSelection === "CLOSED";
  // Canceling a completed trade only takes a status (+note) change.
  const notesOnly = status === "CLOSED" && statusSelection === "CANCELED";
  // Entry/size/time/leverage are final once a trade is completed; a correction
  // can still amend notes, the quantity unit and the user-reported exit.
  const completedLocked = statusSelection === "CLOSED";
  const sizeLocked = statusSelection === "OPEN" && hasClosures;

  const sizing = useMemo(() => trade ? positionSizing({
    symbol: trade.symbol,
    positionType: (trade.position_type || "UNKNOWN") as "SPOT" | "LONG" | "SHORT" | "UNKNOWN",
    side: trade.side,
    entryPrice: Number(entryPrice),
    qty: Number(qty),
    leverage: leverage === "" ? null : Number(leverage),
    exitPrice: trade.exit_price != null ? Number(trade.exit_price) : null,
    qtyUnit,
    serverVerified,
  }) : null, [trade, entryPrice, qty, leverage, qtyUnit, serverVerified]);

  const refreshPrice = async () => {
    if (quoteBusy) return;
    setQuoteBusy(true);
    setQuoteError(null);
    try {
      const response = await apiFetch(apiUrl("/api/v1/trades/quotes/refresh"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ trade_ids: [tradeId] }),
      });
      const data: unknown = await response.json();
      const quotes = (data as { quotes?: Record<string, TradeQuote> })?.quotes;
      if (!response.ok || !quotes || !quotes[tradeId]) throw new Error(t("journal_edit.refresh_failed"));
      setQuote(quotes[tradeId]);
    } catch (cause) {
      setQuoteError(cause instanceof Error ? cause.message : t("journal_edit.refresh_failed"));
    } finally {
      setQuoteBusy(false);
    }
  };

  const save = async () => {
    if (!trade || isSaving) return;
    const originalEntryInput = trade.entry_time ? utcIsoToIstanbulInput(trade.entry_time) || "" : "";
    const entryTimeDirty = entryTime !== originalEntryInput;
    if (!completedLocked && entryTimeDirty && !(entryTime && istanbulInputToUtcIso(entryTime))) {
      setSaveError(t("journal_edit.reason_time_invalid"));
      return;
    }
    if (entryPrice !== "" && Number(entryPrice) <= 0) {
      setSaveError(t("order_ticket.errors.entry_required"));
      return;
    }
    if (qty !== "" && Number(qty) <= 0) {
      setSaveError(t("order_ticket.errors.qty_required"));
      return;
    }
    if (entryTime && isFutureIstanbulInput(entryTime)) {
      setSaveError(t("order_ticket.errors.time_future"));
      return;
    }
    const changes: Record<string, unknown> = {};
    if (statusChange) changes.status = statusSelection;
    if (showExitFields) {
      const exitValue = Number(exitPrice);
      const exitTimeIso = exitTime ? istanbulInputToUtcIso(exitTime) : null;
      if (!Number.isFinite(exitValue) || exitValue <= 0 || !exitTimeIso) {
        setSaveError(t("journal_edit.reason_exit_required"));
        return;
      }
      const storedExit = trade.exit_price != null ? Number(trade.exit_price) : null;
      const storedExitIso = trade.exit_time ? new Date(trade.exit_time).toISOString() : null;
      if (closingFromHere || exitValue !== storedExit || exitTimeIso !== storedExitIso) {
        changes.exit_price = exitValue;
        changes.exit_time = exitTimeIso;
      }
    }
    const nextEntryTimeIso = entryTime ? istanbulInputToUtcIso(entryTime) : null;
    if (!completedLocked && !sizeLocked) {
      if (Number(entryPrice) !== Number(trade.entry_price)) changes.entry_price = Number(entryPrice);
      if (Number(qty) !== Number(trade.qty)) changes.qty = Number(qty);
      const nextLeverage = leverage === "" ? null : Number(leverage);
      const currentLeverage = trade.leverage ?? null;
      if (nextLeverage !== currentLeverage) changes.leverage = nextLeverage;
    }
    if (!completedLocked && entryTimeDirty && nextEntryTimeIso) {
      // A minute-precision comparison: an unrelated save never rewrites the
      // stored seconds of the entry timestamp.
      changes.entry_time = nextEntryTimeIso;
    }
    if (!notesOnly && qtyUnit !== (trade.qty_unit === "BASE" ? "BASE" : "UNKNOWN")) {
      changes.qty_unit = qtyUnit;
    }
    if (!notesOnly && !tracking) {
      // The single stop/target fields are only authoritative when no local
      // plan exists; with a plan the plan editor below owns them.
      const nextStop = stopLoss === "" ? null : Number(stopLoss);
      const currentStop = trade.stop_loss ?? null;
      if (nextStop !== currentStop) changes.stop_loss = nextStop;
      const nextTarget = takeProfit === "" ? null : Number(takeProfit);
      const currentTarget = trade.take_profit ?? null;
      if (nextTarget !== currentTarget) changes.take_profit = nextTarget;
    }
    if ((notes || "") !== (trade.notes || "")) changes.notes = notes;

    if (tracking && statusSelection === "OPEN") {
      const planStopValue = planStop === "" ? null : Number(planStop);
      const currentPlanStop = tracking.stop_loss == null ? null : Number(tracking.stop_loss);
      const currentTargets = tracking.targets.map((target) => ({
        price: String(target.price),
        percent: String(target.percent),
      }));
      const nextTargets = planTargets.map((target) => ({ price: String(target.price), percent: String(target.percent) }));
      const targetsChanged = JSON.stringify(nextTargets) !== JSON.stringify(currentTargets);
      const stopChanged = planStopValue !== currentPlanStop;
      const enabledChanged = planEnabled !== tracking.enabled;
      if (targetsChanged || stopChanged || enabledChanged) {
        if (!validTargets(planTargets, Number(entryPrice), trade.side, planStopValue)) {
          setPlanError(t("tracking.invalid"));
          return;
        }
        changes.local_tracking = {
          expected_revision: tracking.revision,
          enabled: planEnabled,
          source_id: tracking.source_id,
          source_symbol: tracking.source_symbol,
          stop_loss: planStopValue,
          targets: targetPayload(planTargets),
        };
      }
    }

    if (Object.keys(changes).length === 0) {
      setNotice(t("journal_edit.no_changes"));
      return;
    }
    changes.expected_revision = trade.revision ?? 1;
    setIsSaving(true);
    setSaveError(null);
    setConflict(false);
    setNotice(null);
    try {
      const response = await apiFetch(apiUrl(`/api/v1/trades/${encodeURIComponent(tradeId)}`), {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(changes),
      });
      const data: unknown = await response.json();
      if (response.status === 409) {
        setConflict(true);
        setSaveError(t("journal_edit.reason_revision_conflict"));
        return;
      }
      if (!response.ok) {
        const detail = (data as { detail?: unknown })?.detail;
        let message = t("journal_edit.save_failed");
        if (detail && typeof detail === "object") {
          const reason = String((detail as { reason?: unknown }).reason || "");
          const backendMessage = String((detail as { message?: unknown }).message || "");
          const mapped = REASON_KEYS[reason] ? t(REASON_KEYS[reason]) : "";
          message = mapped || backendMessage || message;
        } else if (typeof detail === "string") {
          message = detail;
        }
        setSaveError(message);
        return;
      }
      const saved = (data as { trade?: unknown })?.trade;
      if (!isTrade(saved)) {
        setSaveError(t("journal_edit.save_failed"));
        return;
      }
      applyTrade(saved);
      const savedTracking = (data as { tracking?: unknown })?.tracking;
      if (savedTracking === null || isTrackingState(savedTracking)) applyTracking(savedTracking);
      onSaved?.(saved);
      setNotice(t("journal_edit.saved"));
      void load();
    } catch (cause) {
      setSaveError(cause instanceof Error ? cause.message : t("journal_edit.save_failed"));
    } finally {
      setIsSaving(false);
    }
  };

  const quoteView = quote && (() => {
    if (quote.price == null) {
      return (
        <span className="text-amber-300">
          {t("journal_edit.quote_unavailable")}
          {quote.last_known && (
            <span className="block k-help">
              {t("journal_edit.quote_last_known", {
                price: quote.last_known.price,
                time: formatIstanbulDateTime(quote.last_known.observed_at),
              })}
            </span>
          )}
        </span>
      );
    }
    return (
      <span className="text-slate-100">
        <span className="font-semibold">{quote.price}</span>
        <span className="ml-2 text-accent">{quote.quote_status}</span>
        <span className="ml-2 k-help">{formatIstanbulDateTime(quote.observed_at)}</span>
      </span>
    );
  })();

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" role="presentation">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="trade-edit-title"
        data-testid="trade-edit-modal"
        onKeyDown={(event) => {
          if (event.key === "Escape") {
            event.preventDefault();
            onClose();
          }
        }}
        className="bg-[#111722] border border-surface-border rounded-xl w-full max-w-2xl p-5 shadow-2xl flex flex-col max-h-[92vh]"
      >
        <div className="flex items-center justify-between border-b border-surface-border pb-3">
          <h3 id="trade-edit-title" className="text-lg font-bold text-white flex items-center gap-2">
            <Pencil className="w-5 h-5 text-accent" />
            {t("journal_edit.title", { symbol: trade?.symbol || tradeId })}
          </h3>
          <button type="button" onClick={onClose} aria-label={t("journal_edit.cancel")} className="text-slate-400 hover:text-white p-2 -m-1">
            <X className="w-5 h-5" />
          </button>
        </div>

        {isLoading && <p role="status" className="mt-4 k-help">{t("journal_edit.loading")}</p>}
        {loadError && (
          <div role="alert" className="mt-4 rounded border border-loss/40 bg-loss/10 p-3 text-loss text-sm">
            {loadError}
            <button type="button" onClick={() => void load()} className="ml-2 underline">{t("journal_edit.reload")}</button>
          </div>
        )}

        {trade && !isLoading && (
          <div className="mt-4 space-y-4 overflow-y-auto pr-1">
            {notesOnly && (
              <p role="status" data-testid="trade-edit-closed-notice" className="rounded border border-amber-400/40 bg-amber-950/20 p-3 text-sm text-amber-200">
                {t("journal_edit.reason_closed_notes_only")}
              </p>
            )}
            {status === "CLOSED" && !statusChange && (
              <p role="status" data-testid="trade-edit-completed-notice" className="rounded border border-surface-border bg-[#0b0e14] p-3 text-sm text-slate-300">
                {t("journal_edit.completed_correction_notice")}
              </p>
            )}
            {status === "CLOSED" && statusSelection === "OPEN" && (
              <p role="status" data-testid="trade-edit-reopen-notice" className="rounded border border-amber-400/40 bg-amber-950/20 p-3 text-sm text-amber-200">
                {t("journal_edit.reopen_notice")}
              </p>
            )}
            {sizeLocked && (
              <p role="status" className="rounded border border-amber-400/40 bg-amber-950/20 p-3 text-sm text-amber-200">
                {t("journal_edit.reason_partial_close_locked")}
              </p>
            )}

            <section className="k-card space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <span className="text-base font-semibold text-white">{trade.symbol}</span>
                  <span className="ml-2 rounded bg-[#1a2234] px-2 py-0.5 text-sm text-slate-300">
                    {trade.position_type === "SPOT" ? t("order_ticket.side_spot") : trade.side}
                  </span>
                  <span className="ml-2 rounded bg-[#1a2234] px-2 py-0.5 text-sm text-slate-300">{trade.status}</span>
                </div>
                <div className="text-right k-help">
                  <span className="block">{t("journal_edit.revision", { value: trade.revision ?? 1 })}</span>
                  {trade.tracking_started_at && (
                    <span className="block">{t("journal_edit.tracking_started", { time: formatIstanbulDateTime(trade.tracking_started_at) })}</span>
                  )}
                </div>
              </div>

              <div>
                <span className="k-label">{t("journal_edit.status_label")}</span>
                <div className="grid grid-cols-3 gap-2 mt-1" role="group" aria-label={t("journal_edit.status_label")} data-testid="trade-edit-status">
                  <button
                    type="button"
                    data-testid="trade-edit-status-open"
                    aria-pressed={statusSelection === "OPEN"}
                    onClick={() => { setStatusSelection("OPEN"); setSaveError(null); }}
                    className={`k-btn justify-center ${statusSelection === "OPEN" ? "bg-accent/20 text-accent border border-accent/40" : "bg-[#1a2234] text-slate-300"}`}
                  >
                    {t("journal_edit.status_open")}
                  </button>
                  <button
                    type="button"
                    data-testid="trade-edit-status-closed"
                    aria-pressed={statusSelection === "CLOSED"}
                    onClick={() => { setStatusSelection("CLOSED"); setSaveError(null); }}
                    className={`k-btn justify-center ${statusSelection === "CLOSED" ? "bg-accent/20 text-accent border border-accent/40" : "bg-[#1a2234] text-slate-300"}`}
                  >
                    {t("journal_edit.status_closed")}
                  </button>
                  <button
                    type="button"
                    data-testid="trade-edit-status-canceled"
                    aria-pressed={statusSelection === "CANCELED"}
                    onClick={() => { setStatusSelection("CANCELED"); setSaveError(null); }}
                    className={`k-btn justify-center ${statusSelection === "CANCELED" ? "bg-loss/20 text-loss border border-loss/40" : "bg-[#1a2234] text-slate-300"}`}
                  >
                    {t("journal_edit.status_canceled")}
                  </button>
                </div>
                <p className="k-help">{t("journal_edit.status_help")}</p>
                {showExitFields && (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-2 rounded border border-surface-border bg-[#0b0e14] p-3">
                    <label className="block">
                      <span className="k-label">{t("order_ticket.exit_price_label")}</span>
                      <input
                        type="number" step="any" min="0" data-testid="trade-edit-exit-price"
                        value={exitPrice}
                        onChange={(e) => { setExitPrice(e.target.value); setSaveError(null); }}
                        className="k-input mt-1" aria-label={t("order_ticket.exit_price_label")}
                      />
                    </label>
                    <label className="block">
                      <span className="k-label">{t("order_ticket.exit_time_label")}</span>
                      <input
                        type="datetime-local" data-testid="trade-edit-exit-time"
                        value={exitTime}
                        onChange={(e) => { setExitTime(e.target.value); setSaveError(null); }}
                        className="k-input mt-1" aria-label={t("order_ticket.exit_time_label")}
                      />
                      <span className="k-help">{t("order_ticket.turkey_time")}</span>
                    </label>
                  </div>
                )}
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <label className="block">
                  <span className="k-label">{t("order_ticket.entry_label")}</span>
                  <input
                    type="number" step="any" min="0" data-testid="trade-edit-entry"
                    value={entryPrice} disabled={completedLocked || sizeLocked}
                    autoFocus={!completedLocked && !sizeLocked}
                    onChange={(e) => setEntryPrice(e.target.value)}
                    className="k-input mt-1" aria-label={t("order_ticket.entry_label")}
                  />
                </label>
                <label className="block">
                  <span className="k-label">{t("order_ticket.qty_label")}</span>
                  <input
                    type="number" step="any" min="0" data-testid="trade-edit-qty"
                    value={qty} disabled={completedLocked || sizeLocked}
                    onChange={(e) => setQty(e.target.value)}
                    className="k-input mt-1" aria-label={t("order_ticket.qty_label")}
                  />
                </label>
                <label className="block">
                  <span className="k-label">{t("order_ticket.trade_time_label")}</span>
                  <input
                    type="datetime-local" data-testid="trade-edit-entry-time"
                    value={entryTime} disabled={completedLocked}
                    onChange={(e) => setEntryTime(e.target.value)}
                    className="k-input mt-1" aria-label={t("order_ticket.trade_time_label")}
                  />
                  <span className="k-help">{t("order_ticket.turkey_time")}</span>
                </label>
                <label className="block">
                  <span className="k-label">{t("order_ticket.leverage_label")}</span>
                  <input
                    type="number" step="any" min="1" max="1000" data-testid="trade-edit-leverage"
                    value={leverage} disabled={completedLocked || trade.position_type === "SPOT" || sizeLocked}
                    onChange={(e) => setLeverage(e.target.value)}
                    className="k-input mt-1" aria-label={t("order_ticket.leverage_label")}
                  />
                </label>
                {!tracking && (
                  <>
                    <label className="block">
                      <span className="k-label">{t("order_ticket.sl_label")}</span>
                      <input
                        type="number" step="any" min="0" data-testid="trade-edit-stop"
                        value={stopLoss} disabled={completedLocked}
                        onChange={(e) => setStopLoss(e.target.value)}
                        className="k-input mt-1 text-loss" aria-label={t("order_ticket.sl_label")}
                      />
                    </label>
                    <label className="block">
                      <span className="k-label">{t("order_ticket.tp_label")}</span>
                      <input
                        type="number" step="any" min="0" data-testid="trade-edit-target"
                        value={takeProfit} disabled={completedLocked}
                        onChange={(e) => setTakeProfit(e.target.value)}
                        className="k-input mt-1 text-gain" aria-label={t("order_ticket.tp_label")}
                      />
                    </label>
                  </>
                )}
              </div>

              {tracking && statusSelection === "OPEN" && (
                <section className="rounded border border-surface-border bg-[#0b0e14] p-3 space-y-3" data-testid="trade-edit-plan">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="k-section-title">{t("journal_edit.plan_section")}</span>
                    <span className="k-help">
                      {t("journal_edit.revision", { value: tracking.revision })}
                      {hasClosures && <span> · {t("journal_edit.plan_locked_note")}</span>}
                    </span>
                  </div>
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={planEnabled}
                      disabled={notesOnly}
                      onChange={(e) => { setPlanEnabled(e.target.checked); setPlanError(null); }}
                    />
                    {t("tracking.enabled")}
                  </label>
                  <label className="block max-w-xs">
                    <span className="k-label">{t("tracking.stop")}</span>
                    <input
                      type="number" step="any" min="0" data-testid="trade-edit-plan-stop"
                      value={planStop} disabled={notesOnly}
                      onChange={(e) => { setPlanStop(e.target.value); setPlanError(null); }}
                      className="k-input mt-1 text-loss" aria-label={t("tracking.stop")}
                    />
                  </label>
                  <TargetPlanFields
                    targets={planTargets}
                    onChange={(next) => { setPlanTargets(next); setPlanError(null); }}
                    locked={tracking.closures.map((closure) => closure.target_id)}
                  />
                  <p className="k-help">
                    {tracking.source_id
                      ? `${t(`tracking.${tracking.source_id}`)} · ${tracking.source_symbol ?? "—"}`
                      : t("tracking.no_source")}
                    {hasClosures && <span> · {t("journal_edit.plan_source_locked")}</span>}
                  </p>
                  {planError && <p role="alert" className="k-error">{planError}</p>}
                </section>
              )}

              <label className="block">
                <span className="k-label">{t("order_ticket.notes_label")}</span>
                <textarea
                  value={notes} disabled={false} rows={2}
                  onChange={(e) => setNotes(e.target.value)}
                  className="k-input mt-1 min-h-16 py-2" aria-label={t("order_ticket.notes_label")}
                />
              </label>

              {sizing?.instrument.verification === "PROVIDER_CATALOG" ? (
                <p className="k-help text-gain" data-testid="trade-edit-verified-instrument">
                  {t("order_ticket.verification_PROVIDER_CATALOG")}
                </p>
              ) : (
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    data-testid="trade-edit-qty-unit"
                    checked={qtyUnit === "BASE"}
                    disabled={notesOnly}
                    onChange={(e) => setQtyUnit(e.target.checked ? "BASE" : "UNKNOWN")}
                  />
                  {t("order_ticket.qty_unit_base_label")}
                </label>
              )}
              {sizing && (
                <p className="k-help">
                  {t(`order_ticket.verification_${sizing.instrument.verification}`)}
                </p>
              )}

              {sizing && (
                <p className="k-help">
                  {t("journal_edit.sizing_summary", {
                    notional: formatNotional(trade.symbol, sizing.notional.value),
                    margin: formatNotional(trade.symbol, sizing.marginEstimate.value),
                    leverage: sizing.leverage.value ?? "—",
                  })}
                </p>
              )}
            </section>

            <section className="k-card space-y-2">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="k-section-title">{t("journal_edit.price_section")}</span>
                <button
                  type="button" data-testid="trade-edit-refresh-price"
                  onClick={() => void refreshPrice()} disabled={quoteBusy}
                  className="k-btn border border-surface-border text-accent hover:bg-[#1f2d47] disabled:opacity-50"
                >
                  <RefreshCw className={`w-4 h-4 ${quoteBusy ? "animate-spin" : ""}`} />
                  {t("journal_edit.refresh_price")}
                </button>
              </div>
              {quoteError && <p role="alert" className="k-error">{quoteError}</p>}
              {quoteView ? <p className="text-sm">{quoteView}</p> : <p className="k-help">{t("journal_edit.quote_not_loaded")}</p>}
              <p className="k-help">{t("journal_edit.quote_identity_notice")}</p>
            </section>

            {saveError && (
              <div role="alert" data-testid="trade-edit-error" className="rounded border border-loss/40 bg-loss/10 p-3 text-sm text-loss">
                <AlertTriangle className="inline w-4 h-4 mr-1" />
                {saveError}
                {conflict && (
                  <button type="button" data-testid="trade-edit-reload" onClick={() => void load()} className="ml-2 underline">
                    {t("journal_edit.reload")}
                  </button>
                )}
              </div>
            )}
            {notice && <p role="status" data-testid="trade-edit-notice" className="text-sm text-gain">{notice}</p>}

            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <button
                  type="button" data-testid="trade-edit-save"
                  onClick={() => void save()}
                  disabled={isSaving}
                  className="k-btn bg-accent hover:bg-sky-400 text-black disabled:opacity-50"
                >
                  {isSaving ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                  {isSaving ? t("journal_edit.saving") : t("journal_edit.save")}
                </button>
                {trade.status === "CLOSED" && onOpenReplay && (
                  <button
                    type="button" data-testid="trade-edit-replay"
                    onClick={() => onOpenReplay(trade.id)}
                    className="k-btn border border-surface-border text-slate-200 hover:bg-[#1f2d47]"
                  >
                    <PlayCircle className="w-4 h-4 text-accent" />
                    {t("journal_edit.open_replay")}
                  </button>
                )}
              </div>
              <button type="button" onClick={onClose} className="k-btn border border-surface-border text-slate-300 hover:bg-[#1f2d47]">
                {t("journal_edit.cancel")}
              </button>
            </div>

            <section className="k-card">
              <button
                type="button"
                className="flex w-full items-center justify-between text-left"
                onClick={() => setShowHistory((current) => !current)}
                aria-expanded={showHistory}
              >
                <span className="k-section-title flex items-center gap-2">
                  <History className="w-4 h-4 text-accent" />
                  {t("journal_edit.history_title")}
                </span>
                <ChevronDown className={`w-4 h-4 transition ${showHistory ? "rotate-180" : ""}`} />
              </button>
              {showHistory && (
                <div className="mt-2 space-y-2" data-testid="trade-edit-revisions">
                  {revisions.length === 0 && <p className="k-help">{t("journal_edit.history_empty")}</p>}
                  {revisions.map((revision) => (
                    <div key={revision.event_id} className="rounded border border-surface-border p-2 text-sm">
                      <div className="flex justify-between">
                        <span className="font-semibold">{t("journal_edit.revision", { value: revision.revision ?? "?" })}</span>
                        <span className="k-help">{formatIstanbulDateTime(revision.occurred_at_utc)}</span>
                      </div>
                      {Object.entries(revision.changed_fields).map(([field, change]) => (
                        <p key={field} className="k-help">
                          {t(`journal_edit.field_${field}`)}: <span className="text-slate-400">{String(change.from ?? "—")}</span>
                          {" → "}<span className="text-slate-200">{String(change.to ?? "—")}</span>
                        </p>
                      ))}
                    </div>
                  ))}
                </div>
              )}
            </section>
          </div>
        )}
      </div>
    </div>
  );
};
