# Neltrix Onchain

Pattern intelligence over DEX swap data, built entirely from onchain events and sold per call to software.

Neltrix derives OHLCV candles from individual Uniswap/SushiSwap swap events indexed by The Graph — no centralised price feed anywhere in the stack — runs candlestick, chart and harmonic pattern detection over them, and gates the analysis endpoint behind a per-request HBAR payment using x402 on Hedera.

**Built for ETHOnline 2026**, targeting The Graph, Uniswap Foundation and Hedera tracks.

---

## What problem this solves

Every trade on a DEX is public, but there is no market-data layer over it. To answer *"give me hourly candles with support levels for this pool"* you would have to replay 1.45M swap events, know that Uniswap V4 uses a completely different schema from V3, and discover on your own that some pools report negative TVL and that ~9% of published hourly candles carry poisoned wicks.

Neltrix is that missing layer, and adds two things on top:

- **Composability** — one query shape runs unmodified across three DEXs with three different schemas, so a caller doesn't care which venue the data came from.
- **Machine-payable access** — an agent with no account, no API key and no subscription discovers the price from a `402` response and pays for a single call.

### What it is not

It does not trade, hold positions, or execute swaps. The pattern verdict is a deterministic roll-up of geometric matches — **it has not been backtested against forward returns**, so its "confidence" measures agreement between rules, not probability of being right. The trustworthy outputs are the price history, the support/resistance levels, and the data-quality findings.

---

## Architecture

```
                 The Graph (decentralized network gateway)
                            |
   Messari "dex-amm" subgraphs     Uniswap V4 native subgraph
   (Uniswap V3, SushiSwap)         (poolHourDatas / poolDayDatas / swaps)
            |                               |
   standardized_query.py            uniswap/v4_pool_client.py
            \_______________  _______________/
                           \/
                    data_sources.py          <- one interface, both schemas
                           |
                  graph/candle_source.py     <- picks aggregate vs swap replay
                           |
                 graph/candle_builder.py     <- OHLCV + sanitising
                           |
                   engine/pipeline.py        <- detect -> score -> explain
                           |
                  FastAPI  :8000
                     /            \
        frontend :3000        paywall :8402  (x402, Hedera)
        (free browsing)              |
                              agent/  (pays 0.1 HBAR per call)
```

Full detail in [docs/architecture.md](docs/architecture.md).

---

## The payment flow

`POST /api/analyse` is the only priced route. Everything else — protocol listing, pool discovery, health — is free, so the UI browses without paying.

```
agent                          paywall :8402                    Blocky402            Hedera
  |                                 |                               |                   |
  |-- POST /api/analyse ----------->|                               |                   |
  |   (no payment)                  |                               |                   |
  |<-- 402 + PAYMENT-REQUIRED ------|                               |                   |
  |    scheme=exact                 |                               |                   |
  |    network=hedera:testnet       |                               |                   |
  |    asset=0.0.0 (HBAR)           |                               |                   |
  |    amount=10000000 tinybars     |                               |                   |
  |    payTo=<merchant>             |                               |                   |
  |    extra.feePayer=0.0.7162784   |                               |                   |
  |                                 |                               |                   |
  | builds + partially signs a Hedera transfer for exactly that amount                   |
  |                                 |                               |                   |
  |-- POST + PAYMENT-SIGNATURE ---->|                               |                   |
  |                                 |-- /verify ------------------->|                   |
  |                                 |<-- ok ------------------------|                   |
  |                                 | (forwards to FastAPI :8000)   |                   |
  |                                 |-- /settle ------------------->|-- CRYPTOTRANSFER->|
  |                                 |<-- tx id ---------------------|<-- SUCCESS -------|
  |<-- 200 + analysis JSON ---------|                               |                   |
  |    + PAYMENT-RESPONSE (receipt) |                               |                   |
```

Notes that cost real debugging time:

- x402 v2 uses **unprefixed** headers: `PAYMENT-SIGNATURE`, `PAYMENT-REQUIRED`, `PAYMENT-RESPONSE` — not `X-PAYMENT-*`.
- The **facilitator pays network fees** (`0.0.7162784`), so the payer's balance moves by exactly the price with no gas noise.
- The client's default spend controls reject native HBAR outright (it only permits recognised assets under a $1 cap). The agent opts HBAR in explicitly with a **0.5 HBAR per-call ceiling** rather than disabling controls — an autonomous payer should refuse an overpriced `402` before signing.

Verified working: three payments settled on Hedera testnet, confirmed via mirror node independently of application code.

---

## Setup

### Prerequisites

