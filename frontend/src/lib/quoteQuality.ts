import type { QuoteStatus, QuoteTimeMetadata } from "../types";

export interface QuoteQualityInput extends QuoteTimeMetadata {
  status?: QuoteStatus;
  quote_status?: QuoteStatus;
  observed_at: string | null;
  source_id?: string | null;
  source_symbol?: string | null;
  price?: number | null;
}

/** A local/naive/download timestamp cannot establish price freshness. */
export function quoteQuality(quote: QuoteQualityInput, nowMs: number) {
  const basis = quote.timestamp_basis || "UNKNOWN";
  const hasZone = typeof quote.observed_at === "string" && /(?:Z|[+-]\d{2}:\d{2})$/i.test(quote.observed_at);
  const timestamp = hasZone ? Date.parse(quote.observed_at!) : NaN;
  const age = Number.isFinite(timestamp) ? (nowMs - timestamp) / 1000 : null;
  const event = basis === "PROVIDER_EVENT";
  const freshness = event && age != null && age >= -5 ? (age <= 60 ? "FRESH" : "STALE")
    : basis === "CANDLE_OPEN" ? "DISPLAY_ONLY" : "UNKNOWN";
  let status = quote.quote_status || quote.status || "UNAVAILABLE";
  if (status === "LIVE" && freshness !== "FRESH") status = "DELAYED";
  return { status, freshness, basis, age };
}
