import Link from "next/link";

const SOURCES = [
  {
    name: "Uniswap V4",
    detail: "Flagship pool source, on Uniswap's own subgraph schema.",
    badge: "Flagship",
  },
  {
    name: "Uniswap V3",
    detail: "Messari dex-amm Standardized Subgraph.",
  },
  {
    name: "SushiSwap",
    detail: "Same query shape as V3, no protocol-specific code.",
  },
];

export default function Home() {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col justify-center px-6 py-20">
      <h1 className="text-4xl font-semibold tracking-tight text-zinc-50">
        Neltrix Onchain
      </h1>
      <p className="mt-3 max-w-xl text-lg leading-relaxed text-zinc-400">
        Candlestick, chart, and harmonic pattern detection built directly on DEX swap
        events — no centralised price feed, no off-chain OHLCV vendor. Candles are
        derived from individual swaps indexed by The Graph.
      </p>

      <ul className="mt-10 space-y-3">
        {SOURCES.map((source) => (
          <li
            key={source.name}
            className="flex items-center justify-between gap-4 rounded-lg border border-zinc-800 bg-zinc-950 px-4 py-3"
          >
            <div>
              <p className="flex items-center gap-2 text-sm font-medium text-zinc-100">
                {source.name}
                {source.badge && (
                  <span className="rounded bg-pink-500/15 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-pink-400">
                    {source.badge}
                  </span>
                )}
              </p>
              <p className="mt-0.5 text-xs text-zinc-500">{source.detail}</p>
            </div>
          </li>
        ))}
      </ul>

      <Link
        href="/workspace"
        className="mt-10 inline-flex w-fit items-center gap-2 rounded-lg bg-zinc-100 px-5 py-2.5 text-sm font-medium text-zinc-900 transition-colors hover:bg-white"
      >
        Open workspace →
      </Link>
    </main>
  );
}
