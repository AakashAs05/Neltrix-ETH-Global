# Uniswap Developer Feedback

> **Status: draft, not yet submitted.** This is the content prepared for the Uniswap
> Developer Feedback Form. It still needs to be submitted through the form itself —
> once that's done, replace this line with a link to / confirmation of the submission.

**Project:** Neltrix Onchain — pattern detection over DEX swap data
**Integration:** Uniswap V4 as the flagship pool source, plus Uniswap V3 for comparison
**Date:** 2026-09-10

---

## What we built on Uniswap

Neltrix derives OHLCV candles directly from individual Uniswap swap events and runs
candlestick / chart / harmonic pattern detection over them. There's no centralised price
feed anywhere in the stack — every candle traces back to `Swap` entities on a Uniswap
pool. Uniswap V4 is the default and flagship source in the UI; Uniswap V3 and SushiSwap
are available for cross-protocol comparison.

## What went well

- **V4's swap data is genuinely sufficient to rebuild price history.** `amount0`,
  `amount1`, and `amountUSD` on each `Swap`, plus token decimals, was everything we
  needed to derive a per-swap price and bucket it into candles. We didn't need
  `sqrtPriceX96` decoding or any tick math for the core use case.
- **Pool coverage is good.** The major pairs we cared about (ETH/USDC, ETH/USDT,
  ETH/WBTC, WBTC/USDC) all had deep, actively-traded V4 pools — the ETH/USDC 0.05% pool
  alone had over 1.4M swaps indexed.
- **`amountUSD` being pre-computed saved real work.** Not having to resolve token prices
  ourselves to get a USD-denominated volume figure removed an entire class of problem.

## Friction we hit

**1. No standardized-schema deployment for V4, which breaks cross-protocol composability.**

Our project's core premise is running one unmodified query across multiple DEXs, which
works for Uniswap V3 and SushiSwap because Messari publishes both as `dex-amm`
Standardized Subgraphs. V4 has no such deployment, so it needed a bespoke adapter
(`backend/app/uniswap/v4_pool_client.py`) translating V4's native `{amount0, amount1,
amountUSD}` shape into the `{tokenIn, tokenOut, amountIn, amountOut}` shape the rest of
our engine already spoke. That's ~200 lines that exist purely because V4 sits outside the
standardized schema. An official or Messari-published `dex-amm` V4 deployment would let
integrators treat V4 as a drop-in alongside every other AMM.

**2. The documented mainnet subgraph is explicitly disclaimed.**

The V4 endpoints published in Uniswap's own developer docs carry the note that they
"are not official deployments and may not be actively maintained by Uniswap Labs."
For a hackathon that's workable, but it's an uncomfortable foundation for anything
production-facing, and it's the *only* discovery path a new integrator has. A clearly
blessed, Uniswap-maintained mainnet deployment — even one labelled best-effort — would
remove the guesswork about which of the several V4 subgraphs on the network to trust.

**3. Pool-level `totalValueLockedUSD` is unreliable, sometimes negative.**

Several high-volume V4 pools report nonsensical TVL. Concrete examples from the mainnet
deployment on 2026-09-10:

| Pool | Pair | Reported TVL |
| --- | --- | --- |
| `0x8aa4e11c…8e4e47` | USDC/USDT | **-$24,748,309** |
| `0x0fb0e40c…423239` | USDC/USDT | **-$3,101,419,726,418,866** |
| `0x98914a9e…5898eb` | ETH/1xETH | $2,319,558,110,317 |

Negative TVL isn't a ranking nuisance, it's an invalid value — we had to abandon TVL as
a sort key entirely and rank pools by `volumeUSD` instead, then filter to an allowlist of
major token symbols to keep wash-traded pairs out of the pool picker. Since V4 makes pool
creation permissionless *and* hook-extensible, the junk-to-signal ratio in an unfiltered
pool list is meaningfully worse than V3's, so integrators building any kind of pool
browser will all hit this. Surfacing a "verified"/curated flag, or fixing the TVL
accounting drift, would help.

**4. `feeTier` overloads the dynamic-fee flag with rate values.**

V4 signals a dynamic-fee pool by setting `0x800000` (8388608) in the fee field rather
than storing a rate. Formatted naively as a rate, that renders as "838.86%". It's
correct once you know, but it's not obvious from the schema alone that `feeTier` isn't
always a fee tier, and a separate boolean (or a documented note on the field) would stop
integrators shipping that bug.

**5. Pool identity changes shape between V3 and V4.**

V3 pool ids are 42-char contract addresses; V4 pool ids are 66-char bytes32 hashes, and
V4 pools have no `name` field to fall back on. Both are reasonable given the singleton
architecture, but code that assumed "pool id = address" needed widening, and pool display
names had to be composed by hand from `token0`/`token1`/`feeTier`. Worth calling out
prominently in V3→V4 migration docs.

## Summary

The data is there and the integration works — the friction was almost entirely about
*discovery and trust* (which deployment is real?) and *data hygiene* (negative TVL, junk
pools) rather than anything missing from the protocol itself. The single highest-impact
change for integrators like us would be a standardized-schema V4 deployment, so V4 stops
being the one protocol that needs custom code.
