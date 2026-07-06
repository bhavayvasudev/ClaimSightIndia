"use client";

import { useEffect, useRef, useState } from "react";
import { animate, useInView } from "framer-motion";
import { Reveal } from "../ui/Reveal";
import { SectionLabel } from "../ui/SectionLabel";
import { SectionDivider } from "../ui/SectionDivider";
import { metrics } from "@/lib/content";
import { EASE } from "@/lib/motion";

export function Metrics() {
  return (
    <section id="metrics" className="relative bg-white">
      <SectionDivider />
      <div className="mx-auto flex min-h-screen max-w-content flex-col items-center justify-center px-6 py-28 md:px-8">
        <Reveal className="text-center">
          <SectionLabel tone="mint">Impact</SectionLabel>
        </Reveal>
        <Reveal delay={0.1} className="text-center">
          <h2 className="mx-auto mt-6 max-w-[680px] text-balance text-[34px] font-semibold leading-[1.12] tracking-display text-carbon sm:text-[44px] md:text-[54px]">
            The numbers that follow.
          </h2>
        </Reveal>

        <div className="mt-16 grid w-full grid-cols-1 gap-4 sm:grid-cols-3 md:mt-20">
          {metrics.map((metric, i) => (
            <Reveal key={metric.label} delay={0.15 + i * 0.12}>
              <div className="h-full rounded-card border border-fog bg-white p-8 text-center transition-[transform,box-shadow] duration-500 ease-out hover:-translate-y-1.5 hover:shadow-panel">
                <p className="text-[56px] font-semibold leading-none tracking-display text-carbon md:text-[64px]">
                  <CountUp value={metric.value} />
                  <span className="text-mint">{metric.suffix}</span>
                </p>
                <p className="mt-4 text-[16px] font-medium tracking-heading text-carbon">
                  {metric.label}
                </p>
                <p className="mt-2 text-[14px] leading-relaxed tracking-body text-graphite">
                  {metric.detail}
                </p>
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}

function CountUp({ value }: { value: number }) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, margin: "-15% 0px" });
  const [display, setDisplay] = useState(0);

  useEffect(() => {
    if (!inView) return;
    const controls = animate(0, value, {
      duration: 1.8,
      ease: EASE,
      onUpdate: (v) => setDisplay(Math.round(v)),
    });
    return () => controls.stop();
  }, [inView, value]);

  return <span ref={ref}>{display}</span>;
}
