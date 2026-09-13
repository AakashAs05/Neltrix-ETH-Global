"use client";

import Link from "next/link";
import { motion } from "motion/react";

import { Aurora } from "@/components/motion/Aurora";
import { Counter } from "@/components/motion/Counter";

const HEADLINE = ["Onchain trades,", "turned into", "market intelligence."];

const STATS = [
  { value: 1451228, label: "swaps indexed in one pool", prefix: "" },
  { value: 12, label: "billion in pool volume", prefix: "$", suffix: "B" },
  { value: 3, label: "DEXs, one query shape" },
];

export function Hero() {
  return (
    <section className="relative overflow-hidden border-b border-zinc-900">
      <Aurora />

      <div className="relative mx-auto flex max-w-4xl flex-col items-center px-6 pb-24 pt-36 text-center sm:pt-44">
        <h1 className="max-w-3xl text-5xl font-semibold leading-[1.05] tracking-tight text-zinc-50 sm:text-7xl">
          {HEADLINE.map((line, i) => (
            <motion.span
              key={line}
              className="block"
              initial={{ opacity: 0, y: 26, filter: "blur(8px)" }}
              animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
              transition={{ duration: 0.75, delay: 0.12 + i * 0.12, ease: [0.21, 0.47, 0.32, 0.98] }}
            >
              {i === 2 ? (
                <span className="bg-gradient-to-r from-zinc-50 via-pink-200 to-sky-200 bg-clip-text text-transparent">
                  {line}
                </span>
              ) : (
                line
              )}
            </motion.span>
          ))}
        </h1>

        <motion.p
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.5 }}
          className="mt-7 max-w-2xl text-lg leading-relaxed text-zinc-400"
        >
          Neltrix rebuilds price history from individual swap events on Uniswap and SushiSwap,
          detects chart structure in it, and sells each analysis to software for a fraction of
          a cent. No price feed, no API key, no account.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.62 }}
          className="mt-10 flex flex-wrap items-center justify-center gap-3"
        >
          <MagneticLink href="/workspace">Open the workspace</MagneticLink>
          <a
            href="#pipeline"
            className="rounded-lg border border-zinc-800 px-5 py-3 text-sm text-zinc-300 transition-colors hover:border-zinc-700 hover:bg-zinc-900 hover:text-zinc-100"
          >
            See how it works
          </a>
        </motion.div>

        <motion.dl
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.8, delay: 0.8 }}
          className="mt-16 grid w-full max-w-3xl grid-cols-1 gap-px overflow-hidden rounded-xl border border-zinc-900 bg-zinc-900 sm:grid-cols-3"
        >
          {STATS.map((stat) => (
            <div key={stat.label} className="bg-zinc-950 px-5 py-5 text-center">
              <dt className="font-mono text-2xl text-zinc-100">
                <Counter to={stat.value} prefix={stat.prefix} suffix={stat.suffix} />
              </dt>
              <dd className="mt-1 text-xs leading-relaxed text-zinc-500">{stat.label}</dd>
            </div>
          ))}
        </motion.dl>
      </div>
    </section>
  );
}

/** Button that leans toward the cursor. Subtle, capped at a few pixels. */
function MagneticLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <motion.div
      whileHover={{ scale: 1.03 }}
      whileTap={{ scale: 0.98 }}
      transition={{ type: "spring", stiffness: 400, damping: 22 }}
    >
      <Link
        href={href}
        className="group inline-flex items-center gap-2 rounded-lg bg-zinc-100 px-5 py-3 text-sm font-medium text-zinc-900 transition-colors hover:bg-white"
      >
        {children}
        <motion.span
          aria-hidden
          className="inline-block"
          initial={{ x: 0 }}
          whileHover={{ x: 3 }}
        >
          &rarr;
        </motion.span>
      </Link>
    </motion.div>
  );
}
