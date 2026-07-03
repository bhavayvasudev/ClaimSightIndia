"use client";

import { useRef } from "react";
import {
  motion,
  useScroll,
  useSpring,
  useTransform,
  type MotionValue,
} from "framer-motion";
import { PillButton } from "../ui/PillButton";
import { SectionLabel } from "../ui/SectionLabel";
import { VehicleIllustration } from "./VehicleIllustration";

/**
 * Scroll-driven hero: a 600vh track with a sticky viewport. As the user
 * scrolls, the claim analysis assembles in stages — vehicle, OCR, damage,
 * fraud, policy, report — each keyed to a window of scroll progress.
 */
export function Hero() {
  const trackRef = useRef<HTMLElement>(null);
  const { scrollYProgress } = useScroll({
    target: trackRef,
    offset: ["start start", "end end"],
  });
  const p = useSpring(scrollYProgress, { stiffness: 90, damping: 28, restDelta: 0.001 });

  // Opening headline recedes as the story begins
  const headlineOpacity = useTransform(p, [0, 0.09], [1, 0]);
  const headlineY = useTransform(p, [0, 0.09], [0, -56]);
  const headlinePointer = useTransform(headlineOpacity, (o) => (o < 0.3 ? "none" : "auto"));

  // Product frame
  const frameOpacity = useTransform(p, [0.05, 0.13], [0, 1]);
  const frameScale = useTransform(p, [0.05, 0.13, 0.8, 0.92], [0.96, 1, 1, 0.975]);
  const vehicleOpacity = useTransform(p, [0.1, 0.18], [0, 1]);
  const vehicleY = useTransform(p, [0.1, 0.18], [20, 0]);

  // OCR scan sweep
  const scanOpacity = useTransform(p, [0.19, 0.21, 0.29, 0.32], [0, 1, 1, 0]);
  const scanTop = useTransform(p, [0.2, 0.3], ["18%", "74%"]);

  // Everything on the stage dims once the report takes over
  const stageDim = useTransform(p, [0.78, 0.88], [1, 0.25]);

  return (
    <section ref={trackRef} className="relative h-[600vh]">
      <div className="sticky top-0 flex h-screen flex-col items-center justify-center overflow-hidden pt-16">
        {/* ————— Opening headline ————— */}
        <div className="pointer-events-none absolute inset-0 z-20 flex items-center justify-center px-6 pt-16">
          <motion.div
            style={{ opacity: headlineOpacity, y: headlineY, pointerEvents: headlinePointer }}
            className="mx-auto flex max-w-content flex-col items-center text-center"
          >
            <motion.div
              initial={{ opacity: 0, y: 24 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
            >
              <SectionLabel>AI claim intelligence · Indian motor insurance</SectionLabel>
            </motion.div>
            <motion.h1
              initial={{ opacity: 0, y: 28 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 1, ease: [0.22, 1, 0.36, 1], delay: 0.1 }}
              className="mt-6 max-w-[820px] text-[44px] font-semibold leading-[1.1] tracking-display text-carbon sm:text-[56px] md:text-[64px]"
            >
              Every claim, <span className="text-lavender">seen clearly.</span>
            </motion.h1>
            <motion.p
              initial={{ opacity: 0, y: 24 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1], delay: 0.22 }}
              className="mt-6 max-w-copy text-[16px] leading-relaxed tracking-body text-ash"
            >
              ClaimSight reads damage photos, policy PDFs, registration numbers and accident
              narratives together — and returns one structured, audit-ready triage report.
            </motion.p>
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1], delay: 0.34 }}
              className="mt-9 flex items-center gap-3"
            >
              <PillButton href="#demo" size="lg">
                Request a demo
              </PillButton>
              <PillButton href="#problem" variant="ghost" size="lg">
                See how it works
              </PillButton>
            </motion.div>
            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 1.2, delay: 1 }}
              className="mt-14 text-[12px] font-medium uppercase tracking-[0.08em] text-ash"
            >
              Scroll to watch a claim come alive
            </motion.p>
            <motion.span
              aria-hidden
              animate={{ y: [0, 6, 0] }}
              transition={{ duration: 2.2, repeat: Infinity, ease: "easeInOut" }}
              className="mt-3 text-ash"
            >
              ↓
            </motion.span>
          </motion.div>
        </div>

        {/* ————— Product stage ————— */}
        <motion.div
          style={{ opacity: frameOpacity, scale: frameScale }}
          className="relative z-10 w-full max-w-[880px] px-5 md:px-0"
        >
          {/* slow breathing float */}
          <motion.div
            animate={{ y: [0, -9, 0] }}
            transition={{ duration: 7, repeat: Infinity, ease: "easeInOut" }}
            className="relative"
          >
            <div className="rounded-card border border-fog bg-white shadow-panel">
              {/* chrome bar */}
              <div className="flex items-center justify-between border-b border-fog px-5 py-3">
                <div className="flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-full bg-fog" />
                  <span className="h-2.5 w-2.5 rounded-full bg-fog" />
                  <span className="h-2.5 w-2.5 rounded-full bg-fog" />
                </div>
                <p className="hidden text-[12px] font-medium tracking-body text-ash sm:block">
                  ClaimSight Console — Claim #CS-2481
                </p>
                <span className="inline-flex items-center gap-1.5 rounded-full bg-mist px-2.5 py-1 text-[11px] font-medium text-graphite">
                  <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-mint" />
                  Analyzing
                </span>
              </div>

              {/* stage body */}
              <motion.div style={{ opacity: stageDim }} className="relative px-6 py-10 md:px-14 md:py-14">
                <motion.div style={{ opacity: vehicleOpacity, y: vehicleY }}>
                  <VehicleIllustration />
                </motion.div>

                {/* OCR scan sweep */}
                <motion.div
                  aria-hidden
                  style={{ opacity: scanOpacity, top: scanTop }}
                  className="absolute inset-x-[8%] h-px bg-sky/70 shadow-[0_0_12px_rgba(44,120,252,0.5)]"
                />

                {/* OCR plate highlight + readout */}
                <Staged
                  p={p}
                  appear={[0.24, 0.32]}
                  className="absolute left-[77.5%] top-[61.5%] h-[7.5%] w-[8%] rounded-[4px] border-2 border-sky"
                />
                <Staged p={p} appear={[0.26, 0.34]} from={{ y: 10 }} className="absolute right-[7%] top-[81%]">
                  <div className="rounded-input border border-fog bg-white px-3 py-2 shadow-subtle-2">
                    <p className="text-[10px] font-medium uppercase tracking-[0.08em] text-ash">Plate OCR</p>
                    <p className="mt-0.5 flex items-center gap-1.5 text-[13px] font-semibold tracking-body text-carbon">
                      <span className="h-1.5 w-1.5 rounded-full bg-sky" />
                      DL 3C CX 1234
                    </p>
                  </div>
                </Staged>

                {/* Damage annotations */}
                <Staged
                  p={p}
                  appear={[0.36, 0.42]}
                  className="absolute left-[69%] top-[56%] h-[14%] w-[8.5%] rounded-full border-2 border-dashed border-magenta"
                />
                <Staged p={p} appear={[0.38, 0.44]} from={{ y: 10 }} className="absolute left-[58%] top-[18%]">
                  <div className="rounded-input border border-fog bg-white px-3 py-2 shadow-subtle-2">
                    <p className="text-[10px] font-medium uppercase tracking-[0.08em] text-ash">Damage 01</p>
                    <p className="mt-0.5 flex items-center gap-1.5 text-[13px] font-semibold tracking-body text-carbon">
                      <span className="h-1.5 w-1.5 rounded-full bg-magenta" />
                      Front fender — Moderate
                    </p>
                  </div>
                </Staged>
                <Staged
                  p={p}
                  appear={[0.41, 0.47]}
                  className="absolute left-[38%] top-[56%] h-[16%] w-[8%] rounded-full border-2 border-dashed border-amber"
                />
                <Staged p={p} appear={[0.43, 0.49]} from={{ y: 10 }} className="absolute left-[14%] top-[24%]">
                  <div className="rounded-input border border-fog bg-white px-3 py-2 shadow-subtle-2">
                    <p className="text-[10px] font-medium uppercase tracking-[0.08em] text-ash">Damage 02</p>
                    <p className="mt-0.5 flex items-center gap-1.5 text-[13px] font-semibold tracking-body text-carbon">
                      <span className="h-1.5 w-1.5 rounded-full bg-amber" />
                      Rear door — Minor
                    </p>
                  </div>
                </Staged>
              </motion.div>
            </div>

            {/* Fraud score card */}
            <Staged
              p={p}
              appear={[0.5, 0.58]}
              from={{ x: 36 }}
              className="absolute -right-3 top-[16%] w-[186px] md:-right-20 md:w-[230px]"
            >
              <motion.div style={{ opacity: stageDim }} className="rounded-card border border-fog bg-white p-4 shadow-panel md:p-5">
                <p className="text-[10px] font-medium uppercase tracking-[0.08em] text-ash">Fraud risk</p>
                <p className="mt-1 text-[26px] font-semibold leading-none tracking-heading text-carbon">
                  12<span className="text-[14px] font-medium text-ash"> / 100</span>
                </p>
                <span className="mt-2 inline-flex rounded-full bg-mint-wash px-2.5 py-1 text-[11px] font-medium text-mint">
                  Low risk
                </span>
                <ul className="mt-3 space-y-1.5 border-t border-fog pt-3">
                  {["Narrative consistent", "Photo metadata intact", "No prior claims"].map((row) => (
                    <li key={row} className="flex items-center gap-2 text-[12px] tracking-body text-graphite">
                      <span className="h-1.5 w-1.5 rounded-full bg-mint" />
                      {row}
                    </li>
                  ))}
                </ul>
              </motion.div>
            </Staged>

            {/* Policy analysis card */}
            <Staged
              p={p}
              appear={[0.62, 0.7]}
              from={{ x: -36 }}
              className="absolute -left-3 top-[38%] w-[186px] md:-left-20 md:w-[230px]"
            >
              <motion.div style={{ opacity: stageDim }} className="rounded-card border border-fog bg-white p-4 shadow-panel md:p-5">
                <p className="text-[10px] font-medium uppercase tracking-[0.08em] text-ash">Policy analysis</p>
                <p className="mt-1 text-[14px] font-semibold tracking-body text-carbon">
                  Comprehensive · IDV ₹8.4L
                </p>
                <ul className="mt-3 space-y-1.5 border-t border-fog pt-3">
                  {["Own damage — Covered", "Zero depreciation — Active", "No exclusions triggered"].map((row) => (
                    <li key={row} className="flex items-center gap-2 text-[12px] tracking-body text-graphite">
                      <span className="h-1.5 w-1.5 rounded-full bg-lavender" />
                      {row}
                    </li>
                  ))}
                </ul>
              </motion.div>
            </Staged>

            {/* Final report assembles over the stage */}
            <Staged
              p={p}
              appear={[0.78, 0.88]}
              from={{ y: 72 }}
              className="absolute inset-x-3 bottom-4 md:inset-x-14 md:bottom-8"
            >
              <div className="rounded-card border border-fog bg-white p-5 shadow-panel md:p-6">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <p className="text-[14px] font-semibold tracking-body text-carbon">
                    Triage report — Claim #CS-2481
                  </p>
                  <span className="inline-flex rounded-full bg-mint-wash px-2.5 py-1 text-[11px] font-medium text-mint">
                    Fast-track recommended
                  </span>
                </div>
                <div className="mt-4 grid grid-cols-2 gap-4 border-t border-fog pt-4 md:grid-cols-4">
                  {[
                    { label: "Verification", value: "Confirmed" },
                    { label: "Damage", value: "Moderate" },
                    { label: "Fraud risk", value: "Low · 12/100" },
                    { label: "Est. repair", value: "₹35k–45k" },
                  ].map((item) => (
                    <div key={item.label}>
                      <p className="text-[10px] font-medium uppercase tracking-[0.08em] text-ash">{item.label}</p>
                      <p className="mt-1 text-[14px] font-semibold tracking-body text-carbon">{item.value}</p>
                    </div>
                  ))}
                </div>
              </div>
            </Staged>
          </motion.div>

          {/* Stage captions */}
          <div className="relative mt-6 h-6 md:mt-8" aria-hidden>
            <Caption p={p} appear={[0.13, 0.18]} exit={[0.22, 0.26]}>Vehicle identified — 2019 sedan</Caption>
            <Caption p={p} appear={[0.24, 0.3]} exit={[0.34, 0.38]}>Registration read via OCR</Caption>
            <Caption p={p} appear={[0.37, 0.43]} exit={[0.47, 0.51]}>Damage localized and graded</Caption>
            <Caption p={p} appear={[0.5, 0.56]} exit={[0.6, 0.63]}>Fraud signals scored</Caption>
            <Caption p={p} appear={[0.62, 0.68]} exit={[0.73, 0.77]}>Policy coverage verified</Caption>
            <Caption p={p} appear={[0.8, 0.88]}>One audit-ready report, assembled in minutes</Caption>
          </div>
        </motion.div>
      </div>
    </section>
  );
}

