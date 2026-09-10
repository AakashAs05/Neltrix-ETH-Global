"use client";

import { useMemo, useState } from "react";

import { formatTimestamp } from "@/lib/api";
import type { Pattern, PatternCategory } from "@/lib/types";

const DIRECTION_BADGE: Record<Pattern["direction"], string> = {
  bullish: "bg-green-500/10 text-green-400 border-green-500/30",
  bearish: "bg-red-500/10 text-red-400 border-red-500/30",
  neutral: "bg-zinc-500/10 text-zinc-400 border-zinc-500/30",
};

/** Mirrors CATEGORY_WEIGHT in backend/app/engine/signals.py — harmonic
 *  patterns are rarer and more specific, so they count for more. */
const CATEGORY_LABEL: Record<PatternCategory, string> = {
  harmonic: "Harmonic",
  classic: "Chart",
  candlestick: "Candlestick",
};

const CATEGORY_ORDER: PatternCategory[] = ["harmonic", "classic", "candlestick"];

type Filter = "all" | PatternCategory;

interface PatternPanelProps {
  patterns: Pattern[];
  totalDetected?: number;
}

export default function PatternPanel({ patterns, totalDetected }: PatternPanelProps) {
  const [filter, setFilter] = useState<Filter>("all");

  const counts = useMemo(() => {
    const byCategory = { harmonic: 0, classic: 0, candlestick: 0 } as Record<PatternCategory, number>;
    for (const pattern of patterns) byCategory[pattern.category] += 1;
    return byCategory;
  }, [patterns]);

  const visible = useMemo(() => {
    const filtered = filter === "all" ? patterns : patterns.filter((p) => p.category === filter);
    // Most-significant first: harmonic > chart > candlestick, then by confidence.
    return [...filtered].sort((a, b) => {
      const byCategory =
        CATEGORY_ORDER.indexOf(a.category) - CATEGORY_ORDER.indexOf(b.category);
      if (byCategory !== 0) return byCategory;
      return b.confidence - a.confidence;
    });
  }, [patterns, filter]);

  return (
    <section className="rounded-lg border border-zinc-800 bg-zinc-950">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-800 px-4 py-3">
        <h2 className="text-sm font-medium text-zinc-200">
          Significant patterns{" "}
          <span className="font-mono text-zinc-500">({patterns.length})</span>
          {typeof totalDetected === "number" && totalDetected > patterns.length && (
            <span
              className="ml-2 font-normal text-xs text-zinc-500"
              title="Raw geometric matches are filtered by confidence, by whether the shape sits at a contested price level, and by suppressing overlapping duplicates."
            >
              filtered from {totalDetected} raw matches
            </span>
          )}
        </h2>
        <div className="flex flex-wrap gap-1">
          {(["all", ...CATEGORY_ORDER] as Filter[]).map((option) => {
            const label =
              option === "all" ? "All" : `${CATEGORY_LABEL[option]} (${counts[option]})`;
            const active = filter === option;
            return (
              <button
                key={option}
                type="button"
                onClick={() => setFilter(option)}
                className={`rounded px-2 py-1 text-xs transition-colors ${
                  active
                    ? "bg-zinc-100 text-zinc-900"
                    : "bg-zinc-900 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200"
                }`}
              >
                {label}
              </button>
            );
          })}
        </div>
      </header>

      {visible.length === 0 ? (
        <p className="px-4 py-6 text-sm text-zinc-500">
          No patterns in this category for the current window.
        </p>
      ) : (
        <ul className="max-h-[520px] divide-y divide-zinc-900 overflow-y-auto">
          {visible.map((pattern, i) => (
            <li key={`${pattern.name}-${pattern.start_timestamp}-${i}`} className="px-4 py-3">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-medium text-zinc-100">{pattern.name}</span>
                    <span
                      className={`rounded border px-1.5 py-0.5 text-[10px] uppercase tracking-wide ${
                        DIRECTION_BADGE[pattern.direction]
                      }`}
                    >
                      {pattern.direction}
                    </span>
                    <span className="rounded border border-zinc-700 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-zinc-500">
                      {CATEGORY_LABEL[pattern.category]}
                    </span>
                  </div>
                  <p className="mt-1 text-xs leading-relaxed text-zinc-400">
                    {pattern.description}
                  </p>
                  <p className="mt-1 font-mono text-[11px] text-zinc-600">
                    {formatTimestamp(pattern.start_timestamp)}
                    {pattern.end_timestamp !== pattern.start_timestamp &&
                      ` → ${formatTimestamp(pattern.end_timestamp)}`}
                  </p>
                </div>
                <div className="shrink-0 text-right">
                  <p className="font-mono text-sm text-zinc-300">
                    {Math.round(pattern.confidence * 100)}%
                  </p>
                  <div className="mt-1 h-1 w-14 overflow-hidden rounded-full bg-zinc-800">
                    <div
                      className={`h-full rounded-full ${
                        pattern.direction === "bullish"
                          ? "bg-green-500"
                          : pattern.direction === "bearish"
                            ? "bg-red-500"
                            : "bg-zinc-500"
                      }`}
                      style={{ width: `${Math.max(pattern.confidence * 100, 3)}%` }}
                    />
                  </div>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
