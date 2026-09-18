import React, { useEffect, useMemo, useRef, useState } from "react";
import { X, Check, RefreshCw, Zap, AlertTriangle, CalendarClock, Scale, Target, Ruler, ClipboardList } from "lucide-react";
import { useMarketStore } from "../stores/marketStore";
import { useTradeStore } from "../stores/tradeStore";
import { useTranslation } from "../context/I18nContext";
import { MarketQuote, TradeSide } from "../types";
import { apiFetch, apiUrl } from "../lib/backend";
import { createManualMarketInstrument, normalizeMarketSymbol } from "../lib/marketSymbols";
import { MarketInstrument } from "../lib/marketSymbols";
import { useInstrumentSearch } from "../hooks/useInstrumentSearch";
import { TargetPlanFields } from "./TargetPlanFields";
import { targetPayload, validTargets, type TargetDraft } from "../lib/localTracking";
import { istanbulInputToUtcIso, istanbulInputValue, isFutureIstanbulInput } from "../lib/tradeTime";
import { equalPercentages, formatNotional, positionSizing, formatPositionValue } from "../lib/positionMath";

const FREE_QUOTE_SOURCE_IDS = new Set([
  "binance_public",
  "bybit_public",
  "biquote_public",
  "yahoo_public",
  "stooq_public",
]);

const PREFS_KEY = "kuantra_trade_prefs_v1";

interface TradePrefs {
  recordMode: "EXTERNAL" | "SIMULATION";
  positionType: "SPOT" | "LONG" | "SHORT";
  leverage: number | null;
}

function loadPrefs(): TradePrefs {
  const fallback: TradePrefs = { recordMode: "EXTERNAL", positionType: "SPOT", leverage: null };
  try {
    const raw = localStorage.getItem(PREFS_KEY);
    if (!raw) return fallback;
    const parsed = JSON.parse(raw) as Partial<TradePrefs>;
    return {
      recordMode: parsed.recordMode === "SIMULATION" ? "SIMULATION" : "EXTERNAL",
      positionType: parsed.positionType === "LONG" || parsed.positionType === "SHORT" ? parsed.positionType : "SPOT",
      leverage: typeof parsed.leverage === "number" && Number.isFinite(parsed.leverage) && parsed.leverage > 0
        ? parsed.leverage : null,
    };
  } catch {
    return fallback;
  }
}

function savePrefs(prefs: TradePrefs): void {
  try {
    localStorage.setItem(PREFS_KEY, JSON.stringify(prefs));
  } catch {
    // Preferences are a convenience; a storage failure must not block recording.
  }
}

function isMarketQuote(value: unknown): value is MarketQuote {
  if (!value || typeof value !== "object") return false;
  const quote = value as Partial<MarketQuote>;
  if (
    typeof quote.requested_symbol !== "string" ||
    !["LIVE", "DELAYED", "EOD", "UNAVAILABLE"].includes(String(quote.status)) ||
    quote.free_source !== true ||
    quote.credentials_required !== false
  ) {
    return false;
  }
  if (quote.status === "UNAVAILABLE") {
    return quote.price === null && quote.price_kind === null;
  }
  return Boolean(
    typeof quote.source_id === "string" &&
    FREE_QUOTE_SOURCE_IDS.has(quote.source_id) &&
    typeof quote.source_symbol === "string" &&
    quote.source_symbol.length > 0 &&
    typeof quote.observed_at === "string" &&
    quote.observed_at.length > 0 &&
    (quote.price_kind === "LAST" || quote.price_kind === "CLOSE") &&
    typeof quote.price === "number" &&
    Number.isFinite(quote.price) &&
    quote.price > 0
  );
}

interface NewTradeModalProps {
  isOpen: boolean;
  onClose: () => void;
  onOpenApiKeySettings?: () => void;
}

interface TradeFormErrors {
  symbol?: string;
  entry?: string;
  qty?: string;
  size?: string;
  leverage?: string;
  stop?: string;
  target?: string;
  allocation?: string;
  time?: string;
  exit?: string;
  submit?: string;
}