- Python 3.12+, Node 20+
- A **Graph API key** — https://thegraph.com/studio/apikeys/
- Two **Hedera testnet accounts** — https://portal.hedera.com/ (free, pre-funded)

### Configure

```bash
cp .env.example .env
```

Fill in `.env` (git-ignored — never commit it):

| Variable | Notes |
| --- | --- |
| `GRAPH_API_KEY` | from The Graph Studio |
| `HEDERA_MERCHANT_ACCOUNT_ID` | receives payment; **no private key needed** |
| `HEDERA_AGENT_ACCOUNT_ID` | the buyer |
| `HEDERA_AGENT_PRIVATE_KEY` | hex ECDSA key, `0x` + 64 chars; signs the transfer |
| `X402_PRICE_TINYBARS` | price per call (default `10000000` = 0.1 HBAR) |

### Install

```bash
cd backend && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
cd ../frontend && npm install
cd ../paywall && npm install
cd ../agent && npm install
```

### Run

Backend (terminal 1):
```bash
cd backend && source .venv/bin/activate && uvicorn app.main:app --port 8000 --reload
```

Frontend (terminal 2) — http://localhost:3000
```bash
cd frontend && npm run dev
```

Paywall (terminal 3), only needed for the payment demo:
```bash
cd paywall && node server.mjs
```

Then buy one analysis:
```bash
cd agent && npm start
```

---

## API

| Route | Price | Purpose |
| --- | --- | --- |
| `GET /api/health` | free | liveness |
| `GET /api/protocols` | free | available protocols + which schema each speaks |
| `GET /api/pools?protocol=…` | free | top pools by traded volume |
| `GET /api/ohlcv?protocol=…&pool=…&interval=…&range=…` | free | candles only |
| `POST /api/analyse` | **0.1 HBAR** via `:8402` | candles + patterns + levels + verdict |

`interval` ∈ `5m 15m 1h 4h 1d` · `range` ∈ `1d 1w 1m 3m 1y`

---

## Track qualification

### The Graph

`backend/app/graph/standardized_query.py` sends **one query string** to Uniswap V3 and SushiSwap, both published by Messari on the `dex-amm` Standardized Subgraph schema. Adding another dex-amm protocol is a one-line registry entry — no new query, no new parsing.

What the standardized schema made easier, stated explicitly because it's the point of the track: two independently-built AMMs became interchangeable data sources behind a single code path. The contrast is Uniswap V4, which has **no** Messari deployment and therefore needed a bespoke ~250-line adapter to reach the same internal shape.

The constraint that fell out of it: the shared query can only use fields present on *every* deployment. Uniswap V3 is on schema v4.0.1 and SushiSwap on v1.3.2, so `cumulativeSwapCount` exists on one and not the other and had to leave the shared query.

Live data only — every candle traces to indexed swap events on Ethereum mainnet. No mocked datasets.

### Uniswap

Uniswap V4 is the flagship pool source (`backend/app/uniswap/v4_pool_client.py`), with V3 available for comparison. Feedback drafted in [docs/FEEDBACK.md](docs/FEEDBACK.md).

### Hedera

Live x402-gated service on Hedera testnet settled through Blocky402 (`paywall/server.mjs`), plus an agent that completes real paid requests end to end (`agent/pay_and_analyse.mjs`).

---

## Data quality

Onchain data is not clean, and pretending otherwise would produce confident nonsense. What the pipeline detects and repairs, all reported in the API response rather than silently applied:

| Problem | Example found | Handling |
| --- | --- | --- |
| Pool-creation artifacts | rows inverting to **$3×10²⁰** | dropped (non-positive / zero-volume) |
| Single bad prints | one hour claiming ETH traded **$4 – $2,446** | wick clamped to a local rolling median; body preserved |
| Negative TVL | top V4 USDC/USDT pool at **−$24.7M** | pools ranked by volume, never TVL |
| Wash-traded pools | ETH/"1xETH" claiming **$2.3T** TVL | major-token allowlist for rankings |
| Unhealthy indexers | "bad indexers", read timeouts | retry with backoff; surfaced as 502, never a bare 500 |

Data quality is itself a signal. On the same pair and week, the ETH/USDC **0.05%** pool needed no repairs while the **0.01%** tier needed 7 wick clamps — evidence the thinner tier gets sandwiched. A centralised chart showing an averaged market price structurally cannot tell you that.

---

## Repository layout

```
backend/     FastAPI service — Graph clients, candle pipeline, pattern engine
frontend/    Next.js UI — pool picker, SVG candlestick chart, pattern panel
paywall/     x402 payment gateway (Express sidecar) for POST /api/analyse
agent/       Autonomous buyer that pays for one analysis
docs/        Architecture, Uniswap feedback, demo script
```
