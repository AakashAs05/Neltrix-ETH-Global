/**
 * Mirrors the Pydantic response models in backend/app/api/schemas.py and
 * routes_analyse.py. Kept hand-written rather than generated so the shapes
 * stay readable; if the backend models change, change these too.
 */

export type Direction = "bullish" | "bearish" | "neutral";
export type PatternCategory = "candlestick" | "classic" | "harmonic";
export type LevelKind = "support" | "resistance";

/** "messari-dex-amm" = one shared query shape across protocols; */
/** "uniswap-native" = Uniswap V4's own schema, adapted in the backend. */
export type SchemaFamily = "messari-dex-amm" | "uniswap-native";

export interface Protocol {
  key: string;
  display_name: string;
  network: string;
  schema_family: SchemaFamily;
  is_flagship: boolean;
}

export interface Pool {
  id: string;
  name: string;
  tokens: string[];
  total_value_locked_usd: number;
  cumulative_volume_usd: number;
}

export interface Candle {
  timestamp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume_usd: number;
  trade_count: number;
}

export interface Pattern {
  name: string;
  category: PatternCategory;
  direction: Direction;
  confidence: number;
  start_timestamp: number;
  end_timestamp: number;
  description: string;
}

export interface PriceLevel {
  price: number;
  kind: LevelKind;
  touches: number;
  strength: number;
}

export interface Verdict {
  direction: Direction;
  confidence: number;
  score: number;
  pattern_count: number;
}

/**
 * Where the candles came from. "subgraph-aggregate" means the subgraph
 * published real OHLC (cheap, covers long ranges); "derived-from-swaps"
 * means they were rebuilt from individual swap events (works everywhere,
 * but the cost scales with how busy the pool is).
 */
export type CandleSource = "subgraph-aggregate" | "derived-from-swaps";

export interface SeriesMeta {
  source: CandleSource;
  quote_symbol: string;
  swaps_scanned: number;
  rows_dropped: number;
  truncated: boolean;
  notes: string[];
}

export interface OhlcvResponse {
  protocol: string;
  pool: string;
  base_symbol: string;
  interval: string;
  range: string;
  source: CandleSource;
  quote_symbol: string;
  truncated: boolean;
  notes: string[];
  candles: Candle[];
}

export interface AnalyseResponse {
  protocol: string;
  pool: string;
  base_symbol: string;
  interval: string;
  range: string;
  series: SeriesMeta;
  candles: Candle[];
  patterns: Pattern[];
  /** Raw geometric matches before significance filtering. */
  total_detected: number;
  support_resistance: PriceLevel[];
  verdict: Verdict;
  explanation: string;
}

export interface AnalyseRequest {
  protocol: string;
  pool: string;
  interval?: string;
  range?: string;
  base_symbol?: string | null;
}

export const INTERVALS = ["5m", "15m", "1h", "4h", "1d"] as const;
export type Interval = (typeof INTERVALS)[number];

export const RANGES = ["1d", "1w", "1m", "3m", "1y"] as const;
export type Range = (typeof RANGES)[number];

export const RANGE_LABELS: Record<Range, string> = {
  "1d": "1 day",
  "1w": "1 week",
  "1m": "1 month",
  "3m": "3 months",
  "1y": "1 year",
};

/**
 * Which interval/range pairs the backend can serve from published OHLC
 * aggregates rather than by replaying swaps. Mirrors AGGREGATE_PLAN in
 * backend/app/graph/candle_source.py — used only to warn the user up
 * front that a combination will be slow or truncated.
 */
const AGGREGATE_INTERVALS: string[] = ["1h", "4h", "1d"];
const LONG_RANGES: string[] = ["1m", "3m", "1y"];

export function willBeExpensive(
  protocol: Protocol | undefined,
  interval: string,
  range: string,
): boolean {
  if (!LONG_RANGES.includes(range)) return false;
  const hasAggregates = protocol?.schema_family === "uniswap-native";
  return !(hasAggregates && AGGREGATE_INTERVALS.includes(interval));
}
