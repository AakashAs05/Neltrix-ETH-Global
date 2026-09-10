"""Uniswap V4 — the flagship pool source, on Uniswap's own native schema.

Unlike Uniswap V3 and SushiSwap (both published by Messari as "dex-amm"
Standardized Subgraphs — see app/graph/standardized_query.py), Uniswap V4
has no Messari standardized deployment: V4's singleton `PoolManager` +
hooks architecture doesn't map onto the existing dex-amm schema, and
Messari hasn't published one for it. Verified on 2026-09-10 against both
Messari's deployment registry and The Graph's explorer.

So V4 is queried through its own native schema instead:

    Pool  { id, token0, token1, feeTier, volumeUSD, txCount, ... }
    Swap  { timestamp, amount0, amount1, amountUSD, sqrtPriceX96, tick }

The important design point: `_normalize_swap()` converts that native shape
into the *same* intermediate dict `standardized_query.get_recent_swaps()`
returns for Messari subgraphs. Everything downstream — candle_builder, all
three pattern detectors, signals, the explainer, /api/analyse — then runs
on Uniswap V4 data completely unmodified. The engine never learns that a
second schema exists; only this adapter knows.

Subgraph: DiYPVdygkfjDWhbxGSqAQxwBKmfKnkWQojqeM2rkLb3G (Ethereum mainnet),
the V4 mainnet deployment published in Uniswap's own developer docs. Note
that Uniswap's docs explicitly caveat these example deployments as "not
official deployments and may not be actively maintained by Uniswap Labs" —
see docs/FEEDBACK.md, where that's part of the feedback submitted.

Data-quality caveat found while integrating: a number of V4 pools report
nonsensical `totalValueLockedUSD` (wildly inflated, and in several cases
negative — e.g. the top USDC/USDT pool by volume reports roughly
-$24.7M TVL). V4 lets anyone open a pool with arbitrary hooks, so the junk
ratio is higher than V3's. get_top_pools() therefore ranks by volumeUSD and
filters to major tokens rather than trusting TVL.
"""

from __future__ import annotations

import os
from decimal import Decimal
from typing import Any

from app.graph.candle_builder import Candle
from app.graph.graph_client import get_client

PROTOCOL_KEY = "uniswap-v4-ethereum"
PROTOCOL_DISPLAY_NAME = "Uniswap V4 (Ethereum)"
NETWORK = "mainnet"

SUBGRAPH_ID = os.getenv(
    "UNISWAP_V4_ETHEREUM_SUBGRAPH_ID", "DiYPVdygkfjDWhbxGSqAQxwBKmfKnkWQojqeM2rkLb3G"
)

# The Graph caps `first` at 1000 per query — same constraint, same
# pagination strategy as app/graph/standardized_query.py.
MAX_PAGE_SIZE = 1000

# Ranking "top pools" on V4 needs a token allowlist: the deployment is full
# of wash-traded pairs (ETH/"1xETH" claiming $2.3T TVL, etc.) that would
# otherwise dominate every ordering.
MAJOR_SYMBOLS = ["ETH", "WETH", "USDC", "USDT", "DAI", "WBTC"]

_STABLECOIN_SYMBOLS = {"USDC", "USDT", "USD", "DAI", "BUSD", "TUSD", "USDP", "FRAX", "LUSD", "GUSD"}


TOP_POOLS_QUERY = """
query TopV4Pools($first: Int!, $symbols: [String!]!) {
  pools(
    first: $first
    orderBy: volumeUSD
    orderDirection: desc
    where: { token0_: { symbol_in: $symbols }, token1_: { symbol_in: $symbols } }
  ) {
    id
    token0 { symbol decimals }
    token1 { symbol decimals }
    feeTier
    volumeUSD
    totalValueLockedUSD
    txCount
  }
}
"""

POOL_INFO_QUERY = """
query V4PoolInfo($pool: String!) {
  pool(id: $pool) {
    id
    token0 { symbol decimals }
    token1 { symbol decimals }
    feeTier
  }
}
"""

