import { Reveal } from "../ui/Reveal";
import { SectionLabel } from "../ui/SectionLabel";
import { SectionDivider } from "../ui/SectionDivider";

const FLOW_STEPS = [
  "Damage Assessment",
  "Repair Intelligence",
  "Policy Understanding",
  "Risk Review",
  "Claim Report",
];

const PRINCIPLES = [
  {
    title: "Evidence over guesswork",
    description:
      "Every finding traces back to a specific detection in a specific photo, or a specific clause in a specific policy document — never a confident-sounding answer with nothing behind it.",
  },
  {
    title: "Human review where confidence is weak",
    description:
      "A low-confidence detection, an unclear policy clause, or an inconsistent signal is routed for manual review, not silently accepted or silently dropped.",
  },
  {
    title: "Built for how claims work in India",
    description:
      "Vehicle categories, repair-cost ranges, and policy language are modeled around the Indian motor insurance and repair market — not adapted from a template built for somewhere else.",
  },
];

export function About() {
  return (
    <section id="about" className="relative bg-white">
      <SectionDivider />
      <div className="mx-auto max-w-content px-6 py-24 md:px-8 md:py-32">
        <Reveal className="mx-auto max-w-[640px] text-center">
          <SectionLabel>About ClaimSight</SectionLabel>
        </Reveal>
        <Reveal delay={0.08} className="mx-auto max-w-[640px] text-center">
          <h2 className="mx-auto mt-6 text-balance text-[34px] font-semibold leading-[1.12] tracking-display text-carbon sm:text-[44px] md:text-[54px]">
            Vehicle claims are complicated.
            <br />
            Understanding them shouldn&rsquo;t be.
          </h2>
        </Reveal>
        <Reveal delay={0.16} className="mx-auto max-w-[640px] text-center">
          <p className="mx-auto mt-6 max-w-copy text-[16px] leading-relaxed tracking-body text-graphite">
            A single motor claim touches damage assessment, repair estimation, policy
            interpretation, and manual review — and today those stages usually happen separately,
            by different people, with no shared view of the evidence. ClaimSight India brings them
            into one structured workflow.
          </p>
          <p className="mx-auto mt-4 max-w-copy text-[16px] leading-relaxed tracking-body text-graphite">
            It turns vehicle damage photos into a structured first-pass assessment: it identifies
            visibly damaged areas, maps them to specific vehicle parts, estimates severity and an
            indicative repair range priced for the Indian market, and flags anything uncertain for
            human review instead of guessing. Attach a policy document and the claim report also
            relates each finding to the policy&rsquo;s own wording.
          </p>
        </Reveal>

        {/* Product flow */}
        <Reveal delay={0.24} className="mt-16">
          <div className="rounded-card border border-fog bg-mist/40 p-6 md:p-10">
            <div className="flex flex-col gap-3 md:flex-row md:flex-wrap md:items-center md:justify-center md:gap-2">
              {FLOW_STEPS.map((step, i) => (
                <div key={step} className="flex items-center gap-2 md:gap-2">
                  <span className="inline-flex items-center rounded-full border border-fog bg-white px-4 py-2 text-[13px] font-medium tracking-body text-carbon">
                    {step}
                  </span>
                  {i < FLOW_STEPS.length - 1 && (
                    <span aria-hidden className="hidden text-ash md:inline">
                      →
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        </Reveal>

        {/* Why escalation + Indian market framing, folded into one restrained note */}
        <Reveal delay={0.3} className="mx-auto mt-10 max-w-[720px] text-center">
          <p className="text-[14px] leading-relaxed tracking-body text-graphite">
            ClaimSight assists triage — it does not adjudicate a claim, and it does not replace an
            insurer&rsquo;s final decision. Where the evidence is unclear, the system says so
            explicitly instead of rounding an uncertain result up to a confident one.
          </p>
        </Reveal>

        {/* Product principles */}
        <div className="mt-16 grid grid-cols-1 gap-5 md:grid-cols-3">
          {PRINCIPLES.map((principle, i) => (
            <Reveal key={principle.title} delay={0.1 + i * 0.06}>
              <div className="h-full rounded-card border border-fog bg-white p-6">
                <h3 className="text-[16px] font-semibold tracking-heading text-carbon">
                  {principle.title}
                </h3>
                <p className="mt-2.5 text-[14px] leading-relaxed tracking-body text-graphite">
                  {principle.description}
                </p>
              </div>
            </Reveal>
          ))}
        </div>

        {/* Contact — smaller final element, not the whole section */}
        <Reveal delay={0.1} className="mt-16 flex flex-col items-center gap-2 border-t border-fog pt-8 text-center">
          <p className="text-[13px] tracking-body text-ash">Questions about ClaimSight?</p>
          <a
            href="mailto:claimsightindia@gmail.com"
            className="text-[14px] font-medium text-graphite transition-colors hover:text-carbon"
          >
            claimsightindia@gmail.com
          </a>
        </Reveal>
      </div>
    </section>
  );
}
