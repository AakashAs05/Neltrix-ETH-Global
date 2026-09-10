from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_analyse import router as analyse_router
from app.api.routes_ohlcv import router as ohlcv_router

app = FastAPI(title="Neltrix ETH Global")

# Both spellings of the dev origin: Next prints "localhost:3000" but
# 127.0.0.1:3000 serves the same app, and CORS treats them as different
# origins — so allowing only one makes the UI fail depending on which URL
# the developer happened to type.
DEV_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=DEV_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ohlcv_router)
app.include_router(analyse_router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
