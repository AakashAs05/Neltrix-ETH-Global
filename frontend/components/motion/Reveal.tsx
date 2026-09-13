"use client";

import { motion, type Variants } from "motion/react";
import type { ReactNode } from "react";

const DIRECTION_OFFSET = {
  up: { y: 28, x: 0 },
  down: { y: -28, x: 0 },
  left: { x: 28, y: 0 },
  right: { x: -28, y: 0 },
  none: { x: 0, y: 0 },
} as const;

interface RevealProps {
  children: ReactNode;
  delay?: number;
  direction?: keyof typeof DIRECTION_OFFSET;
  className?: string;
}

/** Fades content in on scroll. `once` stops it replaying on every scroll
 *  back up, which reads as noise rather than polish. */
export function Reveal({ children, delay = 0, direction = "up", className }: RevealProps) {
  const offset = DIRECTION_OFFSET[direction];

  const variants: Variants = {
    hidden: { opacity: 0, ...offset, filter: "blur(6px)" },
    visible: {
      opacity: 1,
      x: 0,
      y: 0,
      filter: "blur(0px)",
      transition: { duration: 0.65, delay, ease: [0.21, 0.47, 0.32, 0.98] },
    },
  };

  return (
    <motion.div
      className={className}
      variants={variants}
      initial="hidden"
      whileInView="visible"
      viewport={{ once: true, margin: "-80px" }}
    >
      {children}
    </motion.div>
  );
}

/** Parent that releases its children one after another. */
export function Stagger({
  children,
  className,
  gap = 0.08,
}: {
  children: ReactNode;
  className?: string;
  gap?: number;
}) {
  return (
    <motion.div
      className={className}
      initial="hidden"
      whileInView="visible"
      viewport={{ once: true, margin: "-60px" }}
      variants={{ visible: { transition: { staggerChildren: gap } } }}
    >
      {children}
    </motion.div>
  );
}

export const staggerItem: Variants = {
  hidden: { opacity: 0, y: 20, filter: "blur(4px)" },
  visible: {
    opacity: 1,
    y: 0,
    filter: "blur(0px)",
    transition: { duration: 0.55, ease: [0.21, 0.47, 0.32, 0.98] },
  },
};
