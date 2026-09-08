"""GET /api/protocols, /api/pools, /api/ohlcv — the Graph data pipeline surface."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.graph import standardized_query
from app.graph.candle_builder import INTERVAL_SECONDS, build_ohlcv
from app.graph.graph_client import GraphQueryError

from .schemas import CandleOut, OHLCVResponse, PoolOut, ProtocolOut

router = APIRouter(prefix="/api", tags=["graph"])


@router.get("/protocols", response_model=list[ProtocolOut])
def list_protocols() -> list[ProtocolOut]:
    return [
        ProtocolOut(key=p.key, display_name=p.display_name, network=p.network)
        for p in standardized_query.list_protocols()
    ]


@router.get("/pools", response_model=list[PoolOut])
def list_pools(
    protocol: str = Query(..., description="Protocol key, e.g. 'uniswap-v3-ethereum'"),
    limit: int = Query(20, ge=1, le=200),
) -> list[PoolOut]:
    try:
        pools = standardized_query.get_top_pools(protocol, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except GraphQueryError as exc:
        raise HTTPException(status_code=502, detail=f"Graph query failed: {exc}") from exc

    return [
        PoolOut(
            id=p["id"],
            name=p["name"],
            tokens=[t["symbol"] for t in p["inputTokens"]],
            total_value_locked_usd=float(p["totalValueLockedUSD"]),
            cumulative_volume_usd=float(p["cumulativeVolumeUSD"]),
        )
        for p in pools
    ]


@router.get("/ohlcv", response_model=OHLCVResponse)
def get_ohlcv(
    protocol: str = Query(..., description="Protocol key, e.g. 'uniswap-v3-ethereum'"),
    pool: str = Query(..., description="Pool/pair contract address"),
    interval: str = Query("1h", description=f"One of {list(INTERVAL_SECONDS)}"),
    limit: int = Query(1000, ge=1, le=5000, description="How many raw swaps to fetch before bucketing"),
    base_symbol: str | None = Query(None, description="Token to price in USD; auto-detected if omitted"),
) -> OHLCVResponse:
    try:
        resolved_base_symbol = base_symbol or standardized_query.infer_base_symbol(protocol, pool)
        swaps = standardized_query.get_recent_swaps(protocol, pool, limit=limit)
        candles = build_ohlcv(swaps, base_symbol=resolved_base_symbol, interval=interval)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except GraphQueryError as exc:
        raise HTTPException(status_code=502, detail=f"Graph query failed: {exc}") from exc

    return OHLCVResponse(
        protocol=protocol,
        pool=pool,
        base_symbol=resolved_base_symbol,
        interval=interval,
        candles=[CandleOut(**c.__dict__) for c in candles],
    )
