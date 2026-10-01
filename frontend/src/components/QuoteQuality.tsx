import { useEffect, useState } from "react";
import { useTranslation } from "../context/I18nContext";
import { formatIstanbulDateTime, relativeAgeLabel } from "../lib/tradeTime";
import { quoteQuality, type QuoteQualityInput } from "../lib/quoteQuality";

/** Same truthful label in entry, edit, journal and dashboard; no network/write. */
export function QuoteQuality({ quote, nowMs }: { quote: QuoteQualityInput; nowMs?: number }) {
  const { t, locale } = useTranslation();
  const [clock, setClock] = useState(Date.now);
  useEffect(() => {
    if (nowMs !== undefined) return;
    const timer = window.setInterval(() => setClock(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [nowMs]);
  const quality = quoteQuality(quote, nowMs ?? clock);
  const color = quality.status === "LIVE" ? "text-gain" : "text-amber-500";
  return <span className="block text-sm leading-snug" data-quote-status={quality.status} data-time-basis={quality.basis}>
    <span className={color}>{t(`quote_quality.status_${quality.status.toLowerCase()}`)}</span>
    {quality.freshness === "STALE" && <span className="ml-1 text-amber-500">· {t("quote_quality.stale")}</span>}
    {quality.age != null && quality.age >= 0 && quality.basis !== "REQUEST_TIME" && quality.basis !== "UNKNOWN" && (
      <span className="ml-1 text-slate-400">· {relativeAgeLabel(quality.age)}</span>
    )}
    {quote.source_symbol && <span className="block text-slate-400">{quote.source_id?.replace("_public", "")} · {quote.source_symbol}</span>}
    {quality.freshness === "UNKNOWN" ? <span className="block text-amber-500">{t("quote_quality.unknown_time")}</span>
      : <span className="block text-slate-400">{t(quality.basis === "CANDLE_OPEN" ? "quote_quality.candle_open" : "quote_quality.event_time", {
          time: formatIstanbulDateTime(quote.observed_at, locale), interval: quote.candle_interval || "—",
        })}</span>}
    {quality.basis === "CANDLE_OPEN" && <span className="block text-amber-500">{t("quote_quality.display_only")}</span>}
  </span>;
}
