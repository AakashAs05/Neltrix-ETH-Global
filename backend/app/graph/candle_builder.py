"""Turns raw swap events into OHLCV candles.

Messari's standardized DEX schema (see standardized_query.py) does not
ship pre-built price candles — `LiquidityPool` exposes cumulative
volume/TVL/fee metrics, not open/high/low/close. What it does give us is
every individual `Swap`, each carrying enough information to derive an
instantaneous price:

    amountIn, amountInUSD, tokenIn { symbol, decimals }
    amountOut, amountOutUSD, tokenOut { symbol, decimals }

For a chosen "base" token (e.g. WETH in a USDC/WETH pool), each swap gives
one price sample — base-token value in USD — regardless of which side of
the pair was bought or sold. This module buckets those samples into fixed
time windows and reduces each bucket to an OHLCV candle, the same shape
Neltrix's pattern-detection engine expects.
"""

from __future__ import annotations

from dataclasses import dataclass

INTERVAL_SECONDS = {
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "4h": 14400,
    "1d": 86400,
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
