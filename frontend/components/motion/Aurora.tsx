"use client";

import { motion } from "motion/react";

/** Slow drifting colour field behind the hero. Low contrast on purpose, so
 *  it reads as depth rather than competing with the copy. */
export function Aurora() {
  return (
    <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
      <motion.div
        className="absolute -top-1/3 left-1/4 h-[38rem] w-[38rem] rounded-full blur-[120px]"
        style={{ background: "radial-gradient(circle, rgba(236,72,153,0.16), transparent 70%)" }}
        animate={{ x: [0, 60, -30, 0], y: [0, -40, 30, 0] }}
        transition={{ duration: 22, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        className="absolute -top-1/4 right-1/5 h-[32rem] w-[32rem] rounded-full blur-[120px]"
        style={{ background: "radial-gradient(circle, rgba(56,189,248,0.14), transparent 70%)" }}
        animate={{ x: [0, -50, 40, 0], y: [0, 40, -20, 0] }}
        transition={{ duration: 26, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        className="absolute top-1/4 left-1/2 h-[26rem] w-[26rem] rounded-full blur-[110px]"
        style={{ background: "radial-gradient(circle, rgba(34,197,94,0.10), transparent 70%)" }}
        animate={{ x: [0, 40, -40, 0], y: [0, 20, 40, 0] }}
        transition={{ duration: 30, repeat: Infinity, ease: "easeInOut" }}
      />
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,transparent_20%,#09090b_75%)]" />
    </div>
  );
}
