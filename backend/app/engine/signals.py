"""Support/resistance levels and the weighted verdict rules.

The verdict is a deterministic, explainable roll-up of every PatternMatch
the three detectors produced: each pattern's vote is weighted by how
specific its category tends to be (harmonic > classic > candlestick) and
by how recent it is (a pattern that just completed on the latest candle
matters more than one from the start of the window).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.graph.candle_builder import Candle
from app.engine.patterns import BEARISH, BULLISH, PatternMatch, find_swing_points

CATEGORY_WEIGHT = {"harmonic": 1.5, "classic": 1.2, "candlestick": 0.8}
VERDICT_THRESHOLD = 0.12
LEVEL_TOLERANCE = 0.015  # cluster swing points within 1.5% of each other


@dataclass(frozen=True)
class PriceLevel:
    price: float
    kind: str  # "support" | "resistance"
    touches: int
    strength: float  # 0..1


@dataclass(frozen=True)
class Verdict:
    direction: str  # "bullish" | "bearish" | "neutral"
    confidence: float  # 0..1
    score: float  # normalized, roughly -1..1
    pattern_count: int
    contributing_patterns: list[PatternMatch] = field(default_factory=list)


def compute_support_resistance(candles: list[Candle], tolerance: float = LEVEL_TOLERANCE) -> list[PriceLevel]:
    swings = find_swing_points(candles, window=2)
    levels: list[PriceLevel] = []

    for kind, source_kind in (("resistance", "high"), ("support", "low")):
        points = sorted((s for s in swings if s.kind == source_kind), key=lambda s: s.price)
        clusters: list[list[float]] = []
        for point in points:
            if clusters and abs(point.price - clusters[-1][0]) / max(clusters[-1][0], 1e-9) <= tolerance:
                clusters[-1].append(point.price)
            else:
                clusters.append([point.price])
        for cluster in clusters:
            avg_price = sum(cluster) / len(cluster)
            touches = len(cluster)
            levels.append(PriceLevel(price=avg_price, kind=kind, touches=touches, strength=min(1.0, touches / 4)))

    levels.sort(key=lambda level: -level.strength)
    return levels


def compute_verdict(patterns: list[PatternMatch], total_candles: int) -> Verdict:
    if not patterns or total_candles <= 1:
        return Verdict(direction="neutral", confidence=0.0, score=0.0, pattern_count=len(patterns))

    weighted: list[tuple[float, PatternMatch]] = []
    raw_score = 0.0
    max_possible = 0.0

    for pattern in patterns:
        category_weight = CATEGORY_WEIGHT.get(pattern.category, 1.0)
        # Patterns ending later in the window (closer to "now") count for more:
        # 0.5x at the start of the window, up to 1.0x at the most recent candle.
        recency = 0.5 + 0.5 * (pattern.end_index / max(total_candles - 1, 1))
        weight = category_weight * recency * pattern.confidence

        max_possible += category_weight
        if pattern.direction == BULLISH:
            raw_score += weight
        elif pattern.direction == BEARISH:
            raw_score -= weight
        weighted.append((weight, pattern))

    normalized = raw_score / max_possible if max_possible else 0.0

    if normalized > VERDICT_THRESHOLD:
        direction = "bullish"
    elif normalized < -VERDICT_THRESHOLD:
        direction = "bearish"
    else:
        direction = "neutral"

    confidence = max(0.0, min(1.0, abs(normalized) * 2))
    top_patterns = [p for _, p in sorted(weighted, key=lambda item: -item[0])][:5]

    return Verdict(
        direction=direction,
        confidence=confidence,
        score=normalized,
        pattern_count=len(patterns),
        contributing_patterns=top_patterns,
    )
