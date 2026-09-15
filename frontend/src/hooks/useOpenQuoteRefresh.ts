import { useCallback, useEffect, useRef, useState } from "react";
import { apiFetch, apiUrl } from "../lib/backend";
import type { QuoteRefreshResponse, TradeQuote } from "../types";

const OPEN_QUOTE_INTERVAL_MS = 20_000;
const AGE_TICK_MS = 1_000;

/**
 * Shared open-trade quote refresh for journal surfaces.
 *
 * The backend refreshes only the exact provider identities the user confirmed,
 * shares requests per identity and applies its own cache/backoff.  A failed
 * transport/HTTP/malformed response never leaves old data looking live: every
 * displayed price is demoted to an explicit stale "last known" value, the last
 * attempt and last successful check are tracked separately, and the age is
 * derived from the observation time on every tick instead of a frozen value.
 */
export function useOpenQuoteRefresh(enabled: boolean) {
  const [quotes, setQuotes] = useState<Record<string, TradeQuote>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastSuccessAt, setLastSuccessAt] = useState<string | null>(null);
  const [lastAttemptAt, setLastAttemptAt] = useState<string | null>(null);
  const [nowMs, setNowMs] = useState<number>(() => Date.now());
  const requestRef = useRef<AbortController | null>(null);

  useEffect(() => {
    const ticker = window.setInterval(() => setNowMs(Date.now()), AGE_TICK_MS);
    return () => window.clearInterval(ticker);
  }, []);

  const markQuotesStale = useCallback((reason: string) => {
    setQuotes((previous) => {
      const next: Record<string, TradeQuote> = {};
      for (const [tradeId, quote] of Object.entries(previous)) {
        if (quote.price == null) {
          next[tradeId] = { ...quote, quote_status: "UNAVAILABLE", reason: quote.reason || reason };
          continue;
        }
        next[tradeId] = {
          ...quote,
          price: null,
          price_kind: null,
          quote_status: "UNAVAILABLE",
          observed_at: null,
          age_seconds: null,
          reason,
          last_known: {
            price: quote.price,
            observed_at: quote.observed_at,
            quote_status: quote.quote_status,
            stale: true,
          },
        };
      }
      return next;
    });
  }, []);

  const refresh = useCallback(async (tradeIds?: string[]) => {
    if (requestRef.current) return;
    const controller = new AbortController();
    requestRef.current = controller;
    const attemptAt = new Date().toISOString();
    setBusy(true);
    setError(null);
    setLastAttemptAt(attemptAt);
    try {
      const response = await apiFetch(apiUrl("/api/v1/trades/quotes/refresh"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(tradeIds && tradeIds.length > 0 ? { trade_ids: tradeIds } : {}),
        signal: controller.signal,
      });
      const data: unknown = await response.json();
      if (
        !response.ok ||
        !data ||
        typeof data !== "object" ||
        typeof (data as QuoteRefreshResponse).quotes !== "object" ||
        (data as QuoteRefreshResponse).quotes === null
      ) {
        throw new Error(`Quote refresh failed (HTTP ${response.status})`);
      }
      if (controller.signal.aborted) return;
      const payload = data as QuoteRefreshResponse;
      setQuotes((previous) => ({ ...previous, ...payload.quotes }));
      setLastSuccessAt(payload.checked_at || attemptAt);
    } catch (cause) {
      if (controller.signal.aborted) return;
      const message = cause instanceof Error ? cause.message : "Quote refresh failed";
      setError(message);
      markQuotesStale("REFRESH_FAILED");
    } finally {
      if (requestRef.current === controller) {
        requestRef.current = null;
        setBusy(false);
      }
    }
  }, [markQuotesStale]);

  useEffect(() => {
    if (!enabled) return;
    void refresh();
    const timer = window.setInterval(() => {
      if (document.visibilityState !== "hidden") void refresh();
    }, OPEN_QUOTE_INTERVAL_MS);
    return () => {
      window.clearInterval(timer);
      requestRef.current?.abort();
      requestRef.current = null;
    };
  }, [enabled, refresh]);

  return {
    quotes,
    refresh,
    busy,
    error,
    lastSuccessAt,
    lastAttemptAt,
    nowMs,
  };
}

/**
 * Age of the displayed price in seconds, derived from the observation time so
 * it keeps advancing between refreshes.  Falls back to the stale last-known
 * observation when the current price is unavailable.
 */
export function quoteAgeSeconds(quote: TradeQuote | undefined | null, nowMs: number): number | null {
  if (!quote) return null;
  const observed = quote.price != null
    ? quote.observed_at
    : quote.last_known?.observed_at ?? quote.observed_at;
  if (!observed) return null;
  const parsed = Date.parse(observed);
  if (!Number.isFinite(parsed)) return null;
  return Math.max(0, (nowMs - parsed) / 1000);
}
