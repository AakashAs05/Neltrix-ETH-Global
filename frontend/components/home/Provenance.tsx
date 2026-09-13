"use client";

import Link from "next/link";
import { motion } from "motion/react";

import { Reveal, Stagger, staggerItem } from "@/components/motion/Reveal";

const GUARANTEES = [
  {
    title: "Every number is reproducible",
    body: "Candles are arithmetic over settled transactions. Anyone with the pool address can recompute them and get the same answer.",
  },
  {
    title: "Sources are never blended",
    body: "A chart shows one venue. Prices are not averaged across exchanges, so what you see is what that pool actually traded.",
  },
  {
    title: "Repairs are disclosed",
    body: "When a candle is dropped or a wick is clamped, the response says so and says why. Nothing is silently reshaped.",
  },
];

export function Provenance() {
  return (
    <section className="py-24">
      <div className="mx-auto max-w-6xl px-6">
        <Reveal>
          <p className="text-xs uppercase tracking-[0.2em] text-zinc-500">Provenance</p>
          <h2 className="mt-3 max-w-2xl text-3xl font-semibold tracking-tight text-zinc-50 sm:text-4xl">
            Every figure traces back to a transaction.
          </h2>
          <p className="mt-4 max-w-2xl leading-relaxed text-zinc-400">
            There is no vendor feed in this stack and no cached snapshot. Each response
            carries its own lineage, down to how many swaps were replayed to produce it.
          </p>
        </Reveal>

        <Stagger className="mt-12 grid gap-4 md:grid-cols-3">
          {GUARANTEES.map((g) => (
            <motion.div
              key={g.title}
              variants={staggerItem}
              className="rounded-xl border border-zinc-900 bg-zinc-950 p-5"
            >
              <h3 className="text-sm font-medium text-zinc-100">{g.title}</h3>
              <p className="mt-2 text-xs leading-relaxed text-zinc-400">{g.body}</p>
            </motion.div>
          ))}
        </Stagger>

        <Reveal delay={0.2}>
          <div className="relative mt-20 overflow-hidden rounded-2xl border border-zinc-900 bg-gradient-to-br from-zinc-950 via-zinc-950 to-black px-8 py-14 text-center">
            <motion.div
              aria-hidden
              className="pointer-events-none absolute inset-0"
              animate={{ backgroundPosition: ["0% 50%", "100% 50%", "0% 50%"] }}
              transition={{ duration: 18, repeat: Infinity, ease: "linear" }}
              style={{
                background:
                  "linear-gradient(90deg, transparent, rgba(236,72,153,0.07), rgba(56,189,248,0.07), transparent)",
                backgroundSize: "200% 100%",
              }}
            />
            <div className="relative">
              <h2 className="text-3xl font-semibold tracking-tight text-zinc-50">
                Pick a pool. See what the trades say.
              </h2>
              <p className="mx-auto mt-3 max-w-xl text-sm leading-relaxed text-zinc-400">
                Live Uniswap V4, Uniswap V3 and SushiSwap pools on Ethereum mainnet.
                Choose an interval and a window, and every candle is rebuilt in front of you.
              </p>
              <motion.div
                whileHover={{ scale: 1.03 }}
                whileTap={{ scale: 0.98 }}
                transition={{ type: "spring", stiffness: 400, damping: 22 }}
                className="mt-8 inline-block"
              >
                <Link
                  href="/workspace"
                  className="inline-flex items-center gap-2 rounded-lg bg-zinc-100 px-6 py-3 text-sm font-medium text-zinc-900 transition-colors hover:bg-white"
                >
                  Open the workspace
                  <span aria-hidden>&rarr;</span>
                </Link>
              </motion.div>
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
