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


# The head has to actually stand out from the shoulders. Without this a
# barely-higher middle peak in ordinary chop reads as a Head & Shoulders,
# which is why six of them were being reported in a single week of hourly
# candles — a formation that should be rare.
MIN_HEAD_PROMINENCE = 0.02

# The two troughs between the peaks form the neckline. A real formation
# has a roughly level neckline; if the two lows are far apart the shape
# isn't the pattern regardless of what the peaks do.
NECKLINE_TOLERANCE = 0.03


def _head_and_shoulders_confidence(
    left: SwingPoint, head: SwingPoint, right: SwingPoint, neck_a: float, neck_b: float
) -> float:
    """Score how well-formed the shape is, rather than assuming a flat 0.65.

    Three independent qualities, averaged: how symmetric the shoulders
    are, how level the neckline is, and how far the head stands proud of
    the shoulders. All three are what a chartist actually eyeballs.
    """
    shoulder_symmetry = 1 - min(1.0, abs(left.price - right.price) / max(left.price, 1e-9) / 0.04)
    neckline_levelness = 1 - min(1.0, abs(neck_a - neck_b) / max(neck_a, 1e-9) / NECKLINE_TOLERANCE)
    shoulder_avg = (left.price + right.price) / 2
    prominence = abs(head.price - shoulder_avg) / max(shoulder_avg, 1e-9)
    prominence_score = min(1.0, prominence / 0.06)
    return max(0.0, min(1.0, (shoulder_symmetry + neckline_levelness + prominence_score) / 3))


def _detect_head_and_shoulders(swings: list[SwingPoint], candles: list[Candle]) -> list[PatternMatch]:
    matches: list[PatternMatch] = []
    highs = [s for s in swings if s.kind == "high"]
    lows = [s for s in swings if s.kind == "low"]

    def troughs_between(a: SwingPoint, b: SwingPoint, source: list[SwingPoint]) -> list[SwingPoint]:
        return [s for s in source if a.index < s.index < b.index]

    for left, head, right in zip(highs, highs[1:], highs[2:]):
        if not (head.price > left.price and head.price > right.price):
            continue
        if not _close_enough(left.price, right.price, tolerance=0.04):
            continue
        shoulder_avg = (left.price + right.price) / 2
        if (head.price - shoulder_avg) / shoulder_avg < MIN_HEAD_PROMINENCE:
            continue
        # Neckline: the lows between left/head and head/right.
        first = troughs_between(left, head, lows)
        second = troughs_between(head, right, lows)
        if not first or not second:
            continue
        neck_a, neck_b = min(s.price for s in first), min(s.price for s in second)
        if not _close_enough(neck_a, neck_b, tolerance=NECKLINE_TOLERANCE):
            continue

        matches.append(
            PatternMatch(
                name="Head and Shoulders",
                category="classic",
                direction=BEARISH,
                confidence=_head_and_shoulders_confidence(left, head, right, neck_a, neck_b),
                start_index=left.index,
                end_index=right.index,
                start_timestamp=left.timestamp,
                end_timestamp=right.timestamp,
                description=(
                    f"Head at ${head.price:.4f} above two roughly-equal shoulders "
                    f"(${left.price:.4f}, ${right.price:.4f}), neckline near ${(neck_a + neck_b) / 2:.4f}."
                ),
            )
        )

    for left, head, right in zip(lows, lows[1:], lows[2:]):
        if not (head.price < left.price and head.price < right.price):
            continue
        if not _close_enough(left.price, right.price, tolerance=0.04):
            continue
        shoulder_avg = (left.price + right.price) / 2
        if (shoulder_avg - head.price) / shoulder_avg < MIN_HEAD_PROMINENCE:
            continue
        first = troughs_between(left, head, highs)
        second = troughs_between(head, right, highs)
        if not first or not second:
            continue
        neck_a, neck_b = max(s.price for s in first), max(s.price for s in second)
        if not _close_enough(neck_a, neck_b, tolerance=NECKLINE_TOLERANCE):
            continue

        matches.append(
            PatternMatch(
                name="Inverse Head and Shoulders",
                category="classic",
                direction=BULLISH,
                confidence=_head_and_shoulders_confidence(left, head, right, neck_a, neck_b),
                start_index=left.index,
                end_index=right.index,
                start_timestamp=left.timestamp,
                end_timestamp=right.timestamp,
                description=(
                    f"Head at ${head.price:.4f} below two roughly-equal shoulders "
                    f"(${left.price:.4f}, ${right.price:.4f}), neckline near ${(neck_a + neck_b) / 2:.4f}."
                ),
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
