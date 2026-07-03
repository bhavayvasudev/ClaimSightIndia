"use client";

import { motion } from "framer-motion";
import { PillButton } from "../ui/PillButton";
import { EASE } from "@/lib/motion";

const links = [
  { label: "The problem", href: "#problem" },
  { label: "How it works", href: "#workflow" },
  { label: "Agents", href: "#agents" },
  { label: "Demo", href: "#demo" },
];

export function Nav() {
  return (
    <motion.header
      initial={{ opacity: 0, y: -16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.8, ease: EASE }}
      className="fixed inset-x-0 top-0 z-50 border-b border-fog bg-white/85 backdrop-blur-md"
    >
      <div className="mx-auto flex h-16 max-w-content items-center justify-between px-6 md:px-8">
        <a href="#" className="flex items-center gap-2">
          <span className="h-2.5 w-2.5 rounded-full bg-lavender" aria-hidden />
          <span className="text-[15px] font-semibold tracking-heading text-carbon">
            ClaimSight <span className="font-normal text-ash">India</span>
          </span>
        </a>

        <nav className="hidden items-center gap-8 md:flex">
          {links.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="text-[14px] font-medium text-graphite transition-colors hover:text-carbon"
            >
              {link.label}
            </a>
          ))}
        </nav>

        <PillButton href="#demo">Request a demo</PillButton>
      </div>
    </motion.header>
  );
}
