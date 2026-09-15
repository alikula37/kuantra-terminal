/**
 * Frontend mirror of the backend position-summary rules.
 *
 * The three return layers stay separate: the raw price move never multiplies
 * by leverage; only the margin return does.  Unknown contract sizes and
 * missing fees are labeled, never replaced with synthetic certainty.  Monetary
 * amounts are produced only for instruments whose base-unit pricing is
 * established; everything else returns `null` with an explicit reason.  The
 * backend remains authoritative for stored trades.
 */

export type InstrumentKind = "CRYPTO_PAIR" | "MACRO_OR_COMMODITY" | "GENERIC";
export type PositionType = "SPOT" | "LONG" | "SHORT" | "UNKNOWN";

export type UnitVerification = "EXPLICIT_QTY_UNIT" | "NONE";

export interface InstrumentIdentity {
  kind: InstrumentKind;
  base: string;
  quote: string;
  contractSize: "BASE_UNIT" | "UNVERIFIED";
  verification: UnitVerification;
  verificationSource: "USER_DECLARATION" | "NONE";
}

export interface MonetaryCalculation {
  status: "READY" | "UNAVAILABLE";
  reason: "CONTRACT_SIZE_UNVERIFIED" | null;
}

export interface PositionSizing {
  instrument: InstrumentIdentity;
  monetaryCalculation: MonetaryCalculation;
  leverage: { value: number | null; source: "SPOT_IMPLIED" | "USER_DECLARED" | "NOT_DECLARED" };
  notional: { value: number | null; currency: string };
  marginEstimate: { value: number | null; source: string };
  quantity: number | null;
  priceReturnPct: number | null;
  positionReturnPctGross: number | null;
  marginReturnPctGross: number | null;
  warnings: string[];
}

const KNOWN_QUOTES = ["USDT", "USDC", "BUSD", "FDUSD", "USD", "EUR", "TRY", "BTC", "ETH"];
const MACRO_SYMBOLS = new Set([
  "XAUUSD", "XAUUSD=X", "GOLD", "XAGUSD", "XAGUSD=X", "XPTUSD", "XPDUSD",
  "WTIUSD", "BRENTUSD", "USOIL", "UKOIL", "NATGASUSD", "NGUSD",
  "SPXUSD", "NASUSD", "US30", "GER40", "DAX40",
]);
const PROVIDER_SEPARATORS = ["=", "^", "/", ":", " "];
const CURRENCY_SYMBOLS: Record<string, string> = {
  USD: "$",
  USDT: "$",
  USDC: "$",
  BUSD: "$",
  FDUSD: "$",
  EUR: "€",
  TRY: "₺",
  BTC: "₿",
  ETH: "Ξ",
};

export function classifyInstrument(symbol: string | null | undefined): InstrumentIdentity {
  const raw = String(symbol || "").trim().toUpperCase();
  if (MACRO_SYMBOLS.has(raw)) {
    return { kind: "MACRO_OR_COMMODITY", base: raw, quote: "UNSPECIFIED", contractSize: "UNVERIFIED", verification: "NONE", verificationSource: "NONE" };
  }
  if (PROVIDER_SEPARATORS.some((separator) => raw.includes(separator))) {
    return { kind: "GENERIC", base: raw, quote: "UNSPECIFIED", contractSize: "UNVERIFIED", verification: "NONE", verificationSource: "NONE" };
  }
  for (const suffix of KNOWN_QUOTES) {
    if (raw.length > suffix.length && raw.endsWith(suffix)) {
      return { kind: "CRYPTO_PAIR", base: raw.slice(0, -suffix.length), quote: suffix, contractSize: "UNVERIFIED", verification: "NONE", verificationSource: "NONE" };
    }
  }
  return { kind: "GENERIC", base: raw, quote: "UNSPECIFIED", contractSize: "UNVERIFIED", verification: "NONE", verificationSource: "NONE" };
}

/**
 * Unit basis for monetary math.  Only an explicit user `qty_unit=BASE`
 * declaration qualifies and the result is labeled as a user declaration;
 * provider labels and symbol suffixes are not verification.
 */
export function instrumentUnitBasis(
  symbol: string | null | undefined,
  options: { qtyUnit?: string | null } = {},
): InstrumentIdentity {
  const identity = classifyInstrument(symbol);
  const explicit = String(options.qtyUnit || "UNKNOWN").toUpperCase() === "BASE";
  return {
    ...identity,
    contractSize: explicit ? "BASE_UNIT" : "UNVERIFIED",
    verification: explicit ? "EXPLICIT_QTY_UNIT" : "NONE",
    verificationSource: explicit ? "USER_DECLARATION" : "NONE",
  };
}

export function formatPrice(symbol: string | null | undefined, value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "—";
  const { quote } = classifyInstrument(symbol);
  const prefix = quote === "UNSPECIFIED" ? "" : CURRENCY_SYMBOLS[quote] || "";
  return `${prefix}${value.toLocaleString("en-US", { maximumFractionDigits: 8 })}`;
}

