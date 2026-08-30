import { useEffect, useState, useCallback } from "react";

export interface TvSyncState {
  symbol: string;
  timeframe: string;
  exchange: string;
  lastUpdated: number;
}

export const useTradingViewSync = (onSymbolChange?: (symbol: string, timeframe: string) => void) => {
  const [syncState, setSyncState] = useState<TvSyncState>({
    symbol: "BTCUSDT",
    timeframe: "15m",
    exchange: "BINANCE",
    lastUpdated: Date.now(),
  });

  const [isConnected, setIsConnected] = useState<boolean>(false);

  const fetchCurrentSync = useCallback(() => {
    fetch("http://127.0.0.1:8000/api/v1/tv/sync-status")
      .then((res) => res.json())
      .then((data) => {
        if (data.active_symbol) {
          setSyncState({
            symbol: data.active_symbol,
            timeframe: data.active_timeframe || "15m",
            exchange: data.active_exchange || "BINANCE",
            lastUpdated: data.last_sync_timestamp * 1000,
          });
        }
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    fetchCurrentSync();
    // Poll sync status periodically as fallback
    const interval = setInterval(fetchCurrentSync, 1000);
    return () => clearInterval(interval);
  }, [fetchCurrentSync]);

  return {
    syncState,
    isConnected,
    refresh: fetchCurrentSync,
  };
};