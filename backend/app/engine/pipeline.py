"""Orchestrates the full analysis: fetch (Graph) -> detect -> score -> serialize.

This is the one function routes_analyse.py calls. Keeping it separate from
the route handler means the same analysis can be driven from a script or a
test without going through FastAPI.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.ai.explainer import explain
from app.engine.patterns import PatternMatch, candlestick, classic, harmonic
from app.engine.signals import PriceLevel, Verdict, compute_support_resistance, compute_verdict
from app.graph import standardized_query
from app.graph.candle_builder import Candle, build_ohlcv

MIN_CANDLES = 5


@dataclass
class AnalysisResult:
    protocol: str
    pool: str
    base_symbol: str
    interval: str
    candles: list[Candle]
    patterns: list[PatternMatch] = field(default_factory=list)
    support_resistance: list[PriceLevel] = field(default_factory=list)
    verdict: Verdict | None = None
    explanation: str = ""


def run_analysis(
    protocol_key: str,
    pool_id: str,
    interval: str = "1h",
    limit: int = 1000,
    base_symbol: str | None = None,
) -> AnalysisResult:
    resolved_base_symbol = base_symbol or standardized_query.infer_base_symbol(protocol_key, pool_id)

    swaps = standardized_query.get_recent_swaps(protocol_key, pool_id, limit=limit)
    candles = build_ohlcv(swaps, base_symbol=resolved_base_symbol, interval=interval)

    if len(candles) < MIN_CANDLES:
        raise ValueError(
            f"Only {len(candles)} candle(s) built from {len(swaps)} swap(s) — "
            f"need at least {MIN_CANDLES} for pattern detection. Try a larger "
            "`limit` or a shorter `interval`."
        )

    patterns: list[PatternMatch] = []
    patterns += candlestick.detect(candles)
    patterns += classic.detect(candles)
    patterns += harmonic.detect(candles)

    support_resistance = compute_support_resistance(candles)
    verdict = compute_verdict(patterns, total_candles=len(candles))
    explanation = explain(verdict, patterns, support_resistance, resolved_base_symbol)

    return AnalysisResult(
        protocol=protocol_key,
        pool=pool_id,
        base_symbol=resolved_base_symbol,
        interval=interval,
        candles=candles,
        patterns=patterns,
        support_resistance=support_resistance,
        verdict=verdict,
        explanation=explanation,
    )
