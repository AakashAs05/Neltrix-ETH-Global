"""Multi-candle chart patterns built from swing highs/lows.

Detected here: Double Top/Bottom, Head & Shoulders (and inverse), and the
triangle/wedge family (built from the trendline slope through the last few
swings). All of it operates on find_swing_points() from __init__.py, so
it's tolerant of the same window/threshold constants regardless of which
pattern is being checked.
"""

from __future__ import annotations

from app.graph.candle_builder import Candle

from . import BEARISH, BULLISH, NEUTRAL, PatternMatch, SwingPoint, find_swing_points

PEAK_TOLERANCE = 0.02  # swing points within 2% of each other count as "equal"
MIN_DEPTH = 0.03  # the trough/peak between them must differ by at least 3%


def _close_enough(a: float, b: float, tolerance: float = PEAK_TOLERANCE) -> bool:
    return abs(a - b) / max(abs(a), 1e-9) <= tolerance


def _detect_double_top_bottom(swings: list[SwingPoint], candles: list[Candle]) -> list[PatternMatch]:
    matches: list[PatternMatch] = []
    highs = [s for s in swings if s.kind == "high"]
    lows = [s for s in swings if s.kind == "low"]

    for a, b in zip(highs, highs[1:]):
        between = [low for low in lows if a.index < low.index < b.index]
        if not between:
            continue
        trough = min(between, key=lambda low: low.price)
        if _close_enough(a.price, b.price) and (a.price - trough.price) / a.price >= MIN_DEPTH:
            closeness = 1 - abs(a.price - b.price) / max(a.price, 1e-9) / PEAK_TOLERANCE
            matches.append(
                PatternMatch(
                    name="Double Top",
                    category="classic",
                    direction=BEARISH,
                    confidence=max(0.3, min(1.0, closeness)),
                    start_index=a.index,
                    end_index=b.index,
                    start_timestamp=a.timestamp,
                    end_timestamp=b.timestamp,
                    description=f"Two peaks near ${a.price:.4f} and ${b.price:.4f} with a trough at ${trough.price:.4f} between them.",
                )
            )

    for a, b in zip(lows, lows[1:]):
        between = [high for high in highs if a.index < high.index < b.index]
        if not between:
            continue
        peak = max(between, key=lambda high: high.price)
        if _close_enough(a.price, b.price) and (peak.price - a.price) / max(a.price, 1e-9) >= MIN_DEPTH:
            closeness = 1 - abs(a.price - b.price) / max(a.price, 1e-9) / PEAK_TOLERANCE
            matches.append(
                PatternMatch(
                    name="Double Bottom",
                    category="classic",
                    direction=BULLISH,
                    confidence=max(0.3, min(1.0, closeness)),
                    start_index=a.index,
                    end_index=b.index,
                    start_timestamp=a.timestamp,
                    end_timestamp=b.timestamp,
                    description=f"Two troughs near ${a.price:.4f} and ${b.price:.4f} with a peak at ${peak.price:.4f} between them.",
                )
            )
    return matches


def _detect_head_and_shoulders(swings: list[SwingPoint], candles: list[Candle]) -> list[PatternMatch]:
    matches: list[PatternMatch] = []
    highs = [s for s in swings if s.kind == "high"]
    lows = [s for s in swings if s.kind == "low"]

    for left, head, right in zip(highs, highs[1:], highs[2:]):
        if head.price > left.price and head.price > right.price and _close_enough(left.price, right.price, tolerance=0.04):
            matches.append(
                PatternMatch(
                    name="Head and Shoulders",
                    category="classic",
                    direction=BEARISH,
                    confidence=0.65,
                    start_index=left.index,
                    end_index=right.index,
                    start_timestamp=left.timestamp,
                    end_timestamp=right.timestamp,
                    description=f"Head at ${head.price:.4f} above two roughly-equal shoulders (${left.price:.4f}, ${right.price:.4f}).",
                )
            )

    for left, head, right in zip(lows, lows[1:], lows[2:]):
        if head.price < left.price and head.price < right.price and _close_enough(left.price, right.price, tolerance=0.04):
            matches.append(
                PatternMatch(
                    name="Inverse Head and Shoulders",
                    category="classic",
                    direction=BULLISH,
                    confidence=0.65,
                    start_index=left.index,
                    end_index=right.index,
                    start_timestamp=left.timestamp,
                    end_timestamp=right.timestamp,
                    description=f"Head at ${head.price:.4f} below two roughly-equal shoulders (${left.price:.4f}, ${right.price:.4f}).",
                )
            )
    return matches


def _slope(points: list[SwingPoint]) -> float:
    """Simple two-point slope (price change per candle index) rather than a
    full least-squares fit — good enough for classifying flat/rising/falling."""
    if len(points) < 2:
        return 0.0
    first, last = points[0], points[-1]
    if last.index == first.index:
        return 0.0
    return (last.price - first.price) / (last.index - first.index)


def _detect_triangles_and_wedges(swings: list[SwingPoint], candles: list[Candle], lookback: int = 4) -> list[PatternMatch]:
    highs = [s for s in swings if s.kind == "high"][-lookback:]
    lows = [s for s in swings if s.kind == "low"][-lookback:]
    if len(highs) < 2 or len(lows) < 2:
        return []

    high_slope = _slope(highs)
    low_slope = _slope(lows)
    # Normalize slopes to %-per-candle so flat/rising/falling thresholds
    # don't depend on the asset's absolute price.
    ref_price = candles[-1].close or 1.0
    high_pct = high_slope / ref_price
    low_pct = low_slope / ref_price
    flat = 0.0015  # ~0.15% per candle counts as "flat"

    start = min(highs[0].index, lows[0].index)
    end = max(highs[-1].index, lows[-1].index)
    span = (candles[start].timestamp, candles[end].timestamp)

    def make(name: str, direction: str, confidence: float, description: str) -> PatternMatch:
        return PatternMatch(
            name=name, category="classic", direction=direction, confidence=confidence,
            start_index=start, end_index=end, start_timestamp=span[0], end_timestamp=span[1],
            description=description,
        )

    if abs(high_pct) <= flat and low_pct > flat:
        return [make("Ascending Triangle", BULLISH, 0.55, "Flat resistance with a series of higher lows — bullish continuation setup.")]
    if abs(low_pct) <= flat and high_pct < -flat:
        return [make("Descending Triangle", BEARISH, 0.55, "Flat support with a series of lower highs — bearish continuation setup.")]
    if high_pct < -flat and low_pct > flat:
        return [make("Symmetrical Triangle", NEUTRAL, 0.45, "Highs falling and lows rising into a converging range — breakout direction undetermined.")]
    if high_pct > flat and low_pct > flat and high_pct < low_pct:
        return [make("Rising Wedge", BEARISH, 0.5, "Both highs and lows rising but converging — often resolves lower.")]
    if high_pct < -flat and low_pct < -flat and high_pct < low_pct:
        return [make("Falling Wedge", BULLISH, 0.5, "Both highs and lows falling but converging — often resolves higher.")]
    return []


def detect(candles: list[Candle], swing_window: int = 2) -> list[PatternMatch]:
    swings = find_swing_points(candles, window=swing_window)
    matches: list[PatternMatch] = []
    matches += _detect_double_top_bottom(swings, candles)
    matches += _detect_head_and_shoulders(swings, candles)
    matches += _detect_triangles_and_wedges(swings, candles)
    return matches
