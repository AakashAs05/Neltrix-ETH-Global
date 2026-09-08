"""Pydantic request/response models for the API layer."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ProtocolOut(BaseModel):
    key: str
    display_name: str
    network: str


class TokenOut(BaseModel):
    symbol: str
    decimals: int


class PoolOut(BaseModel):
    id: str
    name: str
    tokens: list[str]
    total_value_locked_usd: float
    cumulative_volume_usd: float


class CandleOut(BaseModel):
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume_usd: float
    trade_count: int


class OHLCVResponse(BaseModel):
    protocol: str
    pool: str
    base_symbol: str
    interval: str
    candles: list[CandleOut] = Field(default_factory=list)
