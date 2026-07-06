import Link from "next/link";
import { PillButton } from "../ui/PillButton";
import { AssessmentCTAButton } from "../ui/AssessmentCTAButton";
import { Reveal } from "../ui/Reveal";
import { SectionDivider } from "../ui/SectionDivider";

export function Footer() {
  return (
    <footer className="relative bg-white">
      <SectionDivider />
      <div className="mx-auto max-w-content px-6 py-20 md:px-8 md:py-28">
        <div className="relative overflow-hidden rounded-[28px] bg-carbon px-6 py-20 text-center md:py-28">
            {/* ambient glow inside the dark band */}
            <div aria-hidden className="pointer-events-none absolute inset-0">
              <div className="absolute left-1/2 top-[-40%] h-[420px] w-[640px] -translate-x-1/2 rounded-full bg-lavender/[0.22] blur-[120px]" />
              <div className="absolute bottom-[-30%] right-[8%] h-[280px] w-[360px] rounded-full bg-sky/[0.1] blur-[110px]" />
            </div>

            <div className="relative">
              <Reveal delay={0.05}>
                <h2 className="mx-auto max-w-[640px] text-balance text-[34px] font-semibold leading-[1.12] tracking-display text-white sm:text-[44px] md:text-[54px]">
                  Bring sight to your claims.
                </h2>
              </Reveal>
              <Reveal delay={0.15}>
                <p className="mx-auto mt-6 max-w-copy text-[16px] leading-relaxed tracking-body text-white/55">
                  See how ClaimSight India fits your triage workflow — from first photo to final
                  report.
                </p>
              </Reveal>
              <Reveal delay={0.25}>
                <div className="mt-10 flex flex-wrap items-center justify-center gap-3">
                  <AssessmentCTAButton size="lg">Try ClaimSight</AssessmentCTAButton>
                  <PillButton href="/#agents" variant="inverse" size="lg">
                    View Architecture
                  </PillButton>
                </div>
              </Reveal>
            </div>
          </div>
      </div>

      <div className="border-t border-fog">
        <div className="mx-auto flex max-w-content flex-col items-center gap-5 px-6 py-10 md:flex-row md:justify-between md:px-8">
          <Link href="/" className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full bg-lavender" aria-hidden />
            <span className="text-[15px] font-semibold tracking-heading text-carbon">
              ClaimSight <span className="font-normal text-ash">India</span>
            </span>
          </Link>
          <nav className="flex flex-wrap items-center justify-center gap-7">
            {[
              { label: "The problem", href: "/#problem" },
              { label: "How it works", href: "/#workflow" },
              { label: "About", href: "/#about" },
              { label: "Docs", href: "/docs" },
              { label: "View Interactive Preview", href: "/demo" },
            ].map((item) => (
              <a
                key={item.href}
                href={item.href}
                className="text-[14px] font-medium text-graphite transition-colors hover:text-carbon"
              >
                {item.label}
              </a>
            ))}
          </nav>
          <p className="text-[13px] tracking-body text-ash">AI-powered multimodal claim triage</p>
        </div>
      </div>
    </footer>
  );
}
