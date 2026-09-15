export interface CandlePoint {
  timestamp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export const CHART_INITIAL_LIMIT = 1000;
export const CHART_OLDER_CHUNK = 1000;

export const TIMEFRAME_MS: Record<string, number> = {
  "1m": 60_000,
  "3m": 180_000,
  "5m": 300_000,
  "15m": 900_000,
  "30m": 1_800_000,
  "1h": 3_600_000,
  "2h": 7_200_000,
  "4h": 14_400_000,
  "6h": 21_600_000,
  "8h": 28_800_000,
  "12h": 43_200_000,
  "1d": 86_400_000,
  "3d": 259_200_000,
  "1w": 604_800_000,
  "1M": 2_629_800_000,
};

export function timeframeMs(timeframe: string): number {
  return TIMEFRAME_MS[timeframe] ?? 3_600_000;
}

/**
 * Union two candle arrays by timestamp, keeping the newer record and returning
 * ascending time order.  Used to prepend older history and to keep already
 * loaded history while the live refresh replaces the recent window.
 */
export function mergeCandleHistory(
  first: CandlePoint[],
  second: CandlePoint[],
): CandlePoint[] {
  const byTime = new Map<number, CandlePoint>();
  for (const candle of first) byTime.set(candle.timestamp, candle);
  for (const candle of second) byTime.set(candle.timestamp, candle);
  return Array.from(byTime.values()).sort((a, b) => a.timestamp - b.timestamp);
}

/**
 * The provider returned a full page; older bars may still exist.  A short page
 * means the provider's history start was reached.
 */
export function hasMoreHistory(requested: number, received: number): boolean {
  return received > 0 && received >= requested;
}

export function olderStartMs(oldestTimestampSeconds: number, timeframe: string): number {
  return oldestTimestampSeconds * 1000 - CHART_OLDER_CHUNK * timeframeMs(timeframe);
}
