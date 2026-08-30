import { create } from "zustand";
import { Candle } from "../types";

interface MarketState {
  symbol: string;
  currentPrice: number;
  prevPrice: number;
  latencyMs: number;
  isConnected: boolean;
  candles: Candle[];
  lastTickTime: number;
  recentTicks: { price: number; volume: number; time: number; side: "BUY" | "SELL" }[];
  
  setSymbol: (symbol: string) => void;
  setConnectionStatus: (connected: boolean) => void;
  updateTick: (price: number, latency: number, timestamp: number, volume?: number) => void;
  setCandles: (candles: Candle[]) => void;
  updateCandle: (candle: Candle) => void;
}

export const useMarketStore = create<MarketState>((set) => ({
  symbol: "BTCUSDT",
  currentPrice: 65420.50,
  prevPrice: 65420.50,
  latencyMs: 12,
  isConnected: false,
  candles: [],
  lastTickTime: Date.now(),
  recentTicks: [],

  setSymbol: (symbol) => set({ symbol: symbol.toUpperCase() }),
  setConnectionStatus: (connected) => set({ isConnected: connected }),
  
  updateTick: (price, latency, timestamp, volume = 0.5) => set((state) => {
    const side: "BUY" | "SELL" = price >= state.currentPrice ? "BUY" : "SELL";
    const tick = { price, volume, time: timestamp, side };
    const newRecent = [tick, ...state.recentTicks.slice(0, 19)];
    
    return {
      prevPrice: state.currentPrice,
      currentPrice: price,
      latencyMs: latency,
      lastTickTime: timestamp,
      recentTicks: newRecent,
    };
  }),

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