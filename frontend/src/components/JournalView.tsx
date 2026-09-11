import React, { useState, useEffect, useCallback, useRef } from "react";
import { useTradeStore } from "../stores/tradeStore";
import { Filter, Plus, PlayCircle, BookOpen, Upload, FileCheck2, ClipboardCheck, CalendarClock, Trash2 } from "lucide-react";
import { useTranslation } from "../context/I18nContext";
import { apiFetch, apiUrl } from "../lib/backend";
import { TradeEvidencePanel } from "./TradeEvidencePanel";
import { ReconciliationInbox } from "./ReconciliationInbox";
import { WeeklyReviewPanel } from "./WeeklyReviewPanel";
import type { Trade } from "../types";

interface JournalViewProps {
  onOpenNewTrade: () => void;
  onOpenCsvImport?: () => void;
  onReplayTrade?: (tradeId: string) => void;
  refreshNonce?: number;
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function isTrade(value: unknown): value is Trade {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Record<string, unknown>;
  const optionalNumbers = ["exit_price", "pnl", "r_multiple", "commission", "unrealized_pnl", "current_price"];
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

export const JournalView: React.FC<JournalViewProps> = ({ onOpenNewTrade, onOpenCsvImport, onReplayTrade, refreshNonce = 0 }) => {
  const { t } = useTranslation();
  const { trades, setTrades, openPositions, updatePositionPnl } = useTradeStore();
  const [filterSymbol, setFilterSymbol] = useState<string>("ALL");
  const [filterStatus, setFilterStatus] = useState<string>("ALL");
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
  const loadControllerRef = useRef<AbortController | null>(null);
  const requestIdRef = useRef(0);

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
  }, [setTrades, t]);

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

  const filteredTrades = trades.filter((t) => {
    if (filterSymbol !== "ALL" && t.symbol !== filterSymbol) return false;
    if (filterStatus !== "ALL" && t.status !== filterStatus) return false;
    return true;
  });

