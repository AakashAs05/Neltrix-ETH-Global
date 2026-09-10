"""Shared types and utilities used by all three pattern detectors.

candlestick.py, classic.py, and harmonic.py all consume the same candle
shape (app.graph.candle_builder.Candle) and all report matches as
PatternMatch, so those live here instead of being duplicated three times.
Swing-point detection (local highs/lows) is likewise shared: classic.py
uses it to find double tops/head-and-shoulders/triangles, and harmonic.py
uses the same points as the X-A-B-C-D vertices of a harmonic pattern.
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
    """A candle is a swing high/low if its high/low is the most extreme
    within `window` candles on both sides. Simple and deterministic; not
    as noise-resistant as e.g. ZigZag with a % threshold, but sufficient
    for detecting the chart-pattern and harmonic-pattern vertices below.
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
