export interface MarketSymbolDefinition {
  symbol: string;
  labelKey: string;
  aliases: string[];
}

export interface MarketInstrument {
  symbol: string;
  name: string;
  exchange: string | null;
  asset_type: string;
  source_id: string;
  source_symbol: string;
}

/**
 * This small registry supplies the default watchlist and localized labels
 * only. It is not the supported-instrument universe: provider search results
 * and explicitly confirmed manual symbols can also be used.
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
  const cleaned = value.trim().toUpperCase();
  if (!cleaned || cleaned.length > 64 || !/^[A-Z0-9.^=:/_-]+$/.test(cleaned) || !/[A-Z0-9]/.test(cleaned)) return null;
  return cleaned;
}

function compactMarketSymbol(value: string): string {
  return value.replace(/[\s/_-]+/g, "");
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
  const compact = compactMarketSymbol(normalized);
  const definition = MARKET_SYMBOL_CATALOG.find((item) =>
    item.symbol === normalized ||
    compactMarketSymbol(item.symbol) === compact ||
    item.aliases.some((alias) => {
      const normalizedAlias = normalizeMarketSymbol(alias);
      return normalizedAlias !== null && compactMarketSymbol(normalizedAlias) === compact;
    })
  );
  return definition?.symbol || normalized;
}

/** Build an explicit, unverified candidate without inventing a provider pair. */
export function createManualMarketInstrument(value: string): MarketInstrument | null {
  const symbol = normalizeMarketSymbol(value);
  if (!symbol) return null;
  return {
    symbol,
    name: symbol,
    exchange: null,
    asset_type: "UNKNOWN",
    source_id: "manual",
    source_symbol: symbol,
  };
}
