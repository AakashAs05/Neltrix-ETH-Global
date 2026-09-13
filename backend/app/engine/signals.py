"""Support/resistance levels and the weighted verdict rules.

Each detected pattern votes, weighted by how specific its category tends to
be and by how recently it completed.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field

from app.graph.candle_builder import Candle
from app.engine.patterns import BEARISH, BULLISH, PatternMatch, find_swing_points

CATEGORY_WEIGHT = {"harmonic": 1.5, "classic": 1.2, "candlestick": 0.8}
VERDICT_THRESHOLD = 0.12
LEVEL_TOLERANCE = 0.015  # cluster swing points within 1.5% of each other
MIN_LEVEL_TOUCHES = 2  # price has to have turned there more than once
MAX_LEVELS_PER_KIND = 3  # keep the chart readable; the strongest is drawn


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


def compute_support_resistance(
    candles: list[Candle],
    tolerance: float = LEVEL_TOLERANCE,
    min_touches: int = MIN_LEVEL_TOUCHES,
    max_levels: int = MAX_LEVELS_PER_KIND,
) -> list[PriceLevel]:
    """Cluster swing highs and lows into the few levels worth drawing.

    Clusters against the running mean rather than the first member, requires
    more than one touch, and merges support/resistance sitting on the same
    price. Without all three the chart fills with near-duplicate lines.
    """
    swings = find_swing_points(candles, window=2)
    if not swings:
        return []

    last_index = max(s.index for s in swings)
    levels: list[PriceLevel] = []

    for kind, source_kind in (("resistance", "high"), ("support", "low")):
        points = sorted((s for s in swings if s.kind == source_kind), key=lambda s: s.price)

        clusters: list[list[tuple[float, int]]] = []
        for point in points:
            if clusters:
                running_mean = sum(price for price, _ in clusters[-1]) / len(clusters[-1])
                if abs(point.price - running_mean) / max(running_mean, 1e-9) <= tolerance:
                    clusters[-1].append((point.price, point.index))
                    continue
            clusters.append([(point.price, point.index)])

        for cluster in clusters:
            touches = len(cluster)
            if touches < min_touches:
                continue
            prices = [price for price, _ in cluster]
            newest_index = max(index for _, index in cluster)
            # A recently touched level matters more than a stale one.
            recency = 0.6 + 0.4 * (newest_index / max(last_index, 1))
            strength = min(1.0, (touches / 5) * recency)
            levels.append(
                PriceLevel(
                    price=sum(prices) / touches,
                    kind=kind,
                    touches=touches,
                    strength=strength,
                )
            )

    levels = _merge_colliding_levels(levels, tolerance)
    levels.sort(key=lambda level: -level.strength)

    # Cap per kind, so a chart never ends up all resistance and no support.
    kept: list[PriceLevel] = []
    for kind in ("support", "resistance"):
        kept.extend([level for level in levels if level.kind == kind][:max_levels])
    kept.sort(key=lambda level: -level.strength)
    return kept


def _merge_colliding_levels(levels: list[PriceLevel], tolerance: float) -> list[PriceLevel]:
    """Collapse support/resistance pairs sitting on the same price."""
    merged: list[PriceLevel] = []
    for level in sorted(levels, key=lambda level: level.price):
        if merged:
            previous = merged[-1]
            same_price = abs(level.price - previous.price) / max(previous.price, 1e-9) <= tolerance
            if same_price:
                # A price that flipped roles is one level, not two.
                winner = previous if previous.touches >= level.touches else level
                merged[-1] = PriceLevel(
                    price=(previous.price + level.price) / 2,
                    kind=winner.kind,
                    touches=previous.touches + level.touches,
                    strength=max(previous.strength, level.strength),
                )
                continue
        merged.append(level)
    return merged


# Candlestick shapes are common and individually weak, so they are held to
# a higher bar than the rarer multi-candle formations.
CONFIDENCE_FLOOR = {"harmonic": 0.45, "classic": 0.50, "candlestick": 0.65}

# A candlestick pattern only counts where price was already contested.
LEVEL_PROXIMITY = 0.006


def filter_significant(
    patterns: list[PatternMatch],
    candles: list[Candle],
    levels: list[PriceLevel],
) -> list[PatternMatch]:
    """Cut raw detections down to the ones worth showing.

    Filters on context (a candlestick shape only counts near a level), a
    per-category confidence floor, and non-maximum suppression for
    overlapping matches. The caller keeps both counts, so the trim is visible.
    """
    if not candles:
        return []

    close_by_timestamp = {candle.timestamp: candle.close for candle in candles}
    level_prices = [level.price for level in levels]

    def near_level(pattern: PatternMatch) -> bool:
        close = close_by_timestamp.get(pattern.end_timestamp)
        if close is None or not level_prices:
            return False
        return any(
            abs(close - price) / max(price, 1e-9) <= LEVEL_PROXIMITY for price in level_prices
        )

    survivors: list[PatternMatch] = []
    for pattern in patterns:
        if pattern.confidence < CONFIDENCE_FLOOR.get(pattern.category, 0.5):
            continue
        if pattern.category == "candlestick" and not near_level(pattern):
            continue
        survivors.append(pattern)

    return _suppress_overlapping(survivors)


def _suppress_overlapping(patterns: list[PatternMatch]) -> list[PatternMatch]:
    """Keep the strongest of any same-name matches that overlap in time."""
    best_by_name: dict[str, list[PatternMatch]] = {}
    for pattern in patterns:
        best_by_name.setdefault(pattern.name, []).append(pattern)

    kept: list[PatternMatch] = []
    for group in best_by_name.values():
        # Strongest first, then drop anything overlapping one already kept.
        for pattern in sorted(group, key=lambda p: -p.confidence):
            overlaps = any(
                pattern.start_index <= other.end_index and other.start_index <= pattern.end_index
                for other in kept
                if other.name == pattern.name
            )
            if not overlaps:
                kept.append(pattern)

    kept.sort(key=lambda p: p.end_index)
    return kept


def compute_verdict(patterns: list[PatternMatch], total_candles: int) -> Verdict:
    if not patterns or total_candles <= 1:
        return Verdict(direction="neutral", confidence=0.0, score=0.0, pattern_count=len(patterns))

    weighted: list[tuple[float, PatternMatch]] = []
    raw_score = 0.0
    max_possible = 0.0

    # Repeated instances of the same pattern name inside one window are
    # correlated evidence, not independent confirmation, nine Bearish
    # Haramis in a choppy week describe one recurring characteristic of
    # that chop. Summing them at full weight let a single weak pattern
    # type outvote everything else, so each further occurrence counts for
    # progressively less.
    seen_by_name: Counter[str] = Counter()

    for pattern in patterns:
        seen_by_name[pattern.name] += 1
        repeat_damping = 1.0 / math.sqrt(seen_by_name[pattern.name])
        category_weight = CATEGORY_WEIGHT.get(pattern.category, 1.0) * repeat_damping
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
