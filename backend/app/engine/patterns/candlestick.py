"""Single and multi-candle reversal shapes.

The noisiest signals in the engine, weighted lowest in signals.py. Useful
as corroboration, not as a verdict on their own.
"""

from __future__ import annotations

from app.graph.candle_builder import Candle

from . import BEARISH, BULLISH, NEUTRAL, PatternMatch

TREND_LOOKBACK = 3

# A two-candle pattern reacts to a decisive prior move, so the prior candle
# has to have made one. Otherwise it was indecision, with nothing to reverse.
DECISIVE_BODY_RATIO = 0.5

# The inside candle must be much smaller than the one it sits in. That
# contraction is the signal; merely smaller matches ordinary chop.
HARAMI_BODY_RATIO = 0.5

# An engulfing candle should clearly overpower the previous body.
ENGULF_BODY_MULTIPLE = 1.3


def _body(c: Candle) -> float:
    return abs(c.close - c.open)


def _range(c: Candle) -> float:
    return c.high - c.low


def _upper_wick(c: Candle) -> float:
    return c.high - max(c.open, c.close)


def _lower_wick(c: Candle) -> float:
    return min(c.open, c.close) - c.low


def _is_bullish(c: Candle) -> bool:
    return c.close > c.open


def _is_bearish(c: Candle) -> bool:
    return c.close < c.open


def _prior_trend(candles: list[Candle], i: int, lookback: int = TREND_LOOKBACK) -> str:
    """Trend context, since a hammer after a decline is a hanging man after a rally."""
    if i < lookback:
        return NEUTRAL
    start_close = candles[i - lookback].close
    end_close = candles[i - 1].close
    if end_close < start_close:
        return BEARISH
    if end_close > start_close:
        return BULLISH
    return NEUTRAL


def _match(name: str, direction: str, confidence: float, candles: list[Candle], start: int, end: int, description: str) -> PatternMatch:
    return PatternMatch(
        name=name,
        category="candlestick",
        direction=direction,
        confidence=max(0.0, min(1.0, confidence)),
        start_index=start,
        end_index=end,
        start_timestamp=candles[start].timestamp,
        end_timestamp=candles[end].timestamp,
        description=description,
    )