export function formatNotional(symbol: string | null | undefined, value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "—";
  const { quote } = classifyInstrument(symbol);
  if (quote === "UNSPECIFIED") {
    return value.toLocaleString("en-US", { maximumFractionDigits: 2 });
  }
  return `${CURRENCY_SYMBOLS[quote] || ""}${value.toLocaleString("en-US", { maximumFractionDigits: 2 })}`;
}

export function positionSizing(input: {
  symbol: string;
  positionType: PositionType;
  side: string;
  entryPrice: number | null;
  qty: number | null;
  leverage?: number | null;
  exitPrice?: number | null;
  qtyUnit?: string | null;
}): PositionSizing {
  const instrument = instrumentUnitBasis(input.symbol, { qtyUnit: input.qtyUnit });
  const entry = Number.isFinite(input.entryPrice) ? Number(input.entryPrice) : null;
  const quantity = Number.isFinite(input.qty) ? Number(input.qty) : null;
  const declared = Number.isFinite(input.leverage) ? Number(input.leverage) : null;
  const monetaryReady = instrument.contractSize === "BASE_UNIT";
  const monetaryCalculation: MonetaryCalculation = monetaryReady
    ? { status: "READY", reason: null }
    : { status: "UNAVAILABLE", reason: "CONTRACT_SIZE_UNVERIFIED" };
  const warnings: string[] = [];
  if (!monetaryReady) warnings.push("CONTRACT_SIZE_UNVERIFIED");

  let leverageValue: number | null;
  let leverageSource: PositionSizing["leverage"]["source"];
  if (input.positionType === "SPOT") {
    leverageValue = 1;
    leverageSource = "SPOT_IMPLIED";
  } else if (declared != null && declared > 0) {
    leverageValue = declared;
    leverageSource = "USER_DECLARED";
  } else {
    leverageValue = null;
    leverageSource = "NOT_DECLARED";
    warnings.push("LEVERAGE_NOT_DECLARED");
  }

  const notional = monetaryReady && entry != null && quantity != null ? entry * quantity : null;
  let margin: number | null = null;
  let marginSource = monetaryReady ? "UNKNOWN" : "UNVERIFIED_CONTRACT_SIZE";
  if (notional != null) {
    if (input.positionType === "SPOT") {
      margin = notional;
      marginSource = "SPOT_FULL_PAYMENT";
    } else if (leverageValue != null) {
      margin = notional / leverageValue;
      marginSource = "ESTIMATED_FROM_DECLARED_LEVERAGE";
    }
  }

  let priceReturnPct: number | null = null;
  let positionReturnPctGross: number | null = null;
  let marginReturnPctGross: number | null = null;
  const exit = Number.isFinite(input.exitPrice) ? Number(input.exitPrice) : null;
  if (entry != null && entry > 0 && exit != null) {
    const direction = input.side === "BUY" || input.side === "LONG" ? 1 : -1;
    priceReturnPct = (direction * (exit - entry)) / entry * 100;
    if (notional != null && notional !== 0) {
      positionReturnPctGross = priceReturnPct;
    }
    if (margin != null && margin !== 0) {
      marginReturnPctGross = (priceReturnPct / 100) * (notional as number) / margin * 100;
    }
  }

  return {
    instrument,
    monetaryCalculation,
    leverage: { value: leverageValue, source: leverageSource },
    notional: { value: notional, currency: instrument.quote },
    marginEstimate: { value: margin, source: marginSource },
    quantity,
    priceReturnPct,
    positionReturnPctGross,
    marginReturnPctGross,
    warnings,
  };
}

/** Equal allocation helper: 3 targets -> 33.33 / 33.33 / 33.34 (sums to 100). */
export function equalPercentages(count: number): string[] {
  if (!Number.isInteger(count) || count < 1 || count > 3) return [];
  const base = Math.floor((100 / count) * 100) / 100;
  const values = Array.from({ length: count }, () => base.toFixed(2));
  values[count - 1] = (100 - base * (count - 1)).toFixed(2);
  return values;
}

export function concentrationWarnings(
  targets: Array<{ percent: string | number }>,
  stop: number | null,
  entry: number | null,
): string[] {
  const warnings: string[] = [];
  const percents = targets
    .map((target) => Number(target.percent))
    .filter((value) => Number.isFinite(value) && value > 0);
  if (percents.length > 0) {
    const total = percents.reduce((sum, value) => sum + value, 0);
    if (Math.abs(total - 100) > 1e-9) {
      warnings.push(`ALLOCATION_NOT_TOTAL:${total.toFixed(2)}`);
    }
    const first = percents[0];
    if (percents.length > 1 && first >= 80) {
      warnings.push(`FIRST_TARGET_DOMINANT:${first}`);
    }
  }
  if (stop != null && entry != null && entry > 0 && Math.abs((entry - stop) / entry) > 0.5) {
    warnings.push("STOP_VERY_WIDE");
  }
  return warnings;
}
