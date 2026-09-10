"""XABCD harmonic patterns (Gartley, Bat, Butterfly, Crab) via Fibonacci ratios.

Five consecutive, alternating swing points (X-A-B-C-D) are checked against
each pattern's canonical ratio ranges:

  B = retracement of leg AB against leg XA
  D = retracement/extension of leg AD against leg XA  (Gartley/Bat retrace,
      Butterfly/Crab extend past X)

C is not used to distinguish between patterns here (its valid range
overlaps heavily across all four), but is still required to fall in a
broadly sane retracement band so degenerate/flat legs don't slip through.
"""

from __future__ import annotations

from app.graph.candle_builder import Candle

from . import BEARISH, BULLISH, PatternMatch, find_swing_points

# (b_ratio range, d_ratio range) — tolerance already baked into the ranges.
PATTERN_SPECS: dict[str, tuple[tuple[float, float], tuple[float, float]]] = {
    "Gartley": ((0.56, 0.68), (0.73, 0.85)),
    "Bat": ((0.35, 0.55), (0.83, 0.95)),
    "Butterfly": ((0.72, 0.85), (1.23, 1.65)),
    "Crab": ((0.35, 0.65), (1.55, 1.68)),
}
C_RATIO_RANGE = (0.30, 0.95)


def _ratio(p0: float, p1: float, p2: float) -> float | None:
    leg1 = p1 - p0
    if leg1 == 0:
        return None
    return abs((p2 - p1) / leg1)


def detect(candles: list[Candle], swing_window: int = 2) -> list[PatternMatch]:
    swings = find_swing_points(candles, window=swing_window)
    matches: list[PatternMatch] = []

    for i in range(len(swings) - 4):
        x, a, b, c, d = swings[i : i + 5]
        kinds = (x.kind, a.kind, b.kind, c.kind, d.kind)
        if kinds not in (("low", "high", "low", "high", "low"), ("high", "low", "high", "low", "high")):
            continue

        b_ratio = _ratio(x.price, a.price, b.price)
        d_ratio = _ratio(x.price, a.price, d.price)
        c_ratio = _ratio(a.price, b.price, c.price)
        if b_ratio is None or d_ratio is None or c_ratio is None:
            continue
        if not (C_RATIO_RANGE[0] <= c_ratio <= C_RATIO_RANGE[1]):
            continue

        bullish = x.kind == "low"  # D is a low -> pattern calls for a bounce
        for name, (b_range, d_range) in PATTERN_SPECS.items():
            if b_range[0] <= b_ratio <= b_range[1] and d_range[0] <= d_ratio <= d_range[1]:
                b_mid = sum(b_range) / 2
                d_mid = sum(d_range) / 2
                closeness = 1 - (abs(b_ratio - b_mid) / b_mid + abs(d_ratio - d_mid) / d_mid) / 2
                direction = BULLISH if bullish else BEARISH
                matches.append(
                    PatternMatch(
                        name=f"{'Bullish' if bullish else 'Bearish'} {name}",
                        category="harmonic",
                        direction=direction,
                        confidence=max(0.3, min(1.0, closeness)),
                        start_index=x.index,
                        end_index=d.index,
                        start_timestamp=x.timestamp,
                        end_timestamp=d.timestamp,
                        description=(
                            f"XABCD {name} pattern completing near ${d.price:.4f}: "
                            f"B retraced {b_ratio:.0%} of XA, D at {d_ratio:.0%} of XA — "
                            f"{'reversal up' if bullish else 'reversal down'} expected at D."
                        ),
                    )
                )
                break  # a given XABCD shouldn't be double-counted across patterns
    return matches
