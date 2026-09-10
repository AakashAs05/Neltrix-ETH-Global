"""POST /api/analyse — fetch, detect patterns, score a verdict, explain it."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.engine import pipeline
from app.graph.graph_client import GraphQueryError

from .schemas import CandleOut

router = APIRouter(prefix="/api", tags=["analysis"])


class AnalyseRequest(BaseModel):
    protocol: str = Field(..., description="Protocol key, e.g. 'uniswap-v3-ethereum'")
    pool: str = Field(..., description="Pool/pair contract address")
    interval: str = "1h"
    limit: int = Field(1000, ge=5, le=5000, description="Raw swaps to fetch before bucketing")
    base_symbol: str | None = Field(None, description="Token to price in USD; auto-detected if omitted")


class PatternOut(BaseModel):
    name: str
    category: str
    direction: str
    confidence: float
    start_timestamp: int
    end_timestamp: int
    description: str


class PriceLevelOut(BaseModel):
    price: float
    kind: str
    touches: int
    strength: float


class VerdictOut(BaseModel):
    direction: str
    confidence: float
    score: float
    pattern_count: int


class AnalyseResponse(BaseModel):
    protocol: str
    pool: str
    base_symbol: str
    interval: str
    candles: list[CandleOut]
    patterns: list[PatternOut]
    support_resistance: list[PriceLevelOut]
    verdict: VerdictOut
    explanation: str


@router.post("/analyse", response_model=AnalyseResponse)
def analyse(req: AnalyseRequest) -> AnalyseResponse:
    try:
        result = pipeline.run_analysis(
            req.protocol, req.pool, interval=req.interval, limit=req.limit, base_symbol=req.base_symbol
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except GraphQueryError as exc:
        raise HTTPException(status_code=502, detail=f"Graph query failed: {exc}") from exc

    return AnalyseResponse(
        protocol=result.protocol,
        pool=result.pool,
        base_symbol=result.base_symbol,
        interval=result.interval,
        candles=[CandleOut(**c.__dict__) for c in result.candles],
        patterns=[
            PatternOut(
                name=p.name,
                category=p.category,
                direction=p.direction,
                confidence=p.confidence,
                start_timestamp=p.start_timestamp,
                end_timestamp=p.end_timestamp,
                description=p.description,
            )
            for p in result.patterns
        ],
        support_resistance=[
            PriceLevelOut(price=l.price, kind=l.kind, touches=l.touches, strength=l.strength)
            for l in result.support_resistance
        ],
        verdict=VerdictOut(
            direction=result.verdict.direction,
            confidence=result.verdict.confidence,
            score=result.verdict.score,
            pattern_count=result.verdict.pattern_count,
        ),
        explanation=result.explanation,
    )