def detect(candles: list[Candle]) -> list[PatternMatch]:
    matches: list[PatternMatch] = []
    n = len(candles)

    for i in range(n):
        c = candles[i]
        rng = _range(c)
        if rng <= 0:
            continue
        body = _body(c)
        upper = _upper_wick(c)
        lower = _lower_wick(c)
        trend = _prior_trend(candles, i)

        # Checked first and made exclusive of the Hammer family. With a body
        # this small, `lower >= 2 * body` is nearly always true, so without
        # the guard almost every Doji was also labelled a Hammer.
        is_doji = body <= 0.1 * rng
        if is_doji:
            matches.append(
                _match(
                    "Doji", NEUTRAL, 0.5 + 0.3 * (1 - body / rng), candles, i, i,
                    f"Open and close nearly equal (${c.open:.4f} vs ${c.close:.4f}), indecision.",
                )
            )

        # Hammer / Hanging Man: long lower wick, small body near the top.
        if not is_doji and lower >= 2 * body and upper <= 0.3 * max(body, rng * 0.05) and body > 0:
            confidence = min(1.0, lower / rng)
            if trend == BEARISH:
                matches.append(
                    _match(
                        "Hammer", BULLISH, confidence, candles, i, i,
                        f"Long lower wick (${lower:.4f}) after a decline, buyers rejected lower prices.",
                    )
                )
            elif trend == BULLISH:
                matches.append(
                    _match(
                        "Hanging Man", BEARISH, confidence * 0.8, candles, i, i,
                        f"Long lower wick (${lower:.4f}) after a rally, possible exhaustion.",
                    )
                )

        # Inverted Hammer / Shooting Star: long upper wick, small body near the bottom.
        if not is_doji and upper >= 2 * body and lower <= 0.3 * max(body, rng * 0.05) and body > 0:
            confidence = min(1.0, upper / rng)
            if trend == BEARISH:
                matches.append(
                    _match(
                        "Inverted Hammer", BULLISH, confidence * 0.8, candles, i, i,
                        f"Long upper wick (${upper:.4f}) after a decline, buyers tested higher prices.",
                    )
                )
            elif trend == BULLISH:
                matches.append(
                    _match(
                        "Shooting Star", BEARISH, confidence, candles, i, i,
                        f"Long upper wick (${upper:.4f}) after a rally, sellers rejected higher prices.",
                    )
                )

        if i == 0:
            continue
        prev = candles[i - 1]
        prev_body = _body(prev)

        prev_range = _range(prev)
        # Without this guard the two-candle checks fire on ordinary chop:
        # Bearish Harami alone matched 17% of all candles.
        prev_decisive = prev_range > 0 and prev_body >= DECISIVE_BODY_RATIO * prev_range

        # Engulfs the previous body, opposite colours, and convincingly so.
        engulfs_convincingly = body >= ENGULF_BODY_MULTIPLE * prev_body
        if prev_decisive and engulfs_convincingly:
            if _is_bearish(prev) and _is_bullish(c) and c.open <= prev.close and c.close >= prev.open:
                matches.append(
                    _match(
                        "Bullish Engulfing", BULLISH, min(1.0, body / max(prev_body, 1e-9) / 3), candles, i - 1, i,
                        f"${c.close:.4f} close engulfs the prior red candle's body, buyers took control.",
                    )
                )
            if _is_bullish(prev) and _is_bearish(c) and c.open >= prev.close and c.close <= prev.open:
                matches.append(
                    _match(
                        "Bearish Engulfing", BEARISH, min(1.0, body / max(prev_body, 1e-9) / 3), candles, i - 1, i,
                        f"${c.close:.4f} close engulfs the prior green candle's body, sellers took control.",
                    )
                )

        # Body contained within the previous, much larger one. That
        # contraction is the signal, so a hair smaller does not qualify.
        is_inside_and_small = body <= HARAMI_BODY_RATIO * prev_body
        if prev_decisive and is_inside_and_small:
            if _is_bearish(prev) and _is_bullish(c) and prev.close <= c.open and c.close <= prev.open:
                matches.append(
                    _match(
                        "Bullish Harami", BULLISH, min(1.0, 1 - body / max(prev_body, 1e-9)), candles, i - 1, i,
                        "Small green body tucked inside the prior red candle, downside momentum stalling.",
                    )
                )
            if _is_bullish(prev) and _is_bearish(c) and prev.open <= c.open and c.close <= prev.close:
                matches.append(
                    _match(
                        "Bearish Harami", BEARISH, min(1.0, 1 - body / max(prev_body, 1e-9)), candles, i - 1, i,
                        "Small red body tucked inside the prior green candle, upside momentum stalling.",
                    )
            )

        if i < 2:
            continue
        prev2 = candles[i - 2]

        # Morning Star: big red, small-bodied middle candle, big green closing well into candle 1's body.
        if (
            _is_bearish(prev2)
            and _body(prev2) > _range(prev2) * 0.4
            and _body(prev) <= _range(prev) * 0.3
            and _is_bullish(c)
            and c.close >= (prev2.open + prev2.close) / 2
        ):
            matches.append(
                _match(
                    "Morning Star", BULLISH, 0.7, candles, i - 2, i,
                    f"Three-candle reversal: sharp decline, indecision, then a close (${c.close:.4f}) back above the first candle's midpoint.",
                )
            )

        # Evening Star: mirror of the above.
        if (
            _is_bullish(prev2)
            and _body(prev2) > _range(prev2) * 0.4
            and _body(prev) <= _range(prev) * 0.3
            and _is_bearish(c)
            and c.close <= (prev2.open + prev2.close) / 2
        ):
            matches.append(
                _match(
                    "Evening Star", BEARISH, 0.7, candles, i - 2, i,
                    f"Three-candle reversal: sharp rally, indecision, then a close (${c.close:.4f}) back below the first candle's midpoint.",
                )
            )

    return matches
