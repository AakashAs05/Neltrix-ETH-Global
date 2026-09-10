"use client";

import type { Verdict } from "@/lib/types";

const DIRECTION_STYLES: Record<Verdict["direction"], { label: string; ring: string; text: string; bar: string }> = {
  bullish: {
    label: "Bullish",
    ring: "border-green-500/40 bg-green-500/5",
    text: "text-green-400",
    bar: "bg-green-500",
  },
  bearish: {
    label: "Bearish",
    ring: "border-red-500/40 bg-red-500/5",
    text: "text-red-400",
    bar: "bg-red-500",
  },
  neutral: {
    label: "Neutral",
    ring: "border-zinc-700 bg-zinc-900/60",
    text: "text-zinc-300",
    bar: "bg-zinc-500",
  },
};

interface VerdictCardProps {
  verdict: Verdict;
  explanation: string;
  baseSymbol: string;
  interval: string;
}

export default function VerdictCard({
  verdict,
  explanation,
  baseSymbol,
  interval,
}: VerdictCardProps) {
  const style = DIRECTION_STYLES[verdict.direction];
  const confidencePct = Math.round(verdict.confidence * 100);

  return (
    <section className={`rounded-lg border p-5 ${style.ring}`}>
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-wider text-zinc-500">
            Verdict · {baseSymbol} · {interval}
          </p>
          <p className={`mt-1 text-3xl font-semibold ${style.text}`}>{style.label}</p>
        </div>
        <div className="text-right">
          <p className="text-xs uppercase tracking-wider text-zinc-500">Confidence</p>
          <p className="mt-1 font-mono text-2xl text-zinc-100">{confidencePct}%</p>
        </div>
      </div>

      <div className="mt-4">
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-zinc-800">
          <div
            className={`h-full rounded-full ${style.bar}`}
            style={{ width: `${Math.max(confidencePct, 2)}%` }}
          />
        </div>
        <div className="mt-2 flex justify-between font-mono text-xs text-zinc-500">
          <span>
            score {verdict.score >= 0 ? "+" : ""}
            {verdict.score.toFixed(3)}
          </span>
          <span>{verdict.pattern_count} patterns detected</span>
        </div>
      </div>

      <p className="mt-4 text-sm leading-relaxed text-zinc-300">{explanation}</p>

      <p className="mt-3 border-t border-zinc-800 pt-3 text-xs leading-relaxed text-zinc-500">
        Derived from onchain swap events only. Not financial advice — the verdict is a
        weighted roll-up of detected patterns, not a prediction.
      </p>
    </section>
  );
}
