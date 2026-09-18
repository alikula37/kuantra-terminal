import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const locales = ["en", "tr", "de"] as const;
const read = (lang: string) => JSON.parse(readFileSync(join(process.cwd(), "src", "locales", `${lang}.json`), "utf-8"));

type Domain = { path: string[]; prefix?: string; discovered: string; values: string[] };

// Every dynamically composed translation key family in the frontend source.
// Values come from the backend/component enums that produce them.
const DYNAMIC_FAMILIES: Domain[] = [
  { path: ["order_ticket"], prefix: "verification_", discovered: "order_ticket.verification_", values: ["PROVIDER_CATALOG", "EXPLICIT_QTY_UNIT", "EXPLICIT_USD_VALUE", "NONE"] },
  { path: ["order_ticket"], prefix: "warning_", discovered: "order_ticket.warning_", values: ["CONTRACT_SIZE_UNVERIFIED", "LEVERAGE_NOT_DECLARED", "FEES_UNKNOWN", "QUOTE_NOT_USD_APPROXIMATE"] },
  { path: ["order_ticket"], prefix: "margin_source_", discovered: "order_ticket.margin_source_", values: ["SPOT_FULL_PAYMENT", "ESTIMATED_FROM_DECLARED_LEVERAGE", "UNVERIFIED_CONTRACT_SIZE", "UNKNOWN"] },
  { path: ["order_ticket"], prefix: "leverage_source_", discovered: "order_ticket.leverage_source_", values: ["SPOT_IMPLIED", "USER_DECLARED", "NOT_DECLARED"] },
  { path: ["order_ticket"], prefix: "side_", discovered: "order_ticket.side_", values: ["spot", "buy", "sell"] },
  { path: ["tracking"], prefix: "status_", discovered: "tracking.status_", values: ["ACTIVE", "WAITING_QUOTE", "WAITING_TARGETS", "PAUSED", "COMPLETED", "UNKNOWN"] },
  { path: ["tracking"], prefix: "wait_reason_", discovered: "tracking.wait_reason_", values: ["MARKET_DATA_DISABLED", "PROVIDER_RATE_LIMIT", "PROVIDER_ERROR", "WAITING_FRESH_PROVIDER_EVENT", "WAITING_PROVIDER_OBSERVATION"] },
  { path: ["journal"], prefix: "local_status_", discovered: "journal.local_status_", values: ["active", "waiting_quote", "waiting_targets", "paused", "completed", "unknown"] },
  { path: ["journal_edit"], prefix: "field_", discovered: "journal_edit.field_", values: ["entry_price", "entry_time", "qty", "leverage", "stop_loss", "take_profit", "notes", "qty_unit", "status", "exit_price", "exit_time", "tracking_plan"] },
  { path: ["replay", "open_review"], prefix: "candle_state_", discovered: "replay.open_review.candle_state_", values: ["open", "closed", "unknown"] },
  { path: ["replay", "product_reason"], prefix: "", discovered: "replay.product_reason.", values: ["NO_INDEPENDENT_SOURCE", "INSUFFICIENT_OVERLAP", "FETCH_FAILED", "NO_PRODUCT_KEY", "CHECK_NOT_RUN", "UNKNOWN"] },
  { path: ["evidence_pack"], prefix: "", discovered: "evidence_pack.", values: ["json_export", "html_export", "csv_export", "pdf_export"] },
  { path: ["mt5_preview"], prefix: "", discovered: "mt5_preview.", values: ["counts_orders", "counts_deals", "counts_rows_ok", "counts_rows_errors"] },
  { path: ["mt5_preview"], prefix: "warning_", discovered: "mt5_preview.warning_", values: ["SOURCE_TIME_BASIS_UNVERIFIED", "SOURCE_ACCOUNT_NOT_VERIFIED", "OUT_OF_SCOPE_SECTIONS_PRESENT"] },
  { path: ["tracking"], prefix: "", discovered: "tracking.", values: ["binance_public", "bybit_public", "yahoo_public", "stooq_public", "biquote_public"] },
  { path: ["nav"], prefix: "", discovered: "nav.", values: ["dashboard", "journal", "charts", "mae_mfe", "modstore", "settings"] },
  { path: ["order_ticket"], prefix: "reason_", discovered: "order_ticket.reason_", values: ["QTY_INVALID", "TIME_IN_FUTURE", "EXIT_BEFORE_ENTRY", "REVISION_CONFLICT"] },
  { path: ["replay", "reason"], prefix: "", discovered: "replay.reason.", values: [
    "TRADE_NOT_CLOSED", "TRADE_NOT_FOUND", "CANDLE_STORE_UNAVAILABLE", "CANDLE_ROW_LIMIT", "WINDOW_TOO_LARGE",
    "NO_DATA", "NO_CANDLE_HISTORY", "INCOMPLETE_CANDLE_HISTORY", "CANDLE_IDENTITY_MISMATCH", "CONFLICTING_CANDLES",
    "UNALIGNED_CANDLE", "INVALID_CANDLE_PROVENANCE", "INVALID_OHLC", "INVALID_TIMESTAMP", "INVALID_VOLUME",
    "INVALID_TRADE", "INVALID_TRADE_WINDOW", "INVALID_CONTEXT_WINDOW", "NO_CACHED_CANDLES", "NO_CANDLES_SINCE_ENTRY",
    "TRADE_NOT_OPEN", "REFRESH_FAILED", "PROVIDER_MATCH_REQUIRED", "PROVIDER_NOT_DECLARED", "PROVIDER_IDENTITY_MISMATCH",
    "PROVIDER_NOT_SUPPORTED", "PROVIDER_INSTRUMENT_UNSUPPORTED", "PROVIDER_FETCH_FAILED",
  ] },
  { path: ["replay", "phase"], prefix: "", discovered: "replay.phase.", values: ["pre_entry", "active", "closed"] },
  { path: ["replay", "plan_kind"], prefix: "", discovered: "replay.plan_kind.", values: ["local", "trade_row"] },
  { path: ["replay", "side"], prefix: "", discovered: "replay.side.", values: ["long", "short"] },
];

function node(lang: string, path: string[]): Record<string, string> {
  let current = read(lang);
  for (const segment of path) current = current?.[segment] ?? {};
  return current ?? {};
}

describe("dynamic localization keys resolve for every composed family", () => {
  it("has non-empty text for every value in every family across EN/TR/DE", () => {
    for (const family of DYNAMIC_FAMILIES) {
      for (const lang of locales) {
        for (const value of family.values) {
          const key = `${family.prefix}${value}`;
          const text = node(lang, family.path)[key];
          expect(text, `${lang} ${family.path.join(".")}.${key}`).toBeTruthy();
        }
      }
    }
  });

  it("covers every dynamic t(`...${...}`) prefix discovered in the source", () => {
    const roots = [join(process.cwd(), "src")];
    const files: string[] = [];
    const walk = (dir: string) => {
      for (const entry of readdirSync(dir)) {
        const full = join(dir, entry);
        if (statSync(full).isDirectory()) walk(full);
        else if (full.endsWith(".tsx")) files.push(full);
      }
    };
    roots.forEach(walk);
    const regex = /t\(`([^`$]*)\$\{/g;
    const discovered = new Set<string>();
    for (const file of files) {
      const source = readFileSync(file, "utf-8");
      for (const match of source.matchAll(regex)) discovered.add(match[1]);
    }
    const declared = new Set(DYNAMIC_FAMILIES.map((family) => family.discovered));
    for (const prefix of discovered) {
      expect(declared.has(prefix), `uncovered dynamic translation prefix: ${prefix}`).toBe(true);
    }
  });
});
