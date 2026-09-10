"use client";

/** Protocol + pool picker. Uniswap V4 is the flagship source and is pinned first. */

import Link from "next/link";
import { useEffect, useState } from "react";

import { ApiError, fetchPools, fetchProtocols, formatUsd, shortenId } from "@/lib/api";
import {
  INTERVALS,
  RANGE_LABELS,
  RANGES,
  willBeExpensive,
  type Interval,
  type Pool,
  type Protocol,
  type Range,
} from "@/lib/types";

export default function WorkspacePage() {
  const [protocols, setProtocols] = useState<Protocol[]>([]);
  const [selectedProtocol, setSelectedProtocol] = useState<string | null>(null);
  const [pools, setPools] = useState<Pool[]>([]);
  const [interval, setIntervalChoice] = useState<Interval>("1h");
  const [range, setRange] = useState<Range>("1w");
  const [loadingPools, setLoadingPools] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const activeProtocol = protocols.find((p) => p.key === selectedProtocol);
  const expensive = willBeExpensive(activeProtocol, interval, range);

  useEffect(() => {
    let cancelled = false;
    fetchProtocols()
      .then((list) => {
        if (cancelled) return;
        setProtocols(list);
        setSelectedProtocol((current) => current ?? list[0]?.key ?? null);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(describe(err));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!selectedProtocol) return;
    let cancelled = false;
    setLoadingPools(true);
    setError(null);
    setPools([]);

    fetchPools(selectedProtocol, 20)
      .then((list) => {
        if (!cancelled) setPools(list);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(describe(err));
      })
      .finally(() => {
        if (!cancelled) setLoadingPools(false);
      });

    return () => {
      cancelled = true;
    };
  }, [selectedProtocol]);

  return (
    <main className="mx-auto w-full max-w-6xl px-6 py-10">
      <header>
        <h1 className="text-2xl font-semibold text-zinc-100">Neltrix Onchain</h1>
        <p className="mt-1 text-sm text-zinc-400">
          Pattern intelligence over DEX swap data, indexed by The Graph. Pick a pool to analyse.
        </p>
      </header>

      <section className="mt-8">
        <h2 className="text-xs uppercase tracking-wider text-zinc-500">Protocol</h2>
        <div className="mt-3 flex flex-wrap gap-2">
          {protocols.map((protocol) => {
            const active = protocol.key === selectedProtocol;
            return (
              <button
                key={protocol.key}
                type="button"
                onClick={() => setSelectedProtocol(protocol.key)}
                className={`rounded-lg border px-3 py-2 text-left transition-colors ${
                  active
                    ? "border-zinc-100 bg-zinc-100 text-zinc-900"
                    : "border-zinc-800 bg-zinc-950 text-zinc-300 hover:border-zinc-700 hover:bg-zinc-900"
                }`}
              >
                <span className="flex items-center gap-2 text-sm font-medium">
                  {protocol.display_name}
                  {protocol.is_flagship && (
                    <span
                      className={`rounded px-1.5 py-0.5 text-[10px] uppercase tracking-wide ${
                        active ? "bg-zinc-900 text-zinc-100" : "bg-pink-500/15 text-pink-400"
                      }`}
                    >
                      Flagship
                    </span>
                  )}
                </span>
                <span
                  className={`mt-0.5 block font-mono text-[11px] ${
                    active ? "text-zinc-600" : "text-zinc-500"
                  }`}
                >
                  {protocol.schema_family}
                </span>
              </button>
            );
          })}
        </div>
      </section>

      <section className="mt-6 grid gap-6 sm:grid-cols-2">
        <div>
          <h2 className="text-xs uppercase tracking-wider text-zinc-500">Candle interval</h2>
          <div className="mt-3 flex flex-wrap gap-2">
            {INTERVALS.map((option) => (
              <button
                key={option}
                type="button"
                onClick={() => setIntervalChoice(option)}
                className={`rounded px-3 py-1.5 font-mono text-xs transition-colors ${
                  option === interval
                    ? "bg-zinc-100 text-zinc-900"
                    : "bg-zinc-900 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200"
                }`}
              >
                {option}
              </button>
            ))}
          </div>
        </div>

        <div>
          <h2 className="text-xs uppercase tracking-wider text-zinc-500">Lookback window</h2>
          <div className="mt-3 flex flex-wrap gap-2">
            {RANGES.map((option) => (
              <button
                key={option}
                type="button"
                onClick={() => setRange(option)}
                className={`rounded px-3 py-1.5 text-xs transition-colors ${
                  option === range
                    ? "bg-zinc-100 text-zinc-900"
                    : "bg-zinc-900 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200"
                }`}
              >
                {RANGE_LABELS[option]}
              </button>
            ))}
          </div>
        </div>
      </section>

      {expensive && (
        <p className="mt-4 rounded-lg border border-amber-500/30 bg-amber-500/5 px-4 py-3 text-xs leading-relaxed text-amber-200/80">
          <span className="font-medium text-amber-300">Heads up:</span>{" "}
          {activeProtocol?.display_name} publishes no OHLC aggregates at{" "}
          <span className="font-mono">{interval}</span>, so a{" "}
          {RANGE_LABELS[range].toLowerCase()} window has to be rebuilt from individual swap
          events. On a busy pool that&apos;s slow and will likely be truncated to a shorter
          span. Uniswap V4 at 1h, 4h or 1d serves the full window straight from the
          subgraph&apos;s published candles.
        </p>
      )}

      <section className="mt-8">
        <h2 className="text-xs uppercase tracking-wider text-zinc-500">
          Top pools by traded volume
        </h2>

        {error && (
          <div className="mt-3 rounded-lg border border-red-500/40 bg-red-500/5 px-4 py-3 text-sm text-red-300">
            {error}
          </div>
        )}

        {loadingPools && (
          <p className="mt-3 text-sm text-zinc-500">Loading pools from The Graph…</p>
        )}

        {!loadingPools && !error && pools.length > 0 && (
          <ul className="mt-3 divide-y divide-zinc-900 overflow-hidden rounded-lg border border-zinc-800">
            {pools.map((pool) => (
              <li key={pool.id}>
                <Link
                  href={{
                    pathname: "/workspace/analysis",
                    query: {
                      protocol: selectedProtocol ?? "",
                      pool: pool.id,
                      interval,
                      range,
                    },
                  }}
                  className="flex flex-wrap items-center justify-between gap-3 bg-zinc-950 px-4 py-3 transition-colors hover:bg-zinc-900"
                >
                  <div className="min-w-0">
                    <p className="text-sm text-zinc-100">{pool.name}</p>
                    <p className="mt-0.5 font-mono text-[11px] text-zinc-500">
                      {shortenId(pool.id)}
                    </p>
                  </div>
                  <div className="flex gap-6 text-right">
                    <div>
                      <p className="text-[10px] uppercase tracking-wide text-zinc-600">Volume</p>
                      <p className="font-mono text-sm text-zinc-300">
                        {formatUsd(pool.cumulative_volume_usd)}
                      </p>
                    </div>
                    <div>
                      <p className="text-[10px] uppercase tracking-wide text-zinc-600">TVL</p>
                      <p
                        className={`font-mono text-sm ${
                          pool.total_value_locked_usd < 0 ? "text-amber-500" : "text-zinc-300"
                        }`}
                        title={
                          pool.total_value_locked_usd < 0
                            ? "The subgraph reports a negative TVL for this pool — a known data-quality issue in the V4 deployment, not a computation here."
                            : undefined
                        }
                      >
                        {formatUsd(pool.total_value_locked_usd)}
                      </p>
                    </div>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}

function describe(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) {
    return `${error.message} — is the backend running on ${process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000"}?`;
  }
  return "Unexpected error.";
}