export const NewTradeModal: React.FC<NewTradeModalProps> = ({
  isOpen,
  onClose,
}) => {
  const { t } = useTranslation();
  const { symbol: defaultSymbol } = useMarketStore();
  const { addTrade } = useTradeStore();
  const resolvedDefaultSymbol = normalizeMarketSymbol(defaultSymbol || "");
  const initialSymbol = resolvedDefaultSymbol || "BTCUSDT";
  const initialPrefs = useMemo(() => loadPrefs(), []);

  const [recordMode, setRecordMode] = useState<"EXTERNAL" | "SIMULATION">(initialPrefs.recordMode);
  const [tradeSymbol, setTradeSymbol] = useState<string>(initialSymbol);
  const [symbolInput, setSymbolInput] = useState<string>("");
  const [pendingInstrument, setPendingInstrument] = useState<MarketInstrument | null>(null);
  const [symbolSearchError, setSymbolSearchError] = useState<string | null>(null);
  const [positionType, setPositionType] = useState<"SPOT" | "LONG" | "SHORT">(initialPrefs.positionType);
  const side: TradeSide = positionType === "SHORT" ? "SELL" : "BUY";
  const [tradeStatus, setTradeStatus] = useState<"OPEN" | "CLOSED">("OPEN");
  const [tradeTime, setTradeTime] = useState<string>(() => istanbulInputValue());
  const [exitTime, setExitTime] = useState<string>("");
  const [entryPrice, setEntryPrice] = useState<string>("");
  const [notionalSize, setNotionalSize] = useState<string>("");
  const [leverage, setLeverage] = useState<string>("");
  const [exitPrice, setExitPrice] = useState<string>("");
  const [stopLoss, setStopLoss] = useState<string>("");
  const [targets, setTargets] = useState<TargetDraft[]>([{ price: "", percent: "" }]);
  const takeProfit = Number(targets[0]?.price || 0);
  const [trackingEnabled, setTrackingEnabled] = useState(true);
  const [serverVerified, setServerVerified] = useState(false);
  const [selectedInstrument, setSelectedInstrument] = useState<MarketInstrument | null>(null);
  const [executionVenue, setExecutionVenue] = useState<string>("");
  const [notes, setNotes] = useState<string>("");
  const [advancedOpen, setAdvancedOpen] = useState(false);

  const [isFetchingPrice, setIsFetchingPrice] = useState<boolean>(false);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [fetchNotice, setFetchNotice] = useState<string | null>(null);
  const [errors, setErrors] = useState<TradeFormErrors>({});
  const [quote, setQuote] = useState<MarketQuote | null>(null);
  const [priceOrigin, setPriceOrigin] = useState<"MANUAL" | "PUBLIC_QUOTE">("MANUAL");
  const quoteRequestRef = useRef<AbortController | null>(null);
  const isSymbolSearchPending = Boolean(symbolInput.trim() || pendingInstrument);
  const { results: searchResults, status: searchStatus } = useInstrumentSearch(
    symbolInput,
    isOpen && !pendingInstrument,
  );

  useEffect(() => () => quoteRequestRef.current?.abort(), []);

  useEffect(() => {
    if (isOpen) setTradeTime(istanbulInputValue());
  }, [isOpen]);

  const verifyInstrument = async (symbol: string) => {
    const normalized = symbol.trim().toUpperCase();
    if (!normalized) return;
    try {
      const response = await apiFetch(
        apiUrl(`/api/v1/market-data/instrument?symbol=${encodeURIComponent(normalized)}`),
      );
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const payload = await response.json() as { status?: string; provider?: string; base_asset?: string; quote_asset?: string };
      if (payload.status === "VERIFIED") {
        setServerVerified(true);
      } else {
        setServerVerified(false);
      }
    } catch {
      setServerVerified(false);
    }
  };

  const cancelQuoteRequest = () => {
    quoteRequestRef.current?.abort();
    quoteRequestRef.current = null;
    setIsFetchingPrice(false);
  };

  if (!isOpen) return null;

  const numericEntry = Number(entryPrice);
  // WP45: the position value in USD is the only sizing input.
  const numericQty = Number(notionalSize);
  const numericLeverage = positionType === "SPOT" ? null : Number(leverage) || null;
  const sizing = positionSizing({
    symbol: tradeSymbol,
    positionType,
    side,
    entryPrice: Number.isFinite(numericEntry) ? numericEntry : null,
    qty: Number.isFinite(numericQty) && numericQty > 0 ? numericQty : null,
    leverage: numericLeverage,
    exitPrice: tradeStatus === "CLOSED" && Number(exitPrice) > 0 ? Number(exitPrice) : null,
    qtyUnit: "USD",
    serverVerified,
  });
  const validStop = Number(stopLoss) > 0;
  const validTarget = takeProfit > 0;
  const monetaryReady = sizing.monetaryCalculation.status === "READY";
  const trackingSupported = sizing.instrument.contractSize === "BASE_UNIT" || sizing.instrument.contractSize === "USD_NOTIONAL";
  // WP46: the position value is USD, so risk/reward are price-return fractions
  // of that value -- never a base-quantity multiplication.
  const totalRisk = monetaryReady && validStop && numericQty > 0 && numericEntry > 0
    ? Math.abs(numericEntry - Number(stopLoss)) / numericEntry * numericQty : null;
  const totalReward = monetaryReady && validTarget && numericQty > 0 && numericEntry > 0
    ? Math.abs(takeProfit - numericEntry) / numericEntry * numericQty : null;
  const rrRatio = totalRisk !== null && totalRisk > 0 && totalReward !== null
    ? (totalReward / totalRisk).toFixed(2) : null;
  const enteredPercentTotal = targets
    .map((target) => Number(target.percent))
    .filter((value) => Number.isFinite(value) && value > 0)
    .reduce((sum, value) => sum + value, 0);
  const quotePrice = quote?.price != null ? Number(quote.price) : null;
  const indicatorReached = tradeStatus === "OPEN" && quotePrice !== null && Number.isFinite(numericEntry)
    ? targets.some((target) => Number(target.price) > 0
      && (side === "BUY" ? quotePrice >= Number(target.price) : quotePrice <= Number(target.price)))
      || (validStop && (side === "BUY" ? quotePrice <= Number(stopLoss) : quotePrice >= Number(stopLoss)))
    : false;

  const fieldError = (field: keyof TradeFormErrors) => errors[field] && (
    <p role="alert" data-testid={`new-trade-error-${field}`} className="k-error mt-1">{errors[field]}</p>
  );

  const handleFetchLatestPrice = async () => {
    if (isSymbolSearchPending) {
      setSymbolSearchError(t("order_ticket.select_result_to_confirm"));
      return;
    }
    setIsFetchingPrice(true);
    setFetchNotice(null);
    setErrors((current) => ({ ...current, submit: undefined }));
    quoteRequestRef.current?.abort();
    const controller = new AbortController();
    quoteRequestRef.current = controller;
    try {
      const res = await apiFetch(
        apiUrl(`/api/v1/market-data/quote?symbol=${encodeURIComponent(
          tradeSymbol.toUpperCase()
        )}&source=${encodeURIComponent(selectedInstrument?.source_id && FREE_QUOTE_SOURCE_IDS.has(selectedInstrument.source_id) ? selectedInstrument.source_id : "auto")}`), { signal: controller.signal },
      );
      if (!res.ok) throw new Error("Price fetch failed");
      const candidateValue: unknown = await res.json();
      if (controller.signal.aborted || quoteRequestRef.current !== controller) return;
      const candidate = isMarketQuote(candidateValue) ? candidateValue : null;
      if (!candidate || candidate.requested_symbol !== tradeSymbol.toUpperCase()) {
        throw new Error("Malformed free quote response");
      }
      setQuote(candidate);
      if (candidate && Number.isFinite(candidate.price) && Number(candidate.price) > 0 && candidate.status !== "UNAVAILABLE") {
        void verifyInstrument(tradeSymbol);
        const markPrice = Number(candidate.price);
        setPriceOrigin("PUBLIC_QUOTE");
        setEntryPrice(String(markPrice));
        setFetchNotice(t("order_ticket.latest_price", {
          price: markPrice.toLocaleString(),
          source: candidate.source_symbol || candidate.source_id || "",
          status: candidate.status,
        }));
      } else {
        setPriceOrigin("MANUAL");
        setFetchNotice(t("order_ticket.price_unavailable_manual"));
      }
    } catch {
      if (controller.signal.aborted || quoteRequestRef.current !== controller) return;
      setQuote(null);
      setPriceOrigin("MANUAL");
      setFetchNotice(t("order_ticket.price_unavailable_manual"));
    } finally {
      if (quoteRequestRef.current === controller) {
        quoteRequestRef.current = null;
        setIsFetchingPrice(false);
      }
    }
  };

  const handleSelectSearchResult = (instrument: MarketInstrument) => {
    setPendingInstrument(instrument);
    setSymbolInput(instrument.symbol);
    setSymbolSearchError(null);
    setQuote(null);
    setPriceOrigin("MANUAL");
    setFetchNotice(null);
  };

  const handleConfirmSymbol = () => {
    if (!pendingInstrument) {
      setSymbolSearchError(t("order_ticket.select_result_to_confirm"));
      return;
    }
    setTradeSymbol(pendingInstrument.symbol);
    setSelectedInstrument(pendingInstrument);
    setServerVerified(false);
    void verifyInstrument(pendingInstrument.symbol);
    cancelQuoteRequest();
    if (pendingInstrument.symbol !== tradeSymbol) {
      setEntryPrice("");
      setStopLoss("");
      setTargets([{ price: "", percent: "" }]);
    }
    setSymbolInput("");
    setPendingInstrument(null);
    setSymbolSearchError(null);
    setQuote(null);
    setPriceOrigin("MANUAL");
    setFetchNotice(null);
  };

  const handleCancelSymbolSelection = () => {
    setPendingInstrument(null);
    setSymbolInput("");
    setSymbolSearchError(null);
  };

  const handleEqualSplit = () => {
    const count = Math.min(3, Math.max(1, targets.length));
    const percents = equalPercentages(count);
    setTargets(percents.map((percent, index) => ({ price: targets[index]?.price || "", percent })));
    setErrors((current) => ({ ...current, allocation: undefined }));
  };

  const validate = (): TradeFormErrors => {
    const next: TradeFormErrors = {};
    if (isSymbolSearchPending) next.symbol = t("order_ticket.select_result_to_confirm");
    if (!Number.isFinite(numericEntry) || numericEntry <= 0) next.entry = t("order_ticket.errors.entry_required");
    {
      const positionValue = Number(notionalSize);
      if (!Number.isFinite(positionValue) || positionValue <= 0) next.size = t("order_ticket.errors.position_size_required");
    }
    if (positionType !== "SPOT" && leverage !== "" && (!Number.isFinite(Number(leverage)) || Number(leverage) < 1)) {
      next.leverage = t("order_ticket.errors.leverage_range");
    }
    if (stopLoss !== "" && (!validStop || (side === "BUY" ? Number(stopLoss) >= numericEntry : Number(stopLoss) <= numericEntry))) {
      next.stop = t("order_ticket.errors.stop_wrong_side");
    }
    if (isFutureIstanbulInput(tradeTime)) next.time = t("order_ticket.errors.time_future");
    if (tradeStatus === "CLOSED") {
      if (!istanbulInputToUtcIso(tradeTime)) next.time = t("order_ticket.errors.time_invalid");
      if (!istanbulInputToUtcIso(exitTime)) next.exit = t("order_ticket.errors.exit_time_required");
      if (!Number.isFinite(Number(exitPrice)) || Number(exitPrice) <= 0) next.exit = t("order_ticket.errors.exit_price_required");
      const entryUtc = istanbulInputToUtcIso(tradeTime);
      const exitUtc = istanbulInputToUtcIso(exitTime);
      if (entryUtc && exitUtc && new Date(exitUtc) < new Date(entryUtc)) next.exit = t("order_ticket.errors.exit_before_entry");
      if (isFutureIstanbulInput(exitTime)) next.exit = t("order_ticket.errors.exit_time_future");
    } else if (!validTargets(targets, numericEntry, side, stopLoss === "" ? null : Number(stopLoss))) {
      const partial = targets.some((target) => (target.price !== "") !== (target.percent !== ""));
      if (partial) next.target = t("order_ticket.errors.target_pair_required");
      else if (Math.abs(enteredPercentTotal - 100) > 1e-9 && enteredPercentTotal > 0) {
        next.allocation = t("order_ticket.errors.allocation_total", { total: enteredPercentTotal.toFixed(2) });
      } else next.target = t("order_ticket.errors.target_order");
    }
    return next;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isSubmitting) return;
    const validation = validate();
    setErrors(validation);
    if (Object.values(validation).some(Boolean)) return;
    setIsSubmitting(true);

    const useQuoteProvenance = Boolean(
      priceOrigin === "PUBLIC_QUOTE" && quote?.source_id && Number(quote.price) === numericEntry
    );
    const selectedQuote = useQuoteProvenance ? quote : null;
    // The confirmed instrument identity is separate from the entry-price
    // provenance: a hand-typed execution price must never erase the provider
    // the user confirmed, and the identity is never inferred from symbol text.
    const confirmedIdentity = selectedInstrument && FREE_QUOTE_SOURCE_IDS.has(selectedInstrument.source_id)
      ? selectedInstrument : quote?.source_id && FREE_QUOTE_SOURCE_IDS.has(quote.source_id) ? quote : null;
    const trackingPayload = tradeStatus === "OPEN" && trackingSupported ? {
      enabled: trackingEnabled,
      targets: targetPayload(targets),
      stop_loss: stopLoss === "" ? null : Number(stopLoss),
      source_id: confirmedIdentity?.source_id || null,
      source_symbol: confirmedIdentity?.source_symbol || null,
    } : null;
    const tradePayload: Record<string, unknown> = {
      symbol: tradeSymbol.toUpperCase(),
      side,
      position_type: positionType,
      entry_price: Number(numericEntry),
      size_input_mode: "NOTIONAL",
      notional_size: Number(notionalSize),
      leverage: positionType === "SPOT" ? null : (leverage === "" ? null : Number(leverage)),
      qty_unit: "USD",
      stop_loss: stopLoss === "" ? null : Number(stopLoss),
      take_profit: takeProfit ? Number(takeProfit) : null,
      status: tradeStatus,
      entry_time: istanbulInputToUtcIso(tradeTime),
      ...(tradeStatus === "CLOSED"
        ? { exit_price: Number(exitPrice), exit_time: istanbulInputToUtcIso(exitTime) }
        : {}),
      local_tracking: trackingPayload,
      record_mode: recordMode,
      execution_venue: executionVenue.trim() || null,
      price_source: confirmedIdentity?.source_id || "manual",
      price_source_symbol: confirmedIdentity?.source_symbol || null,
      price_status: selectedQuote?.status || "UNAVAILABLE",
      price_observed_at: selectedQuote?.observed_at || null,
      price_origin: useQuoteProvenance ? "PUBLIC_QUOTE" : "MANUAL",
      notes: notes || undefined,
    };

    try {
      const res = await apiFetch(apiUrl("/api/v1/trades"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(tradePayload),
      });

      const data = await res.json();
      if (!res.ok || !data.id) {
        const detail = data?.detail;
        const reason = typeof detail === "object" && detail !== null ? String(detail.reason || "") : "";
        const backendMessage = typeof detail === "object" && detail !== null ? String(detail.message || "") : typeof detail === "string" ? detail : "";
        const mapped = reason && reason !== "undefined" ? t(`order_ticket.reason_${reason}`) : "";
        const message = mapped && !mapped.startsWith("order_ticket.reason_") ? mapped : backendMessage || data.reason || t("order_ticket.record_failed");
        setErrors((current) => ({ ...current, submit: message }));
        setIsSubmitting(false);
        return;
      }

      savePrefs({
        recordMode,
        positionType,
        leverage: positionType === "SPOT" ? null : numericLeverage,
      });
      addTrade(data);
      onClose();
    } catch (err: any) {
      setErrors((current) => ({ ...current, submit: err.message || t("order_ticket.record_failed") }));
    } finally {
      setIsSubmitting(false);
    }
  };

  const suggestedLeverage = initialPrefs.leverage;
  const showLeverageSuggestion = positionType !== "SPOT" && leverage === "" && suggestedLeverage != null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 font-sans select-none animate-fadeIn">
      <div className="bg-[#111722] border border-surface-border rounded-xl w-full max-w-2xl p-5 shadow-2xl overflow-hidden flex flex-col max-h-[92vh]">
        <div className="flex items-center justify-between border-b border-surface-border pb-3">
          <h3 className="text-lg font-bold text-white flex items-center space-x-2">
            <Zap className="w-5 h-5 text-accent" />
            <span>{t("order_ticket.modal_title")}</span>
          </h3>
          <button onClick={onClose} aria-label={t("order_ticket.cancel")} className="text-slate-400 hover:text-white cursor-pointer p-2 -m-1">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="grid grid-cols-2 gap-2 mt-4 p-1 bg-[#090d14] rounded-lg border border-surface-border text-sm">
          <button
            type="button"
            onClick={() => setRecordMode("EXTERNAL")}
            className={`py-2 rounded-md font-bold transition flex items-center justify-center space-x-1.5 cursor-pointer ${
              recordMode === "EXTERNAL"
                ? "bg-[#162032] text-accent border border-accent/40 shadow-sm"
                : "text-slate-400 hover:text-white"
            }`}
          >
            <span>{t("order_ticket.mode_external")}</span>
          </button>
          <button
            type="button"
            onClick={() => setRecordMode("SIMULATION")}
            className={`py-2 rounded-md font-bold transition flex items-center justify-center space-x-1.5 cursor-pointer ${
              recordMode === "SIMULATION"
                ? "bg-[#162032] text-amber-300 border border-amber-400/40 shadow-sm"
                : "text-slate-400 hover:text-white"
            }`}
          >
            <span>{t("order_ticket.mode_simulation")}</span>
          </button>
        </div>

        <div className="mt-2 rounded border border-surface-border/70 bg-[#0b0e14] px-3 py-2 k-help" data-testid="trade-record-mode-note">
          {recordMode === "EXTERNAL"
            ? t("order_ticket.external_record_notice")
            : t("order_ticket.simulation_notice")}
        </div>

        {errors.submit && (
          <div role="alert" data-testid="new-trade-submit-error" className="mt-3 p-3 bg-loss/15 border border-loss/30 rounded-lg text-loss text-sm flex items-start space-x-2">
            <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
            <span>{errors.submit}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="mt-4 space-y-4 text-sm overflow-y-auto flex-1 pr-1">
          {/* 1 — Trade */}
          <section className="k-card space-y-3" aria-labelledby="new-trade-section-trade">
            <h4 id="new-trade-section-trade" className="k-section-title flex items-center gap-2">
              <ClipboardList className="w-4 h-4 text-accent" />
              {t("order_ticket.section_trade")}
            </h4>

            <label className="block">
              <span className="k-label">{t("order_ticket.execution_venue_label")}</span>
              <input
                type="text"
                value={executionVenue}
                onChange={(e) => setExecutionVenue(e.target.value)}
                placeholder={t("order_ticket.execution_venue_placeholder")}
                className="k-input mt-1"
              />
            </label>

            <div>
              <div data-testid="new-trade-selected-symbol" className="mb-2 rounded border border-accent/30 bg-[#0b0e14] px-3 py-2 text-accent text-base font-semibold">
                {t("order_ticket.selected_symbol", { symbol: tradeSymbol })}
              </div>
              <div className="flex justify-between items-center mb-1 gap-2">
                <label className="k-label" htmlFor="new-trade-symbol-search">{t("order_ticket.symbol_label")}</label>
                {fetchNotice && (
                  <span className="k-help text-accent font-semibold">{fetchNotice}</span>
                )}
              </div>
              <div className="flex items-center space-x-2">
                <input
                  id="new-trade-symbol-search"
                  type="text"
                  value={symbolInput}
                  onChange={(e) => {
                    cancelQuoteRequest();
                    setSymbolInput(e.target.value.toUpperCase());
                    setPendingInstrument(null);
                    setSymbolSearchError(null);
                    setQuote(null);
                    setPriceOrigin("MANUAL");
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      setSymbolSearchError(t("order_ticket.select_result_to_confirm"));
                    }
                  }}
                  placeholder={t("order_ticket.symbol_placeholder")}
                  className="k-input flex-1 uppercase"
                  aria-label={t("order_ticket.symbol_search_label")}
                />
                <button
                  type="button"
                  onClick={handleFetchLatestPrice}
                  disabled={isFetchingPrice || isSymbolSearchPending}
                  className="k-btn border border-surface-border text-accent bg-[#162032] hover:bg-[#1f2d47] disabled:opacity-50"
                  title={t("order_ticket.fetch_price_btn")}
                >
                  <RefreshCw className={`w-4 h-4 ${isFetchingPrice ? "animate-spin" : ""}`} />
                  <span>{t("order_ticket.fetch_price_btn")}</span>
                </button>
              </div>
              {symbolInput.trim() && !pendingInstrument && (
                <div role="listbox" aria-label={t("order_ticket.symbol_search_label")} data-testid="new-trade-symbol-search-results" className="mt-1 max-h-48 overflow-y-auto rounded border border-surface-border bg-[#0b0e14] p-1 shadow-xl">
                  {searchResults.map((item) => (
                    <button
                      key={item.symbol}
                      type="button"
                      role="option"
                      data-testid={`new-trade-symbol-search-result-${item.symbol}`}
                      onClick={() => handleSelectSearchResult(item)}
                      className="w-full flex items-center justify-between gap-3 rounded px-2 py-2 text-left text-sm text-slate-200 hover:bg-[#1a2234]"
                    >
                      <span>
                        <span className="block">{item.name}</span>
                        <span className="block k-help">{item.symbol} · {item.exchange || item.source_id}</span>
                      </span>
                      <span className="k-help text-accent">{t("order_ticket.select_result")}</span>
                    </button>
                  ))}
                  {searchStatus === "SEARCHING" && (
                    <div className="px-2 py-2 text-sm text-slate-400">{t("order_ticket.searching")}</div>
                  )}
                  {searchStatus === "UNAVAILABLE" && (
                    <div className="px-2 py-2 text-sm text-amber-300">{t("order_ticket.search_unavailable")}</div>
                  )}
                  {searchStatus === "NO_MATCH" && (
                    <div className="px-2 py-2 text-sm text-slate-400">{t("order_ticket.no_symbol_matches")}</div>
                  )}
                  {searchStatus !== "SEARCHING" && (() => {
                    const manualInstrument = createManualMarketInstrument(symbolInput);
                    if (!manualInstrument) return null;
                    return (
                      <button
                        type="button"
                        role="option"
                        data-testid="new-trade-manual-symbol-result"
                        onClick={() => handleSelectSearchResult(manualInstrument)}
                        className="mt-1 w-full rounded border border-amber-400/30 bg-amber-950/20 px-2 py-2 text-left text-sm text-amber-200 hover:bg-amber-950/40"
                      >
                        <span className="block">{t("order_ticket.manual_symbol_option", { symbol: manualInstrument.symbol })}</span>
                        <span className="block k-help text-amber-300/80">{t("order_ticket.manual_symbol_notice")}</span>
                      </button>
                    );
                  })()}
                </div>
              )}
              {pendingInstrument && (
                <div role="dialog" data-testid="new-trade-symbol-confirmation" className="mt-2 flex items-center gap-2 rounded border border-accent/40 bg-[#0b0e14] px-2 py-2 text-sm text-slate-200">
                  <span className="flex-1">
                    {t("order_ticket.confirm_symbol", { symbol: pendingInstrument.name })} <span className="text-slate-400">({pendingInstrument.symbol})</span>
                    {pendingInstrument.source_id === "manual" && <span className="block text-amber-300">{t("order_ticket.manual_symbol_notice")}</span>}
                  </span>
                  <button
                    type="button"
                    data-testid="new-trade-confirm-symbol"
                    onClick={handleConfirmSymbol}
                    className="k-btn bg-accent text-black hover:bg-sky-300"
                  >
                    {t("order_ticket.confirm")}
                  </button>
                  <button
                    type="button"
                    data-testid="new-trade-cancel-symbol"
                    onClick={handleCancelSymbolSelection}
                    className="k-btn border border-surface-border text-slate-300 hover:text-white"
                  >
                    {t("order_ticket.cancel")}
                  </button>
                </div>
              )}
              {symbolSearchError && <div role="alert" data-testid="new-trade-symbol-search-error" className="mt-1 k-error">{symbolSearchError}</div>}
              {fieldError("symbol")}
              {quote && (
                <div className="mt-2 k-help" data-testid="trade-quote-status">
                  <span>{t("order_ticket.quote_status", { status: quote.status })}</span>
                  {quote.source_symbol && <span> · {quote.source_id}: {quote.source_symbol}</span>}
                  {quote.observed_at && <span> · {quote.observed_at}</span>}
                </div>
              )}
            </div>

            <div className="grid grid-cols-3 gap-2" role="group" aria-label={t("order_ticket.position_type")}>
              <button type="button" data-testid="new-trade-spot" aria-pressed={positionType === "SPOT"}
                onClick={() => setPositionType("SPOT")}
                className={`k-btn justify-center ${positionType === "SPOT" ? "bg-accent text-black" : "bg-[#1a2234] text-slate-300"}`}>
                {t("order_ticket.side_spot")}
              </button>
              <button
                type="button"
                aria-pressed={positionType === "LONG"}
                onClick={() => setPositionType("LONG")}
                className={`k-btn justify-center ${positionType === "LONG" ? "bg-gain text-black" : "bg-[#1a2234] text-slate-300"}`}
              >
                {t("order_ticket.side_buy")}
              </button>
              <button
                type="button"
                aria-pressed={positionType === "SHORT"}
                onClick={() => setPositionType("SHORT")}
                className={`k-btn justify-center ${positionType === "SHORT" ? "bg-loss text-white" : "bg-[#1a2234] text-slate-300"}`}
              >
                {t("order_ticket.side_sell")}
              </button>
            </div>
            {positionType === "SPOT" && <p className="k-help">{t("order_ticket.spot_notice")}</p>}

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <label className="block">
                <span className="k-label flex items-center gap-1.5">
                  <CalendarClock className="w-4 h-4 text-accent" />
                  {t("order_ticket.trade_time_label")}
                </span>
                <input
                  type="datetime-local"
                  value={tradeTime}
                  onChange={(e) => { setTradeTime(e.target.value); setErrors((c) => ({ ...c, time: undefined })); }}
                  className="k-input mt-1"
                  aria-label={t("order_ticket.trade_time_label")}
                />
                <span className="k-help">{t("order_ticket.turkey_time")}</span>
                {fieldError("time")}
              </label>
              <div>
                <span className="k-label">{t("order_ticket.status_label")}</span>
                <div className="grid grid-cols-2 gap-2 mt-1" role="group" aria-label={t("order_ticket.status_label")}>
                  <button
                    type="button"
                    data-testid="new-trade-status-open"
                    aria-pressed={tradeStatus === "OPEN"}
                    onClick={() => setTradeStatus("OPEN")}
                    className={`k-btn justify-center ${tradeStatus === "OPEN" ? "bg-accent/20 text-accent border border-accent/40" : "bg-[#1a2234] text-slate-300"}`}
                  >
                    {t("order_ticket.status_still_open")}
                  </button>
                  <button
                    type="button"
                    data-testid="new-trade-status-closed"
                    aria-pressed={tradeStatus === "CLOSED"}
                    onClick={() => setTradeStatus("CLOSED")}
                    className={`k-btn justify-center ${tradeStatus === "CLOSED" ? "bg-accent/20 text-accent border border-accent/40" : "bg-[#1a2234] text-slate-300"}`}
                  >
                    {t("order_ticket.status_already_closed")}
                  </button>
                </div>
                <p className="k-help mt-1">
                  {tradeStatus === "OPEN" ? t("order_ticket.open_status_help") : t("order_ticket.closed_status_help")}
                </p>
              </div>
            </div>

            {tradeStatus === "CLOSED" && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 rounded border border-surface-border p-3 bg-[#0b0e14]">
                <label className="block">
                  <span className="k-label">{t("order_ticket.exit_price_label")}</span>
                  <input
                    type="number"
                    step="any"
                    min="0"
                    value={exitPrice}
                    onChange={(e) => { setExitPrice(e.target.value); setErrors((c) => ({ ...c, exit: undefined })); }}
                    placeholder={t("order_ticket.price_placeholder")}
                    className="k-input mt-1"
                    aria-label={t("order_ticket.exit_price_label")}
                  />
                </label>
                <label className="block">
                  <span className="k-label">{t("order_ticket.exit_time_label")}</span>
                  <input
                    type="datetime-local"
                    value={exitTime}
                    onChange={(e) => { setExitTime(e.target.value); setErrors((c) => ({ ...c, exit: undefined })); }}
                    className="k-input mt-1"
                    aria-label={t("order_ticket.exit_time_label")}
                  />
                  <span className="k-help">{t("order_ticket.turkey_time")}</span>
                </label>
                {fieldError("exit")}
                <p className="k-help sm:col-span-2">{t("order_ticket.user_reported_close_notice")}</p>
              </div>
            )}
          </section>

          {/* 2 — Size */}
          <section className="k-card space-y-3" aria-labelledby="new-trade-section-size">
            <h4 id="new-trade-section-size" className="k-section-title flex items-center gap-2">
              <Ruler className="w-4 h-4 text-accent" />
              {t("order_ticket.section_size")}
            </h4>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <label className="block">
                <span className="k-label">{t("order_ticket.entry_label")}</span>
                <input
                  type="number"
                  step="any"
                  value={entryPrice}
                  onChange={(e) => {
                    cancelQuoteRequest();
                    setEntryPrice(e.target.value);
                    setPriceOrigin("MANUAL");
                    setErrors((c) => ({ ...c, entry: undefined }));
                  }}
                  placeholder={t("order_ticket.price_placeholder")}
                  min="0"
                  className="k-input mt-1"
                  aria-label={t("order_ticket.entry_label")}
                  required
                />
                {fieldError("entry")}
              </label>
              <label className="block">
                <span className="k-label">{t("order_ticket.position_value_label")}</span>
                <input
                  type="number"
                  step="any"
                  value={notionalSize}
                  onChange={(e) => { setNotionalSize(e.target.value); setErrors((c) => ({ ...c, size: undefined })); }}
                  placeholder={t("order_ticket.position_value_placeholder")}
                  min="0"
                  className="k-input mt-1"
                  aria-label={t("order_ticket.position_value_label")}
                />
                <span className="k-help">{t("order_ticket.position_value_help")}</span>
                {fieldError("size")}
              </label>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {positionType !== "SPOT" && (
                <label className="block">
                  <span className="k-label">{t("order_ticket.leverage_label")}</span>
                  <input
                    type="number"
                    step="any"
                    min="1"
                    max="1000"
                    value={leverage}
                    onChange={(e) => { setLeverage(e.target.value); setErrors((c) => ({ ...c, leverage: undefined })); }}
                    placeholder={t("order_ticket.leverage_placeholder")}
                    className="k-input mt-1"
                    aria-label={t("order_ticket.leverage_label")}
                  />
                  <span className="k-help">{t("order_ticket.leverage_declared_notice")}</span>
                  {fieldError("leverage")}
                  {showLeverageSuggestion && (
                    <button
                      type="button"
                      data-testid="new-trade-leverage-suggestion"
                      onClick={() => setLeverage(String(suggestedLeverage))}
                      className="mt-1 text-sm text-accent underline"
                    >
                      {t("order_ticket.leverage_suggested", { value: suggestedLeverage })}
                    </button>
                  )}
                </label>
              )}
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3 text-sm rounded border border-surface-border bg-[#0b0e14] p-3">
              <div className="min-w-0">
                <span className="k-help block">{t("order_ticket.derived_notional")}</span>
                <span className="font-semibold text-slate-100 break-words">{formatNotional(tradeSymbol, sizing.notional.value)}</span>
              </div>
              <div className="min-w-0">
                <span className="k-help block">{t("order_ticket.derived_margin")}</span>
                <span className="font-semibold text-slate-100 break-words">{formatNotional(tradeSymbol, sizing.marginEstimate.value)}</span>
                <span className="block k-help break-words">{t(`order_ticket.margin_source_${sizing.marginEstimate.source}`)}</span>
              </div>
              <div className="min-w-0">
                <span className="k-help block">{t("order_ticket.derived_leverage")}</span>
                <span className="font-semibold text-slate-100 break-words">{sizing.leverage.value ?? "—"}</span>
                <span className="block k-help break-words">{t(`order_ticket.leverage_source_${sizing.leverage.source}`)}</span>
              </div>
              <div className="min-w-0">
                <span className="k-help block">{t("order_ticket.derived_contract")}</span>
                <span className="font-semibold text-slate-100 break-words">{t(`order_ticket.verification_${sizing.instrument.verification}`)}</span>
              </div>
              <div className="col-span-full">
                <p className="k-help text-gain" data-testid="new-trade-usd-value-declared">
                  {t("order_ticket.usd_value_declared")}
                </p>
              </div>
              {sizing.warnings.length > 0 && (
                <p className="col-span-full k-help text-amber-300">
                  {sizing.warnings.map((warning) => t(`order_ticket.warning_${warning}`)).join(" ")}
                </p>
              )}
            </div>
          </section>

          {/* 3 — Targets */}
          <section className="k-card space-y-3" aria-labelledby="new-trade-section-targets">
            <h4 id="new-trade-section-targets" className="k-section-title flex items-center gap-2">
              <Target className="w-4 h-4 text-accent" />
              {t("order_ticket.section_targets")}
            </h4>
            <label className="block max-w-xs">
              <span className="k-label">{t("order_ticket.sl_label")}</span>
              <input
                type="number"
                step="any"
                value={stopLoss}
                onChange={(e) => { setStopLoss(e.target.value); setErrors((c) => ({ ...c, stop: undefined })); }}
                placeholder={t("order_ticket.optional_placeholder")}
                className="k-input mt-1 text-loss"
                aria-label={t("order_ticket.sl_label")}
              />
              {fieldError("stop")}
            </label>
            <TargetPlanFields targets={targets} onChange={(next) => { setTargets(next); setErrors((c) => ({ ...c, target: undefined, allocation: undefined })); }} />
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                data-testid="new-trade-equal-split"
                onClick={handleEqualSplit}
                className="k-btn border border-surface-border text-slate-200 hover:bg-[#1f2d47]"
              >
                <Scale className="w-4 h-4" />
                {t("order_ticket.equal_split")}
              </button>
              {enteredPercentTotal > 0 && (
                <span className={`text-sm ${Math.abs(enteredPercentTotal - 100) < 1e-9 ? "text-gain" : "text-amber-300"}`}>
                  {t("order_ticket.allocation_total", { total: enteredPercentTotal.toFixed(2) })}
                </span>
              )}
            </div>
            {fieldError("target")}
            {fieldError("allocation")}
            {tradeStatus === "OPEN" ? (
              trackingSupported ? (
                <>
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      data-testid="new-trade-tracking-enabled"
                      checked={trackingEnabled}
                      onChange={e => setTrackingEnabled(e.target.checked)}
                    />
                    {t("tracking.enabled")}
                  </label>
                  <p className="k-help">{t("tracking.disclaimer")}</p>
                </>
              ) : (
                <p className="k-help text-amber-300" data-testid="new-trade-tracking-unverified">
                  {t("order_ticket.tracking_requires_verified_unit")}
                </p>
              )
            ) : (
              <p className="k-help">{t("order_ticket.closed_no_tracking")}</p>
            )}
          </section>

          {/* 4 — Summary */}
          <section className="k-card space-y-2" aria-labelledby="new-trade-section-summary" data-testid="new-trade-summary">
            <h4 id="new-trade-section-summary" className="k-section-title">{t("order_ticket.section_summary")}</h4>
            <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1 text-sm">
              <div className="flex justify-between gap-3 min-w-0"><dt className="text-slate-400">{t("order_ticket.col_symbol")}</dt><dd className="font-semibold break-words">{tradeSymbol}</dd></div>
              <div className="flex justify-between gap-3"><dt className="text-slate-400">{t("order_ticket.position_type")}</dt><dd className="font-semibold">{t(`order_ticket.side_${positionType === "SPOT" ? "spot" : positionType === "LONG" ? "buy" : "sell"}`)}</dd></div>
              <div className="flex justify-between gap-3"><dt className="text-slate-400">{t("order_ticket.col_time")}</dt><dd className="font-semibold">{t("order_ticket.summary_time", { value: tradeTime.replace("T", " ") })}</dd></div>
              <div className="flex justify-between gap-3"><dt className="text-slate-400">{t("order_ticket.status_label")}</dt><dd className="font-semibold">{t(tradeStatus === "OPEN" ? "order_ticket.status_still_open" : "order_ticket.status_already_closed")}</dd></div>
              <div className="flex justify-between gap-3"><dt className="text-slate-400">{t("order_ticket.entry_label")}</dt><dd className="font-semibold">{entryPrice || "—"}</dd></div>
              <div className="flex justify-between gap-3"><dt className="text-slate-400">{t("order_ticket.col_size")}</dt><dd className="font-semibold">{notionalSize ? `$${Number(notionalSize).toLocaleString("en-US", { maximumFractionDigits: 2 })}` : "—"}</dd></div>
              {tradeStatus === "CLOSED" && (
                <div className="flex justify-between gap-3"><dt className="text-slate-400">{t("order_ticket.exit_price_label")}</dt><dd className="font-semibold">{exitPrice || "—"}</dd></div>
              )}
              {validStop && <div className="flex justify-between gap-3"><dt className="text-slate-400">{t("order_ticket.sl_label")}</dt><dd className="font-semibold text-loss">{stopLoss}</dd></div>}
              {validTarget && <div className="flex justify-between gap-3"><dt className="text-slate-400">{t("order_ticket.tp_label")}</dt><dd className="font-semibold text-gain">{targets[0].price}</dd></div>}
            </dl>
            <div className="flex justify-between k-help">
              <span>{t("order_ticket.risk_amount")}: <span className="font-bold text-loss">{totalRisk === null ? t("order_ticket.estimate_unavailable") : totalRisk.toFixed(2)}</span></span>
              <span>{t("order_ticket.reward_amount")}: <span className="font-bold text-gain">{totalReward === null ? t("order_ticket.estimate_unavailable") : totalReward.toFixed(2)}</span></span>
              <span>{t("order_ticket.rr_ratio")}: <span className="font-bold text-accent">{rrRatio === null ? t("order_ticket.estimate_unavailable") : `1 : ${rrRatio}`}</span></span>
            </div>
            {numericQty > 0 && (
              <p className="k-help" data-testid="new-trade-summary-value">
                {t("order_ticket.summary_position_value", {
                  value: formatPositionValue(numericQty),
                })}
              </p>
            )}
            {indicatorReached && (
              <p role="status" className="text-sm text-amber-300">{t("order_ticket.price_already_reached_warning")}</p>
            )}
            {sizing.marginEstimate.source === "UNKNOWN" && positionType !== "SPOT" && (
              <p className="k-help">{t("order_ticket.margin_unknown_notice")}</p>
            )}
            <p className="k-help">{t("order_ticket.estimate_units_notice")}</p>
          </section>

          <details className="k-card" open={advancedOpen} onToggle={(event) => setAdvancedOpen((event.target as HTMLDetailsElement).open)}>
            <summary className="k-section-title cursor-pointer">{t("order_ticket.advanced")}</summary>
            <label className="block mt-3">
              <span className="k-label">{t("order_ticket.notes_label")}</span>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder={t("order_ticket.notes_placeholder")}
                className="k-input mt-1 min-h-16 py-2"
                rows={2}
              />
            </label>
          </details>

          <button
            type="submit"
            disabled={isSubmitting || isFetchingPrice || isSymbolSearchPending}
            className={`k-btn w-full justify-center ${recordMode === "SIMULATION" ? "bg-amber-400 hover:bg-amber-300 text-black" : "bg-accent hover:bg-sky-400 text-black"} disabled:opacity-60`}
          >
            {isSubmitting ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin" />
                <span>{t("order_ticket.recording_btn")}</span>
              </>
            ) : (
              <>
                <Check className="w-4 h-4" />
                <span>{recordMode === "SIMULATION"
                  ? t("order_ticket.record_simulation_btn")
                  : t("order_ticket.record_external_btn")}</span>
              </>
            )}
          </button>
        </form>
      </div>
    </div>
  );
};