type Window2 = [number, number];

function Staged({
  p,
  appear,
  exit,
  from = { y: 16 },
  className,
  style,
  children,
}: {
  p: MotionValue<number>;
  appear: Window2;
  exit?: Window2;
  from?: { x?: number; y?: number };
  className?: string;
  style?: Record<string, unknown>;
  children?: React.ReactNode;
}) {
  const opacity = useTransform(
    p,
    exit ? [appear[0], appear[1], exit[0], exit[1]] : appear,
    exit ? [0, 1, 1, 0] : [0, 1]
  );
  const x = useTransform(p, appear, [from.x ?? 0, 0]);
  const y = useTransform(p, appear, [from.y ?? 0, 0]);
  return (
    <motion.div className={className} style={{ ...style, opacity, x, y }}>
      {children}
    </motion.div>
  );
}

function Caption({
  p,
  appear,
  exit,
  children,
}: {
  p: MotionValue<number>;
  appear: Window2;
  exit?: Window2;
  children: React.ReactNode;
}) {
  return (
    <Staged
      p={p}
      appear={appear}
      exit={exit}
      from={{ y: 8 }}
      className="absolute inset-x-0 text-center text-[12px] font-medium uppercase tracking-[0.08em] text-ash"
    >
      {children}
    </Staged>
  );
}
