"""Turns a Verdict into plain English.

Sees only the verdict, the matched patterns and the levels, never the raw
candles, so the wording stays tied to what the engine actually computed.
"""

from __future__ import annotations

from app.engine.patterns import PatternMatch
from app.engine.signals import PriceLevel, Verdict


def _describe_patterns(patterns: list[PatternMatch]) -> str:
    if not patterns:
        return "No significant patterns were detected in the available window."
    names = [p.name for p in patterns[:3]]
    return "Key patterns: " + ", ".join(names) + "."


def _describe_levels(levels: list[PriceLevel]) -> str:
    supports = [l for l in levels if l.kind == "support"][:2]
    resistances = [l for l in levels if l.kind == "resistance"][:2]
    parts = []
    if supports:
        parts.append("support near " + ", ".join(f"${l.price:,.4f}" for l in supports))
    if resistances:
        parts.append("resistance near " + ", ".join(f"${l.price:,.4f}" for l in resistances))
    return "; ".join(parts) if parts else "no strong support/resistance clusters yet"


def explain(verdict: Verdict, patterns: list[PatternMatch], support_resistance: list[PriceLevel], base_symbol: str) -> str:
    direction_phrase = {
        "bullish": f"leans bullish on {base_symbol}",
        "bearish": f"leans bearish on {base_symbol}",
        "neutral": f"is neutral on {base_symbol}",
    }[verdict.direction]

    return (
        f"Verdict {direction_phrase} (confidence {verdict.confidence:.0%}, "
        f"from {verdict.pattern_count} pattern(s) detected). "
        f"{_describe_patterns(patterns)} "
        f"Nearby levels: {_describe_levels(support_resistance)}."
    )
