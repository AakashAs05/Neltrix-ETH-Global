"use client";

import { motion, useInView } from "motion/react";
import { useEffect, useRef, useState } from "react";

import { Reveal } from "@/components/motion/Reveal";

const STEPS = [
  { label: "Agent calls the endpoint", detail: "No account. No API key. No prior relationship.", tone: "zinc" },
  { label: "402 Payment Required", detail: "The response carries the price, asset, recipient and network.", tone: "amber" },
  { label: "Agent signs a transfer", detail: "Exactly the quoted amount. The facilitator covers network fees.", tone: "sky" },
  { label: "Verified and settled", detail: "Confirmed on Hedera testnet in the same exchange.", tone: "green" },
  { label: "200 with the data", detail: "Plus a settlement receipt carrying the transaction id.", tone: "green" },
];

const TONE = {
  zinc: "border-zinc-700 text-zinc-300",
  amber: "border-amber-500/50 text-amber-300",
  sky: "border-sky-500/50 text-sky-300",
  green: "border-green-500/50 text-green-300",
} as const;

export function PaymentFlow() {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "-100px" });
  const [step, setStep] = useState(-1);

  useEffect(() => {
    if (!inView) return;
    const timers = STEPS.map((_, i) => setTimeout(() => setStep(i), 400 + i * 700));
    return () => timers.forEach(clearTimeout);
  }, [inView]);

  return (
    <section ref={ref} className="border-b border-zinc-900 py-24">
      <div className="mx-auto max-w-6xl px-6">
        <Reveal>
          <p className="text-xs uppercase tracking-[0.2em] text-zinc-500">Machine payable</p>
          <h2 className="mt-3 max-w-2xl text-3xl font-semibold tracking-tight text-zinc-50 sm:text-4xl">
            Software buys this. Not people.
          </h2>
          <p className="mt-4 max-w-2xl leading-relaxed text-zinc-400">
            Using a paid API normally requires a human to sign up, enter a card and paste a
            key into config. An autonomous agent can do none of that. With x402 the agent
            simply calls the endpoint, gets refused with the price attached, pays, and calls
            again. Two requests, no signup.
          </p>
        </Reveal>

        <div className="mt-12 grid gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,0.85fr)]">
          <div className="relative space-y-2.5">
            <div className="absolute bottom-4 left-[13px] top-4 w-px bg-zinc-900" />
            {STEPS.map((s, i) => {
              const reached = step >= i;
              return (
                <motion.div
                  key={s.label}
                  animate={{ opacity: reached ? 1 : 0.32 }}
                  transition={{ duration: 0.4 }}
                  className="relative flex gap-4 pl-0"
                >
                  <motion.div
                    animate={reached ? { scale: [0.8, 1.15, 1] } : { scale: 0.8 }}
                    transition={{ duration: 0.45 }}
                    className={`relative z-10 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border bg-zinc-950 font-mono text-[10px] ${
                      reached ? TONE[s.tone as keyof typeof TONE] : "border-zinc-800 text-zinc-600"
                    }`}
                  >
                    {i + 1}
                  </motion.div>
                  <div className="pb-3 pt-0.5">
                    <p className="text-sm font-medium text-zinc-200">{s.label}</p>
                    <p className="mt-0.5 text-xs leading-relaxed text-zinc-500">{s.detail}</p>
                  </div>
                </motion.div>
              );
            })}
          </div>

          <motion.div
            initial={{ opacity: 0, scale: 0.97 }}
            animate={inView ? { opacity: 1, scale: 1 } : {}}
            transition={{ duration: 0.6, delay: 0.2 }}
            className="overflow-hidden rounded-xl border border-zinc-900 bg-black/50"
          >
            <div className="border-b border-zinc-900 px-4 py-2.5 font-mono text-[11px] text-zinc-600">
              settlement receipt
            </div>
            <div className="space-y-2.5 px-4 py-4 font-mono text-[11px]">
              <Row k="success" v="true" tone="text-green-400" />
              <Row k="network" v="hedera:testnet" />
              <Row k="amount" v="0.1 HBAR" tone="text-zinc-200" />
              <Row k="payer" v="0.0.10490534" />
              <Row k="transaction" v="0.0.7162784@1789188608" />
              <div className="border-t border-zinc-900 pt-3 text-zinc-500">
                Verified on HashScan, independently of this application.
              </div>
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}

function Row({ k, v, tone = "text-zinc-400" }: { k: string; v: string; tone?: string }) {
  return (
    <div className="flex justify-between gap-4">
      <span className="text-zinc-600">{k}</span>
      <span className={tone}>{v}</span>
    </div>
  );
}
