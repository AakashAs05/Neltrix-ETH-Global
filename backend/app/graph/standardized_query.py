"""One query shape, run unmodified against multiple protocols.

This is the file that earns Neltrix its "composable across The Graph"
claim. Uniswap V3 and SushiSwap are two independently-built, independently
maintained AMMs, but Messari publishes both of them as "dex-amm"
Standardized Subgraphs, which means both expose the *same* GraphQL schema
(`DexAmmProtocol`, `LiquidityPool`, `Swap`, ...). Every function below takes
a `protocol` key and dispatches to a different subgraph ID, but sends the
exact same query string either way. Nothing here is Uniswap-specific or
Sushi-specific.

Verified subgraph IDs (Messari "dex-amm" schema family, Ethereum mainnet,
decentralized network, checked live against the gateway on 2026-09-08):

    uniswap-v3-ethereum  -> 4cKy6QQMc5tpfdx8yxfYeb9TLZmgLQe44ddW1G7NwkA6
    sushiswap-ethereum   -> 77jZ9KWeyi3CJ96zkkj5s1CojKPHt6XJKjLFzsDCd8Fd

Adding a third protocol (e.g. uniswap-v2-ethereum, also "dex-amm") is a
one-line addition to PROTOCOLS below, no new query, no new parsing code.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from .graph_client import get_client


@dataclass(frozen=True)
class Protocol:
    key: str
    display_name: str
    subgraph_id: str
    network: str


def _subgraph_id(env_var: str, fallback: str) -> str:
    return os.getenv(env_var) or fallback


# Registry of protocols that all speak the Messari "dex-amm" standardized
# schema. Add an entry here to bring a new DEX/chain into every endpoint
# in this file with zero other code changes.
PROTOCOLS: dict[str, Protocol] = {
    "uniswap-v3-ethereum": Protocol(
        key="uniswap-v3-ethereum",
        display_name="Uniswap V3 (Ethereum)",
        subgraph_id=_subgraph_id(
            "UNISWAP_V3_ETHEREUM_SUBGRAPH_ID", "4cKy6QQMc5tpfdx8yxfYeb9TLZmgLQe44ddW1G7NwkA6"
        ),
        network="mainnet",
    ),
    "sushiswap-ethereum": Protocol(
        key="sushiswap-ethereum",
        display_name="SushiSwap (Ethereum)",
        subgraph_id=_subgraph_id(
            "SUSHISWAP_ETHEREUM_SUBGRAPH_ID", "77jZ9KWeyi3CJ96zkkj5s1CojKPHt6XJKjLFzsDCd8Fd"
        ),
        network="mainnet",
    ),
}


def list_protocols() -> list[Protocol]:
    return list(PROTOCOLS.values())


def _get_protocol(protocol_key: str) -> Protocol:
    try:
        return PROTOCOLS[protocol_key]
    except KeyError:
        raise ValueError(
            f"Unknown protocol '{protocol_key}'. Known protocols: {list(PROTOCOLS)}"
        ) from None


# --- The one query shape --------------------------------------------------
# Same string, sent to whichever protocol's subgraph_id the caller asked for.

# Deliberately excludes fields like `cumulativeSwapCount` and `tick` that
# exist on Uniswap V3's schema (v4.0.1) but not on SushiSwap's (v1.3.2) —
# Messari schema versions drift slightly between protocols. Only fields
# present in every deployment this project queries belong in a query meant
# to run unmodified across protocols; that constraint is the whole point.
TOP_POOLS_QUERY = """
query TopPools($first: Int!) {
  liquidityPools(first: $first, orderBy: cumulativeVolumeUSD, orderDirection: desc) {
    id
    name
    inputTokens { symbol decimals }
    totalValueLockedUSD
    cumulativeVolumeUSD
  }
}
"""

# The Graph's gateway caps `first` at 1000 per query regardless of what
# any individual indexer advertises — asking for more just returns a
# "bad indexers" error instead of more rows. get_recent_swaps() below
# pages through this in chunks of up to 1000 for any larger `limit`.
MAX_PAGE_SIZE = 1000

RECENT_SWAPS_QUERY = """
query RecentSwaps($pool: String!, $first: Int!) {
  swaps(
    first: $first
    orderBy: timestamp
    orderDirection: desc
    where: { pool: $pool }
  ) {
    id
    timestamp
    amountIn
    amountInUSD
    amountOut
    amountOutUSD
    tokenIn { symbol decimals }
    tokenOut { symbol decimals }
  }
}
"""

# Same query, plus a `timestamp_lte` cursor for continuing past page one.
# graph-node rejects `timestamp_lte: null`, so this can't just be an
# optional variable on RECENT_SWAPS_QUERY above — it has to be a separate
# query string used only once a cursor exists.
RECENT_SWAPS_QUERY_PAGE = """
query RecentSwapsPage($pool: String!, $first: Int!, $before: BigInt!) {
  swaps(
    first: $first
    orderBy: timestamp
    orderDirection: desc
    where: { pool: $pool, timestamp_lte: $before }
  ) {
    id
    timestamp
    amountIn
    amountInUSD
    amountOut
    amountOutUSD
    tokenIn { symbol decimals }
    tokenOut { symbol decimals }
  }
}
"""


def get_top_pools(protocol_key: str, limit: int = 20) -> list[dict[str, Any]]:
    """Top pools by cumulative volume, for the pool picker UI."""
    protocol = _get_protocol(protocol_key)
    data = get_client().query(protocol.subgraph_id, TOP_POOLS_QUERY, {"first": limit})
    return data["liquidityPools"]


def get_recent_swaps(protocol_key: str, pool_id: str, limit: int = 1000) -> list[dict[str, Any]]:
    """Raw swap events for one pool, newest first. Feeds candle_builder.

    Pages through MAX_PAGE_SIZE-sized chunks for any `limit` above that.
    The cursor is the oldest timestamp seen so far, refetched with
    `timestamp_lte` — since many swaps can share one block's timestamp,
    that overlaps the previous page by design and results are deduped by
    `id` rather than risking a `timestamp_lt` cursor silently skipping
    swaps that share a timestamp with the page boundary.
    """
    protocol = _get_protocol(protocol_key)
    client = get_client()
    pool_id = pool_id.lower()

    collected: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    cursor: int | None = None

    while len(collected) < limit:
        page_size = min(MAX_PAGE_SIZE, limit - len(collected))
        if cursor is None:
            data = client.query(protocol.subgraph_id, RECENT_SWAPS_QUERY, {"pool": pool_id, "first": page_size})
        else:
            data = client.query(
                protocol.subgraph_id,
                RECENT_SWAPS_QUERY_PAGE,
                {"pool": pool_id, "first": page_size, "before": cursor},
            )

        page = data["swaps"]
        if not page:
            break

        new_swaps = [s for s in page if s["id"] not in seen_ids]
        if not new_swaps:
            break  # every swap at this cursor has already been collected — no more pages

        for swap in new_swaps:
            seen_ids.add(swap["id"])
        collected.extend(new_swaps)
        cursor = int(page[-1]["timestamp"])

        if len(page) < page_size:
            break  # fewer rows than asked for — reached the end of history

    return collected[:limit]


POOL_INFO_QUERY = """
query PoolInfo($pool: String!) {
  liquidityPool(id: $pool) {
    id
    name
    inputTokens { symbol decimals }
  }
}
"""

# Stablecoins we skip over when guessing which side of a pair to price in
# USD (a WETH/USDC pool should chart WETH's price, not USDC's).
_STABLECOIN_SYMBOLS = {"USDC", "USDT", "DAI", "BUSD", "TUSD", "USDP", "FRAX", "LUSD", "GUSD"}


def get_pool_info(protocol_key: str, pool_id: str) -> dict[str, Any]:
    protocol = _get_protocol(protocol_key)
    data = get_client().query(protocol.subgraph_id, POOL_INFO_QUERY, {"pool": pool_id.lower()})
    pool = data.get("liquidityPool")
    if pool is None:
        raise ValueError(f"Pool '{pool_id}' not found on {protocol.display_name}")
    return pool


def infer_base_symbol(protocol_key: str, pool_id: str) -> str:
    """Pick which side of the pair to chart when the caller doesn't say.

    Prefers the non-stablecoin token (e.g. WETH in a USDC/WETH pool); falls
    back to the first token alphabetically for stable/stable or vol/vol pairs.
    """
    pool = get_pool_info(protocol_key, pool_id)
    symbols = [t["symbol"] for t in pool["inputTokens"]]
    non_stable = [s for s in symbols if s not in _STABLECOIN_SYMBOLS]
    return non_stable[0] if non_stable else sorted(symbols)[0]