_SWAP_FIELDS = """
    id
    timestamp
    amount0
    amount1
    amountUSD
    pool {
      token0 { symbol decimals }
      token1 { symbol decimals }
    }
"""


def _build_swaps_query(*, with_cursor: bool, with_since: bool) -> str:
    """Assemble the swaps query for the filters actually in play.

    graph-node rejects a null `timestamp_lte`/`timestamp_gte`, so an
    unused bound can't just be passed as a null variable — the clause has
    to be absent from the query text entirely.
    """
    declarations = ["$pool: String!", "$first: Int!"]
    filters = ["pool: $pool"]
    if with_cursor:
        declarations.append("$before: BigInt!")
        filters.append("timestamp_lte: $before")
    if with_since:
        declarations.append("$since: BigInt!")
        filters.append("timestamp_gte: $since")

    return f"""
query RecentV4Swaps({", ".join(declarations)}) {{
  swaps(
    first: $first
    orderBy: timestamp
    orderDirection: desc
    where: {{ {", ".join(filters)} }}
  ) {{
{_SWAP_FIELDS}
  }}
}}
"""


# --- Pre-aggregated OHLC ---------------------------------------------------
# Unlike Messari's dex-amm schema, Uniswap's own schema publishes real
# open/high/low/close per hour and per day. That's what makes long ranges
# (a month, a year) affordable here: 365 daily rows instead of millions of
# swap events.
#
# Orientation matters and is easy to get wrong: these OHLC values track
# `token0Price`, which is token0-per-token1 — i.e. the price of *token1*
# denominated in token0. On the ETH/USDC pool (token0=ETH, token1=USDC)
# that reads as ~0.000406 ETH per USDC, so charting ETH means inverting.
# Inverting also swaps the roles of high and low, which is handled in
# _aggregate_rows_to_candles.

# Note the time fields here are `Int`, not the `BigInt` that Swap.timestamp
# uses — declaring these as BigInt makes graph-node reject the whole
# `where` object rather than complain about the specific argument.
HOUR_CANDLES_QUERY = """
query V4HourCandles($pool: String!, $first: Int!, $since: Int!, $before: Int!) {
  poolHourDatas(
    first: $first
    orderBy: periodStartUnix
    orderDirection: desc
    where: { pool: $pool, periodStartUnix_gte: $since, periodStartUnix_lte: $before }
  ) {
    periodStartUnix
    open
    high
    low
    close
    volumeUSD
    txCount
  }
}
"""

DAY_CANDLES_QUERY = """
query V4DayCandles($pool: String!, $first: Int!, $since: Int!, $before: Int!) {
  poolDayDatas(
    first: $first
    orderBy: date
    orderDirection: desc
    where: { pool: $pool, date_gte: $since, date_lte: $before }
  ) {
    date
    open
    high
    low
    close
    volumeUSD
    txCount
  }
}
"""


# V4 flags a dynamic-fee pool by setting the top bit of the fee field
# (0x800000) rather than storing a real rate there, so it has to be
# special-cased — formatted naively it reads as an absurd "838.86%".
DYNAMIC_FEE_FLAG = 0x800000


def get_pool_display_name(pool: dict[str, Any]) -> str:
    """V4 pools have no `name` field (V4 pool ids are bytes32 hashes, not
    contract addresses), so build a readable one the way the UI needs it."""
    fee_tier = int(pool["feeTier"])
    pair = f"{pool['token0']['symbol']}/{pool['token1']['symbol']}"
    if fee_tier == DYNAMIC_FEE_FLAG:
        return f"Uniswap V4 {pair} (dynamic fee)"
    # `:g` keeps V4's very small tiers legible — 10 -> 0.001%, not "0.00%".
    return f"Uniswap V4 {pair} {fee_tier / 10_000:g}%"


def get_top_pools(limit: int = 20) -> list[dict[str, Any]]:
    """Top V4 pools by traded volume, restricted to major-token pairs."""
    data = get_client().query(
        SUBGRAPH_ID, TOP_POOLS_QUERY, {"first": limit, "symbols": MAJOR_SYMBOLS}
    )
    return data["pools"]


