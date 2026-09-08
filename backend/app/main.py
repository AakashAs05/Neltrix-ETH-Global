from fastapi import FastAPI

app = FastAPI(title="Neltrix ETH Global")

@app.get("/api/health")
def health():
    return {"status": "ok"}