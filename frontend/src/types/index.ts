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
  unrealized_pnl?: number | null;
  current_price?: number | null;
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
  price: number | null;
  volume?: number;
  event_age_ms: number | null;
  timestamp: number | null;
  status: MarketDataStatus;
}

export type MarketDataStatus = "LIVE" | "DEGRADED" | "UNAVAILABLE";

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
  risk_unit: number | null;
  mae_price: number | null;
  mfe_price: number | null;
  mae_r: number | null;
  mfe_r: number | null;
  exit_efficiency: number | null;
  pnl: number | null;
  r_multiple: number | null;
  status: string;
  entry_time?: string;
  exit_time?: string;
  provenance?: ReplayProvenance | null;
  risk_reason?: string | null;
}

export interface StopSensitivity {
  stop_distance_r: number;
  survival_rate_pct: number;
}

export interface MaeMfeAnalyticsResponse {
  status: "READY" | "NO_DATA" | "UNAVAILABLE";
  reason: string | null;
  message: string | null;
  provenance: ReplayProvenance | null;
  total_candidates: number;
  total_analyzed: number;
  total_r_analyzed: number;
  excluded_trades: Array<{ trade_id: string; reason: string; message: string }>;
  average_mae_r: number | null;
  average_mfe_r: number | null;
  average_exit_efficiency_pct: number | null;
  trades_left_money_on_table: number;
  recommended_target_r: number | null;
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
  current_price: number | null;
  qty: number;
  stop_loss?: number | null;
  take_profit?: number | null;
  is_active: boolean;
  is_past_exit: boolean;
  phase: "PRE_ENTRY" | "ACTIVE" | "CLOSED";
  risk_unit: number | null;
  unrealized_pnl: number | null;
  realized_pnl: number | null;
  r_multiple: number | null;
  mae_r: number | null;
  mfe_r: number | null;
  entry_index: number | null;
  exit_index: number | null;
}

export interface ReplayProvenance {
  quality: "BAR_APPROXIMATION";
  source: "DUCKDB_CANDLES";
  source_verified: false;
  timeframe: "1m";
  [key: string]: unknown;
}

export interface ReplaySessionResponse {
  status: "READY" | "NO_DATA" | "UNAVAILABLE";
  reason: string | null;
  message: string | null;
  provenance: ReplayProvenance | null;
  session_id: string | null;
  symbol: string | null;
  total_bars: number;
  current_index: number | null;
  entry_index: number | null;
  exit_index: number | null;
  speed_multiplier: number;
  is_playing: boolean;
  current_candle: Candle | null;
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

export interface EvidenceLedgerIntegrity {
  valid: boolean;
  checked_events: number;
  errors: string[];
}

export interface EvidenceCoverage {
  ready: boolean;
  legacy_trade_count?: number;
  projection_trade_count?: number;
  missing_trade_ids?: string[];
  extra_trade_ids?: string[];
  [key: string]: unknown;
}

export interface EvidenceEvent {
  event_id: string;
  event_type: string;
  account_id: string;
  venue: string;
  occurred_at_utc: string;
  received_at_utc?: string;
  chain_date_utc: string;
  chain_sequence: number;
  schema_version: string;
  adapter_version: string;
  correlation_id: string;
  causation_id?: string | null;
  idempotency_key: string;
  raw_payload_sha256: string;
  normalized_payload?: Record<string, unknown>;
  provenance?: Record<string, unknown>;
  prev_hash: string;
  event_hash: string;
}

export interface EvidenceMarketContext {
  status: "READY" | "NO_DATA" | "UNAVAILABLE" | string;
  reason?: string | null;
  message?: string | null;
  provenance?: (Omit<ReplayProvenance, "source_verified"> & { source_verified?: boolean }) | null;
  market_context?: Record<string, unknown> | null;
  candles?: Candle[];
  [key: string]: unknown;
}

export interface EvidenceImportReview {
  status: string;
  decision: string;
  source_type?: string;
  source_file_sha256?: string;
  reconciliation?: {
    status?: string;
    discrepancy_count?: number;
    [key: string]: unknown;
  };
  coverage?: Record<string, unknown>;
  discrepancies?: Array<Record<string, unknown>>;
  event_id?: string;
  event_hash?: string;
  [key: string]: unknown;
}

export type EvidenceCoverageState = "COMPLETE" | "PARTIAL" | "UNKNOWN" | "NOT_AVAILABLE" | string;

export interface EvidenceCoverageSummary {
  overall: EvidenceCoverageState;
  trade_snapshot: EvidenceCoverageState;
  realized_pnl: EvidenceCoverageState;
  fees: EvidenceCoverageState;
  funding_transfer: EvidenceCoverageState;
  account_events: EvidenceCoverageState;
  market_context: EvidenceCoverageState;
  [key: string]: unknown;
}

export interface EvidenceRuleReference {
  kind: "risk" | "playbook" | string;
  rule_id: string;
  version: string;
  snapshot_sha256: string;
  event_id?: string;
  event_hash?: string;
}

export interface TradeEvidencePack {
  trade_id: string;
  trade: Trade | null;
  read_source: "typed_projection" | "compatibility_legacy" | string;
  coverage: EvidenceCoverage;
  ledger_integrity: EvidenceLedgerIntegrity;
  events: EvidenceEvent[];
  event_count: number;
  market_context: EvidenceMarketContext;
  import_review?: EvidenceImportReview | null;
  import_review_history?: EvidenceImportReview[];
  reconciliation_review?: EvidenceImportReview | null;
  reconciliation_review_history?: EvidenceImportReview[];
  coverage_summary?: EvidenceCoverageSummary;
  applicable_rules?: EvidenceRuleReference[];
  snapshot_sha256?: string;
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
export interface VisionParseResult {
  symbol: string;
  timeframe: string;
  side: string;
  entry_price: number;
  stop_loss: number;
  take_profit: number;
  risk_unit: number;
  reward_unit: number;
  risk_reward_ratio: number;
  confidence_score: number;
  validation_notes: string;
  raw_ocr_snippet: string;
}

export interface AiAuditReportResponse {
  grade: string;
  executive_summary: string;
  strengths: string[];
  critical_risks: string[];
  actionable_directives: string[];
  deterministic_context: Record<string, any>;
}

export interface AiQueryResult {
  query: string;
  sql: string;
  total_records: number;
  columns: string[];
  rows: Record<string, any>[];
  ai_commentary: string;
}
export interface HardwareProfile {
  detected_backend: string;
  hardware_tier: string;
  device_name: string;
  vram_gb: number;
  cpu_cores: number;
  recommended_quant: string;
  recommended_threads: number;
  estimated_tokens_per_sec: number;
  notes: string;
}

export interface OnboardingStatusResponse {
  first_boot_completed: boolean;
  ai_mode: string;
  hardware: HardwareProfile;
}

export interface ModelDownloadStatus {
  model_name: string;
  status: string;
  progress_pct: number;
  downloaded_bytes: number;
  total_bytes: number;
  speed_mbps: number;
  is_verified: boolean;
}
