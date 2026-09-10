"""POST /api/analyse — fetch, detect patterns, score a verdict, explain it."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.engine import pipeline
from app.graph.candle_builder import INTERVAL_SECONDS, RANGE_SECONDS
from app.graph.graph_client import GraphQueryError

from .schemas import CandleOut

router = APIRouter(prefix="/api", tags=["analysis"])


class AnalyseRequest(BaseModel):
    protocol: str = Field(..., description="Protocol key, e.g. 'uniswap-v4-ethereum'")
    pool: str = Field(..., description="Pool id / pair contract address")
    interval: str = Field("1h", description=f"One of {list(INTERVAL_SECONDS)}")
    range: str = Field("1w", description=f"Lookback window, one of {list(RANGE_SECONDS)}")
    base_symbol: str | None = Field(None, description="Token to price; auto-detected if omitted")


class SeriesMetaOut(BaseModel):
    """Where the candles came from, so the UI can show provenance rather
    than implying every chart is built the same way."""

    source: str  # "subgraph-aggregate" | "derived-from-swaps"
    quote_symbol: str
    swaps_scanned: int
    rows_dropped: int
    truncated: bool
    notes: list[str]


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
    range: str
    series: SeriesMetaOut
    candles: list[CandleOut]
    patterns: list[PatternOut]
    total_detected: int  # raw geometric matches before significance filtering
    support_resistance: list[PriceLevelOut]
    verdict: VerdictOut
    explanation: str


@router.post("/analyse", response_model=AnalyseResponse)
def analyse(req: AnalyseRequest) -> AnalyseResponse:
    try:
        result = pipeline.run_analysis(
            req.protocol,
            req.pool,
            interval=req.interval,
            range_key=req.range,
            base_symbol=req.base_symbol,
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
        range=result.range_key,
        series=SeriesMetaOut(
            source=result.series.source,
            quote_symbol=result.series.quote_symbol,
            swaps_scanned=result.series.swaps_scanned,
            rows_dropped=result.series.rows_dropped,
            truncated=result.series.truncated,
            notes=result.series.notes,
        ),
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
        total_detected=result.total_detected,
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
