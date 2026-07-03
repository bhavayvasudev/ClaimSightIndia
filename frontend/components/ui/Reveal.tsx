"use client";

import { motion } from "framer-motion";
import type { ReactNode } from "react";
import { EASE, REVEAL_DURATION, VIEWPORT } from "@/lib/motion";

type RevealProps = {
  children: ReactNode;
  delay?: number;
  y?: number;
  className?: string;
};

export function Reveal({ children, delay = 0, y = 28, className }: RevealProps) {
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={VIEWPORT}
      transition={{ duration: REVEAL_DURATION, ease: EASE, delay }}
    >
      {children}
    </motion.div>
  );
}
