"use client";

import { motion, useInView } from "motion/react";
import { useEffect, useRef, useState } from "react";

import { Reveal } from "@/components/motion/Reveal";

/** Steps through the derivation with a real trade, because abstract arrows
 *  do not convey that price is computed rather than reported. */

const STAGES = [
  {
    tag: "01",
    title: "A pool records trades, not prices",
    body: "Uniswap stores what went in and what came out. Nowhere does it write down a price.",
    accent: "text-sky-300",
    ring: "border-sky-500/25 bg-sky-500/[0.04]",
  },
  {
    tag: "02",
    title: "Price is arithmetic",
    body: "Divide one side by the other and the execution price falls out. Every trade gives one sample.",
    accent: "text-pink-300",
    ring: "border-pink-500/25 bg-pink-500/[0.04]",
  },
  {
    tag: "03",
    title: "Thousands of samples become one candle",
    body: "Bucket every trade in an hour and reduce it to five numbers: open, high, low, close, volume.",
    accent: "text-amber-300",
    ring: "border-amber-500/25 bg-amber-500/[0.04]",
  },
  {
    tag: "04",
    title: "Structure emerges from the series",
    body: "Repeated turning points become levels. Recognisable shapes become patterns.",
    accent: "text-green-300",
    ring: "border-green-500/25 bg-green-500/[0.04]",
  },
];

export function PipelineFlow() {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "-120px" });
  const [active, setActive] = useState(0);

  useEffect(() => {
    if (!inView) return;
    const id = setInterval(() => setActive((n) => (n + 1) % STAGES.length), 2600);
    return () => clearInterval(id);
  }, [inView]);

  return (
    <section id="pipeline" ref={ref} className="border-b border-zinc-900 py-24">
      <div className="mx-auto max-w-6xl px-6">
        <Reveal>
          <p className="text-xs uppercase tracking-[0.2em] text-zinc-500">How it works</p>
          <h2 className="mt-3 max-w-2xl text-3xl font-semibold tracking-tight text-zinc-50 sm:text-4xl">
            Nobody publishes a price. We compute one.
          </h2>
          <p className="mt-4 max-w-2xl leading-relaxed text-zinc-400">
            Every number in this product traces back to a settled transaction on Ethereum.
            Here is the whole derivation, using one real trade.
          </p>
        </Reveal>

        <div className="mt-14 grid gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
          <div className="space-y-3">
            {STAGES.map((stage, i) => {
              const isActive = i === active;
              return (
                <button
                  key={stage.tag}
                  type="button"
                  onClick={() => setActive(i)}
                  className={`relative block w-full overflow-hidden rounded-xl border px-5 py-4 text-left transition-colors ${
                    isActive ? stage.ring : "border-zinc-900 bg-zinc-950 hover:border-zinc-800"
                  }`}
                >
                  {isActive && (
                    <motion.span
                      layoutId="stage-marker"
                      className="absolute left-0 top-0 h-full w-0.5 bg-current"
                      style={{ color: "currentColor" }}
                      transition={{ type: "spring", stiffness: 400, damping: 32 }}
                    />
                  )}
                  <div className="flex items-baseline gap-3">
                    <span className={`font-mono text-xs ${isActive ? stage.accent : "text-zinc-600"}`}>
                      {stage.tag}
                    </span>
                    <span
                      className={`text-sm font-medium ${isActive ? "text-zinc-100" : "text-zinc-400"}`}
                    >
                      {stage.title}
                    </span>
                  </div>
                  <motion.p
                    initial={false}
                    animate={{ opacity: isActive ? 1 : 0, height: isActive ? "auto" : 0 }}
                    transition={{ duration: 0.32 }}
                    className="overflow-hidden pl-9 text-xs leading-relaxed text-zinc-400"
                  >
                    <span className="block pt-2">{stage.body}</span>
                  </motion.p>
                </button>
              );
            })}
          </div>

          <div className="relative min-h-[22rem] rounded-xl border border-zinc-900 bg-zinc-950 p-6">
            <StageVisual stage={active} />
          </div>
        </div>
      </div>
    </section>
  );
}

function StageVisual({ stage }: { stage: number }) {
  return (
    <motion.div key={stage} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
      {stage === 0 && <RawSwap />}
      {stage === 1 && <PriceMath />}
      {stage === 2 && <CandleForm />}
      {stage === 3 && <StructureView />}
    </motion.div>
  );
}

function RawSwap() {
  const rows = [
    { time: "05:11:23", who: "0x82c74a84", eth: "+3.909798", usdc: "-9,817.00" },
    { time: "05:09:35", who: "0x6a126f2e", eth: "+0.004074", usdc: "-10.23" },
    { time: "05:09:23", who: "0x44acbed5", eth: "+0.013736", usdc: "-34.50" },
  ];
  return (
    <div>
      <Label>Swap events, exactly as indexed</Label>
      <div className="mt-4 space-y-2 font-mono text-xs">
        {rows.map((r, i) => (
          <motion.div
            key={r.time}
            initial={{ opacity: 0, x: -12 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.1 + i * 0.12 }}
            className="flex flex-wrap items-center gap-x-4 gap-y-1 rounded-lg border border-zinc-900 bg-black/40 px-3 py-2.5"
          >
            <span className="text-zinc-600">{r.time}</span>
            <span className="text-zinc-500">{r.who}</span>
            <span className="text-green-400">ETH {r.eth}</span>
            <span className="text-red-400">USDC {r.usdc}</span>
          </motion.div>
        ))}
      </div>
      <p className="mt-5 text-xs leading-relaxed text-zinc-500">
        Two amounts and a timestamp. That is the entire record. Price is absent by design,
        because an automated market maker settles quantities, not quotes.
      </p>
    </div>
  );
}

