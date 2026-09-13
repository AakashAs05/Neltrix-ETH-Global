# Architecture

How a swap on Ethereum becomes a paid analysis response, and why each piece exists.

---

## 1. The data problem

A Uniswap pool does not store prices. It stores **swaps** - a record that some wallet put in X of one token and took out Y of another:

```
05:11:23  0x82c74a84… put in 3.909798 ETH, took out 9,817.00 USDC   (amountUSD $9,821.83)
```

Price is *derived*: `9817.00 / 3.909798 = $2,512.11 per ETH`. Do that for every swap, bucket by time, and you have a candle. The ETH/USDC 0.05% V4 pool alone holds **1,451,228 swaps since January 2025**.

Two separate obstacles sit between that and usable candles:

1. **Schema fragmentation.** Uniswap V3 and SushiSwap are published by Messari under one standardized `dex-amm` schema. Uniswap V4 is not, and uses a completely different shape.
2. **Cost.** Replaying millions of swap events to chart a year is not viable in a request cycle.

The pipeline below exists to solve exactly those two.

---

## 2. Data sources

### Messari `dex-amm` standardized subgraphs

`backend/app/graph/standardized_query.py`

| Protocol | Subgraph ID | Schema |
| --- | --- | --- |
| `uniswap-v3-ethereum` | `4cKy6QQMc5tpfdx8yxfYeb9TLZmgLQe44ddW1G7NwkA6` | dex-amm v4.0.1 |
| `sushiswap-ethereum` | `77jZ9KWeyi3CJ96zkkj5s1CojKPHt6XJKjLFzsDCd8Fd` | dex-amm v1.3.2 |

Both answer the **same query string**. Entities are `DexAmmProtocol`, `LiquidityPool`, `Swap`, and swaps expose `tokenIn`/`tokenOut` with `amountIn`/`amountOut` plus per-side USD values.

Constraint discovered in practice: schema versions drift between deployments. `cumulativeSwapCount` exists on Uniswap V3's v4.0.1 but not SushiSwap's v1.3.2, so a query intended to run unmodified everywhere can only use the intersection of fields.

Critically, **this schema publishes no OHLC at all.** `LiquidityPoolHourlySnapshot` carries volume, TVL and revenue, but no open/high/low/close. Candles here must be rebuilt from raw swaps.

### Uniswap V4 native subgraph

`backend/app/uniswap/v4_pool_client.py`

`DiYPVdygkfjDWhbxGSqAQxwBKmfKnkWQojqeM2rkLb3G` — the V4 mainnet deployment published in Uniswap's developer docs. V4's singleton `PoolManager` + hooks architecture has no Messari equivalent, so this speaks Uniswap's own schema: `Pool`, `Swap` with signed `amount0`/`amount1`, and — crucially — `poolHourDatas` / `poolDayDatas` **with real open/high/low/close**.

`_normalize_swap()` converts V4's `{amount0, amount1, amountUSD}` into the same `{tokenIn, tokenOut, amountIn, amountOut}` shape the Messari path produces. **Everything downstream runs on V4 unmodified** — only this adapter knows a second schema exists.

Two traps:

- **Orientation.** Published OHLC tracks `token0Price` (token0 *per* token1). On ETH/USDC that reads ~0.000406 ETH per USDC, so charting ETH means inverting — **which swaps high and low**. High/low are re-derived as max/min of the four converted values, which also repairs internally inconsistent rows.
- **Sign convention.** A negative amount means that token left the pool (the trader bought it).

### The dispatch layer

`backend/app/data_sources.py` presents one interface (`list_protocols`, `get_top_pools`, `get_recent_swaps`, `infer_base_symbol`) over both. Routes and the engine never branch on which schema is underneath.

---

## 3. Candle construction

`backend/app/graph/candle_source.py` picks a strategy per request:

| Interval | Uniswap V4 | Messari (V3 / Sushi) |
| --- | --- | --- |
| `5m`, `15m` | replay swaps | replay swaps |
| `1h` | published `poolHourDatas` | replay swaps |
| `4h` | hourly, resampled ×4 | replay swaps |
| `1d` | published `poolDayDatas` | replay swaps |

The difference is large: **a year of daily candles from published aggregates returns 365 rows in ~2 seconds**, versus millions of swap events for the same window.

The swap-replay path is capped at 10,000 swaps. Whether that cap truncated the request is decided by **coverage** — did we actually reach back to the start of the window — not by row count. (An earlier version inferred truncation from `len(swaps) >= ceiling`, which silently under-reported: page-boundary dedup left the loop one row short, so a 1-year request returning 2 days claimed to be complete.)

### Pagination

The Graph's gateway caps `first` at 1000 per query. Both clients page backwards on a `timestamp_lte` cursor and **dedupe by id**, because many swaps share a block's timestamp and a strict `timestamp_lt` cursor would silently drop the ones on the page boundary. Full pages are always requested and trimmed at the end, so the ceiling check stays meaningful.

### Sanitising

`backend/app/graph/candle_builder.py`. Rules are asset-agnostic — the same code charts ETH, WBTC and whatever else a pool holds:

