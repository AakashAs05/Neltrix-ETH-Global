"""Picks how to build candles for a given protocol, interval and range.

Uniswap's own schema publishes real OHLC per hour and day, so a year costs
one query. Messari's publishes none, so those protocols replay raw swaps at
a cost that scales with pool activity. Callers are told which path ran.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from app.graph import standardized_query
from app.graph.candle_builder import (
    INTERVAL_SECONDS,
    RANGE_SECONDS,
    Candle,
    build_ohlcv,
    resample,
    sanitize_candles,
)
from app.uniswap import v4_pool_client

# Ceiling on raw swaps per request. Ten pages is a few seconds; beyond that
# the wait stops being interactive.
MAX_SWAPS_PER_REQUEST = 10_000

# What each interval can be built from. 4h is not published anywhere but
# rolls up cleanly from four hourly candles.
AGGREGATE_PLAN: dict[str, tuple[str, bool]] = {
    # interval: (granularity to fetch, needs resampling)
    "1h": ("1h", False),
    "4h": ("1h", True),
    "1d": ("1d", False),
}

SOURCE_AGGREGATE = "subgraph-aggregate"
SOURCE_SWAPS = "derived-from-swaps"


@dataclass
class CandleSeries:
    candles: list[Candle]
    source: str
    quote_symbol: str
    range_key: str
    interval: str
    swaps_scanned: int = 0
    rows_dropped: int = 0
    truncated: bool = False
    notes: list[str] = field(default_factory=list)


def supports_aggregates(protocol_key: str) -> bool:
    """Only Uniswap's native schema publishes OHLC. Messari's does not."""
    return protocol_key == v4_pool_client.PROTOCOL_KEY


def available_intervals_for_aggregates() -> list[str]:
    return list(AGGREGATE_PLAN)


def _validate(interval: str, range_key: str) -> tuple[int, int]:
    if interval not in INTERVAL_SECONDS:
        raise ValueError(f"Unknown interval '{interval}'. Choose from {list(INTERVAL_SECONDS)}")
    if range_key not in RANGE_SECONDS:
        raise ValueError(f"Unknown range '{range_key}'. Choose from {list(RANGE_SECONDS)}")

    until = int(time.time())
    since = until - RANGE_SECONDS[range_key]
    return since, until


def resolve_candles(
    protocol_key: str,
    pool_id: str,
    base_symbol: str,
    interval: str = "1h",
    range_key: str = "1w",
) -> CandleSeries:
    since, until = _validate(interval, range_key)

    if supports_aggregates(protocol_key) and interval in AGGREGATE_PLAN:
        return _from_aggregates(pool_id, base_symbol, interval, range_key, since, until)

    return _from_swaps(protocol_key, pool_id, base_symbol, interval, range_key, since)


def _from_aggregates(
    pool_id: str,
    base_symbol: str,
    interval: str,
    range_key: str,
    since: int,
    until: int,
) -> CandleSeries:
    granularity, needs_resample = AGGREGATE_PLAN[interval]

    raw, quote_symbol = v4_pool_client.get_aggregate_candles(
        pool_id, base_symbol=base_symbol, granularity=granularity, since=since, until=until
    )
    clean, report = sanitize_candles(raw)

    notes: list[str] = []
    if report.dropped_total:
        notes.append(
            f"Dropped {report.dropped_total} unusable candle(s) published by the subgraph "
            f"({report.dropped_non_positive} non-positive, {report.dropped_zero_volume} "
            f"zero-volume, {report.dropped_extreme_range} implausible range)."
        )
    if report.clamped_wicks:
        notes.append(
            f"Clamped implausible wicks on {report.clamped_wicks} candle(s), single "
            "out-of-range prints (MEV sandwiches, dust swaps) had set highs/lows far "
            "outside local price. Bodies are unchanged."
        )

    candles = resample(clean, interval) if needs_resample else clean

    return CandleSeries(
        candles=candles,
        source=SOURCE_AGGREGATE,
        quote_symbol=quote_symbol,
        range_key=range_key,
        interval=interval,
        rows_dropped=report.dropped_total,
        notes=notes,
    )


def _from_swaps(
    protocol_key: str,
    pool_id: str,
    base_symbol: str,
    interval: str,
    range_key: str,
    since: int,
) -> CandleSeries:
    if supports_aggregates(protocol_key):
        swaps = v4_pool_client.get_recent_swaps(
            pool_id, limit=MAX_SWAPS_PER_REQUEST, since=since
        )
    else:
        swaps = standardized_query.get_recent_swaps(
            protocol_key, pool_id, limit=MAX_SWAPS_PER_REQUEST, since=since
        )

    candles = build_ohlcv(swaps, base_symbol=base_symbol, interval=interval)
    clean, report = sanitize_candles(candles)

    # Truncation is about coverage, not row count. Hitting the ceiling means
    # more data exists; running out of swaps means we got everything. A plain
    # row-count check under-reported, since dedup left the loop a row short.
    hit_ceiling = len(swaps) >= MAX_SWAPS_PER_REQUEST
    oldest_covered = min(int(s["timestamp"]) for s in swaps) if swaps else since
    # One interval of slack, so landing in the first bucket counts as covered.
    truncated = hit_ceiling and oldest_covered > since + INTERVAL_SECONDS[interval]

    notes: list[str] = []
    if truncated:
        notes.append(
            f"Range truncated: this pool trades often enough that the "
            f"{MAX_SWAPS_PER_REQUEST:,}-swap ceiling was reached before covering the full "
            f"'{range_key}' window. Showing data back to "
            f"{time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime(oldest_covered))} instead. "
            "This source publishes no OHLC aggregates, so every candle has to be "
            "rebuilt from individual swaps, a coarser interval on Uniswap V4 covers "
            "far more ground for the same cost."
        )
    if report.dropped_total:
        notes.append(f"Dropped {report.dropped_total} unusable candle(s).")
    if report.clamped_wicks:
        notes.append(f"Clamped implausible wicks on {report.clamped_wicks} candle(s).")

    return CandleSeries(
        candles=clean,
        source=SOURCE_SWAPS,
        quote_symbol="USD",
        range_key=range_key,
        interval=interval,
        swaps_scanned=len(swaps),
        rows_dropped=report.dropped_total,
        truncated=truncated,
        notes=notes,
    )