function PriceMath() {
  return (
    <div>
      <Label>Derivation, one trade</Label>
      <div className="mt-5 rounded-lg border border-zinc-900 bg-black/40 p-5 font-mono text-sm">
        <div className="text-zinc-500">value received</div>
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.15 }}
          className="mt-1 text-zinc-200"
        >
          $9,821.83
        </motion.div>
        <div className="my-3 h-px bg-zinc-800" />
        <div className="text-zinc-500">ETH given up</div>
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.3 }}
          className="mt-1 text-zinc-200"
        >
          3.909798 ETH
        </motion.div>
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5 }}
          className="mt-5 flex items-baseline gap-3 border-t border-zinc-800 pt-4"
        >
          <span className="text-xs text-zinc-500">execution price</span>
          <span className="text-2xl text-pink-300">$2,512.11</span>
        </motion.div>
      </div>
      <p className="mt-5 text-xs leading-relaxed text-zinc-500">
        Repeat for all 1.45 million trades in this pool and you have a complete price history
        that nobody had to publish.
      </p>
    </div>
  );
}

function CandleForm() {
  const bars = [42, 58, 35, 71, 49, 63, 80, 55, 68, 44, 76, 52];
  return (
    <div>
      <Label>Compression into a candle</Label>
      <div className="mt-5 flex h-32 items-end gap-1.5">
        {bars.map((h, i) => (
          <motion.div
            key={i}
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: `${h}%`, opacity: 1 }}
            transition={{ delay: i * 0.04, duration: 0.4, ease: "easeOut" }}
            className="flex-1 rounded-sm bg-gradient-to-t from-zinc-800 to-zinc-600"
          />
        ))}
        <motion.div
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.7, type: "spring", stiffness: 260, damping: 20 }}
          className="ml-3 flex h-full w-10 items-center justify-center"
        >
          <div className="relative h-full w-2.5">
            <div className="absolute left-1/2 top-0 h-full w-px -translate-x-1/2 bg-green-400" />
            <div className="absolute left-0 top-[22%] h-[52%] w-full rounded-sm bg-green-400" />
          </div>
        </motion.div>
      </div>
      <motion.dl
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.85 }}
        className="mt-5 grid grid-cols-2 gap-x-6 gap-y-2 font-mono text-xs sm:grid-cols-3"
      >
        {[
          ["open", "$2,508.44"],
          ["high", "$2,516.90"],
          ["low", "$2,505.12"],
          ["close", "$2,512.11"],
          ["volume", "$1.4M"],
          ["trades", "321"],
        ].map(([k, v]) => (
          <div key={k}>
            <dt className="text-zinc-600">{k}</dt>
            <dd className="text-zinc-300">{v}</dd>
          </div>
        ))}
      </motion.dl>
      <p className="mt-5 text-xs leading-relaxed text-zinc-500">
        One hour of trading, roughly 321 separate swaps, reduced to six figures without
        discarding what matters.
      </p>
    </div>
  );
}

function StructureView() {
  return (
    <div>
      <Label>What the series reveals</Label>
      <svg viewBox="0 0 320 120" className="mt-5 h-36 w-full">
        <motion.line
          x1="0" y1="44" x2="320" y2="44"
          stroke="#ef4444" strokeWidth="1" strokeDasharray="5 4"
          initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 0.9 }}
        />
        <motion.line
          x1="0" y1="92" x2="320" y2="92"
          stroke="#22c55e" strokeWidth="1" strokeDasharray="5 4"
          initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 0.9, delay: 0.2 }}
        />
        <motion.path
          d="M4 78 L28 60 L52 88 L76 46 L100 70 L124 48 L148 84 L172 58 L196 46 L220 76 L244 52 L268 86 L292 62 L316 50"
          fill="none" stroke="#e4e4e7" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"
          initial={{ pathLength: 0 }} animate={{ pathLength: 1 }}
          transition={{ duration: 1.6, ease: "easeInOut" }}
        />
        {[
          { cx: 76, cy: 46 }, { cx: 196, cy: 46 },
        ].map((p, i) => (
          <motion.circle
            key={i} cx={p.cx} cy={p.cy} r="3.5" fill="#ef4444"
            initial={{ scale: 0, opacity: 0 }} animate={{ scale: 1, opacity: 1 }}
            transition={{ delay: 1.3 + i * 0.15, type: "spring", stiffness: 300 }}
          />
        ))}
      </svg>
      <div className="mt-4 space-y-2 text-xs">
        <Fact colour="bg-red-400">Resistance at $2,502, touched 12 times this week</Fact>
        <Fact colour="bg-green-400">Support at $2,464, touched 7 times</Fact>
        <Fact colour="bg-zinc-500">Double top detected across the two marked peaks</Fact>
      </div>
      <p className="mt-4 text-xs leading-relaxed text-zinc-500">
        Levels are counts of where price actually reversed, not forecasts. That distinction
        is kept throughout the product.
      </p>
    </div>
  );
}

function Fact({ colour, children }: { colour: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-2.5 text-zinc-400">
      <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${colour}`} />
      {children}
    </div>
  );
}

function Label({ children }: { children: React.ReactNode }) {
  return <p className="text-[11px] uppercase tracking-[0.16em] text-zinc-600">{children}</p>;
}
