"use client";

import { motion } from "motion/react";

import { Reveal, Stagger, staggerItem } from "@/components/motion/Reveal";

const SOURCES = [
  {
    name: "Uniswap V4",
    schema: "Uniswap native schema",
    note: "Flagship source. Publishes real OHLC per hour and per day, so a full year loads in about two seconds.",
    flagship: true,
    accent: "from-pink-500/20 to-transparent",
    dot: "bg-pink-400",
  },
  {
    name: "Uniswap V3",
    schema: "Messari dex-amm",
    note: "Standardized schema. Candles rebuilt from raw swap events.",
    flagship: false,
    accent: "from-sky-500/20 to-transparent",
    dot: "bg-sky-400",
  },
  {
    name: "SushiSwap",
    schema: "Messari dex-amm",
    note: "Same query string as Uniswap V3. Not one line of protocol specific code.",
    flagship: false,
    accent: "from-violet-500/20 to-transparent",
    dot: "bg-violet-400",
  },
];

export function Composability() {
  return (
    <section className="border-b border-zinc-900 py-24">
      <div className="mx-auto max-w-6xl px-6">
        <Reveal>
          <p className="text-xs uppercase tracking-[0.2em] text-zinc-500">Composability</p>
          <h2 className="mt-3 max-w-2xl text-3xl font-semibold tracking-tight text-zinc-50 sm:text-4xl">
            Three venues. One query.
          </h2>
          <p className="mt-4 max-w-2xl leading-relaxed text-zinc-400">
            Uniswap V3 and SushiSwap are separate protocols built by separate teams, yet
            Messari publishes both under one standardized schema. The same query string
            answers on either. Adding a fourth is a single line.
          </p>
        </Reveal>

        <Stagger className="mt-12 grid gap-4 md:grid-cols-3">
          {SOURCES.map((source) => (
            <motion.article
              key={source.name}
              variants={staggerItem}
              whileHover={{ y: -4 }}
              transition={{ type: "spring", stiffness: 300, damping: 24 }}
              className="group relative overflow-hidden rounded-xl border border-zinc-900 bg-zinc-950 p-5"
            >
              <div
                className={`absolute inset-x-0 top-0 h-24 bg-gradient-to-b ${source.accent} opacity-0 transition-opacity duration-500 group-hover:opacity-100`}
              />
              <div className="relative">
                <div className="flex items-center gap-2">
                  <span className={`h-1.5 w-1.5 rounded-full ${source.dot}`} />
                  <h3 className="text-sm font-medium text-zinc-100">{source.name}</h3>
                  {source.flagship && (
                    <span className="rounded bg-pink-500/15 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-pink-300">
                      Flagship
                    </span>
                  )}
                </div>
                <p className="mt-2 font-mono text-[11px] text-zinc-600">{source.schema}</p>
                <p className="mt-3 text-xs leading-relaxed text-zinc-400">{source.note}</p>
              </div>
            </motion.article>
          ))}
        </Stagger>

        <Reveal delay={0.15}>
          <div className="mt-6 overflow-hidden rounded-xl border border-zinc-900 bg-black/50">
            <div className="flex items-center gap-2 border-b border-zinc-900 px-4 py-2.5">
              <span className="h-2 w-2 rounded-full bg-zinc-700" />
              <span className="h-2 w-2 rounded-full bg-zinc-700" />
              <span className="h-2 w-2 rounded-full bg-zinc-700" />
              <span className="ml-2 font-mono text-[11px] text-zinc-600">
                standardized_query.py
              </span>
            </div>
            <pre className="overflow-x-auto px-4 py-4 font-mono text-[11px] leading-relaxed text-zinc-400">
{`query RecentSwaps($pool: String!, $first: Int!) {
  swaps(first: $first, orderBy: timestamp, orderDirection: desc,
        where: { pool: $pool }) {
    timestamp  amountIn  amountInUSD  amountOut  amountOutUSD
    tokenIn  { symbol decimals }
    tokenOut { symbol decimals }
  }
}`}
            </pre>
            <div className="border-t border-zinc-900 px-4 py-3 text-xs text-zinc-500">
              Sent unchanged to Uniswap V3 and to SushiSwap. Only the subgraph id differs.
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
