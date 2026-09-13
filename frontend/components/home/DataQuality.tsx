"use client";

import { motion } from "motion/react";

import { Reveal, Stagger, staggerItem } from "@/components/motion/Reveal";

const FINDINGS = [
  {
    problem: "Pool creation artifacts",
    found: "Rows inverting to $3 x 10^20",
    fix: "Dropped as structurally invalid",
  },
  {
    problem: "Single bad prints",
    found: "One hour claiming ETH traded between $4 and $2,446",
    fix: "Wick clamped to local price, body preserved",
  },
  {
    problem: "Negative liquidity",
    found: "Top V4 USDC/USDT pool reporting minus $24.7M",
    fix: "Pools ranked by volume, never by TVL",
  },
  {
    problem: "Wash traded pairs",
    found: "ETH against a clone token claiming $2.3T locked",
    fix: "Major token allowlist for rankings",
  },
];

export function DataQuality() {
  return (
    <section className="border-b border-zinc-900 py-24">
      <div className="mx-auto max-w-6xl px-6">
        <Reveal>
          <p className="text-xs uppercase tracking-[0.2em] text-zinc-500">Data quality</p>
          <h2 className="mt-3 max-w-2xl text-3xl font-semibold tracking-tight text-zinc-50 sm:text-4xl">
            Onchain data is public. It is not clean.
          </h2>
          <p className="mt-4 max-w-2xl leading-relaxed text-zinc-400">
            Treating indexed data as trustworthy produces confident nonsense. Every repair
            below was found on live mainnet pools, and every one is reported in the API
            response rather than applied quietly.
          </p>
        </Reveal>

        <Stagger className="mt-12 grid gap-3 sm:grid-cols-2">
          {FINDINGS.map((f) => (
            <motion.div
              key={f.problem}
              variants={staggerItem}
              whileHover={{ borderColor: "rgb(63 63 70)" }}
              className="rounded-xl border border-zinc-900 bg-zinc-950 p-5"
            >
              <h3 className="text-sm font-medium text-zinc-200">{f.problem}</h3>
              <p className="mt-2 font-mono text-[11px] leading-relaxed text-amber-400/80">
                {f.found}
              </p>
              <p className="mt-2 text-xs leading-relaxed text-zinc-500">{f.fix}</p>
            </motion.div>
          ))}
        </Stagger>

        <Reveal delay={0.1}>
          <div className="mt-6 rounded-xl border border-zinc-900 bg-gradient-to-br from-zinc-950 to-black p-6">
            <h3 className="text-sm font-medium text-zinc-200">
              The repairs are themselves a signal
            </h3>
            <p className="mt-2 max-w-3xl text-sm leading-relaxed text-zinc-400">
              On the same pair over the same week, the ETH/USDC 0.05% pool needed no repairs
              while the 0.01% tier needed seven wick clamps. That is evidence the thinner
              tier gets sandwiched. A chart showing an averaged market price cannot tell you
              this, because it never shows you a venue.
            </p>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
