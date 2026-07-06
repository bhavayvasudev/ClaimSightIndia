"use client";

import Link from "next/link";
import { useRef, useState, type MouseEvent, type ReactNode } from "react";
import { motion } from "framer-motion";

type PillButtonProps = {
  children: ReactNode;
  href?: string;
  onClick?: () => void;
  type?: "button" | "submit";
  variant?: "primary" | "ghost" | "inverse";
  size?: "sm" | "md" | "lg";
  disabled?: boolean;
};

const base =
  "inline-flex w-full items-center justify-center rounded-full font-medium tracking-body transition-[background,box-shadow,color] duration-300 disabled:cursor-not-allowed disabled:opacity-50";

const variants = {
  primary:
    "bg-gradient-to-b from-[#9d99f8] to-lavender text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.25),0_1px_2px_rgba(24,25,37,0.16),0_6px_16px_rgba(145,141,246,0.32)] hover:from-[#a7a3ff] hover:to-iris",
  ghost: "bg-mist text-graphite hover:bg-fog hover:text-carbon",
  inverse: "bg-white/10 text-white ring-1 ring-inset ring-white/15 hover:bg-white/[0.16]",
};

const sizes = {
  sm: "px-4 py-2 text-[13px]",
  md: "px-5 py-2.5 text-[14px]",
  lg: "px-7 py-3.5 text-[15px]",
};

/**
 * Magnetic pill button: drifts a few pixels toward the cursor on hover and
 * settles back on leave. Displacement is deliberately capped small so the
 * effect reads as weight, not bounce.
 */
export function PillButton({
  children,
  href,
  onClick,
  type = "button",
  variant = "primary",
  size = "md",
  disabled = false,
}: PillButtonProps) {
  const ref = useRef<HTMLSpanElement>(null);
  const [offset, setOffset] = useState({ x: 0, y: 0 });

  function handleMove(e: MouseEvent) {
    const el = ref.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    setOffset({
      x: (e.clientX - (r.left + r.width / 2)) * 0.12,
      y: (e.clientY - (r.top + r.height / 2)) * 0.22,
    });
  }

  const className = `${base} ${variants[variant]} ${sizes[size]}`;

  return (
    <motion.span
      ref={ref}
      onMouseMove={handleMove}
      onMouseLeave={() => setOffset({ x: 0, y: 0 })}
      animate={{ x: offset.x, y: offset.y }}
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
      transition={{ type: "spring", stiffness: 280, damping: 24, mass: 0.55 }}
      className="inline-flex"
    >
      {href ? (
        <Link href={href} className={className} aria-disabled={disabled}>
          {children}
        </Link>
      ) : (
        <button type={type} onClick={onClick} disabled={disabled} className={className}>
          {children}
        </button>
      )}
    </motion.span>
  );
}
