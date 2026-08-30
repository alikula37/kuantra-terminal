export type TradeSide = "BUY" | "SELL" | "LONG" | "SHORT";
export type TradeStatus = "OPEN" | "CLOSED" | "CANCELED";

export interface Trade {
  id: string;
  symbol: string;
  side: TradeSide;
  entry_price: number;
  exit_price?: number | null;
  qty: number;
  stop_loss?: number | null;
  take_profit?: number | null;
  entry_time: string;
  exit_time?: string | null;
  status: TradeStatus;
  pnl?: number;
  r_multiple?: number | null;
  commission?: number;
  notes?: string;
  created_at?: string;
  updated_at?: string;
  unrealized_pnl?: number;
  current_price?: number;
}

export interface Candle {
  time: number; // UNIX timestamp in seconds
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
  trades_count?: number;
}

export interface MarketTicker {
  symbol: string;
  price: number;
  volume?: number;
  latency_ms: number;
  timestamp: number;
}

export interface QuantScorecard {
  total_trades: number;
  win_rate: number;
  loss_rate: number;
  total_pnl: number;
  avg_win: number;
  avg_loss: number;
  profit_factor: number;
  expectancy: number;
  sqn: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  max_drawdown_amount: number;
  max_drawdown_pct: number;
  half_kelly_pct: number;
}

export interface SymbolBreakdown {
  symbol: string;
  count: number;
  total_pnl: number;
  avg_pnl: number;
  win_rate: number;
}