1. **Non-positive OHLC** → dropped (structurally invalid).
2. **Zero volume** → dropped; no trade means no price discovery. Catches pool-creation rows, e.g. two rows on the V4 ETH/USDC pool that invert to ~$3×10²⁰.
3. **High/low ratio > 20×** → dropped as an indexing artifact.
4. **Outlier wicks** → *clamped*, not dropped. A single out-of-range print (MEV sandwich, dust swap) sets an extreme high or low while open and close stay sane — ~9% of hourly candles on the ETH/USDC 0.01% pool, including one claiming ETH traded between **$4 and $2,446**. Each candle is compared to a centred rolling median of close (25-candle window) and wicks beyond ±25% are pulled back. If the *body* is also outside the band, the candle is left alone — that's a real move, and clamping it would fabricate price action.

Every repair is counted and returned in `series.notes`, never applied silently.

---

## 4. Pattern engine

`backend/app/engine/`

| Module | Detects |
| --- | --- |
| `patterns/candlestick.py` | Doji, Hammer / Hanging Man, Inverted Hammer / Shooting Star, Engulfing, Harami, Morning / Evening Star |
| `patterns/classic.py` | Double Top / Bottom, Head & Shoulders (+ inverse), Triangles, Wedges |
| `patterns/harmonic.py` | Gartley, Bat, Butterfly, Crab via Fibonacci ratios on XABCD swing points |
| `signals.py` | Support/resistance clustering, significance filtering, weighted verdict |
| `pipeline.py` | Orchestration: fetch → detect → filter → score → explain |
| `../ai/explainer.py` | Plain-English summary, grounded in verdict only |

All three detectors share `find_swing_points()` — a candle is a swing high/low if its high/low is the most extreme within a window on both sides.

### Significance filtering

Raw geometric detection reported ~100 matches on a week of hourly candles, which is far more signal than a chart that size can plausibly contain. Three filters, in order of how much they remove:

1. **Context** — a candlestick reversal shape mid-range is noise; the same shape where price has repeatedly turned is the actual setup. Candlestick patterns must land within 0.6% of a support/resistance level. Multi-candle formations carry their own structure and are exempt.
2. **Confidence floor** — per category, since the categories aren't comparable on one scale.
3. **Non-maximum suppression** — overlapping same-name matches describe one formation, so only the strongest survives.

Both counts are returned (`patterns` and `total_detected`) so the trim is visible.

Definitions were also tightened after measurement: Harami originally fired on 17% of all candles because `body < prev_body` matches any alternating pair in ordinary chop. It now requires a *decisive* prior candle (body ≥ 50% of its range) and an inside body ≤ 50% of it. Head & Shoulders gained neckline validation and head-prominence requirements, plus real confidence scoring instead of a hardcoded 0.65. Doji was made mutually exclusive with the Hammer family — when the body is tiny, `lower >= 2 * body` is nearly always true, so the same candle was being labelled both.

### Support and resistance

Swing points are clustered against a **running mean** (not the first member, which let slow drift either split one level or swallow a wide band). A level requires **≥2 touches** — a single swing point is not a level — and support/resistance pairs landing on the same price are merged. Up to 3 per kind are returned; the chart draws only the strongest of each.

### Verdict

Each surviving pattern votes, weighted by category (harmonic 1.5 > classic 1.2 > candlestick 0.8) and recency. Normalised to roughly −1…+1 and thresholded into bullish / bearish / neutral.

**This is not validated.** No backtest checks whether these patterns precede the moves they claim. The confidence figure measures agreement between rules, not probability of being correct — and the UI says so.

---

## 5. Payment layer

`paywall/server.mjs` — an Express sidecar on `:8402` gating **only** `POST /api/analyse` at 0.1 HBAR, proxying everything else through free.

It's a Node sidecar rather than FastAPI middleware because the x402 reference implementation (`@x402/hedera`, `@x402/express`) is TypeScript. Re-implementing Hedera transaction construction and signature verification in Python would mean hand-rolling precisely the parts of the spec most likely to be subtly wrong.

```
paymentMiddlewareFromConfig(routes, HTTPFacilitatorClient, [ExactHederaScheme])
```

`agent/pay_and_analyse.mjs` is the counterpart buyer. It is a **customer of an API** — it purchases one analysis response and prints it. It does not trade, hold positions, or act on the analysis.

See the README for the full request/response sequence and the header-naming and spend-control gotchas.

---

## 6. Frontend

`frontend/` — Next.js 16 App Router, Tailwind v4, committed dark theme.

`components/charts/PoolChart.tsx` is a hand-rolled SVG candlestick chart rather than a charting library, because the pattern overlays need to draw arbitrary spans tied to specific candle indices — more fighting than help with a general-purpose library's API.

The UI talks **directly to FastAPI on :8000** (free routes), not through the paywall. It has no wallet and doesn't handle a `402`, so pointing it at `:8402` would break the analysis page. The payment path is demonstrated by the agent.

---

## 7. Known limitations

- **The verdict is unvalidated.** No backtesting harness exists. Treat patterns as "what shapes are present", not "what happens next".
- **Long ranges on Messari sources are truncated.** No published OHLC means swap replay, which caps out. Reported honestly in `series.notes` rather than hidden.
- **Aggregate prices are quoted in the paired token**, not USD. For stablecoin pairs those coincide; the response states `quote_symbol` either way.
- **The V4 subgraph is community-run.** Uniswap's docs explicitly caveat it as "not official... may not be actively maintained".
- **No tests yet.** `backend/tests/` is empty.
- **Ethereum mainnet only**, though both schemas have deployments on other chains.
