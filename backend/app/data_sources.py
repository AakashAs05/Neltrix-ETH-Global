"""One interface over both data paths.

Uniswap V3 and SushiSwap go through the Messari standardized schema;
Uniswap V4 has no such deployment and uses its own adapter. Nothing above
this module branches on which schema is underneath.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.graph import standardized_query
from app.uniswap import v4_pool_client


@dataclass(frozen=True)
class ProtocolInfo:
    key: str
    display_name: str
    network: str
    schema_family: str  # "messari-dex-amm" | "uniswap-native"
    is_flagship: bool


@dataclass(frozen=True)
class PoolSummary:
    id: str
    name: str
    tokens: list[str]
    total_value_locked_usd: float
    cumulative_volume_usd: float


def _is_v4(protocol_key: str) -> bool:
    return protocol_key == v4_pool_client.PROTOCOL_KEY


def list_protocols() -> list[ProtocolInfo]:
    """V4 first, since it is the flagship source and the UI pins it there."""
    protocols = [
        ProtocolInfo(
            key=v4_pool_client.PROTOCOL_KEY,
            display_name=v4_pool_client.PROTOCOL_DISPLAY_NAME,
            network=v4_pool_client.NETWORK,
            schema_family="uniswap-native",
            is_flagship=True,
        )
    ]
    protocols += [
        ProtocolInfo(
            key=p.key,
            display_name=p.display_name,
            network=p.network,
            schema_family="messari-dex-amm",
            is_flagship=False,
        )
        for p in standardized_query.list_protocols()
    ]
    return protocols


def _assert_known(protocol_key: str) -> None:
    known = {p.key for p in list_protocols()}
    if protocol_key not in known:
        raise ValueError(f"Unknown protocol '{protocol_key}'. Known protocols: {sorted(known)}")


def get_top_pools(protocol_key: str, limit: int = 20) -> list[PoolSummary]:
    _assert_known(protocol_key)

    if _is_v4(protocol_key):
        return [
            PoolSummary(
                id=pool["id"],
                name=v4_pool_client.get_pool_display_name(pool),
                tokens=[pool["token0"]["symbol"], pool["token1"]["symbol"]],
                total_value_locked_usd=float(pool["totalValueLockedUSD"]),
                cumulative_volume_usd=float(pool["volumeUSD"]),
            )
            for pool in v4_pool_client.get_top_pools(limit=limit)
        ]

    return [
        PoolSummary(
            id=pool["id"],
            name=pool["name"],
            tokens=[t["symbol"] for t in pool["inputTokens"]],
            total_value_locked_usd=float(pool["totalValueLockedUSD"]),
            cumulative_volume_usd=float(pool["cumulativeVolumeUSD"]),
        )
        for pool in standardized_query.get_top_pools(protocol_key, limit=limit)
    ]


def get_recent_swaps(protocol_key: str, pool_id: str, limit: int = 1000) -> list[dict[str, Any]]:
    """Raw swaps in candle_builder's shape, whichever schema is underneath."""
    _assert_known(protocol_key)
    if _is_v4(protocol_key):
        return v4_pool_client.get_recent_swaps(pool_id, limit=limit)
    return standardized_query.get_recent_swaps(protocol_key, pool_id, limit=limit)


def infer_base_symbol(protocol_key: str, pool_id: str) -> str:
    _assert_known(protocol_key)
    if _is_v4(protocol_key):
        return v4_pool_client.infer_base_symbol(pool_id)
    return standardized_query.infer_base_symbol(protocol_key, pool_id)
