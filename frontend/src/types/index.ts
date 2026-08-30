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
  time: number;
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

export interface MaeMfePoint {
  trade_id: string;
  symbol: string;
  side: string;
  entry_price: number;
  exit_price: number;
  stop_loss?: number | null;
  take_profit?: number | null;
  risk_unit: number;
  mae_price: number;
  mfe_price: number;
  mae_r: number;
  mfe_r: number;
  exit_efficiency: number;
  pnl: number;
  r_multiple: number;
  status: string;
  entry_time?: string;
  exit_time?: string;
}

export interface StopSensitivity {
  stop_distance_r: number;
  survival_rate_pct: number;
}

export interface MaeMfeAnalyticsResponse {
  total_analyzed: number;
  average_mae_r: number;
  average_mfe_r: number;
  average_exit_efficiency_pct: number;
  trades_left_money_on_table: number;
  recommended_target_r: number;
  stop_loss_sensitivities: StopSensitivity[];
  points: MaeMfePoint[];
}

export interface ComplianceRuleStatus {
  rule: string;
  limit: string;
  current: string;
  utilization_pct: number;
  status: "PASS" | "WARN" | "CRITICAL" | "BREACH" | "IN_PROGRESS" | "PASSED";
}

export interface ComplianceConfigData {
  account_size: number;
  daily_loss_limit_pct: number;
  max_drawdown_pct: number;
  profit_target_pct: number;
  min_trading_days: number;
  trailing_drawdown: boolean;
  require_stop_loss: boolean;
  max_risk_per_trade_pct: number;
}

export interface ComplianceStatusResponse {
  account_size: number;
  current_equity: number;
  high_watermark: number;
  today_pnl: number;
  all_time_pnl: number;
  current_drawdown_amount: number;
  current_drawdown_pct: number;
  daily_loss_budget: number;
  daily_loss_remaining: number;
  max_dd_budget: number;
  max_dd_remaining: number;
  profit_target_amount: number;
  days_traded: number;
  overall_status: "COMPLIANT" | "WARNING" | "CRITICAL" | "BREACHED";
  is_breached: boolean;
  rules: ComplianceRuleStatus[];
  naked_positions_count: number;
  config: ComplianceConfigData;
}

export interface PivotRow {
  dimensions: Record<string, string>;
  group_key: string;
  trades_count: number;
  win_rate: number;
  total_pnl: number;
  avg_pnl: number;
  profit_factor: number;
  avg_r_multiple: number;
  sqn: number;
  expectancy: number;
  max_win: number;
  max_loss: number;
}

export interface PivotGridResponse {
  dimensions: string[];
  total_buckets: number;
  rows: PivotRow[];
}
export interface ReplayTradeState {
  trade_id: string;
  symbol: string;
  side: string;
  entry_price: number;
  current_price: number;
  qty: number;
  stop_loss?: number | null;
  take_profit?: number | null;
  is_active: boolean;
  is_past_exit: boolean;
  unrealized_pnl: number;
  r_multiple: number;
  mae_r: number;
  mfe_r: number;
  entry_index: number;
  exit_index: number;
}

export interface ReplaySessionResponse {
  session_id: string;
  symbol: string;
  total_bars: number;
  current_index: number;
  entry_index: number;
  exit_index: number;
  speed_multiplier: number;
  is_playing: boolean;
  current_candle: Candle;
  trade: ReplayTradeState | null;
  visible_candles: Candle[];
}

export interface PlaybookRule {
  id: string;
  playbook_id: string;
  rule_text: string;
  is_mandatory: number | boolean;
  weight: number;
}

export interface Playbook {
  id: string;
  title: string;
  description: string;
  win_rate_target: number;
  rr_target: number;
  created_at: string;
  updated_at: string;
  rules: PlaybookRule[];
  trades_count: number;
  performance: QuantScorecard;
}

export interface TradeDriftItem {
  trade_id: string;
  symbol: string;
  side: string;
  actual_entry: number;
  planned_entry: number;
  entry_drift_dollars: number;
  actual_exit: number;
  stop_loss?: number | null;
  take_profit?: number | null;
  actual_pnl: number;
  theoretical_pnl: number;
  is_early_exit: boolean;
  panic_cost: number;
  drift_ratio: number;
  risk_unit: number;
}

export interface ExecutionDriftResponse {
  total_trades: number;
  total_actual_pnl: number;
  total_theoretical_pnl: number;
  total_panic_exit_leakage: number;
  early_exits_count: number;
  avg_drift_ratio: number;
  execution_fidelity_pct: number;
  trades: TradeDriftItem[];
}
export interface TiltStatusResponse {
  tilt_score: number;
  status: "CALM" | "ELEVATED" | "HIGH_TILT" | "BREACH_RISK";
  consecutive_losses: number;
  revenge_trades_count: number;
  fomo_trades_count: number;
  lot_escalation_detected: boolean;
  risk_message: string;
}

export interface BehavioralAnomaly {
  trade_id: string;
  symbol: string;
  type: "FOMO_CHASE" | "REVENGE_TRADING" | "IMPULSIVE_CHURN";
  severity: "NORMAL" | "MODERATE" | "HIGH" | "CRITICAL";
  metric_detail: string;
  pnl?: number | null;
  entry_time?: string;
}

export interface AnomaliesResponse {
  total_anomalies_count: number;
  anomalies: BehavioralAnomaly[];
}

export interface FatigueMatrixRow {
  sequence_num: number;
  label: string;
  trades_count: number;
  win_rate: number;
  total_pnl: number;
  avg_pnl: number;
  profit_factor: number;
  expectancy: number;
  fatigue_state: "PEAK_FOCUS" | "OPTIMAL" | "MODERATE_FATIGUE" | "SEVERE_OVERTRADING";
}

export interface FatigueMatrixResponse {
  inflection_point: string;
  early_win_rate_pct: number;
  late_win_rate_pct: number;
  performance_decay_pct: number;
  matrix: FatigueMatrixRow[];
}