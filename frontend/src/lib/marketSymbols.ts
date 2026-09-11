export interface MarketSymbolDefinition {
  symbol: string;
  labelKey: string;
  aliases: string[];
}

/**
 * The UI can only promote a symbol that has an explicit, human-readable
 * catalog entry.  Free-form input is intentionally not treated as a symbol
 * selection: a search result must be selected and then confirmed first.
 */
export const MARKET_SYMBOL_CATALOG: MarketSymbolDefinition[] = [
  { symbol: "BTCUSDT", labelKey: "market_chart.symbol_btc_usdt", aliases: ["btc", "bitcoin"] },
  { symbol: "ETHUSDT", labelKey: "market_chart.symbol_eth_usdt", aliases: ["eth", "ethereum"] },
  { symbol: "SOLUSDT", labelKey: "market_chart.symbol_sol_usdt", aliases: ["sol", "solana"] },
  { symbol: "LINKUSDT", labelKey: "market_chart.symbol_link_usdt", aliases: ["link", "chainlink"] },
  { symbol: "XAUUSD", labelKey: "market_chart.symbol_gold", aliases: ["xau", "gold", "altın"] },
  { symbol: "EURUSD", labelKey: "market_chart.symbol_eur_usd", aliases: ["eur", "euro", "forex"] },
  { symbol: "SPY", labelKey: "market_chart.symbol_sp500", aliases: ["sp500", "s&p", "spy"] },
  { symbol: "NVDA", labelKey: "market_chart.symbol_nvidia", aliases: ["nvidia", "stock"] },
];

export function normalizeMarketSymbol(value: string): string | null {
  const cleaned = value.trim().toUpperCase().replace(/[\s/_-]+/g, "");
  if (!cleaned || cleaned.length > 32 || !/^[A-Z0-9.^=:]+$/.test(cleaned)) return null;
  return cleaned;
}

export function getMarketSymbolDefinition(symbol: string): MarketSymbolDefinition | undefined {
  return MARKET_SYMBOL_CATALOG.find((item) => item.symbol === symbol);
}

/**
 * Normalizes an already-known symbol (including legacy persisted watchlist
 * values). New user input must go through search and confirmation instead.
 */
export function resolveMarketSymbol(value: string): string | null {
  const normalized = normalizeMarketSymbol(value);
  if (!normalized) return null;
  const definition = MARKET_SYMBOL_CATALOG.find((item) =>
    item.symbol === normalized || item.aliases.some((alias) => normalizeMarketSymbol(alias) === normalized)
  );
  return definition?.symbol || normalized;
}

export function searchMarketSymbols(
  query: string,
  translate: (key: string) => string,
): MarketSymbolDefinition[] {
  const normalizedQuery = query.trim().toLowerCase();
  if (!normalizedQuery) return [];
  return MARKET_SYMBOL_CATALOG.filter((item) => {
    const haystack = `${item.symbol} ${item.aliases.join(" ")} ${translate(item.labelKey)}`.toLowerCase();
    return haystack.includes(normalizedQuery);
  }).slice(0, 8);
}
