import { create } from "zustand";
import { Trade, QuantScorecard } from "../types";

interface TradeState {
  trades: Trade[];
  openPositions: Trade[];
  quantScorecard: QuantScorecard | null;
  isLoading: boolean;
  
  setTrades: (trades: Trade[]) => void;
  setOpenPositions: (positions: Trade[]) => void;
  setQuantScorecard: (scorecard: QuantScorecard) => void;
  addTrade: (trade: Trade) => void;
  updatePositionPnl: (positions: Trade[]) => void;
  setLoading: (loading: boolean) => void;
}

export const useTradeStore = create<TradeState>((set) => ({
  trades: [],
  openPositions: [],
  quantScorecard: null,
  isLoading: false,

  setTrades: (trades) => set({ trades }),
  setOpenPositions: (openPositions) => set({ openPositions }),
  setQuantScorecard: (quantScorecard) => set({ quantScorecard }),
  
  addTrade: (trade) => set((state) => ({
    trades: [trade, ...state.trades],
    openPositions: trade.status === "OPEN" ? [trade, ...state.openPositions] : state.openPositions
  })),

  updatePositionPnl: (positions) => set({ openPositions: positions }),
  setLoading: (isLoading) => set({ isLoading }),
}));