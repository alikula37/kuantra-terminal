import React, { useState, useEffect, useCallback, useRef } from "react";
import { useTradeStore } from "../stores/tradeStore";
import { Filter, Plus, Pencil, BookOpen, Upload, FileCheck2, ClipboardCheck, CalendarClock, Trash2, RefreshCw, ChevronDown, Download, CandlestickChart } from "lucide-react";
import { useTranslation } from "../context/I18nContext";
import { apiFetch, apiUrl } from "../lib/backend";
import { TradeEvidencePanel } from "./TradeEvidencePanel";
import { ReconciliationInbox } from "./ReconciliationInbox";
import { WeeklyReviewPanel } from "./WeeklyReviewPanel";
import { useOpenQuoteRefresh, quoteAgeSeconds } from "../hooks/useOpenQuoteRefresh";
import { formatIstanbulDateTime, istanbulDateKey, relativeAgeLabel } from "../lib/tradeTime";
import { JournalExportModal } from "./modals/JournalExportModal";
import { formatPrice } from "../lib/positionMath";
import type { Trade, TradeQuote } from "../types";

interface MultiSelectFilterProps {
  label: string;
  testId: string;
  options: { value: string; label: string }[];
  selected: string[];
  onChange: (next: string[]) => void;
}

const MultiSelectFilter: React.FC<MultiSelectFilterProps> = ({
  label,
  testId,
  options,
  selected,
  onChange,
}) => {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, [open]);

  const toggleOption = (value: string) => {
    onChange(selected.includes(value) ? selected.filter((item) => item !== value) : [...selected, value]);
  };

  return (
    <div
      ref={containerRef}
      className="relative flex items-center gap-2 bg-[#111722] px-3 py-1 rounded border border-surface-border"
    >
      <Filter className="w-4 h-4 text-slate-400" />
      <button
        type="button"
        data-testid={testId}
        aria-label={label}
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
        className="flex items-center gap-1 bg-transparent text-white text-sm py-2 focus:outline-none"
      >
        <span>
          {selected.length > 0
            ? `${label}: ${t("journal.filter_selected_count", { count: selected.length })}`
            : label}
        </span>
        <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
      </button>
      {open && (
        <div
          data-testid={`${testId}-panel`}
          className="absolute left-0 top-full z-30 mt-1 w-56 rounded border border-surface-border bg-elevated p-2 shadow-lg"
        >
          <button
            type="button"
            data-testid={`${testId}-clear`}
            onClick={() => onChange([])}
            className="w-full rounded px-2 py-1 text-left text-sm text-muted hover:bg-hover"
          >
            {t("journal.filter_clear")}
          </button>
          {options.map((option) => (
            <label
              key={option.value}
              className="flex items-center gap-2 rounded px-2 py-1 text-sm text-ink hover:bg-hover"
            >
              <input
                type="checkbox"
                data-testid={`${testId}-option-${option.value}`}
                checked={selected.includes(option.value)}
                onChange={() => toggleOption(option.value)}
              />
              <span>{option.label}</span>
            </label>
          ))}
        </div>
      )}
    </div>
  );
};

