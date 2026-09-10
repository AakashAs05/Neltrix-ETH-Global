"""Turns a Verdict into a plain-English explanation.

Grounded, verdict-only context: this module never sees the raw candle
series, only the already-computed Verdict, the PatternMatch objects that
fed into it, and the support/resistance levels — the same inputs a human
analyst would summarize from. That keeps the explanation tied to what the
engine actually detected. If this is ever swapped for an LLM call (e.g.
Gemini) to make the prose more natural, that call must keep receiving only
this same grounded summary — never the raw candles — so it can't invent
price action the engine didn't compute.
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
