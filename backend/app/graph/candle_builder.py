"""Turns raw swap events into OHLCV candles.

Messari's standardized DEX schema (see standardized_query.py) does not
ship pre-built price candles - `LiquidityPool` exposes cumulative
volume/TVL/fee metrics, not open/high/low/close. What it does give us is
every individual `Swap`, each carrying enough information to derive an
instantaneous price:

    amountIn, amountInUSD, tokenIn { symbol, decimals }
    amountOut, amountOutUSD, tokenOut { symbol, decimals }

For a chosen "base" token (e.g. WETH in a USDC/WETH pool), each swap gives
one price sample, base-token value in USD, regardless of which side of
the pair was bought or sold. This module buckets those samples into fixed
time windows and reduces each bucket to an OHLCV candle, the same shape
Neltrix's pattern-detection engine expects.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median

INTERVAL_SECONDS = {
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "4h": 14400,
    "1d": 86400,
}

# How far back a request can ask for. Which of these is actually cheap
# depends on the source — see graph/candle_source.py.
RANGE_SECONDS = {
    "1d": 86_400,
    "1w": 604_800,
    "1m": 2_592_000,  # 30d
    "3m": 7_776_000,  # 90d
    "1y": 31_536_000,  # 365d
}


@dataclass(frozen=True)
class Candle:
    timestamp: int  # bucket start, unix seconds
    open: float
    high: float
    low: float
    close: float
    volume_usd: float
    trade_count: int


def _raw_amount_to_human(raw_amount: str | int, decimals: int) -> float:
    return int(raw_amount) / (10**decimals)


def _swap_price_and_volume(swap: dict, base_symbol: str) -> tuple[float, float] | None:
    """Return (price of base_symbol in USD, USD volume of the swap), or
    None if this swap doesn't involve base_symbol at all (shouldn't happen
    for a well-formed pool query, but we guard against dirty data).
    """
    token_in = swap["tokenIn"]
    token_out = swap["tokenOut"]

    if token_in["symbol"] == base_symbol:
        amount = _raw_amount_to_human(swap["amountIn"], token_in["decimals"])
        usd = float(swap["amountInUSD"])
    elif token_out["symbol"] == base_symbol:
        amount = _raw_amount_to_human(swap["amountOut"], token_out["decimals"])
        usd = float(swap["amountOutUSD"])
    else:
        return None

    if amount <= 0:
        return None

    price = usd / amount
    # Volume is the USD value that changed hands in this swap; amountInUSD
    # and amountOutUSD are usually near-identical (fee/slippage aside), so
    # either side is a reasonable proxy for trade size.
    volume = float(swap["amountInUSD"])
    return price, volume


def build_ohlcv(swaps: list[dict], base_symbol: str, interval: str = "1h") -> list[Candle]:
    """Bucket `swaps` (as returned by standardized_query.get_recent_swaps)
    into OHLCV candles of `interval` width, oldest candle first.
    """
    if interval not in INTERVAL_SECONDS:
        raise ValueError(f"Unknown interval '{interval}'. Choose from {list(INTERVAL_SECONDS)}")
    bucket_width = INTERVAL_SECONDS[interval]

    # swaps arrive newest-first from the query; process oldest-first so
    # open/close land on the right ends of each bucket.
    ordered = sorted(swaps, key=lambda s: int(s["timestamp"]))

    buckets: dict[int, list[tuple[float, float]]] = {}
    for swap in ordered:
        sample = _swap_price_and_volume(swap, base_symbol)
        if sample is None:
            continue
        bucket_start = (int(swap["timestamp"]) // bucket_width) * bucket_width
        buckets.setdefault(bucket_start, []).append(sample)

    candles: list[Candle] = []
    for bucket_start in sorted(buckets):
        prices_and_volumes = buckets[bucket_start]
        prices = [p for p, _ in prices_and_volumes]
        candles.append(
            Candle(
                timestamp=bucket_start,
                open=prices[0],
                high=max(prices),
                low=min(prices),
                close=prices[-1],
                volume_usd=sum(v for _, v in prices_and_volumes),
                trade_count=len(prices_and_volumes),
            )
        )
    return candles


def resample(candles: list[Candle], interval: str) -> list[Candle]:
    """Roll finer candles up into wider ones (e.g. hourly -> 4h).

    Only ever used to go coarser: a subgraph publishes hourly and daily
    aggregates, so a 4h request is served by rolling up 4 hourly candles
    rather than replaying every swap in the window.
    """
    if interval not in INTERVAL_SECONDS:
        raise ValueError(f"Unknown interval '{interval}'. Choose from {list(INTERVAL_SECONDS)}")
    bucket_width = INTERVAL_SECONDS[interval]

    buckets: dict[int, list[Candle]] = {}
    for candle in sorted(candles, key=lambda c: c.timestamp):
        bucket_start = (candle.timestamp // bucket_width) * bucket_width
        buckets.setdefault(bucket_start, []).append(candle)

    return [
        Candle(
            timestamp=bucket_start,
            open=group[0].open,
            high=max(c.high for c in group),
            low=min(c.low for c in group),
            close=group[-1].close,
            volume_usd=sum(c.volume_usd for c in group),
            trade_count=sum(c.trade_count for c in group),
        )
        for bucket_start, group in sorted(buckets.items())
    ]


# A single candle spanning more than this ratio between its high and low
# is an indexing artifact, not price action. Pool-creation rows are the
# usual culprit: they record a dust initialization price alongside a real
# one, which after inversion reads as a 100,000x wick.
MAX_CANDLE_HIGH_LOW_RATIO = 20.0


@dataclass(frozen=True)
class SanitizeReport:
    kept: int
    dropped_non_positive: int
    dropped_zero_volume: int
    dropped_extreme_range: int
    clamped_wicks: int = 0

    @property
    def dropped_total(self) -> int:
        return self.dropped_non_positive + self.dropped_zero_volume + self.dropped_extreme_range


# A single bad print inside an otherwise ordinary hour is the dominant
# data-quality problem on busy pools: an MEV sandwich or a dust swap
# executed far out of range sets the period's high or low, while the open
# and close stay sane. On the Uniswap V4 ETH/USDC 0.01% pool roughly 9% of
# hourly candles carry a wick like this, including one claiming ETH traded
# between $4 and $2,446 in the same hour. Left in, a handful of them
# stretch a chart's axis so far that all real price action flattens into a
# line.
#
# These are clamped rather than dropped: the body is usually good data, so
# discarding the whole period would throw away a real candle to remove a
# bad wick.
LOCAL_MEDIAN_WINDOW = 25
MAX_DEVIATION_FROM_LOCAL_MEDIAN = 0.25


def _local_median_closes(candles: list[Candle], window: int) -> list[float]:
    """Centred rolling median of close, so a genuine trend isn't treated
    as an outlier the way a single global median would treat it."""
    closes = [c.close for c in candles]
    half = max(1, window // 2)
    medians: list[float] = []
    for i in range(len(closes)):
        lo = max(0, i - half)
        hi = min(len(closes), i + half + 1)
        medians.append(median(closes[lo:hi]))
    return medians


def clamp_outlier_wicks(
    candles: list[Candle], max_deviation: float = MAX_DEVIATION_FROM_LOCAL_MEDIAN
) -> tuple[list[Candle], int]:
    """Pull absurd highs/lows back to a plausible band around local price.

    Returns the repaired candles and how many were altered. A candle whose
    *body* (open and close) also falls outside the band is left untouched —
    that's a real move, not a bad print, and clamping it would fabricate
    price action.
    """
    if len(candles) < 3:
        return candles, 0

    medians = _local_median_closes(candles, LOCAL_MEDIAN_WINDOW)
    repaired: list[Candle] = []
    clamped = 0

    for candle, local in zip(candles, medians):
        if local <= 0:
            repaired.append(candle)
            continue
        upper = local * (1 + max_deviation)
        lower = local * (1 - max_deviation)

        # If the body itself is outside the band, price genuinely moved.
        body_high, body_low = max(candle.open, candle.close), min(candle.open, candle.close)
        if body_high > upper or body_low < lower:
            repaired.append(candle)
            continue

        if candle.high <= upper and candle.low >= lower:
            repaired.append(candle)
            continue

        repaired.append(
            Candle(
                timestamp=candle.timestamp,
                open=candle.open,
                high=min(candle.high, upper),
                low=max(candle.low, lower),
                close=candle.close,
                volume_usd=candle.volume_usd,
                trade_count=candle.trade_count,
            )
        )
        clamped += 1

    return repaired, clamped


def sanitize_candles(candles: list[Candle]) -> tuple[list[Candle], SanitizeReport]:
    """Drop candles that carry no usable price information.

    Subgraph-published aggregates are not clean. On the Uniswap V4
    ETH/USDC pool, the two rows at pool creation (2025-01-23/24) record a
    ~3.3e-21 price with zero volume, which inverts to roughly $3e20 — one
    of those in a series is enough to collapse every real candle onto a
    flat line once the chart autoscales.

    The rules are deliberately asset-agnostic — no hardcoded price bands,
    since the same code charts ETH, WBTC and whatever else a pool holds:

      1. any non-positive OHLC value is structurally invalid
      2. zero traded volume means no price was discovered in the period
      3. a high/low ratio beyond MAX_CANDLE_HIGH_LOW_RATIO is an artifact

    Counts come back in the report rather than being swallowed, so the API
    can tell the caller what was removed instead of quietly reshaping data.
    """
    kept: list[Candle] = []
    non_positive = zero_volume = extreme = 0

    for candle in candles:
        values = (candle.open, candle.high, candle.low, candle.close)
        if min(values) <= 0:
            non_positive += 1
            continue
        if candle.volume_usd <= 0:
            zero_volume += 1
            continue
        if max(values) / min(values) > MAX_CANDLE_HIGH_LOW_RATIO:
            extreme += 1
            continue
        kept.append(candle)

    kept, clamped = clamp_outlier_wicks(kept)

    return kept, SanitizeReport(
        kept=len(kept),
        clamped_wicks=clamped,
        dropped_non_positive=non_positive,
        dropped_zero_volume=zero_volume,
        dropped_extreme_range=extreme,
    )
