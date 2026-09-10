"use client";

/**
 * Runs /api/analyse for the pool named in the query string and renders the
 * chart, the detected patterns, and the verdict.
 *
 * useSearchParams() forces client-side rendering, so the page body sits
 * inside a <Suspense> boundary as Next requires.
 */

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import PatternPanel from "@/components/analysis/PatternPanel";
import VerdictCard from "@/components/analysis/VerdictCard";
import PoolChart from "@/components/charts/PoolChart";
import { analyse, ApiError, formatPrice, shortenId } from "@/lib/api";
import { RANGE_LABELS, type AnalyseResponse, type Range } from "@/lib/types";

export default function AnalysisPage() {
  return (
    <Suspense fallback={<Centered>Loading…</Centered>}>
      <AnalysisView />
    </Suspense>
  );
}

function AnalysisView() {
  const params = useSearchParams();
  const protocol = params.get("protocol") ?? "";
  const pool = params.get("pool") ?? "";
  const interval = params.get("interval") ?? "1h";
  const range = params.get("range") ?? "1w";

  const [result, setResult] = useState<AnalyseResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!protocol || !pool) {
      setError("Missing protocol or pool in the URL.");
      setLoading(false);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);
    setResult(null);

    analyse({ protocol, pool, interval, range })
      .then((data) => {
        if (!cancelled) setResult(data);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(
          err instanceof ApiError
            ? err.message
            : err instanceof Error
              ? err.message
              : "Unexpected error.",
        );
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [protocol, pool, interval, range]);

  const latest = result?.candles.at(-1);
  const first = result?.candles.at(0);
  const changePct =
    latest && first && first.open !== 0
      ? ((latest.close - first.open) / first.open) * 100
      : null;

  return (
    <main className="mx-auto w-full max-w-6xl px-6 py-10">
      <Link href="/workspace" className="text-sm text-zinc-500 transition-colors hover:text-zinc-300">
        ← Back to pools
      </Link>

      <header className="mt-4 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-zinc-100">
            {result
              ? `${result.base_symbol} · ${result.interval} · ${RANGE_LABELS[result.range as Range] ?? result.range}`
              : "Analysing…"}
          </h1>
          <p className="mt-1 font-mono text-xs text-zinc-500">
            {protocol} · {shortenId(pool)}
          </p>
        </div>
        {latest && (
          <div className="text-right">
            <p className="font-mono text-2xl text-zinc-100">{formatPrice(latest.close)}</p>
            {changePct !== null && (
              <p
                className={`font-mono text-xs ${
                  changePct >= 0 ? "text-green-400" : "text-red-400"
                }`}
              >
                {changePct >= 0 ? "+" : ""}
                {changePct.toFixed(2)}% over window
              </p>
            )}
          </div>
        )}
      </header>

      {loading && (
        <Centered>
          Fetching swaps from The Graph and running detection… this can take a few seconds.
        </Centered>
      )}

      {error && (
        <div className="mt-6 rounded-lg border border-red-500/40 bg-red-500/5 px-4 py-4 text-sm text-red-300">
          <p className="font-medium">Analysis failed</p>
          <p className="mt-1 text-red-200/80">{error}</p>
          <p className="mt-2 text-xs text-red-200/60">
            The Graph&apos;s gateway load-balances across indexers, and an unhealthy one can fail a
            query that succeeds on retry. Reloading is often enough.
          </p>
        </div>
      )}

      {result && (
        <div className="mt-6 space-y-6">
          <ProvenanceBar result={result} />
          <PoolChart
            candles={result.candles}
            supportResistance={result.support_resistance}
            patterns={result.patterns}
            baseSymbol={result.base_symbol}
          />

          <div className="grid gap-6 lg:grid-cols-[1fr_1.15fr]">
            <div className="space-y-6">
              <VerdictCard
                verdict={result.verdict}
                explanation={result.explanation}
                baseSymbol={result.base_symbol}
                interval={result.interval}
              />
              <LevelsCard result={result} />
            </div>
            <PatternPanel patterns={result.patterns} totalDetected={result.total_detected} />
          </div>
        </div>
      )}
    </main>
  );
}

/**
 * Says where these candles came from. Two pools charted side by side can
 * be built completely differently — one from the subgraph's published
 * OHLC, one replayed swap by swap — and that difference is worth showing
 * rather than implying every chart is equivalent.
 */
function ProvenanceBar({ result }: { result: AnalyseResponse }) {
  const { series, candles } = result;
  const fromAggregate = series.source === "subgraph-aggregate";

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-lg border border-zinc-800 bg-zinc-950 px-4 py-2.5 text-xs text-zinc-500">
        <span className="flex items-center gap-1.5">
          <span
            className={`inline-block h-1.5 w-1.5 rounded-full ${
              fromAggregate ? "bg-sky-400" : "bg-amber-400"
            }`}
          />
          <span className="text-zinc-300">
            {fromAggregate ? "Subgraph-published OHLC" : "Derived from raw swaps"}
          </span>
        </span>
        <span>
          {candles.length} candles · priced in{" "}
          <span className="font-mono text-zinc-400">{series.quote_symbol}</span>
        </span>
        {series.swaps_scanned > 0 && (
          <span>{series.swaps_scanned.toLocaleString()} swaps replayed</span>
        )}
        {series.rows_dropped > 0 && (
          <span className="text-amber-500/80">{series.rows_dropped} unusable dropped</span>
        )}
      </div>

      {series.notes.map((note) => (
        <p
          key={note}
          className={`rounded-lg border px-4 py-3 text-xs leading-relaxed ${
            series.truncated
              ? "border-amber-500/30 bg-amber-500/5 text-amber-200/80"
              : "border-zinc-800 bg-zinc-950 text-zinc-500"
          }`}
        >
          {note}
        </p>
      ))}
    </div>
  );
}

function LevelsCard({ result }: { result: AnalyseResponse }) {
  const supports = result.support_resistance.filter((l) => l.kind === "support").slice(0, 4);
  const resistances = result.support_resistance.filter((l) => l.kind === "resistance").slice(0, 4);

  return (
    <section className="rounded-lg border border-zinc-800 bg-zinc-950 p-4">
      <h2 className="text-sm font-medium text-zinc-200">Support &amp; resistance</h2>
      <p className="mt-1 text-xs text-zinc-500">
        Swing highs and lows clustered within 1.5% of each other, from{" "}
        {result.candles.length} candles. Only the strongest of each is drawn on the chart;
        the rest are listed here.
      </p>
      <div className="mt-3 grid grid-cols-2 gap-4">
        {[
          ["Resistance", resistances, "text-red-400"],
          ["Support", supports, "text-green-400"],
        ].map(([label, levels, color]) => (
          <div key={label as string}>
            <p className="text-[10px] uppercase tracking-wide text-zinc-600">{label as string}</p>
            <ul className="mt-1 space-y-1">
              {(levels as typeof supports).length === 0 && (
                <li className="text-xs text-zinc-600">None found</li>
              )}
              {(levels as typeof supports).map((level) => (
                <li key={level.price} className="flex justify-between gap-2 font-mono text-xs">
                  <span className={color as string}>{formatPrice(level.price)}</span>
                  <span className="text-zinc-600">
                    {level.touches}×
                  </span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </section>
  );
}

function Centered({ children }: { children: React.ReactNode }) {
  return (
    <div className="mt-8 rounded-lg border border-zinc-800 bg-zinc-950 px-4 py-10 text-center text-sm text-zinc-500">
      {children}
    </div>
  );
}
