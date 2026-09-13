"use client";

/** Shimmer placeholder sized to the content it stands in for, so the
 *  layout does not jump when real data lands. */
export function Skeleton({ className = "" }: { className?: string }) {
  return (
    <div
      className={`animate-pulse rounded bg-gradient-to-r from-zinc-900 via-zinc-800/60 to-zinc-900 bg-[length:200%_100%] ${className}`}
      style={{ animation: "shimmer 1.6s ease-in-out infinite" }}
    />
  );
}

export function AnalysisSkeleton() {
  return (
    <div className="mt-6 space-y-6">
      <Skeleton className="h-11 w-full" />
      <Skeleton className="h-[430px] w-full" />
      <div className="grid gap-6 lg:grid-cols-[1fr_1.15fr]">
        <div className="space-y-6">
          <Skeleton className="h-56 w-full" />
          <Skeleton className="h-44 w-full" />
        </div>
        <Skeleton className="h-[340px] w-full" />
      </div>
    </div>
  );
}
