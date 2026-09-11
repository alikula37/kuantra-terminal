import { useEffect, useState } from "react";
import { apiFetch, apiUrl } from "../lib/backend";
import { MarketInstrument } from "../lib/marketSymbols";

export type InstrumentSearchStatus = "IDLE" | "SEARCHING" | "READY" | "NO_MATCH" | "UNAVAILABLE";

interface InstrumentSearchPayload {
  status?: unknown;
  results?: unknown;
}

type SearchResponseStatus = "READY" | "NO_MATCH" | "UNAVAILABLE" | "INVALID_QUERY";

interface ParsedSearchPayload {
  results: MarketInstrument[];
  status: SearchResponseStatus;
}

function parseResults(value: unknown): ParsedSearchPayload | null {
  if (!value || typeof value !== "object") return null;
  const payload = value as InstrumentSearchPayload;
  if (!Array.isArray(payload.results)) return null;
  const status = payload.status;
  if (status !== "READY" && status !== "NO_MATCH" && status !== "UNAVAILABLE" && status !== "INVALID_QUERY") {
    return null;
  }
  const results: MarketInstrument[] = [];
  for (const item of payload.results) {
    if (!item || typeof item !== "object") return null;
    const candidate = item as Record<string, unknown>;
    if (
      typeof candidate.symbol !== "string" ||
      typeof candidate.name !== "string" ||
      (candidate.exchange !== null && typeof candidate.exchange !== "string") ||
      typeof candidate.asset_type !== "string" ||
      typeof candidate.source_id !== "string" ||
      typeof candidate.source_symbol !== "string"
    ) {
      return null;
    }
    results.push(candidate as unknown as MarketInstrument);
  }
  return { results, status };
}

export function useInstrumentSearch(query: string, enabled = true) {
  const [results, setResults] = useState<MarketInstrument[]>([]);
  const [status, setStatus] = useState<InstrumentSearchStatus>("IDLE");

  useEffect(() => {
    const cleanedQuery = query.trim();
    if (!enabled || !cleanedQuery) {
      setResults([]);
      setStatus("IDLE");
      return;
    }

    const controller = new AbortController();
    setResults([]);
    setStatus("SEARCHING");
    const timer = window.setTimeout(() => {
      void apiFetch(
        apiUrl(`/api/v1/market-data/search?query=${encodeURIComponent(cleanedQuery)}&limit=20`),
        { signal: controller.signal },
      )
        .then(async (response) => {
          if (!response.ok) throw new Error(`Search failed (${response.status})`);
          const parsed = parseResults(await response.json());
          if (!parsed) throw new Error("Search response was malformed");
          return parsed;
        })
        .then((parsed) => {
          if (controller.signal.aborted) return;
          setResults(parsed.results);
          if (parsed.status === "UNAVAILABLE") {
            setStatus("UNAVAILABLE");
          } else if (parsed.status === "NO_MATCH" || parsed.status === "INVALID_QUERY") {
            setStatus("NO_MATCH");
          } else {
            setStatus(parsed.results.length ? "READY" : "NO_MATCH");
          }
        })
        .catch((error: unknown) => {
          if (controller.signal.aborted) return;
          console.warn("[InstrumentSearch] Search unavailable:", error);
          setResults([]);
          setStatus("UNAVAILABLE");
        });
    }, 300);

    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [enabled, query]);

  return { results, status };
}