def get_pool_info(pool_id: str) -> dict[str, Any]:
    data = get_client().query(SUBGRAPH_ID, POOL_INFO_QUERY, {"pool": pool_id.lower()})
    pool = data.get("pool")
    if pool is None:
        raise ValueError(f"Pool '{pool_id}' not found on {PROTOCOL_DISPLAY_NAME}")
    return pool


def infer_base_symbol(pool_id: str) -> str:
    """Which side of the pair to price in USD. Mirrors the Messari-path
    heuristic in standardized_query.infer_base_symbol."""
    pool = get_pool_info(pool_id)
    symbols = [pool["token0"]["symbol"], pool["token1"]["symbol"]]
    non_stable = [s for s in symbols if s not in _STABLECOIN_SYMBOLS]
    return non_stable[0] if non_stable else sorted(symbols)[0]


def _to_raw_units(amount: Decimal, decimals: int) -> str:
    """V4 reports amounts as already-scaled BigDecimals ("0.5230024177...")
    while the Messari schema reports raw integer units plus a `decimals`
    field. candle_builder expects the latter, so scale back up — via Decimal
    rather than float, so 18-decimal amounts stay exact."""
    return str(int(amount * (Decimal(10) ** int(decimals))))


def _normalize_swap(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Uniswap V4's {amount0, amount1, amountUSD} -> the
    {tokenIn/tokenOut, amountIn/amountOut} shape candle_builder consumes.

    Sign convention: a negative amount means that token left the pool (the
    trader bought it); positive means it went in. Swaps where both sides
    share a sign are degenerate and get skipped rather than guessed at.
    """
    token0 = raw["pool"]["token0"]
    token1 = raw["pool"]["token1"]
    amount0 = Decimal(raw["amount0"])
    amount1 = Decimal(raw["amount1"])

    if amount0 < 0 < amount1:
        token_out, amount_out = token0, -amount0
        token_in, amount_in = token1, amount1
    elif amount1 < 0 < amount0:
        token_out, amount_out = token1, -amount1
        token_in, amount_in = token0, amount0
    else:
        return None

    # V4 reports one USD value for the whole swap; the Messari schema
    # carries a per-side value. They're within fees/slippage of each other
    # there, so using the single value for both sides is consistent.
    usd = str(abs(Decimal(raw["amountUSD"])))

    return {
        "id": raw["id"],
        "timestamp": raw["timestamp"],
        "amountIn": _to_raw_units(amount_in, token_in["decimals"]),
        "amountInUSD": usd,
        "tokenIn": {"symbol": token_in["symbol"], "decimals": int(token_in["decimals"])},
        "amountOut": _to_raw_units(amount_out, token_out["decimals"]),
        "amountOutUSD": usd,
        "tokenOut": {"symbol": token_out["symbol"], "decimals": int(token_out["decimals"])},
    }


def get_recent_swaps(
    pool_id: str, limit: int = 1000, since: int | None = None
) -> list[dict[str, Any]]:
    """Recent swaps for one V4 pool, newest first, already normalized to
    the shared candle_builder input shape.

    Same cursor-pagination strategy as the Messari path: page on
    `timestamp_lte` and dedupe by id, since many swaps share a block's
    timestamp and a strict `timestamp_lt` cursor would silently drop the
    ones sitting on the page boundary. `since` bounds how far back to
    walk; `limit` still caps the total, so a caller asking for a long
    range on a busy pool gets a truncated (but clearly reported) window
    rather than an unbounded crawl.
    """
    client = get_client()
    pool_id = pool_id.lower()

    collected: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    cursor: int | None = None

    while len(collected) < limit:
        # Full pages every time — see the matching note in
        # standardized_query.get_recent_swaps: shrinking the page to the
        # remaining shortfall degenerates into 1-row requests that return
        # only already-seen rows, stalling one short of the ceiling.
        page_size = MAX_PAGE_SIZE
        variables: dict[str, Any] = {"pool": pool_id, "first": page_size}
        if cursor is not None:
            variables["before"] = cursor
        if since is not None:
            variables["since"] = since

        data = client.query(
            SUBGRAPH_ID,
            _build_swaps_query(with_cursor=cursor is not None, with_since=since is not None),
            variables,
        )

        page = data["swaps"]
        if not page:
            break

        fresh = [s for s in page if s["id"] not in seen_ids]
        if not fresh:
            break

        for raw in fresh:
            seen_ids.add(raw["id"])
            normalized = _normalize_swap(raw)
            if normalized is not None:
                collected.append(normalized)

        cursor = int(page[-1]["timestamp"])

        if len(page) < page_size:
            break

    return collected[:limit]


def _aggregate_rows_to_candles(
    rows: list[dict[str, Any]], time_field: str, invert: bool
) -> list[Candle]:
    """Turn poolHourDatas/poolDayDatas rows into Candles.

    When `invert` is set, every price is flipped to the other side of the
    pair — which means the row's `high` becomes the *low* and vice versa.
    Rather than track that by hand, high and low are re-derived as the max
    and min of all four converted values, which also repairs rows whose
    published OHLC is internally inconsistent (the V4 deployment has
    some, particularly around pool creation).
    """
    candles: list[Candle] = []
    for row in rows:
        try:
            values = [float(row[key]) for key in ("open", "high", "low", "close")]
        except (TypeError, ValueError):
            continue
        if invert:
            if any(value <= 0 for value in values):
                # Can't invert through zero; sanitize_candles drops these.
                continue
            values = [1.0 / value for value in values]

        open_, high, low, close = values[0], values[1], values[2], values[3]
        candles.append(
            Candle(
                timestamp=int(row[time_field]),
                open=open_,
                high=max(open_, high, low, close),
                low=min(open_, high, low, close),
                close=close,
                volume_usd=float(row["volumeUSD"]),
                trade_count=int(row["txCount"]),
            )
        )
    candles.sort(key=lambda c: c.timestamp)
    return candles


def get_aggregate_candles(
    pool_id: str, base_symbol: str, granularity: str, since: int, until: int
) -> tuple[list[Candle], str]:
    """Pre-aggregated OHLC straight from the subgraph.

    `granularity` is "1h" or "1d" — the two the schema actually publishes.
    Returns the candles plus the symbol the price is denominated in (the
    other side of the pair), because unlike the swap path these prices are
    quoted in the paired token rather than in USD.
    """
    if granularity not in ("1h", "1d"):
        raise ValueError(f"No published aggregate for '{granularity}' (only 1h and 1d)")

    pool = get_pool_info(pool_id)
    token0 = pool["token0"]["symbol"]
    token1 = pool["token1"]["symbol"]

    if base_symbol == token0:
        # OHLC is token0-per-token1, so pricing token0 means inverting.
        invert, quote_symbol = True, token1
    elif base_symbol == token1:
        invert, quote_symbol = False, token0
    else:
        raise ValueError(f"'{base_symbol}' is not in this pool ({token0}/{token1})")

    query = HOUR_CANDLES_QUERY if granularity == "1h" else DAY_CANDLES_QUERY
    time_field = "periodStartUnix" if granularity == "1h" else "date"
    rows_key = "poolHourDatas" if granularity == "1h" else "poolDayDatas"

    client = get_client()
    collected: list[dict[str, Any]] = []
    cursor = until

    # Page backwards through the window; each row is one period, so a year
    # of hourly data is ~9 pages and a year of daily is a single page.
    while True:
        data = client.query(
            SUBGRAPH_ID,
            query,
            {"pool": pool_id.lower(), "first": MAX_PAGE_SIZE, "since": since, "before": cursor},
        )
        page = data[rows_key]
        if not page:
            break
        collected.extend(page)
        oldest = int(page[-1][time_field])
        if len(page) < MAX_PAGE_SIZE or oldest <= since:
            break
        cursor = oldest - 1

    return _aggregate_rows_to_candles(collected, time_field, invert), quote_symbol