interface JournalViewProps {
  onOpenNewTrade: () => void;
  onOpenCsvImport?: () => void;
  onEditTrade?: (tradeId: string) => void;
  onOpenReplay?: (tradeId: string) => void;
  refreshNonce?: number;
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

const LOCAL_TRACKING_STATUSES = new Set(["ACTIVE", "WAITING_QUOTE", "WAITING_TARGETS", "PAUSED", "COMPLETED", "UNKNOWN"]);

function isTrade(value: unknown): value is Trade {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Record<string, unknown>;
  const optionalNumbers = ["exit_price", "pnl", "r_multiple", "commission", "unrealized_pnl", "current_price", "leverage"];
  return typeof candidate.id === "string"
    && typeof candidate.symbol === "string"
    && (candidate.side === "BUY" || candidate.side === "SELL" || candidate.side === "LONG" || candidate.side === "SHORT")
    && isFiniteNumber(candidate.entry_price)
    && isFiniteNumber(candidate.qty)
    && typeof candidate.entry_time === "string"
    && (candidate.status === "OPEN" || candidate.status === "CLOSED" || candidate.status === "CANCELED")
    && optionalNumbers.every((field) => candidate[field] === undefined || candidate[field] === null || isFiniteNumber(candidate[field]));
}

async function readTradeList(response: Response): Promise<Trade[]> {
  if (!response.ok) {
    let detail = "";
    try {
      const payload = await response.json() as { detail?: unknown };
      if (typeof payload.detail === "string") detail = payload.detail;
    } catch {
      // Keep the HTTP status as the bounded error when the body is not JSON.
    }
    throw new Error(detail || `Trade list request failed (HTTP ${response.status})`);
  }
  const payload = await response.json();
  if (!Array.isArray(payload) || !payload.every(isTrade)) {
    throw new Error("Trade list response was malformed");
  }
  return payload;
}

export const JournalView: React.FC<JournalViewProps> = ({ onOpenNewTrade, onOpenCsvImport, onEditTrade, onOpenReplay, refreshNonce = 0 }) => {
  const { t, locale } = useTranslation();
  const { trades, setTrades, openPositions, updatePositionPnl } = useTradeStore();
  const [filterSymbols, setFilterSymbols] = useState<string[]>([]);
  const [filterStatuses, setFilterStatuses] = useState<string[]>([]);
  const [filterDateFrom, setFilterDateFrom] = useState<string>("");
  const [filterDateTo, setFilterDateTo] = useState<string>("");
  const [exportOpen, setExportOpen] = useState(false);
  const [evidenceTradeId, setEvidenceTradeId] = useState<string | null>(null);
  const [reconciliationInboxOpen, setReconciliationInboxOpen] = useState(false);
  const [weeklyReviewOpen, setWeeklyReviewOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [loadMoreError, setLoadMoreError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cancelled, setCancelled] = useState(false);
  const [cancellationTarget, setCancellationTarget] = useState<Trade | null>(null);
  const [cancellingTradeId, setCancellingTradeId] = useState<string | null>(null);
  const [cancellationError, setCancellationError] = useState<string | null>(null);
  const [cancellationNotice, setCancellationNotice] = useState<string | null>(null);
  const [trackingByTrade, setTrackingByTrade] = useState<Record<string, Record<string, unknown>>>({});
  const loadControllerRef = useRef<AbortController | null>(null);
  const requestIdRef = useRef(0);

  // Local tracking status is a separate row annotation: it is an estimate, not
  // the external trade's lifecycle state, and the journal never rewrites one
  // into the other.
  const loadLocalTracking = useCallback(async () => {
    try {
      const response = await apiFetch(apiUrl("/api/v1/local-tracking"));
      if (!response.ok) return;
      const payload: unknown = await response.json();
      if (!Array.isArray(payload)) return;
      const next: Record<string, Record<string, unknown>> = {};
      for (const view of payload) {
        if (view && typeof view === "object" && typeof (view as Record<string, unknown>).trade_id === "string") {
          next[String((view as Record<string, unknown>).trade_id)] = view as Record<string, unknown>;
        }
      }
      setTrackingByTrade(next);
    } catch {
      // The row stays without the local annotation; no invented status.
    }
  }, []);

  const hasOpenTrades = trades.some((trade) => trade.status === "OPEN");
  const {
    quotes,
    refresh: refreshQuotes,
    busy: quoteBusy,
    error: quoteError,
    lastSuccessAt,
    lastAttemptAt,
    nowMs,
  } = useOpenQuoteRefresh(hasOpenTrades);

  const loadTrades = useCallback(async () => {
    loadControllerRef.current?.abort();
    const controller = new AbortController();
    const requestId = ++requestIdRef.current;
    loadControllerRef.current = controller;
    setIsLoading(true);
    setError(null);
    setLoadMoreError(null);
    setCancelled(false);
    setHasMore(false);

    try {
      const nextTrades = await apiFetch(apiUrl("/api/v1/trades?limit=201&offset=0"), { signal: controller.signal }).then(readTradeList);
      if (controller.signal.aborted || requestId !== requestIdRef.current) return;
      setTrades(nextTrades.slice(0, 200));
      setHasMore(nextTrades.length > 200);
      void loadLocalTracking();
    } catch (cause) {
      if (controller.signal.aborted || requestId !== requestIdRef.current) return;
      console.warn("[JournalView] Failed to fetch trade list:", cause);
      setError(cause instanceof Error ? cause.message : t("journal.error"));
    } finally {
      if (requestId === requestIdRef.current) {
        setIsLoading(false);
        loadControllerRef.current = null;
      }
    }
  }, [setTrades, t, loadLocalTracking]);

  const loadMoreTrades = async () => {
    if (!hasMore || isLoadingMore || isLoading) return;
    const controller = new AbortController();
    const requestId = ++requestIdRef.current;
    loadControllerRef.current = controller;
    setIsLoadingMore(true);
    setLoadMoreError(null);
    try {
      const nextTrades = await apiFetch(apiUrl(`/api/v1/trades?limit=201&offset=${trades.length}`), { signal: controller.signal }).then(readTradeList);
      if (controller.signal.aborted || requestId !== requestIdRef.current) return;
      const knownIds = new Set(trades.map((trade) => trade.id));
      const uniqueTrades = nextTrades.slice(0, 200).filter((trade) => !knownIds.has(trade.id));
      setTrades([...trades, ...uniqueTrades]);
      setHasMore(nextTrades.length > 200);
    } catch (cause) {
      if (controller.signal.aborted || requestId !== requestIdRef.current) return;
      console.warn("[JournalView] Failed to load more trades:", cause);
      setLoadMoreError(cause instanceof Error ? cause.message : t("journal.error"));
    } finally {
      if (requestId === requestIdRef.current) {
        setIsLoadingMore(false);
        loadControllerRef.current = null;
      }
    }
  };

  useEffect(() => {
    void loadTrades();
    return () => {
      requestIdRef.current += 1;
      loadControllerRef.current?.abort();
      loadControllerRef.current = null;
    };
  }, [loadTrades, refreshNonce]);

  const cancelLoad = () => {
    const controller = loadControllerRef.current;
    if (!controller) return;
    requestIdRef.current += 1;
    controller.abort();
    loadControllerRef.current = null;
    setIsLoading(false);
    setCancelled(true);
    setError(t("journal.cancelled"));
  };

  const cancelTrade = async () => {
    const target = cancellationTarget;
    if (!target || cancellingTradeId) return;

    setCancellingTradeId(target.id);
    setCancellationError(null);
    setCancellationNotice(null);

    try {
      const response = await apiFetch(apiUrl(`/api/v1/trades/${encodeURIComponent(target.id)}`), { method: "DELETE" });
      let payload: unknown = null;
      try {
        payload = await response.json();
      } catch {
        // The bounded error below explains the malformed or empty response.
      }

      const payloadRecord = payload && typeof payload === "object" ? payload as Record<string, unknown> : null;
      if (!response.ok) {
        const detail = payloadRecord && typeof payloadRecord.detail === "string" ? payloadRecord.detail : "";
        throw new Error(detail || `Trade cancellation failed (HTTP ${response.status})`);
      }

      const canceledTrade = payloadRecord?.trade;
      if (!isTrade(canceledTrade) || canceledTrade.id !== target.id || canceledTrade.status !== "CANCELED") {
        throw new Error("Trade cancellation response was malformed");
      }

      // Keep the canonical row visible as a tombstone; the evidence chain is never physically deleted.
      setTrades(trades.map((trade) => trade.id === target.id ? canceledTrade : trade));
      if (target.status === "OPEN") {
        updatePositionPnl(openPositions.filter((position) => position.id !== target.id));
      }
      setCancellationTarget(null);
      setCancellationNotice(t("journal.cancel_success"));
    } catch (cause) {
      console.warn("[JournalView] Failed to cancel trade:", cause);
      setCancellationError(cause instanceof Error ? cause.message : t("journal.cancel_failed"));
    } finally {
      setCancellingTradeId(null);
    }
  };

  const filteredTrades = trades.filter((trade) => {
    if (filterSymbols.length > 0 && !filterSymbols.includes(trade.symbol)) return false;
    if (filterStatuses.length > 0 && !filterStatuses.includes(trade.status)) return false;
    const dayKey = istanbulDateKey(trade.entry_time);
    if (filterDateFrom && (!dayKey || dayKey < filterDateFrom)) return false;
    if (filterDateTo && (!dayKey || dayKey > filterDateTo)) return false;
    return true;
  });

  const symbols = Array.from(new Set(trades.map((trade) => trade.symbol))).sort();

  const renderSimulationBadge = (trade: Trade) => trade.record_mode === "SIMULATION" ? (
    <span
      data-testid={`journal-sim-badge-${trade.id}`}
      className="ml-2 align-middle px-2 py-0.5 rounded text-sm font-bold bg-amber-400/15 text-amber-300 border border-amber-400/40"
    >
      {t("journal.simulation_badge")}
    </span>
  ) : null;

  const renderLocalTracking = (trade: Trade) => {
    const view = trackingByTrade[trade.id];
    const rawStatus = view && typeof view.tracking_status === "string" ? view.tracking_status : null;
    if (!rawStatus) return null;
    const status = LOCAL_TRACKING_STATUSES.has(rawStatus) ? rawStatus : "UNKNOWN";
    const rawRemaining = view.remaining_qty;
    const remaining = rawRemaining == null || rawRemaining === "" ? "—" : String(rawRemaining);
    return (
      <span
        className="mt-1 block leading-tight"
        data-testid={`journal-local-tracking-${trade.id}`}
        data-tracking-status={status}
      >
        <span className="block text-sm text-slate-400 whitespace-nowrap">
          {t(`journal.local_status_${status.toLowerCase()}`, { remaining })}
        </span>
        {status === "COMPLETED" && trade.status === "OPEN" && (
          <span className="block text-sm text-amber-300" data-testid={`journal-local-completed-note-${trade.id}`}>
            {t("journal.local_completed_external_open")}
          </span>
        )}
      </span>
    );
  };

  const renderQuote = (trade: Trade) => {
    if (trade.status !== "OPEN") return <span className="text-slate-500">—</span>;
    const quote: TradeQuote | undefined = quotes[trade.id];
    if (!quote) return <span className="k-help">{t("journal.quote_pending")}</span>;
    const live = quote.price != null;
    const stale = quote.last_known?.stale === true;
    const age = quoteAgeSeconds(quote, nowMs);
    return (
      <div className="leading-tight">
        {live ? (
          <span className="font-semibold text-slate-100">{formatPrice(trade.symbol, quote.price)}</span>
        ) : (
          <span className="font-semibold text-amber-300">{t("journal.quote_unavailable")}</span>
        )}
        <span className={`ml-2 text-sm ${live ? (quote.quote_status === "LIVE" ? "text-gain" : "text-amber-300") : "text-loss"}`}>
          {quote.quote_status}
          {age != null && <span className="ml-1 text-slate-400">· {relativeAgeLabel(age)}</span>}
        </span>
        {stale && quote.last_known && (
          <span className="block k-help text-amber-300">
            {t("journal.quote_last_known", {
              price: formatPrice(trade.symbol, quote.last_known.price),
              time: formatIstanbulDateTime(quote.last_known.observed_at, locale),
            })}
          </span>
        )}
        {quote.observed_at && !stale && (
          <span className="block k-help">{formatIstanbulDateTime(quote.observed_at, locale)}</span>
        )}
      </div>
    );
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-[#0b0e14] overflow-hidden p-4 select-none font-sans">
      <div className="flex flex-wrap items-center justify-between gap-3 pb-4 border-b border-surface-border">
        <div>
          <h2 className="text-lg font-bold text-white">{t("journal.title")}</h2>
          <p className="k-help">{t("journal.subtitle")}</p>
        </div>

        <div className="flex flex-wrap items-center gap-2 text-sm">
          <MultiSelectFilter
            label={t("journal.filter_all_symbols")}
            testId="journal-filter-symbols"
            options={symbols.map((symbol) => ({ value: symbol, label: symbol }))}
            selected={filterSymbols}
            onChange={setFilterSymbols}
          />

          <MultiSelectFilter
            label={t("journal.filter_all_status")}
            testId="journal-filter-statuses"
            options={[
              { value: "OPEN", label: t("journal.status_open") },
              { value: "CLOSED", label: t("journal.status_closed") },
              { value: "CANCELED", label: t("journal.status_canceled") },
            ]}
            selected={filterStatuses}
            onChange={setFilterStatuses}
          />

          <div className="flex items-center gap-1 bg-[#111722] px-3 py-1 rounded border border-surface-border">
            <input
              type="date"
              value={filterDateFrom}
              onChange={(e) => setFilterDateFrom(e.target.value)}
              aria-label={t("journal.filter_date_from")}
              className="bg-transparent text-white focus:outline-none text-sm py-2"
            />
            <span className="text-slate-500">–</span>
            <input
              type="date"
              value={filterDateTo}
              onChange={(e) => setFilterDateTo(e.target.value)}
              aria-label={t("journal.filter_date_to")}
              className="bg-transparent text-white focus:outline-none text-sm py-2"
            />
            <span className="k-help">{t("order_ticket.turkey_time")}</span>
          </div>

          <button
            type="button"
            data-testid="journal-refresh-all"
            onClick={() => void refreshQuotes()}
            disabled={quoteBusy || !hasOpenTrades}
            className="k-btn border border-surface-border bg-[#162032] hover:bg-[#1f2d47] text-slate-200 disabled:opacity-50"
            title={t("journal.refresh_all_title")}
          >
            <RefreshCw className={`w-4 h-4 text-accent ${quoteBusy ? "animate-spin" : ""}`} />
            <span>{quoteBusy ? t("journal.refresh_busy") : t("journal.refresh_all")}</span>
          </button>

          <button
            type="button"
            data-testid="journal-export-open"
            onClick={() => setExportOpen(true)}
            className="k-btn border border-surface-border bg-[#162032] hover:bg-[#1f2d47] text-slate-200"
          >
            <Download className="w-4 h-4 text-accent" />
            <span>{t("journal.export")}</span>
          </button>

          <button
            onClick={onOpenCsvImport}
            className="k-btn border border-surface-border bg-[#162032] hover:bg-[#1f2d47] text-slate-200"
          >
            <Upload className="w-4 h-4 text-accent" />
            <span>{t("journal.import_csv")}</span>
          </button>

          <button
            onClick={() => setReconciliationInboxOpen(true)}
            className="k-btn border border-amber-400/40 bg-[#162032] hover:bg-[#1f2d47] text-amber-300"
          >
            <ClipboardCheck className="w-4 h-4" />
            <span>{t("journal.reconciliation_inbox")}</span>
          </button>

          <button
            onClick={() => setWeeklyReviewOpen(true)}
            className="k-btn border border-accent/40 bg-[#162032] hover:bg-[#1f2d47] text-accent"
          >
            <CalendarClock className="w-4 h-4" />
            <span>{t("journal.weekly_review")}</span>
          </button>

          <button
            onClick={onOpenNewTrade}
            className="k-btn bg-accent hover:bg-sky-400 text-black"
          >
            <Plus className="w-4 h-4" />
            <span>{t("journal.manual_entry")}</span>
          </button>
        </div>
      </div>

      {(cancellationNotice || quoteError || lastSuccessAt) && (
        <div role="status" data-testid="journal-cancel-success" className={`mt-3 rounded border px-3 py-2 text-sm ${quoteError ? "border-amber-400/40 bg-amber-950/20 text-amber-200" : "border-gain/40 bg-gain/10 text-gain"}`}>
          {quoteError && (
            <span>
              {t("journal.refresh_failed")}: {quoteError}
              {lastAttemptAt && <span className="k-help"> · {t("journal.refresh_attempt", { time: formatIstanbulDateTime(lastAttemptAt, locale) })}</span>}
              {lastSuccessAt && <span className="k-help"> · {t("journal.refresh_last_success", { time: formatIstanbulDateTime(lastSuccessAt, locale) })}</span>}
            </span>
          )}
          {cancellationNotice}
          {!quoteError && lastSuccessAt && <span className="k-help"> · {t("journal.refresh_checked", { time: formatIstanbulDateTime(lastSuccessAt, locale) })}</span>}
        </div>
      )}

      {isLoading ? (
        <div role="status" data-testid="journal-loading" className="flex-1 mt-4 rounded-lg border border-surface-border bg-[#0d121c] flex flex-col items-center justify-center p-8 text-center select-none text-slate-400 text-sm space-y-3">
          <span>{t("journal.loading")}</span>
          <button type="button" data-testid="journal-cancel" onClick={cancelLoad} className="k-btn border border-surface-border text-slate-300 hover:bg-slate-800">
            {t("journal.cancel_load")}
          </button>
        </div>
      ) : error ? (
        <div role="alert" data-testid={cancelled ? "journal-cancelled" : "journal-error"} className="flex-1 mt-4 rounded-lg border border-loss/50 bg-loss/10 flex flex-col items-center justify-center p-8 text-center select-none text-loss text-sm space-y-3">
          <span className="break-words">{error}</span>
          <button type="button" data-testid="journal-retry" onClick={() => void loadTrades()} className="k-btn border border-loss/50 text-loss font-bold hover:bg-loss/10">
            {t("journal.retry")}
          </button>
        </div>
      ) : trades.length === 0 ? (
        <div data-testid="journal-empty" className="flex-1 mt-4 rounded-lg border border-surface-border bg-[#0d121c] flex flex-col items-center justify-center p-8 text-center select-none">
          <div className="w-14 h-14 rounded-full bg-[#162032] flex items-center justify-center mb-3 border border-surface-border">
            <BookOpen className="w-7 h-7 text-accent" />
          </div>
          <h3 className="text-base font-bold text-white mb-1.5">
            {t("journal.empty_title")}
          </h3>
          <p className="k-help max-w-md mb-6">
            {t("journal.empty_desc")}
          </p>
          <div className="flex items-center space-x-3">
            <button
              onClick={onOpenNewTrade}
              className="k-btn bg-accent hover:bg-sky-400 text-black"
            >
              <Plus className="w-4 h-4" />
              <span>{t("journal.manual_entry")}</span>
            </button>
            <button
              onClick={onOpenCsvImport}
              className="k-btn border border-surface-border bg-[#162032] hover:bg-[#1f2d47] text-slate-200"
            >
              <Upload className="w-4 h-4 text-accent" />
              <span>{t("journal.import_csv")}</span>
            </button>
          </div>
        </div>
      ) : (
        <div className="flex-1 mt-4 overflow-auto rounded-lg border border-surface-border bg-[#0d121c]">
          <table className="w-full text-left text-sm">
            <thead className="bg-[#090d14] text-sm text-slate-400 sticky top-0 border-b border-surface-border">
              <tr>
                <th className="px-3 py-3">{t("journal.col_trade_id")}</th>
                <th className="px-3 py-3">{t("journal.col_symbol")}</th>
                <th className="px-3 py-3">{t("journal.col_side")}</th>
                <th className="px-3 py-3">{t("journal.col_entry")}</th>
                <th className="px-3 py-3">{t("journal.col_exit")}</th>
                <th className="px-3 py-3">{t("journal.col_qty")}</th>
                <th className="px-3 py-3">{t("journal.col_pnl")}</th>
                <th className="px-3 py-3">{t("journal.col_r")}</th>
                <th className="px-3 py-3">{t("journal.col_time")}</th>
                <th className="px-3 py-3">{t("journal.col_quote")}</th>
                <th className="px-3 py-3">{t("journal.col_status")}</th>
                <th className="px-3 py-3 text-right sticky right-0 z-10 bg-[#090d14] border-l border-surface-border/40">{t("journal.col_actions")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-border/40">
              {filteredTrades.length === 0 ? (
                <tr>
                  <td colSpan={12} className="px-4 py-12 text-center text-slate-500">
                    {t("journal.no_matching")}
                  </td>
                </tr>
              ) : (
              filteredTrades.map((tItem) => {
                const pnl = tItem.pnl;
                const hasPnl = pnl != null;
                const isWin = hasPnl && pnl > 0;
                return (
                  <tr key={tItem.id} className="group hover:bg-[#111722] transition">
                    <td className="px-3 py-3 font-bold text-accent">{tItem.id}</td>
                    <td className="px-3 py-3 font-bold text-white">
                      <span>{tItem.symbol}</span>
                      {renderSimulationBadge(tItem)}
                    </td>
                    <td className="px-3 py-3">
                      <span
                        className={`px-2 py-0.5 rounded text-sm font-bold ${
                          tItem.side === "BUY" || tItem.side === "LONG"
                            ? "bg-gain/20 text-gain"
                            : "bg-loss/20 text-loss"
                        }`}
                      >
                        {tItem.position_type === "SPOT" ? t("order_ticket.side_spot") : tItem.side}
                      </span>
                    </td>
                    <td className="px-3 py-3 text-slate-200 font-semibold">{formatPrice(tItem.symbol, tItem.entry_price)}</td>
                    <td className="px-3 py-3 text-slate-200">
                      {tItem.exit_price != null ? formatPrice(tItem.symbol, tItem.exit_price) : "—"}
                    </td>
                    <td className="px-3 py-3 text-slate-300">{tItem.qty}</td>
                    <td className={`px-3 py-3 font-bold ${!hasPnl ? "text-slate-400" : isWin ? "text-gain" : pnl < 0 ? "text-loss" : "text-slate-400"}`}>
                      {tItem.status !== "CLOSED" ? "—" : hasPnl ? `${isWin ? "+" : ""}${pnl.toFixed(2)}` : t("journal.unknown_value")}
                    </td>
                    <td className={`px-3 py-3 font-bold ${!hasPnl ? "text-slate-400" : isWin ? "text-gain" : pnl < 0 ? "text-loss" : "text-slate-400"}`}>
                      {tItem.r_multiple != null ? `${tItem.r_multiple > 0 ? "+" : ""}${tItem.r_multiple}R` : "—"}
                    </td>
                    <td className="px-3 py-3 text-slate-400 text-sm">
                      {formatIstanbulDateTime(tItem.entry_time, locale)}
                    </td>
                    <td className="px-3 py-3">{renderQuote(tItem)}</td>
                    <td className="px-3 py-3">
                      <span
                        className={`px-2 py-0.5 rounded text-sm font-bold ${
                          tItem.status === "OPEN"
                            ? "bg-sky-500/20 text-accent border border-accent/30"
                            : "bg-slate-800 text-slate-300"
                        }`}
                      >
                        {tItem.status}
                      </span>
                      {renderLocalTracking(tItem)}
                    </td>
                    <td className="px-3 py-3 text-right whitespace-nowrap sticky right-0 z-10 bg-[#0d121c] group-hover:bg-[#111722] border-l border-surface-border/40 transition">
                      <button
                        type="button"
                        data-testid="journal-edit-action"
                        data-trade-id={tItem.id}
                        onClick={() => onEditTrade && onEditTrade(tItem.id)}
                        className="k-btn border border-accent/40 bg-accent/15 hover:bg-accent/30 text-accent px-3 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
                        title={t("journal.edit_title")}
                      >
                        <Pencil className="w-4 h-4" />
                        <span>{t("journal.edit_action")}</span>
                      </button>
                      <button
                        type="button"
                        data-testid="journal-evidence-action"
                        onClick={() => setEvidenceTradeId(tItem.id)}
                        className="k-btn ml-1 border border-surface-border bg-[#162032] hover:bg-[#1f2d47] text-slate-200 px-3 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
                        title={t("journal.evidence_title")}
                      >
                        <FileCheck2 className="w-4 h-4 text-accent" />
                        <span>{t("journal.evidence_action")}</span>
                      </button>
                      {tItem.status !== "CANCELED" && onOpenReplay && (
                        <button
                          type="button"
                          data-testid="journal-replay-action"
                          data-trade-id={tItem.id}
                          onClick={() => onOpenReplay(tItem.id)}
                          className="k-btn ml-1 border border-surface-border bg-[#162032] hover:bg-[#1f2d47] text-slate-200 px-3 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
                          title={t("journal.replay_title")}
                        >
                          <CandlestickChart className="w-4 h-4 text-accent" />
                          <span>{t("journal.replay_action")}</span>
                        </button>
                      )}
                      {tItem.status !== "CANCELED" && (
                        <button
                          type="button"
                          data-testid="journal-cancel-action"
                          data-trade-id={tItem.id}
                          onClick={() => {
                            setCancellationTarget(tItem);
                            setCancellationError(null);
                            setCancellationNotice(null);
                          }}
                          className="k-btn ml-1 border border-loss/40 bg-loss/10 hover:bg-loss/20 text-loss px-3 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
                          title={t("journal.cancel_action_title")}
                        >
                          <Trash2 className="w-4 h-4" />
                          <span>{t("journal.cancel_action")}</span>
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
        {loadMoreError && (
          <div role="alert" className="flex items-center justify-center gap-3 border-t border-loss/30 p-3 text-sm text-loss">
            <span className="break-words">{loadMoreError}</span>
            <button type="button" onClick={() => void loadMoreTrades()} className="k-btn border border-loss/50 font-bold hover:bg-loss/10">
              {t("journal.retry")}
            </button>
          </div>
        )}
        {hasMore && (
          <div className="flex justify-center border-t border-surface-border p-3">
            <button
              type="button"
              onClick={() => void loadMoreTrades()}
              disabled={isLoadingMore}
              className="k-btn border border-accent/50 text-accent hover:bg-accent/10 disabled:opacity-50"
            >
              {isLoadingMore ? t("journal.loading_more") : t("journal.load_more")}
            </button>
          </div>
        )}
      </div>
    )}
      {evidenceTradeId && (
        <TradeEvidencePanel tradeId={evidenceTradeId} onClose={() => setEvidenceTradeId(null)} />
      )}
      {reconciliationInboxOpen && (
        <ReconciliationInbox
          onClose={() => setReconciliationInboxOpen(false)}
          onOpenEvidence={(tradeId) => {
            setReconciliationInboxOpen(false);
            setEvidenceTradeId(tradeId);
          }}
        />
      )}
      {weeklyReviewOpen && <WeeklyReviewPanel onClose={() => setWeeklyReviewOpen(false)} />}
      {cancellationTarget && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="journal-cancel-title"
          aria-describedby="journal-cancel-description"
          data-testid="journal-cancel-dialog"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
        >
          <div className="w-full max-w-md rounded-lg border border-surface-border bg-[#0d121c] p-5 shadow-2xl">
            <h2 id="journal-cancel-title" className="text-lg font-bold text-white">{t("journal.cancel_title")}</h2>
            <p id="journal-cancel-description" className="mt-3 text-sm leading-relaxed text-slate-300">
              {t("journal.cancel_description", { id: cancellationTarget.id, symbol: cancellationTarget.symbol })}
            </p>
            <p className="mt-2 text-sm leading-relaxed text-slate-400">{t("journal.cancel_audit_note")}</p>
            {cancellationError && (
              <div role="alert" data-testid="journal-cancel-error" className="mt-3 rounded border border-loss/40 bg-loss/10 px-3 py-2 text-sm text-loss">
                {cancellationError}
              </div>
            )}
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => {
                  setCancellationTarget(null);
                  setCancellationError(null);
                }}
                disabled={cancellingTradeId === cancellationTarget.id}
                className="k-btn border border-surface-border text-slate-300 hover:bg-slate-800 disabled:opacity-50"
              >
                {t("journal.cancel_keep")}
              </button>
              <button
                type="button"
                data-testid="journal-cancel-confirm"
                onClick={() => void cancelTrade()}
                disabled={cancellingTradeId === cancellationTarget.id}
                className="k-btn bg-loss text-white hover:bg-rose-700 disabled:opacity-50"
              >
                <Trash2 className="h-4 w-4" />
                {cancellingTradeId === cancellationTarget.id ? t("journal.cancel_in_progress") : t("journal.cancel_confirm")}
              </button>
            </div>
          </div>
        </div>
      )}
      {exportOpen && (
        <JournalExportModal
          onClose={() => setExportOpen(false)}
          filters={{
            symbols: filterSymbols,
            statuses: filterStatuses,
            dateFrom: filterDateFrom,
            dateTo: filterDateTo,
          }}
        />
      )}
  </div>
  );
};
