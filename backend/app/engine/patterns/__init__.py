"""Shared types and the swing-point finder used by all three detectors.

Kept here rather than duplicated, since classic.py and harmonic.py read the
same swing points as chart vertices.
"""

from __future__ import annotations

from dataclasses import dataclass

BULLISH = "bullish"
BEARISH = "bearish"
NEUTRAL = "neutral"


@dataclass(frozen=True)
class PatternMatch:
    name: str
    category: str  # "candlestick" | "classic" | "harmonic"
    direction: str  # BULLISH | BEARISH | NEUTRAL
    confidence: float  # 0..1, how well-formed the pattern is
    start_index: int
    end_index: int
    start_timestamp: int
    end_timestamp: int
    description: str


@dataclass(frozen=True)
class SwingPoint:
    index: int
    timestamp: int
    price: float
    kind: str  # "high" | "low"


def find_swing_points(candles: list, window: int = 2) -> list[SwingPoint]:
    """A candle is a swing point if it is the most extreme within `window`
    candles either side. Less noise-resistant than ZigZag, but enough here.
    """
    points: list[SwingPoint] = []
    n = len(candles)
    for i in range(window, n - window):
        c = candles[i]
        neighborhood = candles[i - window : i] + candles[i + 1 : i + 1 + window]
        if all(c.high >= other.high for other in neighborhood):
            points.append(SwingPoint(index=i, timestamp=c.timestamp, price=c.high, kind="high"))
        elif all(c.low <= other.low for other in neighborhood):
            points.append(SwingPoint(index=i, timestamp=c.timestamp, price=c.low, kind="low"))
    return points