  return (
    <div className="flex-1 flex flex-col h-full bg-[#0b0e14] overflow-hidden p-4 select-none font-mono">
      <div className="flex items-center justify-between pb-4 border-b border-surface-border">
        <div>
          <h2 className="text-base font-bold text-white">{t("journal.title")}</h2>
          <p className="text-xs text-slate-400">{t("journal.subtitle")}</p>
        </div>

        <div className="flex items-center space-x-3 text-xs">
          <div className="flex items-center space-x-2 bg-[#111722] px-3 py-1.5 rounded border border-surface-border">
            <Filter className="w-3.5 h-3.5 text-slate-400" />
            <select
              value={filterSymbol}
              onChange={(e) => setFilterSymbol(e.target.value)}
              className="bg-transparent text-white focus:outline-none"
            >
              <option value="ALL">{t("journal.filter_all_symbols")}</option>
              <option value="BTCUSDT">BTCUSDT</option>
              <option value="ETHUSDT">ETHUSDT</option>
              <option value="SOLUSDT">SOLUSDT</option>
            </select>
          </div>

          <div className="flex items-center space-x-2 bg-[#111722] px-3 py-1.5 rounded border border-surface-border">
            <select
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
              className="bg-transparent text-white focus:outline-none"
            >
              <option value="ALL">{t("journal.filter_all_status")}</option>
              <option value="OPEN">{t("journal.status_open")}</option>
              <option value="CLOSED">{t("journal.status_closed")}</option>
              <option value="CANCELED">{t("journal.status_canceled")}</option>
            </select>
          </div>

          <button
            onClick={onOpenCsvImport}
            className="flex items-center space-x-1.5 bg-[#162032] hover:bg-[#1f2d47] border border-surface-border text-slate-200 font-semibold px-3 py-1.5 rounded transition shadow-sm cursor-pointer"
          >
            <Upload className="w-3.5 h-3.5 text-accent" />
            <span>{t("journal.import_csv")}</span>
          </button>

          <button
            onClick={() => setReconciliationInboxOpen(true)}
            className="flex items-center space-x-1.5 bg-[#162032] hover:bg-[#1f2d47] border border-amber-400/40 text-amber-300 font-semibold px-3 py-1.5 rounded transition shadow-sm cursor-pointer"
          >
            <ClipboardCheck className="w-3.5 h-3.5" />
            <span>{t("journal.reconciliation_inbox")}</span>
          </button>

          <button
            onClick={() => setWeeklyReviewOpen(true)}
            className="flex items-center space-x-1.5 bg-[#162032] hover:bg-[#1f2d47] border border-accent/40 text-accent font-semibold px-3 py-1.5 rounded transition shadow-sm cursor-pointer"
          >
            <CalendarClock className="w-3.5 h-3.5" />
            <span>{t("journal.weekly_review")}</span>
          </button>

          <button
            onClick={onOpenNewTrade}
            className="flex items-center space-x-1.5 bg-accent hover:bg-sky-400 text-black font-bold px-3 py-1.5 rounded transition shadow-md cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>{t("journal.manual_entry")}</span>
          </button>
        </div>
      </div>

      {cancellationNotice && (
        <div role="status" data-testid="journal-cancel-success" className="mt-3 rounded border border-gain/40 bg-gain/10 px-3 py-2 text-xs text-gain">
          {cancellationNotice}
        </div>
      )}

      {isLoading ? (
        <div role="status" data-testid="journal-loading" className="flex-1 mt-4 rounded-lg border border-surface-border bg-[#0d121c] flex flex-col items-center justify-center p-8 text-center select-none font-mono text-slate-400 text-xs space-y-3">
          <span>{t("journal.loading")}</span>
          <button type="button" data-testid="journal-cancel" onClick={cancelLoad} className="px-2 py-1 rounded border border-surface-border text-slate-300 hover:bg-slate-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent">
            {t("journal.cancel_load")}
          </button>
        </div>
      ) : error ? (
        <div role="alert" data-testid={cancelled ? "journal-cancelled" : "journal-error"} className="flex-1 mt-4 rounded-lg border border-loss/50 bg-loss/10 flex flex-col items-center justify-center p-8 text-center select-none font-mono text-loss text-xs space-y-3">
          <span className="break-words">{error}</span>
          <button type="button" data-testid="journal-retry" onClick={() => void loadTrades()} className="px-2 py-1 rounded border border-loss/50 text-loss font-bold hover:bg-loss/10 focus:outline-none focus-visible:ring-2 focus-visible:ring-loss">
            {t("journal.retry")}
          </button>
        </div>
      ) : trades.length === 0 ? (
        <div data-testid="journal-empty" className="flex-1 mt-4 rounded-lg border border-surface-border bg-[#0d121c] flex flex-col items-center justify-center p-8 text-center select-none font-mono">
          <div className="w-14 h-14 rounded-full bg-[#162032] flex items-center justify-center mb-3 border border-surface-border">
            <BookOpen className="w-7 h-7 text-accent" />
          </div>
          <h3 className="text-base font-bold text-white mb-1.5 uppercase tracking-wide">
            {t("journal.empty_title")}
          </h3>
          <p className="text-xs text-slate-400 max-w-md mb-6 leading-relaxed">
            {t("journal.empty_desc")}
          </p>
          <div className="flex items-center space-x-3">
            <button
              onClick={onOpenNewTrade}
              className="flex items-center space-x-1.5 px-4 py-2 bg-accent hover:bg-sky-400 text-black font-bold rounded text-xs transition shadow-md cursor-pointer"
            >
              <Plus className="w-4 h-4" />
              <span>{t("journal.manual_entry")}</span>
            </button>
            <button
              onClick={onOpenCsvImport}
              className="flex items-center space-x-1.5 px-4 py-2 bg-[#162032] hover:bg-[#1f2d47] border border-surface-border text-slate-200 font-semibold rounded text-xs transition cursor-pointer"
            >
              <Upload className="w-4 h-4 text-accent" />
              <span>{t("journal.import_csv")}</span>
            </button>
          </div>
        </div>
      ) : (
        <div className="flex-1 mt-4 overflow-y-auto rounded-lg border border-surface-border bg-[#0d121c]">
          <table className="w-full text-left text-xs">
            <thead className="bg-[#090d14] text-[10px] text-slate-400 uppercase tracking-wider sticky top-0 border-b border-surface-border">
              <tr>
                <th className="px-4 py-3">{t("journal.col_trade_id")}</th>
                <th className="px-4 py-3">{t("journal.col_symbol")}</th>
                <th className="px-4 py-3">{t("journal.col_side")}</th>
                <th className="px-4 py-3">{t("journal.col_entry")}</th>
                <th className="px-4 py-3">{t("journal.col_exit")}</th>
                <th className="px-4 py-3">{t("journal.col_qty")}</th>
                <th className="px-4 py-3">{t("journal.col_pnl")}</th>
                <th className="px-4 py-3">{t("journal.col_r")}</th>
                <th className="px-4 py-3">{t("journal.col_time")}</th>
                <th className="px-4 py-3">{t("journal.col_status")}</th>
                <th className="px-4 py-3 text-right">{t("journal.col_actions")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-border/40 text-[11px]">
              {filteredTrades.length === 0 ? (
                <tr>
                    <td colSpan={11} className="px-4 py-12 text-center text-slate-500">
                    {t("journal.no_matching")}
                  </td>
                </tr>
              ) : (
              filteredTrades.map((tItem) => {
                const pnl = tItem.pnl;
                const hasPnl = pnl != null;
                const isWin = hasPnl && pnl > 0;
                return (
                  <tr key={tItem.id} className="hover:bg-[#111722] transition">
                    <td className="px-4 py-2.5 font-bold text-accent">{tItem.id}</td>
                    <td className="px-4 py-2.5 font-bold text-white">{tItem.symbol}</td>
                    <td className="px-4 py-2.5">
                      <span
                        className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                          tItem.side === "BUY" || tItem.side === "LONG"
                            ? "bg-gain/20 text-gain"
                            : "bg-loss/20 text-loss"
                        }`}
                      >
                        {tItem.side}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-slate-200">${Number(tItem.entry_price).toFixed(2)}</td>
                    <td className="px-4 py-2.5 text-slate-200">
                      {tItem.exit_price != null ? `$${Number(tItem.exit_price).toFixed(2)}` : "-"}
                    </td>
                    <td className="px-4 py-2.5 text-slate-300">{tItem.qty}</td>
                    <td className={`px-4 py-2.5 font-bold ${!hasPnl ? "text-slate-400" : isWin ? "text-gain" : pnl < 0 ? "text-loss" : "text-slate-400"}`}>
                      {tItem.status !== "CLOSED" ? "-" : hasPnl ? `${isWin ? "+" : ""}$${pnl.toFixed(2)}` : t("journal.unknown_value")}
                    </td>
                    <td className={`px-4 py-2.5 font-bold ${!hasPnl ? "text-slate-400" : isWin ? "text-gain" : pnl < 0 ? "text-loss" : "text-slate-400"}`}>
                      {tItem.r_multiple != null ? `${tItem.r_multiple > 0 ? "+" : ""}${tItem.r_multiple}R` : "-"}
                    </td>
                    <td className="px-4 py-2.5 text-slate-400 text-[10px]">
                      {new Date(tItem.entry_time).toLocaleString()}
                    </td>
                    <td className="px-4 py-2.5">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          tItem.status === "OPEN"
                            ? "bg-sky-500/20 text-accent border border-accent/30"
                            : "bg-slate-800 text-slate-300"
                        }`}
                      >
                        {tItem.status}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-right">
                      <button
                        onClick={() => onReplayTrade && onReplayTrade(tItem.id)}
                        className="inline-flex items-center space-x-1 px-2 py-0.5 bg-accent/15 hover:bg-accent/30 border border-accent/40 text-accent font-bold rounded text-[10px] transition"
                        title={t("journal.replay_title")}
                      >
                        <PlayCircle className="w-3 h-3" />
                        <span>{t("journal.replay_btn")}</span>
                      </button>
                      <button
                        onClick={() => setEvidenceTradeId(tItem.id)}
                        className="inline-flex items-center space-x-1 px-2 py-0.5 ml-1 bg-[#162032] hover:bg-[#1f2d47] border border-surface-border text-slate-200 font-bold rounded text-[10px] transition"
                        title={t("journal.evidence_title")}
                      >
                        <FileCheck2 className="w-3 h-3 text-accent" />
                        <span>{t("journal.evidence_action")}</span>
                      </button>
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
                          className="inline-flex items-center space-x-1 px-2 py-0.5 ml-1 bg-loss/10 hover:bg-loss/20 border border-loss/40 text-loss font-bold rounded text-[10px] transition"
                          title={t("journal.cancel_action_title")}
                        >
                          <Trash2 className="w-3 h-3" />
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
          <div role="alert" className="flex items-center justify-center gap-3 border-t border-loss/30 p-3 text-xs text-loss">
            <span className="break-words">{loadMoreError}</span>
            <button type="button" onClick={() => void loadMoreTrades()} className="px-2 py-1 rounded border border-loss/50 font-bold hover:bg-loss/10 focus:outline-none focus-visible:ring-2 focus-visible:ring-loss">
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
              className="px-3 py-1.5 rounded border border-accent/50 text-accent text-xs font-bold hover:bg-accent/10 disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
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
            <h2 id="journal-cancel-title" className="text-base font-bold text-white">{t("journal.cancel_title")}</h2>
            <p id="journal-cancel-description" className="mt-3 text-xs leading-relaxed text-slate-300">
              {t("journal.cancel_description", { id: cancellationTarget.id, symbol: cancellationTarget.symbol })}
            </p>
            <p className="mt-2 text-xs leading-relaxed text-slate-400">{t("journal.cancel_audit_note")}</p>
            {cancellationError && (
              <div role="alert" data-testid="journal-cancel-error" className="mt-3 rounded border border-loss/40 bg-loss/10 px-3 py-2 text-xs text-loss">
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
                className="rounded border border-surface-border px-3 py-1.5 text-xs font-bold text-slate-300 hover:bg-slate-800 disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
              >
                {t("journal.cancel_keep")}
              </button>
              <button
                type="button"
                data-testid="journal-cancel-confirm"
                onClick={() => void cancelTrade()}
                disabled={cancellingTradeId === cancellationTarget.id}
                className="inline-flex items-center gap-1.5 rounded bg-loss px-3 py-1.5 text-xs font-bold text-white hover:bg-rose-700 disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-loss"
              >
                <Trash2 className="h-3.5 w-3.5" />
                {cancellingTradeId === cancellationTarget.id ? t("journal.cancel_in_progress") : t("journal.cancel_confirm")}
              </button>
            </div>
          </div>
        </div>
      )}
  </div>
  );
};
