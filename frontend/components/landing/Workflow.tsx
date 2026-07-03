import { Reveal } from "../ui/Reveal";
import { SectionLabel } from "../ui/SectionLabel";
import { workflowSteps } from "@/lib/content";

export function Workflow() {
  return (
    <section id="workflow" className="border-t border-fog bg-white">
      <div className="mx-auto grid min-h-screen max-w-content grid-cols-1 items-center gap-12 px-6 py-24 md:grid-cols-[1fr_1.3fr] md:gap-20 md:px-8">
        <div className="md:sticky md:top-32 md:self-start">
          <Reveal>
            <SectionLabel>How it works</SectionLabel>
          </Reveal>
          <Reveal delay={0.1}>
            <h2 className="mt-6 max-w-[440px] text-[34px] font-semibold leading-[1.15] tracking-display text-carbon sm:text-[44px] md:text-[52px]">
              From upload to report in minutes.
            </h2>
          </Reveal>
          <Reveal delay={0.2}>
            <p className="mt-6 max-w-[420px] text-[16px] leading-relaxed tracking-body text-ash">
              One pipeline reads every artefact of the claim, cross-checks them against each
              other, and hands the adjuster a decision they can defend.
            </p>
          </Reveal>
        </div>

        <div>
          {workflowSteps.map((step, i) => (
            <Reveal key={step.index} delay={i * 0.08}>
              <div className="grid grid-cols-[56px_1fr] items-baseline gap-5 border-b border-fog py-8 first:border-t md:py-9">
                <span className="text-[14px] font-semibold tracking-body text-lavender">
                  {step.index}
                </span>
                <div>
                  <h3 className="text-[22px] font-medium leading-tight tracking-heading text-carbon md:text-[24px]">
                    {step.title}
                  </h3>
                  <p className="mt-2 max-w-[480px] text-[15px] leading-relaxed tracking-body text-graphite">
                    {step.description}
                  </p>
                </div>
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
