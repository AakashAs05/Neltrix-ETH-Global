"""Turns raw swap events into OHLCV candles.

The Messari schema ships no price candles, only cumulative volume and TVL.
Each swap does carry enough to derive one price sample, so this buckets
those samples by time and reduces each bucket to a candle.
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

# How far back a request can ask for. Which are cheap depends on the source.
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
    """Price of base_symbol in USD plus the swap's USD volume.

    None when the swap doesn't involve base_symbol, which only happens on
    dirty data but is cheap to guard against.
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
    # Either USD side works as trade size; they agree within fees.
    volume = float(swap["amountInUSD"])
    return price, volume


def build_ohlcv(swaps: list[dict], base_symbol: str, interval: str = "1h") -> list[Candle]:
    """Bucket `swaps` (as returned by standardized_query.get_recent_swaps)
    into OHLCV candles of `interval` width, oldest candle first.
    """
    if interval not in INTERVAL_SECONDS:
        raise ValueError(f"Unknown interval '{interval}'. Choose from {list(INTERVAL_SECONDS)}")
    bucket_width = INTERVAL_SECONDS[interval]

    # Queries return newest first, so reverse to get open/close right.
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
    """Roll finer candles up into wider ones, e.g. hourly into 4h.

    Only ever goes coarser. A 4h request rolls up four published hourly
    candles instead of replaying every swap in the window.
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


# A high/low ratio beyond this is an indexing artifact, not price action.
# Pool-creation rows are the usual culprit.
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


# One bad print sets a period's high or low while open and close stay sane.
# About 9% of hourly candles on the V4 ETH/USDC 0.01% pool look like this.
# Clamped rather than dropped, since the body is usually fine.
LOCAL_MEDIAN_WINDOW = 25
MAX_DEVIATION_FROM_LOCAL_MEDIAN = 0.25


def _local_median_closes(candles: list[Candle], window: int) -> list[float]:
    """Centred rolling median of close, so a real trend isn't read as an outlier."""
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
    """Pull absurd highs and lows back to a band around local price.

    A candle whose body is also outside the band is left alone. That is a
    real move, and clamping it would fabricate price action.
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

    Rules are asset-agnostic, so no hardcoded price bands: non-positive OHLC
    is invalid, zero volume means no price was discovered, and an extreme
    high/low ratio is an artifact. Counts are reported, never swallowed.
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
