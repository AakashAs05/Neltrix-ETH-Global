from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_ohlcv import router as ohlcv_router

app = FastAPI(title="Neltrix ETH Global")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ohlcv_router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
