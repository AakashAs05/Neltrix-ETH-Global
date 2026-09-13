import { Composability } from "@/components/home/Composability";
import { DataQuality } from "@/components/home/DataQuality";
import { Hero } from "@/components/home/Hero";
import { PaymentFlow } from "@/components/home/PaymentFlow";
import { PipelineFlow } from "@/components/home/PipelineFlow";
import { Provenance } from "@/components/home/Provenance";
import { SiteNav } from "@/components/SiteNav";

export default function Home() {
  return (
    <>
      <SiteNav />
      <main>
        <Hero />
        <PipelineFlow />
        <div id="composability">
          <Composability />
        </div>
        <div id="payments">
          <PaymentFlow />
        </div>
        <DataQuality />
        <Provenance />
      </main>
      <footer className="border-t border-zinc-900 py-8">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-6 text-xs text-zinc-600">
          <span>Neltrix Onchain. Built for ETHOnline 2026.</span>
          <span className="font-mono">
            The Graph · Uniswap V4 · Hedera x402
          </span>
        </div>
      </footer>
    </>
  );
}
