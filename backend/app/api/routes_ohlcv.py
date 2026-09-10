"""GET /api/protocols, /api/pools, /api/ohlcv — the Graph data pipeline surface."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app import data_sources
from app.graph.candle_builder import INTERVAL_SECONDS, RANGE_SECONDS
from app.graph.candle_source import resolve_candles
from app.graph.graph_client import GraphQueryError

from .schemas import CandleOut, OHLCVResponse, PoolOut, ProtocolOut

router = APIRouter(prefix="/api", tags=["graph"])


@router.get("/protocols", response_model=list[ProtocolOut])
def list_protocols() -> list[ProtocolOut]:
    return [
        ProtocolOut(
            key=p.key,
            display_name=p.display_name,
            network=p.network,
            schema_family=p.schema_family,
            is_flagship=p.is_flagship,
        )
        for p in data_sources.list_protocols()
    ]


@router.get("/pools", response_model=list[PoolOut])
def list_pools(
    protocol: str = Query(..., description="Protocol key, e.g. 'uniswap-v4-ethereum'"),
    limit: int = Query(20, ge=1, le=200),
) -> list[PoolOut]:
    try:
        pools = data_sources.get_top_pools(protocol, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except GraphQueryError as exc:
        raise HTTPException(status_code=502, detail=f"Graph query failed: {exc}") from exc

    return [
        PoolOut(
            id=p.id,
            name=p.name,
            tokens=p.tokens,
            total_value_locked_usd=p.total_value_locked_usd,
            cumulative_volume_usd=p.cumulative_volume_usd,
        )
        for p in pools
    ]


@router.get("/ohlcv", response_model=OHLCVResponse)
def get_ohlcv(
    protocol: str = Query(..., description="Protocol key, e.g. 'uniswap-v4-ethereum'"),
    pool: str = Query(..., description="Pool id / pair contract address"),
    interval: str = Query("1h", description=f"One of {list(INTERVAL_SECONDS)}"),
    range: str = Query("1w", description=f"Lookback window, one of {list(RANGE_SECONDS)}"),
    base_symbol: str | None = Query(None, description="Token to price; auto-detected if omitted"),
) -> OHLCVResponse:
    try:
        resolved_base_symbol = base_symbol or data_sources.infer_base_symbol(protocol, pool)
        series = resolve_candles(
            protocol,
            pool,
            base_symbol=resolved_base_symbol,
            interval=interval,
            range_key=range,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except GraphQueryError as exc:
        raise HTTPException(status_code=502, detail=f"Graph query failed: {exc}") from exc

    return OHLCVResponse(
        protocol=protocol,
        pool=pool,
        base_symbol=resolved_base_symbol,
        interval=interval,
        range=range,
        source=series.source,
        quote_symbol=series.quote_symbol,
        truncated=series.truncated,
        notes=series.notes,
        candles=[CandleOut(**c.__dict__) for c in series.candles],
    )
