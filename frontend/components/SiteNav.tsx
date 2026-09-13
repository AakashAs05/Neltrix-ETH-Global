"use client";

import Link from "next/link";
import { motion, useScroll, useMotionValueEvent } from "motion/react";
import { useState } from "react";

const LINKS = [
  { href: "#pipeline", label: "How it works" },
  { href: "#composability", label: "Composability" },
  { href: "#payments", label: "Payments" },
];

export function SiteNav() {
  const { scrollY } = useScroll();
  const [solid, setSolid] = useState(false);
  useMotionValueEvent(scrollY, "change", (v) => setSolid(v > 24));

  return (
    <motion.header
      initial={{ y: -24, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.5 }}
      className={`fixed inset-x-0 top-0 z-50 transition-colors duration-300 ${
        solid ? "border-b border-zinc-900 bg-zinc-950/80 backdrop-blur-xl" : "bg-transparent"
      }`}
    >
      <nav className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3.5">
        <Link href="/" className="group flex items-center gap-2.5">
          <span className="flex h-6 w-6 items-center justify-center rounded bg-gradient-to-br from-pink-400 to-sky-400 font-mono text-[11px] font-bold text-zinc-950">
            N
          </span>
          <span className="text-sm font-medium tracking-tight text-zinc-100">Neltrix</span>
        </Link>

        <div className="hidden items-center gap-7 md:flex">
          {LINKS.map((l) => (
            <a
              key={l.href}
              href={l.href}
              className="text-xs text-zinc-500 transition-colors hover:text-zinc-200"
            >
              {l.label}
            </a>
          ))}
        </div>

        <Link
          href="/workspace"
          className="rounded-lg bg-zinc-100 px-3.5 py-1.5 text-xs font-medium text-zinc-900 transition-colors hover:bg-white"
        >
          Launch app
        </Link>
      </nav>
    </motion.header>
  );
}
