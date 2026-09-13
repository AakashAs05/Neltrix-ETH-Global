"""Uniswap V4, on Uniswap's own schema rather than Messari's.

No Messari dex-amm deployment exists for V4, so this speaks the native
schema and normalizes swaps into the same shape the Messari path returns.
Everything downstream then runs on V4 unmodified.
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

# The Graph caps `first` at 1000 per query, same as the Messari path.
MAX_PAGE_SIZE = 1000

# Ranking needs a token allowlist. Wash-traded pairs claiming trillions in
# TVL would otherwise dominate every ordering.
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

    graph-node rejects a null timestamp bound, so an unused one has to be
    absent from the query text rather than passed as null.
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


# Uniswap's schema publishes real OHLC per hour and day, which is what makes
# long ranges affordable: 365 daily rows instead of millions of swaps.
# These track token0Price, so charting token0 means inverting (see below).

# These time fields are Int, not the BigInt that Swap.timestamp uses.
# Declaring them BigInt makes graph-node reject the whole where object.
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


# V4 flags a dynamic-fee pool with the top bit of the fee field rather than
# a real rate. Formatted naively it reads as an absurd "838.86%".
DYNAMIC_FEE_FLAG = 0x800000


def get_pool_display_name(pool: dict[str, Any]) -> str:
    """V4 pool ids are bytes32 hashes with no name field, so compose one."""
    fee_tier = int(pool["feeTier"])
    pair = f"{pool['token0']['symbol']}/{pool['token1']['symbol']}"
    if fee_tier == DYNAMIC_FEE_FLAG:
        return f"Uniswap V4 {pair} (dynamic fee)"
    # `:g` keeps V4's tiny fee tiers legible: 10 becomes 0.001%, not 0.00%.
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
    """Which side of the pair to price. Mirrors the Messari-path heuristic."""
    pool = get_pool_info(pool_id)
    symbols = [pool["token0"]["symbol"], pool["token1"]["symbol"]]
    non_stable = [s for s in symbols if s not in _STABLECOIN_SYMBOLS]
    return non_stable[0] if non_stable else sorted(symbols)[0]


def _to_raw_units(amount: Decimal, decimals: int) -> str:
    """V4 reports scaled decimals; candle_builder expects raw integer units.

    Scaled via Decimal rather than float so 18-decimal amounts stay exact.
    """
    return str(int(amount * (Decimal(10) ** int(decimals))))


def _normalize_swap(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Convert V4's signed amounts into the shape candle_builder consumes.

    A negative amount means that token left the pool. Swaps where both sides
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

    # V4 reports one USD value per swap where Messari carries a per-side
    # value. They agree within fees, so reusing it on both sides is fine.
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
    """Recent swaps for one V4 pool, normalized to candle_builder's shape.

    Same cursor pagination as the Messari path: page on `timestamp_lte` and
    dedupe by id. `since` bounds the walk, `limit` caps it.
    """
    client = get_client()
    pool_id = pool_id.lower()

    collected: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    cursor: int | None = None

    while len(collected) < limit:
        # Full pages only. Shrinking to the shortfall degenerates into
        # 1-row requests that return duplicates and stall short of the ceiling.
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
    """Turn published hourly/daily rows into Candles.

    Inverting flips high and low, so both are re-derived as the max and min
    of the four converted values. That also repairs inconsistent rows.
    """
    candles: list[Candle] = []
    for row in rows:
        try:
            values = [float(row[key]) for key in ("open", "high", "low", "close")]
        except (TypeError, ValueError):
            continue
        if invert:
            if any(value <= 0 for value in values):
                continue  # can't invert through zero; sanitize drops these
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
    """Pre-aggregated OHLC straight from the subgraph, hourly or daily.

    Also returns the symbol the price is quoted in, since unlike the swap
    path these are denominated in the paired token rather than USD.
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

    # Page backwards through the window. A year of hourly is about 9 pages,
    # a year of daily is one.
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
