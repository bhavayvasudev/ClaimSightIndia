import { Reveal } from "../ui/Reveal";
import { SectionLabel } from "../ui/SectionLabel";
import { problemStats } from "@/lib/content";

export function Problem() {
  return (
    <section id="problem" className="border-t border-fog bg-linen">
      <div className="mx-auto flex min-h-screen max-w-content flex-col items-center justify-center px-6 py-24 md:px-8">
        <Reveal className="text-center">
          <SectionLabel>The problem</SectionLabel>
        </Reveal>
        <Reveal delay={0.1} className="text-center">
          <h2 className="mx-auto mt-6 max-w-[760px] text-[34px] font-semibold leading-[1.15] tracking-display text-carbon sm:text-[44px] md:text-[52px]">
            Manual claim triage is slow, inconsistent, and blind to fraud.
          </h2>
        </Reveal>
        <Reveal delay={0.2} className="text-center">
          <p className="mx-auto mt-6 max-w-copy text-[16px] leading-relaxed tracking-body text-ash">
            Every motor claim in India arrives as a pile of photos, PDFs and phone-typed
            narratives. Adjusters reconcile them by hand — and the backlog decides the payout
            speed, not the evidence.
          </p>
        </Reveal>

        <div className="mt-16 grid w-full grid-cols-1 gap-4 sm:grid-cols-3 md:mt-20">
          {problemStats.map((stat, i) => (
            <Reveal key={stat.label} delay={0.15 + i * 0.12}>
              <div className="h-full rounded-card border border-fog bg-white p-8">
                <p className="text-[40px] font-semibold leading-none tracking-heading text-carbon md:text-[48px]">
                  {stat.value}
                  <span className="ml-2 text-[16px] font-medium text-ash">{stat.unit}</span>
                </p>
                <p className="mt-4 text-[14px] leading-relaxed tracking-body text-graphite">
                  {stat.label}
                </p>
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
