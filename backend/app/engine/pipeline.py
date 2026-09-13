"""Fetch, detect, score, serialize.

Kept out of the route handler so the same analysis can run from a script or
a test without FastAPI in the way.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app import data_sources
from app.ai.explainer import explain
from app.engine.patterns import PatternMatch, candlestick, classic, harmonic
from app.engine.signals import (
    PriceLevel,
    Verdict,
    compute_support_resistance,
    compute_verdict,
    filter_significant,
)
from app.graph.candle_builder import Candle
from app.graph.candle_source import CandleSeries, resolve_candles

MIN_CANDLES = 5


@dataclass
class AnalysisResult:
    protocol: str
    pool: str
    base_symbol: str
    interval: str
    range_key: str
    candles: list[Candle]
    series: CandleSeries | None = None
    patterns: list[PatternMatch] = field(default_factory=list)
    # Raw match count before filtering, reported so the trim is visible.
    total_detected: int = 0
    support_resistance: list[PriceLevel] = field(default_factory=list)
    verdict: Verdict | None = None
    explanation: str = ""


def run_analysis(
    protocol_key: str,
    pool_id: str,
    interval: str = "1h",
    range_key: str = "1w",
    base_symbol: str | None = None,
) -> AnalysisResult:
    resolved_base_symbol = base_symbol or data_sources.infer_base_symbol(protocol_key, pool_id)

    series = resolve_candles(
        protocol_key,
        pool_id,
        base_symbol=resolved_base_symbol,
        interval=interval,
        range_key=range_key,
    )
    candles = series.candles

    if len(candles) < MIN_CANDLES:
        raise ValueError(
            f"Only {len(candles)} candle(s) available for this pool over the "
            f"'{range_key}' window at '{interval}', need at least {MIN_CANDLES} "
            "for pattern detection. Try a longer range or a shorter interval."
        )

    detected: list[PatternMatch] = []
    detected += candlestick.detect(candles)
    detected += classic.detect(candles)
    detected += harmonic.detect(candles)

    support_resistance = compute_support_resistance(candles)

    # Levels must exist before patterns can be judged against them.
    patterns = filter_significant(detected, candles, support_resistance)

    # Only what survived gets a vote. Raw matches let weak candlestick
    # shapes outvote the real formations.
    verdict = compute_verdict(patterns, total_candles=len(candles))
    explanation = explain(verdict, patterns, support_resistance, resolved_base_symbol)

    return AnalysisResult(
        protocol=protocol_key,
        pool=pool_id,
        base_symbol=resolved_base_symbol,
        interval=interval,
        range_key=range_key,
        candles=candles,
        series=series,
        patterns=patterns,
        total_detected=len(detected),
        support_resistance=support_resistance,
        verdict=verdict,
        explanation=explanation,
    )
