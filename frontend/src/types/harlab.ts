export type Side = "buy" | "sell";

export interface ActiveOrder {
  order_id: string;
  side: Side;
  price: number;
  quantity: number;
  initial_quantity: number;
  status: string;
  timestamp: number;
}

export interface TradeRecord {
  trade_id: number;
  buy_order_id: string;
  sell_order_id: string;
  price: number;
  quantity: number;
  aggressor_side: Side;
  timestamp: number;
}

export interface ExecutionStats {
  submitted_orders: number;
  cancelled_orders: number;
  active_orders: number;
  trade_count: number;
  total_executed_quantity: number;
  notional_value: number;
  vwap: number | null;
  average_trade_size: number | null;
  fill_rate: number | null;
  buy_aggressor_volume: number;
  sell_aggressor_volume: number;
}

export interface BookMetrics {
  best_bid: number | null;
  best_ask: number | null;
  spread: number | null;
  relative_spread: number | null;
  relative_spread_bps: number | null;
  mid_price: number | null;
  weighted_mid_price: number | null;
  microprice: number | null;
  order_imbalance_l1: number | null;
  order_imbalance_l5: number | null;
  bid_depth_l1: number;
  ask_depth_l1: number;
  bid_depth_total: number;
  ask_depth_total: number;
  total_displayed_depth: number;
  tick_size: number;
  execution?: ExecutionStats;
}

export interface BookSnapshot {
  data_origin: string;
  is_synthetic: boolean;
  tick_size: number;
  bids: [number, number][];
  asks: [number, number][];
  active_orders: ActiveOrder[];
  recent_trades: TradeRecord[];
  metrics: BookMetrics;
}

export interface DatasetMetadata {
  dataset_id: string;
  name: string;
  source_type: string;
  is_synthetic: boolean;
  has_order_book_depth: boolean;
  row_count: number;
  columns: string[];
  timestamp_column: string;
  missing_values_dropped: number;
  description: string;
  notes: string;
}

export interface SimulationPoint {
  step: number;
  best_bid: number | null;
  best_ask: number | null;
  mid_price: number | null;
  microprice: number | null;
  spread: number | null;
  imbalance_l1: number | null;
  imbalance_l5: number | null;
  bid_depth_l1: number;
  ask_depth_l1: number;
  bid_depth_total: number;
  ask_depth_total: number;
  cumulative_volume: number;
  last_trade_price: number | null;
}

export interface SimulationOutput {
  data_origin: string;
  is_synthetic: boolean;
  disclaimer: string;
  config: Record<string, unknown>;
  series: SimulationPoint[];
  events: Record<string, unknown>[];
  total_events: number;
  trades: TradeRecord[];
  execution_stats: ExecutionStats;
}

export interface Hypothesis {
  hypothesis_id: string;
  title: string;
  question: string;
  null_hypothesis: string;
  independent_variable: string;
  dependent_variable: string;
  requires_order_book_depth: boolean;
  assumptions: string[];
  limitations: string[];
}

export interface StatsBlock {
  n: number;
  pearson_r: number | null;
  pearson_p: number | null;
  spearman_rho: number | null;
  spearman_p: number | null;
  ols_slope: number | null;
  ols_intercept: number | null;
  r_squared: number | null;
  ci_95_low: number | null;
  ci_95_high: number | null;
  note: string | null;
}

export interface BacktestSummary {
  trade_count: number;
  gross_return_bps: number;
  net_return_bps: number;
  total_cost_bps: number;
  mean_net_trade_bps: number;
  hit_rate: number | null;
  sharpe_like: number | null;
  fee_bps: number;
  slippage_bps: number;
}

export interface ExperimentResult {
  experiment_id: string;
  created_at: string;
  hypothesis: Hypothesis;
  dataset: DatasetMetadata;
  config: Record<string, unknown>;
  leakage_check: {
    passed: boolean;
    causal_ordering_ok: boolean;
    temporal_boundary_ok: boolean;
    train_max_target_index: number;
    test_min_feature_index: number | null;
  };
  in_sample_stats: StatsBlock;
  out_of_sample_stats: StatsBlock;
  walk_forward: {
    fold: number;
    train_count: number;
    test_count: number;
    pearson_r: number | null;
    pearson_p: number | null;
    r_squared: number | null;
  }[];
  baseline_comparison: {
    out_of_sample_directional_accuracy: number | null;
    naive_majority_baseline_accuracy: number | null;
    nonzero_target_count: number;
  };
  cost_aware_backtest: BacktestSummary | null;
  conclusion: string;
  warnings: string[];
  scatter_sample: { x: number; y: number }[];
}

export interface AIProviderStatus {
  provider: string;
  model: string;
  configured: boolean;
  priority: number;
  requests_succeeded: number;
  requests_failed: number;
  in_cooldown: boolean;
  cooldown_remaining_seconds: number;
  last_error_kind: string | null;
  last_error_message: string | null;
}

export interface AIRouterStatus {
  priority_order: string[];
  any_configured: boolean;
  cooldown_seconds: number;
  providers: AIProviderStatus[];
}

export interface HealthResponse {
  status: string;
  project: string;
  version: string;
  datasets_count: number;
  experiments_count: number;
  simulations_run: number;
  ai: AIRouterStatus;
}

export interface RegimeSummary {
  dataset_id: string;
  train_rows: number;
  test_rows: number;
  fitted_train_thresholds: {
    vol_low: number;
    vol_high: number;
    spread_high: number | null;
  };
  out_of_sample_regime_counts: Record<string, number>;
}
