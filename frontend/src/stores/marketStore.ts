import { create } from "zustand";
import { Candle, MarketDataStatus } from "../types";

interface MarketState {
  symbol: string;
  currentPrice: number | null;
  prevPrice: number | null;
  eventAgeMs: number | null;
  isConnected: boolean;
  marketDataStatus: MarketDataStatus;
  candles: Candle[];
  lastTickTime: number | null;
  recentTicks: { price: number; volume: number; time: number; side: "BUY" | "SELL" | "UNKNOWN" }[];
  
  setSymbol: (symbol: string) => void;
  setConnectionStatus: (connected: boolean) => void;
  setMarketDataStatus: (status: MarketDataStatus) => void;
  updateTick: (price: number, eventAgeMs: number | null, timestamp: number, volume: number, side?: string) => void;
  setMarketSnapshot: (price: number | null, eventAgeMs: number | null, timestamp: number | null, status?: MarketDataStatus) => void;
  setCandles: (candles: Candle[]) => void;
  updateCandle: (candle: Candle) => void;
}

export const useMarketStore = create<MarketState>((set) => ({
  symbol: "BTCUSDT",
  currentPrice: null,
  prevPrice: null,
  eventAgeMs: null,
  isConnected: false,
  marketDataStatus: "UNAVAILABLE",
  candles: [],
  lastTickTime: null,
  recentTicks: [],

  setSymbol: (symbol) => set({ symbol: symbol.toUpperCase() }),
  setConnectionStatus: (connected) => set({ isConnected: connected }),
  setMarketDataStatus: (status) => set({ marketDataStatus: status }),
  
  updateTick: (price, eventAgeMs, timestamp, volume, side) => set((state) => {
    const tickSide: "BUY" | "SELL" | "UNKNOWN" = side === "BUY" || side === "SELL" || side === "UNKNOWN" ? side : "UNKNOWN";
    const tick = { price, volume, time: timestamp, side: tickSide };
    const newRecent = [tick, ...state.recentTicks.slice(0, 19)];
    
    return {
      prevPrice: state.currentPrice,
      currentPrice: price,
      eventAgeMs,
      lastTickTime: timestamp,
      marketDataStatus: "LIVE",
      recentTicks: newRecent,
    };
  }),

  setMarketSnapshot: (price, eventAgeMs, timestamp, status = "UNAVAILABLE") => set((state) => ({
    prevPrice: state.currentPrice,
    currentPrice: price,
    eventAgeMs,
    lastTickTime: timestamp,
    marketDataStatus: status,
  })),

  setCandles: (candles) => set({ candles }),
  
  updateCandle: (candle) => set((state) => {
    const existingIndex = state.candles.findIndex((c) => c.time === candle.time);
    if (existingIndex >= 0) {
      const updated = [...state.candles];
      updated[existingIndex] = candle;
      return { candles: updated };
    } else {
      return { candles: [...state.candles, candle] };
    }
  }),
}));
